# Eidon — Demo / Prototype

An AI-driven project intelligence agent. This demo shows:
- Sidebar nav: **Portfolio → Projects → Sprints → Risks → Inbox → Settings → AI Insights**
- KPI row (Projects, Open Risks, Budget Used, On-time Delivery)
- Portfolio extras: **Velocity, Health %, highlight chips**
- Sprints cockpit: **Burndown, WSJF suggestions, Nudge owner, Publish summary** (simulated)
- Risks: **Auto-detected Top-3** with **Why/Actions** + simple **history chart**
- Inbox: **Daily Digest, Approve/Review, Snooze, Ask-Why**
- Settings: mock **Jira/Confluence/Slack** tokens + **Sync Now**
- Overlay editing at `~/.eidon/demo-overlay` + **Reset Seed**

> Built with Python stdlib + Streamlit. Tested with **eidon 0.1.5**.

---

## Quickstart

```bash
# Build and install locally (Apple Silicon / macOS)
cd ~/Projects/eidon
uv build
pipx install --force ./dist/eidon-0.1.5-py3-none-any.whl

# Verify CLI version
eidon --version

# Launch the demo
eidon demo-web
