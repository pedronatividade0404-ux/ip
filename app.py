import os
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import create_client, Client
import httpx

load_dotenv()

TOKEN = os.getenv("JARVIS_CLOUD_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

if not TOKEN:
    raise RuntimeError("JARVIS_CLOUD_TOKEN nao configurado")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL/SUPABASE_SERVICE_KEY nao configurados")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
app = FastAPI(title="JARVIS Cloud", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("JARVIS_CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)

def ok_token(value: str | None) -> bool:
    return bool(value) and value == TOKEN

def denied():
    return JSONResponse({"ok": False, "error": "unauthorized"}, 401)

def db_error(exc: Exception):
    print("[SUPABASE]", repr(exc))
    return JSONResponse({"ok": False, "error": "database_error", "detail": str(exc)}, 500)

@app.get("/")
def root():
    return {"ok": True, "service": "JARVIS Cloud", "version": "2.0", "database": "Supabase"}

@app.get("/health")
def health():
    try:
        supabase.table("jarvis_devices").select("device_id").limit(1).execute()
        db = "online"
    except Exception:
        db = "offline"
    return {"ok": True, "service": "jarvis-cloud", "database": db, "time": time.time()}

@app.post("/v1/device/heartbeat")
async def heartbeat(req: Request, x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        b = await req.json()
        device_id = str(b.get("device_id") or "j4plus")
        row = {
            "device_id": device_id,
            "device_name": str(b.get("device_name") or device_id),
            "device_type": str(b.get("device_type") or "android"),
            "battery": b.get("battery"),
            "charging": b.get("charging"),
            "metadata": b.get("metadata") if isinstance(b.get("metadata"), dict) else {},
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        r = supabase.table("jarvis_devices").upsert(row, on_conflict="device_id").execute()
        return {"ok": True, "device": (r.data or [row])[0]}
    except Exception as exc: return db_error(exc)

@app.get("/v1/devices")
def devices(x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        r = supabase.table("jarvis_devices").select("*").order("last_seen", desc=True).execute()
        return {"ok": True, "devices": r.data or []}
    except Exception as exc: return db_error(exc)

@app.post("/v1/location")
async def location(req: Request, x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        b = await req.json()
        lat = b.get("latitude", b.get("lat")); lon = b.get("longitude", b.get("lon"))
        if lat is None or lon is None:
            return JSONResponse({"ok": False, "error": "latitude_longitude_required"}, 400)
        row = {
            "device_id": str(b.get("device_id") or "j4plus"),
            "latitude": float(lat), "longitude": float(lon),
            "accuracy": b.get("accuracy"), "altitude": b.get("altitude"), "battery": b.get("battery")
        }
        r = supabase.table("jarvis_location").upsert(row, on_conflict="device_id").execute()
        return {"ok": True, "location": (r.data or [row])[0]}
    except Exception as exc: return db_error(exc)

@app.get("/v1/location")
def location_get(device_id: str = "j4plus", x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        r = supabase.table("jarvis_location").select("*").eq("device_id", device_id).limit(1).execute()
        return {"ok": True, "location": (r.data or [None])[0]}
    except Exception as exc: return db_error(exc)

@app.post("/v1/sentinel/state")
async def sentinel_state_set(req: Request, x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        b = await req.json(); device_id = str(b.get("device_id") or b.get("device") or "j4plus")
        row = {"device_id": device_id, "enabled": bool(b.get("enabled")), "mode": str(b.get("mode") or "motion")}
        r = supabase.table("jarvis_sentinel_state").upsert(row, on_conflict="device_id").execute()
        return {"ok": True, "state": (r.data or [row])[0]}
    except Exception as exc: return db_error(exc)

@app.get("/v1/sentinel/state")
def sentinel_state_get(device_id: str = "j4plus", x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        r = supabase.table("jarvis_sentinel_state").select("*").eq("device_id", device_id).limit(1).execute()
        return {"ok": True, "state": (r.data or [{"device_id": device_id, "enabled": False, "mode": "motion"}])[0]}
    except Exception as exc: return db_error(exc)

@app.post("/v1/sentinel/event")
async def sentinel_event(req: Request, x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        b = await req.json()
        metadata: Any = b.get("metadata", b.get("extra", {}))
        if not isinstance(metadata, dict): metadata = {"value": metadata}
        note = b.get("note")
        if note: metadata["note"] = note
        row = {
            "device_id": str(b.get("device_id") or b.get("device") or "j4plus"),
            "event_type": str(b.get("event_type") or b.get("kind") or "motion"),
            "person_name": b.get("person_name"), "confidence": b.get("confidence"),
            "image_url": b.get("image_url"), "metadata": metadata,
        }
        r = supabase.table("jarvis_sentinel_events").insert(row).execute()
        return {"ok": True, "event": (r.data or [row])[0]}
    except Exception as exc: return db_error(exc)

@app.get("/v1/sentinel/events")
def sentinel_events(limit: int = Query(50, ge=1, le=500), device_id: str | None = None, x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        q = supabase.table("jarvis_sentinel_events").select("*")
        if device_id: q = q.eq("device_id", device_id)
        r = q.order("created_at", desc=True).limit(limit).execute()
        return {"ok": True, "events": r.data or []}
    except Exception as exc: return db_error(exc)


@app.post("/v1/chat")
async def cloud_chat(req: Request, x_jarvis_token: str | None = Header(None)):
    """Cerebro do JARVIS em nuvem. Mantem o historico por dispositivo no Supabase."""
    if not ok_token(x_jarvis_token): return denied()
    if not GROQ_API_KEY:
        return JSONResponse({"ok": False, "error": "groq_not_configured"}, 503)
    try:
        b = await req.json()
        device_id = str(b.get("device_id") or "unknown")
        text = str(b.get("text") or "").strip()
        if not text:
            return JSONResponse({"ok": False, "error": "text_required"}, 400)

        # Ultimas mensagens do mesmo dispositivo.
        hist = (supabase.table("jarvis_cloud_messages")
                .select("role,content,created_at")
                .eq("device_id", device_id)
                .order("created_at", desc=True).limit(12).execute()).data or []
        hist.reverse()
        messages = [{"role": "system", "content": (
            "Voce e JARVIS, um assistente pessoal em portugues brasileiro. "
            "Seja natural, objetivo e util. O usuario pode usar PC, TV e um Galaxy J4+ "
            "como terminal/sensor. Nao afirme que executou uma acao local se ela nao foi confirmada."
        )}]
        messages += [{"role": x["role"], "content": x["content"]} for x in hist if x.get("role") in ("user","assistant")]
        messages.append({"role": "user", "content": text})

        async with httpx.AsyncClient(timeout=45) as client:
            rr = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": messages, "temperature": 0.5, "max_tokens": 700},
            )
        if rr.status_code >= 400:
            return JSONResponse({"ok": False, "error": "groq_error", "detail": rr.text[:1000]}, 502)
        answer = rr.json()["choices"][0]["message"]["content"].strip()
        supabase.table("jarvis_cloud_messages").insert([
            {"device_id": device_id, "role": "user", "content": text},
            {"device_id": device_id, "role": "assistant", "content": answer},
        ]).execute()
        return {"ok": True, "answer": answer, "device_id": device_id, "model": GROQ_MODEL}
    except Exception as exc:
        print("[CHAT]", repr(exc))
        return JSONResponse({"ok": False, "error": "chat_error", "detail": str(exc)}, 500)

@app.get("/v1/chat/history")
def cloud_chat_history(device_id: str = "unknown", limit: int = Query(30, ge=1, le=200), x_jarvis_token: str | None = Header(None)):
    if not ok_token(x_jarvis_token): return denied()
    try:
        r = (supabase.table("jarvis_cloud_messages").select("*")
             .eq("device_id", device_id).order("created_at", desc=True).limit(limit).execute())
        items = r.data or []
        items.reverse()
        return {"ok": True, "messages": items}
    except Exception as exc: return db_error(exc)
