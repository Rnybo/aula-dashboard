from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from aula_client import AulaClient
import os

load_dotenv()

app = FastAPI()
client = AulaClient()


class SessionUpdate(BaseModel):
    phpsessid: str
    csrf_token: str


@app.get("/api/status")
def status():
    valid = client.check_session()
    return {"session_valid": valid}


@app.post("/api/refresh-session")
def refresh_session(body: SessionUpdate):
    client.update_credentials(body.phpsessid, body.csrf_token)
    valid = client.check_session()
    if not valid:
        raise HTTPException(status_code=401, detail="New credentials rejected by Aula")
    return {"ok": True}


@app.get("/api/profile")
def profile():
    try:
        return client.get_profile()
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages")
def messages(page: int = 0):
    try:
        threads = client.get_threads(page)
        return [{"id": t["id"], "subject": t.get("subject", ""), "read": t.get("read", True)} for t in threads]
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/messages/{thread_id}")
def thread(thread_id: int):
    try:
        return client.get_messages_for_thread(thread_id)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar")
def calendar(inst_profile_ids: str = ""):
    try:
        ids = [int(i) for i in inst_profile_ids.split(",") if i]
        return client.get_calendar_events(ids)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/", StaticFiles(directory="static", html=True), name="static")
