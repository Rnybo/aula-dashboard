"""
routers/cast.py — Cast state endpoints + WebSocket stream
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException

from backend.cast_service import get_state, get_devices, add_listener, control_device, transfer_playback

router        = APIRouter()
router_auth   = APIRouter()  # control endpoints med API-nøgle krav

# ── WebSocket queue per forbundet klient ──────────────────────────────────────
_ws_queues: list[asyncio.Queue] = []


def _on_cast_state(device: str, state: dict):
    """Kaldes fra cast_service når state ændrer sig — pusher til alle WS-klienter."""
    try:
        from backend.mqtt_client import mqtt_client
        mqtt_client.publish(f"familieoverblik/cast/{device}/state", state, retain=True)
    except Exception:
        pass
    data = json.dumps(state)
    for q in list(_ws_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass


# Registrer listener én gang
add_listener(_on_cast_state)


_MOCK_STATE = {
    "Stuen": {
        "device": "Stuen", "app": "Spotify", "state": "PLAYING",
        "title": "Blinding Lights", "artist": "The Weeknd", "album": "After Hours",
        "image": "https://i.scdn.co/image/ab67616d0000b273ef017e899c0547766997d874",
        "volume": 0.45,
    },
    "Køkken Hub": {
        "device": "Køkken Hub", "app": "YouTube Music", "state": "PAUSED",
        "title": "Bohemian Rhapsody", "artist": "Queen", "album": "A Night at the Opera",
        "image": None, "volume": 0.6,
    },
}


@router.get("/api/cast/state")
def cast_state():
    """Returnerer seneste state for alle Cast-enheder."""
    import os
    if os.getenv("CAST_MOCK", "").lower() in ("1", "true", "yes"):
        return _MOCK_STATE
    return get_state()


@router.websocket("/ws/cast")
async def cast_ws(websocket: WebSocket):
    """WebSocket stream — sender state-opdateringer i real-time."""
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _ws_queues.append(queue)
    try:
        for state in get_state().values():
            await websocket.send_text(json.dumps(state))
        while True:
            data = await asyncio.wait_for(queue.get(), timeout=30)
            await websocket.send_text(data)
    except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
        pass
    finally:
        _ws_queues.remove(queue)


@router.get("/api/cast/devices")
def cast_devices():
    """Returnerer liste af alle kendte Cast-enheder."""
    return {"devices": get_devices()}


@router_auth.post("/api/cast/{device}/transfer")
async def cast_transfer(device: str, request: Request):
    data = await request.json()
    target = data.get("target", "")
    if not target:
        raise HTTPException(400, "target required")
    result = transfer_playback(device, target)
    return result


@router_auth.post("/api/cast/{device}/pause")
def cast_pause(device: str):
    return {"ok": control_device(device, "pause")}

@router_auth.post("/api/cast/{device}/play")
def cast_play(device: str):
    return {"ok": control_device(device, "play")}

@router_auth.post("/api/cast/{device}/stop")
def cast_stop(device: str):
    return {"ok": control_device(device, "stop")}

@router_auth.post("/api/cast/{device}/next")
def cast_next(device: str):
    return {"ok": control_device(device, "next")}

@router_auth.post("/api/cast/{device}/previous")
def cast_previous(device: str):
    return {"ok": control_device(device, "previous")}

@router_auth.post("/api/cast/{device}/seek")
async def cast_seek(device: str, request: Request):
    data = await request.json()
    delta = float(data.get("delta", 0))
    return {"ok": control_device(device, "seek", delta=delta)}

@router_auth.post("/api/cast/{device}/volume")
async def cast_volume(device: str, request: Request):
    data = await request.json()
    level = float(data.get("level", 0.5))
    return {"ok": control_device(device, "volume", level=level)}
