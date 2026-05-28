import requests
import os
import logging
import json
import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

API_BASE = "https://www.aula.dk/api/v"
API_VERSION = "23"
SESSION_FILE = Path(__file__).parent.parent / "session.json"


class AulaClient:
    def __init__(self):
        self.session = requests.Session()
        self.session_valid = False
        self._profile_cache = None  # cached profile data, invalidated on new credentials
        self._load_credentials()

    def _load_credentials(self):
        phpsessid = None
        csrf_token = None
        if SESSION_FILE.exists():
            try:
                data = json.loads(SESSION_FILE.read_text())
                phpsessid = data.get("PHPSESSID")
                csrf_token = data.get("CSRF_TOKEN")
                logger.info("Loaded credentials from session.json")
            except Exception as e:
                logger.warning(f"Could not read session.json: {e}")
        if not phpsessid:
            phpsessid = os.getenv("AULA_PHPSESSID", "")
        if not csrf_token:
            csrf_token = os.getenv("AULA_CSRF_TOKEN", "")
        self._apply_credentials(phpsessid, csrf_token)

    def _apply_credentials(self, phpsessid: str, csrf_token: str):
        self._csrf_token = csrf_token
        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "referer": "https://www.aula.dk/portal/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        })
        self.session.cookies.update({
            "PHPSESSID": phpsessid,
            "Csrfp-Token": csrf_token,
            "initialLogin": "true",
        })

    def _post(self, method: str, body: dict) -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}"
        resp = self.session.post(url, json=body, verify=True,
            headers={"csrfp-token": self._csrf_token})
        resp.raise_for_status()
        return resp.json()

    def update_credentials(self, phpsessid: str, csrf_token: str):
        self._apply_credentials(phpsessid, csrf_token)
        self._profile_cache = None  # invalidate cache on new session
        SESSION_FILE.write_text(json.dumps({
            "PHPSESSID": phpsessid,
            "CSRF_TOKEN": csrf_token
        }))
        self.session_valid = True
        logger.info("Credentials updated and saved to session.json")

    def check_session(self) -> bool:
        try:
            resp = self.session.get(
                f"{API_BASE}{API_VERSION}/?method=profiles.getProfilesByLogin",
                verify=True,
                allow_redirects=False
            )
            data = resp.json()
            self.session_valid = resp.status_code == 200 and data.get("status", {}).get("code") == 0
        except Exception:
            self.session_valid = False
        if not self.session_valid:
            self._profile_cache = None
        return self.session_valid

    def _get(self, method: str, extra_params: str = "") -> dict:
        url = f"{API_BASE}{API_VERSION}/?method={method}{extra_params}"
        resp = self.session.get(url, verify=True)
        if resp.status_code == 401:
            self.session_valid = False
            raise PermissionError("Session expired")
        resp.raise_for_status()
        return resp.json()

    def get_profile(self) -> dict:
        if self._profile_cache is None:
            self._profile_cache = self._get("profiles.getProfileContext", "&portalrole=guardian")
        return self._profile_cache

    def _get_institutions(self) -> list:
        """Return institutions list from cached profile."""
        return self.get_profile().get("data", {}).get("institutions") or []

    def _get_guardian_profile_ids(self) -> list:
        """Guardian institutionProfileId per institution."""
        return [i.get("institutionProfileId") for i in self._get_institutions() if i.get("institutionProfileId")]

    def _get_inst_codes(self) -> list:
        """Institution codes (e.g. G20341) for all institutions."""
        return list({i.get("institutionCode") for i in self._get_institutions() if i.get("institutionCode")})

    def get_threads(self, page: int = 0) -> list:
        data = self._get("messaging.getThreads", f"&sortOn=date&orderDirection=desc&page={page}")
        return data.get("data", {}).get("threads", [])

    def get_messages_for_thread(self, thread_id: int, page: int = 0) -> dict:
        data = self._get("messaging.getMessagesForThread", f"&threadId={thread_id}&page={page}")
        return data.get("data", {})

    def get_calendar_events(self, inst_profile_ids: list, from_date: str = None, to_date: str = None) -> list:
        today = datetime.date.today()
        if not from_date:
            from_date = today.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (today + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        tz_offset = datetime.datetime.now().astimezone().strftime("%z")
        tz_str = f"{tz_offset[:3]}:{tz_offset[3:]}"
        start = f"{from_date} 00:00:00.0000{tz_str}"
        end = f"{to_date} 23:59:59.9990{tz_str}"
        data = self._post("calendar.getEventsByProfileIdsAndResourceIds", {
            "instProfileIds": inst_profile_ids,
            "resourceIds": [],
            "start": start,
            "end": end
        })
        return data.get("data") or []

    def get_albums(self, inst_profile_ids: list, index: int = 0, limit: int = 24) -> list:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("gallery.getAlbums", f"&index={index}&limit={limit}&sortOn=mediaCreatedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", []) or []

    def get_album_media(self, album_id: int, inst_profile_ids: list = None, index: int = 0, limit: int = 40) -> dict:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in (inst_profile_ids or []))
        data = self._get("gallery.getMedia", f"&albumId={album_id}&index={index}&limit={limit}&sortOn=uploadedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", {})

    def get_user_media(self, inst_profile_ids: list, index: int = 0, limit: int = 12) -> dict:
        ids_param = "".join(f"&filterInstProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("gallery.getMedia", f"&userSpecificAlbum=true&index={index}&limit={limit}&sortOn=uploadedAt&orderDirection=desc&filterBy=all{ids_param}")
        return data.get("data", {})

    def get_posts(self, inst_profile_ids: list, index: int = 0, limit: int = 10) -> dict:
        all_ids = list(dict.fromkeys(self._get_guardian_profile_ids() + inst_profile_ids))
        ids_param = "".join(f"&institutionProfileIds[]={i}" for i in all_ids)
        data = self._get("posts.getAllPosts", f"&parent=profile&index={index}&limit={limit}{ids_param}")
        return data.get("data", {})

    def get_important_dates(self, inst_profile_ids: list, limit: int = 20) -> list:
        data = self._get("calendar.getImportantDates", f"&limit={limit}&include_today=false")
        items = data.get("data", []) or []
        # Deduplicate — merge belongsToProfiles from duplicates
        seen, result = {}, []
        for item in items:
            key = item.get("title","") + "|" + item.get("startDateTime","")[:10]
            if key not in seen:
                seen[key] = item
                result.append(item)
            else:
                # Merge child IDs from duplicate entry
                existing = seen[key]
                merged = list(set((existing.get("belongsToProfiles") or []) + (item.get("belongsToProfiles") or [])))
                existing["belongsToProfiles"] = merged
        return result

    def get_birthdays(self, inst_profile_ids: list) -> list:
        inst_codes = self._get_inst_codes()
        if not inst_codes:
            return []
        today = datetime.date.today()
        end = today + datetime.timedelta(days=30)
        tz_offset = datetime.datetime.now().astimezone().strftime("%z")
        codes_param = "".join(f"&instCodes[]={c}" for c in inst_codes)
        url = f"https://www.aula.dk/api/v23/?method=calendar.getBirthdayEventsForInstitutions&start={today}T00:00:00.000%2B{tz_offset[1:3]}%3A{tz_offset[3:]}&end={end}T23:59:59.000%2B{tz_offset[1:3]}%3A{tz_offset[3:]}{codes_param}"
        resp = self.session.get(url, verify=True)
        if resp.status_code == 401:
            raise PermissionError("Session expired")
        resp.raise_for_status()
        return resp.json().get("data", []) or []

    def get_groups(self) -> list:
        """Return children's primary groups with all children and their parents.

        Strategy:
        1. From getProfileContext, get each child's institutionProfileId and institution.
        2. Call groups.getGroupsForProfile for each child to find their mainGroupId.
        3. Call getMemberships for each unique mainGroupId.
        4. Return structured list of groups with children and parents.
        """
        profile_data = self.get_profile().get("data", {})
        institutions = profile_data.get("institutions") or []

        # Collect children across all institutions
        # child: {name, institutionProfileId, institutionCode}
        my_children = []
        for inst in institutions:
            for child in (inst.get("children") or []):
                my_children.append({
                    "name": child.get("name", ""),
                    "institutionProfileId": child.get("institutionProfileId"),
                    "institutionCode": inst.get("institutionCode", ""),
                })

        if not my_children:
            return []

        # Find groupId for each child via groups.getGroupsForProfile
        child_group_ids = {}  # child institutionProfileId -> mainGroupId
        for child in my_children:
            pid = child["institutionProfileId"]
            if not pid:
                continue
            try:
                data = self._get("groups.getGroupsForProfile", f"&profileId={pid}")
                groups = data.get("data", []) or []
                # Find the group where type == "primary" or pick the first one
                for g in groups:
                    if g.get("type") in ("primary", "institutional") or not child_group_ids.get(pid):
                        child_group_ids[pid] = g.get("id")
                        if g.get("type") == "primary":
                            break
            except Exception as e:
                logger.warning(f"Could not get groups for child {pid}: {e}")

        unique_group_ids = list(dict.fromkeys(v for v in child_group_ids.values() if v))

        result = []
        for group_id in unique_group_ids:
            try:
                # Get group name
                group_data = self._get("groups.getGroupById", f"&groupId={group_id}")
                group_name = group_data.get("data", {}).get("name", f"Gruppe {group_id}")

                # Get all memberships
                memberships_data = self._get("groups.getMemberships", f"&groupId={group_id}")
                memberships = memberships_data.get("data", {}).get("memberships", []) or []

                children = []
                for m in memberships:
                    if m.get("institutionRole") not in ("daycare", "student", "child"):
                        continue
                    ip = m.get("institutionProfile", {})
                    pic = ip.get("profilePicture") or {}
                    pic_key = pic.get("key", "")
                    photo_url = f"https://media-prod.aula.dk/{pic_key}_200x200.jpg" if pic_key else ""

                    # Parents are in relations with role guardian
                    parents = []
                    for rel in (ip.get("relations") or []):
                        if rel.get("role") == "guardian":
                            rel_pic = rel.get("profilePicture") or {}
                            rel_pic_key = rel_pic.get("key", "")
                            parents.append({
                                "name": rel.get("fullName", ""),
                                "gender": rel.get("gender", ""),
                                "photoUrl": f"https://media-prod.aula.dk/{rel_pic_key}_200x200.jpg" if rel_pic_key else "",
                            })

                    children.append({
                        "id": ip.get("id"),
                        "name": ip.get("fullName", ""),
                        "gender": ip.get("gender", ""),
                        "photoUrl": photo_url,
                        "parents": parents,
                    })

                # Sort children alphabetically by first name
                children.sort(key=lambda c: c["name"])

                result.append({
                    "id": group_id,
                    "name": group_name,
                    "children": children,
                })
            except Exception as e:
                logger.warning(f"Could not get group {group_id}: {e}")

        return result

    def get_presence(self, inst_profile_ids: list, from_date: str = None, to_date: str = None) -> list:
        today = datetime.date.today()
        if not from_date:
            from_date = today.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (today + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        ids_param = "".join(f"&filterInstitutionProfileIds[]={i}" for i in inst_profile_ids)
        data = self._get("presence.getPresenceTemplates", f"{ids_param}&fromDate={from_date}&toDate={to_date}")
        return data.get("data", {}).get("presenceWeekTemplates", []) or []
