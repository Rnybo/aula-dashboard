"""
routers/weather.py — Weather endpoint
"""
import datetime
import os

import requests as req
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/api/weather")
def weather():
    lat = os.getenv("WEATHER_LAT", "56.127")
    lon = os.getenv("WEATHER_LON", "10.178")
    try:
        r = req.get(
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}",
            headers={"User-Agent": "home-dashboard/1.0 github.com/Rnybo/home-dashboard"},
            timeout=8
        )
        r.raise_for_status()
        series = r.json()["properties"]["timeseries"]
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        result, seen_hours = [], set()
        for entry in series:
            t = datetime.datetime.fromisoformat(entry["time"])
            hour = t.replace(minute=0, second=0, microsecond=0)
            if hour < now - datetime.timedelta(minutes=30): continue
            if hour in seen_hours: continue
            seen_hours.add(hour)
            instant = entry["data"]["instant"]["details"]
            next1h  = entry["data"].get("next_1_hours", {})
            next6h  = entry["data"].get("next_6_hours", {})
            result.append({
                "time":     hour.isoformat(),
                "temp":     round(instant.get("air_temperature", 0)),
                "wind":     round(instant.get("wind_speed", 0), 1),
                "wind_dir": round(instant.get("wind_from_direction", 0)),
                "symbol":   next1h.get("summary", {}).get("symbol_code", "")
                            or next6h.get("summary", {}).get("symbol_code", ""),
                "precip":   next1h.get("details", {}).get("precipitation_amount", 0)
                            or next6h.get("details", {}).get("precipitation_amount", 0),
            })
            if len(result) >= 168: break
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
