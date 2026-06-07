# Sentinel Prime — Command Center (dashboard integration)

The "Command Center" dashboard is a design-tool **bundle** (a self-contained React SPA exported
from a design tool) served by the `sentinel-premium` Flask app. `v2-integrate.js` is the
**integration layer** that wires that static design to the live backend. It is appended to the
served HTML between `<!--SP-WIRE-START-->` and `<!--SP-WIRE-END-->`.

## What the integration wires (all client-side, same-origin `/api/*` — no secrets)
- **Chat** → `/api/chat/sentinel/stream` (SSE) to the Sentinel Prime Hermes agent, with a
  Claude-style "thinking" indicator; lives as a body-overlay inside `#root` so React never
  fights it; conversation persists across nav; loads history from `/api/conversations`.
- **Model switcher + Auto** → `/api/models`, `/api/models/switch`, `/api/models/auto-route`.
- **Live data** → enables the bundle's `HERMES` poller against `/api/dashboard`; the panels
  (fleet, brain, providers, stats) go live.
- **Layout** → chat moved to the **AI Chat** tab; **Overview** repurposed (CSS-only) to a
  system overview (no chat).
- **Buttons wired** (were decorative): notifications bell + **Clear all**, settings **gear**,
  sidebar **collapse**, top-bar **search**, Model Router **Scan**, and the chat **quick-actions**.
- **Mission Control (TV)** → a rotating display cycling NEURAL NETWORK (Three.js `Network3D`) →
  FLEET → MEMORY → SYSTEM VITALS every ~11s.

## Deploy
Append the script to the served HTML (idempotent):
```bash
F=/opt/hermes-workspace/sentinel-prime-premium/public/index.html   # and v2.html
sed -i '/SP-WIRE-START/,/SP-WIRE-END/d' "$F"
printf '\n<!--SP-WIRE-START-->\n' >> "$F"; cat v2-integrate.js >> "$F"; printf '\n<!--SP-WIRE-END-->\n' >> "$F"
```

## Backend dependencies (configured on the server — NOT in this public repo)
- `chat_agents.json` → the `sentinel` agent points at the Hermes agent `http://localhost:8765/v1`.
- systemd drop-in `HERMES_HOME=/opt/hermes-state` (so `/api/models` catalog loads).
- `app.py` provides `/api/dashboard` + keeps chat on the agent (switch only changes the agent's model).

## Full restorable backup (incl. the 1.8MB bundle + secret-bearing backend files)
Kept **off this public repo** to avoid leaking API keys, on NUKE at:
`/opt/hermes-workspace/sentinel-prime-premium/backups/2026-06-07-working/` (see its `README.txt`).
