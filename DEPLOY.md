# ShauryaGPT — Android app (PWA) setup

A native `.apk` isn't something buildable in a sandboxed environment
like the one that generated this — that needs the Android SDK/Gradle
toolchain from Google's servers, which isn't reachable here. This is
the practical equivalent: an installable web app. Anvi opens a link
once, taps "Add to Home Screen" in Chrome, and it behaves like a real
app from then on — own icon, full-screen, no browser bar, works from
a cached shell even with a flaky connection.

If you specifically want a real native APK later, the natural next
step is wrapping this same web app in a thin native shell (Capacitor
or a WebView wrapper) — that does need Android Studio on an actual
machine with normal internet access, not achievable here.

## What's in here

```
api_server.py       — backend, wraps ShauryaGPT, exposes POST /chat
shauryagpt.py        — your existing RAG-lite logic (unchanged)
usage_tracker.py     — free/premium daily cap (unchanged)
chat_index.*          — your prebuilt retrieval index
web/
  index.html          — the chat app itself
  manifest.json       — makes it installable
  sw.js               — offline app-shell caching
  icon-192.png / icon-512.png — app icon (matches the app's glow theme)
```

## 1. Get a free Gemini API key

No credit card needed. Go to https://aistudio.google.com/apikey, sign
in with a Google account, click "Create API key." Free tier limits
(roughly 10-15 requests/minute, a few hundred/day depending on the
model) are far more than one person texting casually will hit.

## 2. Deploy the backend

Pick one (all have free tiers, this workload costs nothing on them):

**Render.com**
1. Push this folder to a GitHub repo.
2. New → Web Service → connect the repo.
3. Start command: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `GEMINI_API_KEY` = your free key from AI Studio
   - `APP_ACCESS_TOKEN` = make up a random string (this is the shared
     secret the app uses so randoms can't hit your API and burn credits)
5. Deploy. You'll get a URL like `https://shauryagpt.onrender.com`.

**Railway.app** — same idea, it auto-detects Python + the start command.

## 2. Point the frontend at your backend

In `web/index.html`, near the top of the `<script>` block, set:

```html
<script>
  window.SHAURYAGPT_API_BASE = "https://your-deployed-url.com";
  window.SHAURYAGPT_ACCESS_TOKEN = "the same random string you set as APP_ACCESS_TOKEN";
</script>
```

Add this as its own `<script>` tag right before the existing one, so
it runs first.

## 3. Host the frontend

Any static host works — Vercel, Netlify, GitHub Pages, or even
Render's static site option. Drag the `web/` folder in, or connect
the repo and point it at `web/` as the root.

## 4. Get it on Anvi's phone

1. Send her the frontend URL.
2. She opens it in Chrome on Android.
3. Chrome menu (⋮) → "Add to Home screen" → Install.
4. It now opens like any other app — icon, splash, full screen.

## Notes

- The glow behind the chat shifts and brightens while a reply is
  generating — that's the "presence" effect, driven by CSS animation
  + a `.thinking` class toggled during the fetch.
- The access token is basic protection, not real auth — fine for
  "keep strangers who stumble on the URL from burning your API
  credits," not meant to survive someone deliberately trying to
  extract it from the app's source (it's visible in plain JS).
- Session history resets when she closes the tab/app (uses
  `sessionStorage`, not permanent storage) — say if you want it to
  persist across sessions instead.
