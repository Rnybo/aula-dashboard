"""
routers/google.py — Google Calendar + OAuth endpoints
"""
import datetime
import logging
import os

import requests as req
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from icalendar import Calendar
import recurring_ical_events

from backend.google_utils import (
    _get_google_access_token, GOOGLE_TOKEN_URL, GOOGLE_AUTH_URL, GOOGLE_OAUTH_SCOPES,
)

router = APIRouter()

COLORS = ["#e53935", "#8e24aa", "#1e88e5", "#43a047", "#fb8c00"]
FAELLES_COLOR = "#e53935"  # Alle fælleskalender-events vises med samme røde farve

_LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=1))  # Fallback hvis systemets tzdata mangler


def _normalize_vevent(component, cal_meta: dict, local_lookup: dict) -> dict | None:
    """
    Konverterer et VEVENT-komponent til et garanteret konsistent event-dict.

    Håndterer:
    - All-day events (DATE) vs tidsbaserede (DATETIME)
    - Manglende DTEND → DURATION fallback → same-day fallback
    - Naive datetimes (ingen tzinfo) → antager lokal tidszone
    - DURATION på tidsbaserede events (f.eks. iCloud)
    - Encoding af SUMMARY/LOCATION (bytes → str)

    Returnerer None hvis eventet ikke kan parses.
    """
    try:
        dtstart = component.get("DTSTART")
        if not dtstart:
            return None

        val = dtstart.dt
        all_day = not hasattr(val, "hour")

        # ── Start ISO ──────────────────────────────────────────────────────────
        if all_day:
            start_iso = val.isoformat()          # "2026-06-15"
        else:
            if val.tzinfo is None:               # naive datetime — giv lokal tz
                val = val.replace(tzinfo=_LOCAL_TZ)
            start_iso = val.astimezone(datetime.timezone.utc).isoformat()

        # ── End ISO ────────────────────────────────────────────────────────────
        dtend = component.get("DTEND")
        duration = component.get("DURATION")

        if dtend:
            end_val = dtend.dt
        elif duration:
            # DURATION kan forekomme i stedet for DTEND (iCloud, Outlook)
            dur = duration.dt if isinstance(duration.dt, datetime.timedelta) else datetime.timedelta(0)
            end_val = val + dur
        else:
            # Ingen end og ingen duration — all-day = næste dag, tidsbaseret = +1 time
            if all_day:
                end_val = val + datetime.timedelta(days=1)
            else:
                end_val = val + datetime.timedelta(hours=1)

        if all_day:
            end_iso = end_val.isoformat() if not hasattr(end_val, "hour") else end_val.date().isoformat()
        else:
            if hasattr(end_val, "tzinfo"):
                if end_val.tzinfo is None:
                    end_val = end_val.replace(tzinfo=_LOCAL_TZ)
                end_iso = end_val.astimezone(datetime.timezone.utc).isoformat()
            else:
                # end_val er en date (ikke datetime) — konverter
                end_iso = datetime.datetime.combine(end_val, datetime.time.min, tzinfo=_LOCAL_TZ).isoformat()

        # ── Felter ────────────────────────────────────────────────────────────
        def _str(field: str, fallback: str = "") -> str:
            v = component.get(field)
            if v is None:
                return fallback
            s = str(v)
            # icalendar returnerer sommetider bytes ved encoding-fejl
            if isinstance(v, bytes):
                s = v.decode("utf-8", errors="replace")
            return s.strip() or fallback

        uid = _str("UID")
        ext_cals = local_lookup.get(uid, "") if uid else ""

        return {
            "title":                    _str("SUMMARY", "(ingen titel)"),
            "start":                    start_iso,
            "end":                      end_iso,
            "allDay":                   all_day,
            "owner":                    cal_meta["name"],
            "color":                    cal_meta["color"],
            "location":                 _str("LOCATION"),
            "familieoverblik_calendars": ext_cals,
        }

    except Exception as ex:
        logging.debug("VEVENT normalize fejl (springer over): %s", ex)
        return None


@router.get("/api/google-calendar")
def google_calendar(from_date: str = "", to_date: str = ""):
    today     = datetime.date.today()
    date_from = datetime.date.fromisoformat(from_date) if from_date else today
    date_to   = datetime.date.fromisoformat(to_date)   if to_date   else today + datetime.timedelta(days=6)
    events    = []

    # Build lookup of familieoverblik_calendars from local custom_events.json
    # Key: google_event_id → calendar string
    from backend.store import load_custom_events
    local_lookup = {
        e["google_event_id"]: e.get("calendar", "")
        for e in load_custom_events()
        if e.get("google_event_id")
    }

    # Build ICS calendar list from env
    seen, ics_calendars = set(), []
    for idx in range(1, 11):
        suffix = "" if idx == 1 else f"_{idx}"
        url  = os.getenv(f"GOOGLE_CALENDAR_ICS{suffix}", "")
        name = os.getenv(f"GOOGLE_CALENDAR_NAME{suffix}", f"Kalender {idx}")
        if url and url not in seen:
            seen.add(url)
            ics_calendars.append({"url": url, "name": name, "color": FAELLES_COLOR})
    ics_calendars.append({
        "url":   "https://calendar.google.com/calendar/ical/da.danish%23holiday%40group.v.calendar.google.com/public/basic.ics",
        "name":  "Helligdag",
        "color": "#f59e0b",
    })

    for cal in ics_calendars:
        if not cal["url"]: continue
        try:
            r = req.get(cal["url"], timeout=8)
            r.raise_for_status()
            gcal = Calendar.from_ical(r.content)
            for component in recurring_ical_events.of(gcal).between(date_from, date_to):
                if component.name != "VEVENT": continue
                event = _normalize_vevent(component, cal, local_lookup)
                if event:
                    events.append(event)
        except Exception as ex:
            logging.warning(f"ICS fetch failed for {cal['name']}: {ex}")

    return events


@router.get("/api/google-oauth/connect")
def google_oauth_connect(request: Request):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(400, "GOOGLE_CLIENT_ID not configured")
    from urllib.parse import urlencode
    params = {
        "client_id":     client_id,
        "redirect_uri":  "http://localhost:8000/auth/google/callback",
        "response_type": "code",
        "scope":         GOOGLE_OAUTH_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    return {"auth_url": GOOGLE_AUTH_URL + "?" + urlencode(params)}


@router.get("/auth/google/callback")
def oauth_callback(request: Request, code: str = "", error: str = ""):
    if error:
        return RedirectResponse(url=f"/settings.html?oauth=error&reason={error}")
    if not code:
        raise HTTPException(400, "No code received")

    r = req.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri":  "http://localhost:8000/auth/google/callback",
        "grant_type":    "authorization_code",
    }, timeout=10)
    r.raise_for_status()
    tokens = r.json()
    refresh_token = tokens.get("refresh_token", "")

    from pathlib import Path
    from dotenv import load_dotenv
    ROOT = Path(__file__).parent.parent.parent
    env_path = ROOT / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    def _set(key, val):
        nonlocal lines
        for i, l in enumerate(lines):
            if l.startswith(f"{key}="):
                lines[i] = f"{key}={val}"; return
        lines.append(f"{key}={val}")

    if refresh_token:
        _set("GOOGLE_OAUTH_REFRESH_TOKEN", refresh_token)
    _set("GOOGLE_OAUTH_ACCESS_TOKEN", tokens.get("access_token", ""))
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(env_path, override=True)

    return RedirectResponse(url="http://familiekalender.local:8000/settings.html?oauth=success")
