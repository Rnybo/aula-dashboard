"""
Familieoverblik â€” API Test Suite
KÃ¸r: python tests/test_api.py
KrÃ¦ver at serveren kÃ¸rer pÃ¥ localhost:8000
"""
import requests
import json
import os
import sys
import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"
API_KEY  = os.getenv("API_KEY", "")
HEADERS  = {"x-api-key": API_KEY}

PASS = "\033[92mâœ“\033[0m"
FAIL = "\033[91mâœ—\033[0m"

results = []

def test(name, fn):
    try:
        fn()
        print(f"  {PASS} {name}")
        results.append((name, True, None))
    except AssertionError as e:
        print(f"  {FAIL} {name}: {e}")
        results.append((name, False, str(e)))
    except Exception as e:
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")
        results.append((name, False, str(e)))

def get(path, params=None, timeout=10):
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=timeout)

def post(path, body, timeout=10):
    return requests.post(f"{BASE_URL}{path}", headers={**HEADERS, "Content-Type": "application/json"},
                         data=json.dumps(body), timeout=timeout)

def delete(path, params=None, timeout=10):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=timeout)


print("\nðŸ”µ Server")

def t_status():
    r = get("/api/status")
    assert r.status_code == 200, f"status {r.status_code}"
    assert "session_valid" in r.json(), "missing session_valid"
test("GET /api/status returnerer session_valid", t_status)

def t_frontend():
    r = requests.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200 and "<html" in r.text.lower(), "ikke HTML"
test("GET / returnerer HTML", t_frontend)

def t_settings():
    r = requests.get(f"{BASE_URL}/settings.html", timeout=5)
    assert r.status_code == 200, f"status {r.status_code}"
test("GET /settings.html returnerer 200", t_settings)


print("\nðŸ”µ Auth")

def t_auth_accounts():
    r = get("/api/login/accounts")
    assert r.status_code == 200 and isinstance(r.json(), list), f"fejl: {r.status_code}"
test("GET /api/login/accounts returnerer liste", t_auth_accounts)

def t_oauth_connect():
    r = get("/api/google-oauth/connect")
    assert r.status_code == 200, f"status {r.status_code}"
    data = r.json()
    assert "url" in data or "auth_url" in data, f"mangler url: {data}"
test("GET /api/google-oauth/connect returnerer auth URL", t_oauth_connect)


print("\nðŸ”µ Google Calendar")

today = datetime.date.today().isoformat()
next_week = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

def t_gcal():
    r = get("/api/google-calendar", params={"from_date": today, "to_date": next_week})
    assert r.status_code == 200 and isinstance(r.json(), list), f"fejl: {r.status_code}"
test("GET /api/google-calendar returnerer liste", t_gcal)

def t_gcal_fields():
    r = get("/api/google-calendar", params={"from_date": today, "to_date": next_week})
    data = r.json()
    if data:
        for field in ("title", "start", "allDay", "owner", "color"):
            assert field in data[0], f"mangler felt: {field}"
test("Google Calendar events har pÃ¥krÃ¦vede felter", t_gcal_fields)

def t_weather():
    r = get("/api/weather")
    assert r.status_code == 200 and isinstance(r.json(), list), f"fejl: {r.status_code}"
test("GET /api/weather returnerer vejrdata", t_weather)


print("\nðŸ”µ Custom Events (CRUD)")

created_id = None

def t_custom_get():
    r = get("/api/custom-events")
    assert r.status_code == 200 and isinstance(r.json(), list), f"fejl: {r.status_code}"
test("GET /api/custom-events returnerer liste", t_custom_get)

def t_custom_post():
    global created_id
    r = post("/api/custom-events", {
        "title": "TEST_EVENT", "start": f"{today}T10:00", "end": f"{today}T11:00",
        "allDay": False, "calendar": "cal-faelles", "color": "#e53935", "description": "Test"
    })
    assert r.status_code == 200, f"status {r.status_code}"
    data = r.json()
    assert data.get("ok") and "id" in data, f"uventet svar: {data}"
    created_id = data["id"]
test("POST /api/custom-events opretter event", t_custom_post)

def t_custom_visible():
    if not created_id: raise AssertionError("intet event oprettet")
    ids = [e["id"] for e in get("/api/custom-events").json()]
    assert created_id in ids, "oprettet event ikke fundet"
test("Oprettet event vises i GET liste", t_custom_visible)

def t_custom_delete():
    if not created_id: raise AssertionError("intet event oprettet")
    r = delete(f"/api/custom-events/{created_id}")
    assert r.status_code == 200 and r.json().get("ok"), f"fejl: {r.text}"
test("DELETE /api/custom-events/{id} sletter event", t_custom_delete)

def t_custom_gone():
    if not created_id: raise AssertionError("intet event oprettet")
    ids = [e["id"] for e in get("/api/custom-events").json()]
    assert created_id not in ids, "slettet event vises stadig"
test("Slettet event mangler i GET liste", t_custom_gone)


print("\nðŸ”µ Aula")

def t_aula_posts():
    r = get("/api/posts")
    assert r.status_code in (200, 401, 403), f"uventet status {r.status_code}"
test("GET /api/posts svarer", t_aula_posts)

def t_aula_profile():
    r = get("/api/aula/profile")
    assert r.status_code in (200, 401, 403, 404), f"uventet status {r.status_code}"
test("GET /api/aula/profile svarer", t_aula_profile)


# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)

print(f"\n{'='*45}")
print(f"  Resultat: {passed}/{total} tests bestÃ¥et", end="")
if failed:
    print(f"  ({failed} fejlede)\n\n  Fejlede tests:")
    for name, ok, err in results:
        if not ok:
            print(f"    âœ— {name}\n      {err}")
else:
    print(" ðŸŽ‰")
print(f"{'='*45}\n")

sys.exit(0 if failed == 0 else 1)

