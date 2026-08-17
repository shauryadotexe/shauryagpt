"""
ShauryaGPT API server — the backend the Android/PWA app talks to.

Keeps your ANTHROPIC_API_KEY on the server, never in the app itself.
Anvi's device only ever talks to this server over HTTPS.

Run locally:
    export ANTHROPIC_API_KEY=your_key_here
    uvicorn api_server:app --host 0.0.0.0 --port 8000

Deploy (pick one, all have free tiers that easily cover this workload):
    - Render.com   -> New Web Service -> connect repo -> start command:
                      uvicorn api_server:app --host 0.0.0.0 --port $PORT
    - Railway.app  -> same idea, auto-detects the start command
    - Fly.io       -> fly launch, then fly deploy
Set ANTHROPIC_API_KEY as an environment variable on whichever you pick —
never commit it into the code.
"""

import os
import secrets

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shauryagpt import ShauryaGPT

# Simple shared-secret so random people who find the URL can't hit your API
# and burn your Claude credits. Anvi's app sends this in every request.
APP_ACCESS_TOKEN = os.environ.get("APP_ACCESS_TOKEN", "changeme")

app = FastAPI(title="ShauryaGPT API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your actual app's origin once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = ShauryaGPT()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": str}, ...]
    user_id: str = "anvi"


class ChatResponse(BaseModel):
    reply: str
    remaining_today: int | None  # null = unlimited (premium)


def check_auth(x_access_token: str | None):
    if not x_access_token or not secrets.compare_digest(x_access_token, APP_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid access token")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_access_token: str | None = Header(default=None)):
    check_auth(x_access_token)
    reply_text = bot.reply(req.message, recent_history=req.history, user_id=req.user_id)
    return ChatResponse(reply=reply_text, remaining_today=bot.remaining_today(req.user_id))


@app.get("/health")
def health():
    return {"status": "ok"}
