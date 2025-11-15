"""
Eidon Demo Web (Phase 5 • Acceptance-ready, polished)
- Dark theme (from .streamlit/config.toml)
- SVG-safe logo
- Sidebar: Portfolio → Projects → Sprints → Risks → Inbox → Settings → AI Insights
- KPI row (Projects, Open Risks, Budget Used, On-time Delivery)
- Portfolio extras: Velocity, Health % (color-coded), highlight chips, blockers link
- Projects: Health card, workload chart + capacity alerts, recent activity
- Sprints: Burndown, WSJF Suggested Scope (inline editors + persist), Nudge Owner, Publish Summary (sim)
- Risks: Rule-based detection (Top-3), Why + Recommended Action, history chart
- Inbox: Daily Digest, Approve/Review/Snooze/Ask-Why, Dismiss + 'Show dismissed', project filter
- Settings: Mock integrations + Sync Now
- AI Insights: 👍 feedback + learning progress

Stdlib-only (plus streamlit). No extra deps required.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import shutil
import zipfile
from datetime import datetime
from importlib import resources as ires
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import datetime as dt
import os
import time

import streamlit as st
from streamlit.components.v1 import html as st_html

# ──────────────────────────────
# Page setup
# ──────────────────────────────
st.set_page_config(page_title="Eidon Demo", page_icon="📊", layout="wide")

NAV = ["Portfolio", "Projects", "Sprints", "Risks", "Inbox", "Settings", "AI Insights"]
DEFAULT_PROJECT = "P-1002"
OVERLAY_DIR = Path.home() / ".eidon" / "demo-overlay"  # editable copies of JSON live here

# Overlay companion files created on-demand
SETTINGS_PATH = OVERLAY_DIR / "settings.json"
INBOX_PATH = OVERLAY_DIR / "inbox.json"
RISK_LOG_PATH = OVERLAY_DIR / "risk_actions.json"
FEATURES_PATH = OVERLAY_DIR / "features.json"
CAPACITY_MAP_PATH = OVERLAY_DIR / "capacity.json"  # optional: {"Alice": 8, "Bob": 10}
CAPACITY_DEFAULT = 8


# ──────────────────────────────
# Query params helpers (new API)
# ──────────────────────────────
def _get_qp() -> Dict[str, List[str] | str]:
    try:
        qp = dict(st.query_params)
        return {k: ([v] if isinstance(v, str) else v) for k, v in qp.items()}
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}


def _set_qp(**kwargs: str) -> None:
    try:
        upd = {k: ("" if v is None else str(v)) for k, v in kwargs.items()}
        st.query_params.update(upd)
    except Exception:
        try:
            st.experimental_set_query_params(**kwargs)
        except Exception:
            pass


# ──────────────────────────────
# Utility: assets & formatting
# ──────────────────────────────
def _load_logo() -> tuple[bytes | None, str | None]:
    for name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.svg"):
        try:
            p = ires.files("eidon") / "assets" / name
            b = p.read_bytes()
            return b, p.suffix.lower()
        except Exception:
            continue
    return None, None


def _render_logo() -> None:
    data, ext = _load_logo()
    if not data or not ext:
        return
    if ext == ".svg":
        try:
            svg = data.decode("utf-8", errors="ignore")
            st_html(f'<div style="width:100%;max-width:104px">{svg}</div>', height=120)
        except Exception:
            pass
    else:
        st.image(data, use_container_width=True)


def _fmt_money(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return "${:,.0f}".format(float(v)) if float(v) >= 1000 else "${:,.2f}".format(float(v))
    except Exception:
        return "—"


def _fmt_int(v: Any) -> str:
    try:
        if v is None:
            return "—"
        i = int(v)
        return f"{i:,}"
    except Exception:
        return "—"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.0f}%"
    except Exception:
        return "—"


def _parse_date(s: Any) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


# ──────────────────────────────
# UI scaffolding
# ──────────────────────────────
def _app_header() -> None:
    col1, col2 = st.columns([1, 7])
    with col1:
        _render_logo()
    with col2:
        st.title("Eidon — Portfolio & Delivery Demo")
    st.caption("Polished UI for stakeholder walkthroughs")


def _goto(page: str) -> None:
    st.session_state["eidon_nav"] = page
    _set_qp(page=page, project=st.session_state.get("selected_project", DEFAULT_PROJECT))
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()


def _sidebar_nav() -> Tuple[str, bool, bool]:
    with st.sidebar:
        st.caption("Navigation")

        if "eidon_nav" not in st.session_state:
            qp = _get_qp()
            st.session_state["eidon_nav"] = (qp.get("page", [NAV[0]]) or [NAV[0]])[0]

        current = st.session_state.get("eidon_nav", NAV[0])

        page = st.radio(
            "Go to",
            NAV,
            index=NAV.index(current) if current in NAV else 0,
            label_visibility="collapsed",
            help="Pick a section. Use 'Demo Mode' to show helper text and Next buttons.",
        )

        if page != current:
            st.session_state["eidon_nav"] = page
            _set_qp(page=page, project=st.session_state.get("selected_project", DEFAULT_PROJECT))

        st.divider()
        demo_mode = st.toggle(
            "Demo Mode",
            key="eidon_demo_mode",
            help="Adds helper text and Next buttons to guide a stakeholder walkthrough.",
            value=st.session_state.get("eidon_demo_mode", True),
        )
        reset_clicked = st.button(
            "Reset Seed",
            help="Re-seed ~/.eidon/demo-overlay from packaged demo JSON, then rerun.",
        )

        if OVERLAY_DIR.exists():
            st.caption(f"Editing data at:\n`{OVERLAY_DIR}`")

    return page, demo_mode, reset_clicked


def _maybe_demo_help(enabled: bool, text: str) -> None:
    if enabled:
        st.info(text, icon="💡")


# ──────────────────────────────
# Data loading + overlay
# ──────────────────────────────
def _find_default_demo_dir() -> Optional[Path]:
    candidates: List[Path] = []
    try:
        candidates.append(ires.files("eidon") / "data" / "demo")
    except Exception:
        pass
    candidates.append(Path(__file__).resolve().parent / "data" / "demo")
    candidates.append(Path.cwd() / "src" / "eidon" / "data" / "demo")
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def _copy_seed(src: Path, dst: Path, overwrite: bool) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.glob("*.json"):
        tgt = dst / p.name
        if overwrite or not tgt.exists():
            tgt.write_text(p.read_text())


def _ensure_overlay(default_dir: Path) -> Path:
    if not OVERLAY_DIR.exists():
        _copy_seed(default_dir, OVERLAY_DIR, overwrite=False)
    return OVERLAY_DIR


def _reset_overlay(default_dir: Path) -> None:
    if OVERLAY_DIR.exists():
        shutil.rmtree(OVERLAY_DIR)
    _copy_seed(default_dir, OVERLAY_DIR, overwrite=True)


def _load_all_json(demo_dir: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in demo_dir.iterdir():
        if p.suffix.lower() != ".json":
            continue
        try:
            out[p.stem] = json.loads(p.read_text())
        except Exception:
            out[p.stem] = None
    return out


def _flatten_find(d: Any, key: str) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k == key and isinstance(v, list):
                    found.extend([x for x in v if isinstance(x, dict)])
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return found


# Overlay JSON helpers
def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_overlay(path: Path, default):
    _ensure_dir(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_overlay(path: Path, data) -> None:
    _ensure_dir(path)
    path.write_text(json.dumps(data, indent=2))


def _now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Capacity helpers
def _load_capacity() -> Dict[str, int]:
    raw = _load_overlay(CAPACITY_MAP_PATH, {})
    try:
        return {str(k): int(v) for k, v in raw.items()}
    except Exception:
        return {}


def _capacity_for(name: str) -> int:
    return _load_capacity().get(name, CAPACITY_DEFAULT)


# ──────────────────────────────
# KPI computation
# ──────────────────────────────
def _compute_kpis(all_json: Dict[str, Any]) -> Dict[str, Any]:
    k = {"projects": None, "open_risks": None, "budget_used": None, "on_time": None}
    try:
        projs = _flatten_find(all_json, "projects")
        if not projs and isinstance(all_json.get("projects"), list):
            projs = [x for x in all_json["projects"] if isinstance(x, dict)]
        k["projects"] = len(projs) or None

        risks = _flatten_find(all_json, "risks")
        if not risks and isinstance(all_json.get("risks"), list):
            risks = [x for x in all_json["risks"] if isinstance(x, dict)]

        def _is_open(r: Dict[str, Any]) -> bool:
            s = str(r.get("status", "")).lower()
            return s not in {"closed", "resolved", "done"}

        k["open_risks"] = sum(1 for r in risks if _is_open(r)) or None

        total_spend = 0.0
        found_any = False
        for p in projs:
            v = p.get("spent") or p.get("actual_cost") or p.get("budget_spent") or p.get("cost_to_date")
            try:
                total_spend += float(str(v).replace(",", ""))
                found_any = True
            except Exception:
                continue
        if found_any:
            k["budget_used"] = total_spend

        sprints = _flatten_find(all_json, "sprints")
        if not sprints and isinstance(all_json.get("sprints"), list):
            sprints = [x for x in all_json["sprints"] if isinstance(x, dict)]
        ontime = 0
        considered = 0
        for s in sprints:
            planned = _parse_date(s.get("planned_end"))
            actual = _parse_date(s.get("actual_end"))
            forecast = _parse_date(s.get("forecast_end"))
            if not planned:
                continue
            considered += 1
            if actual:
                if actual <= planned:
                    ontime += 1
            elif forecast:
                if forecast <= planned:
                    ontime += 1
            else:
                considered -= 1
        if considered > 0:
            k["on_time"] = 100.0 * ontime / considered
    except Exception:
        pass
    return k


def _kpi_row(k: Dict[str, Any]) -> None:
    st.subheader("Key Indicators")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Projects", _fmt_int(k.get("projects")))
        st.caption("ⓘ Total projects (auto-detected).")
    with c2:
        st.metric("Open Risks", _fmt_int(k.get("open_risks")))
        st.caption("ⓘ Status not Closed/Resolved/Done.")
    with c3:
        st.metric("Budget Used", _fmt_money(k.get("budget_used")))
        st.caption("ⓘ Sum of 'spent' across projects.")
    with c4:
        st.metric("On-time Delivery", _fmt_pct(k.get("on_time")))
        st.caption("ⓘ % sprints where actual_end ≤ planned_end (or forecast_end).")


# ──────────────────────────────
# Export helpers
# ──────────────────────────────
def _kpi_svg(k: Dict[str, Any]) -> str:
    p = _fmt_int(k.get("projects"))
    r = _fmt_int(k.get("open_risks"))
    b = _fmt_money(k.get("budget_used"))
    o = _fmt_pct(k.get("on_time"))
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='180'>
      <rect width='1200' height='180' rx='16' ry='16' fill='#0F172A'/>
      <text x='40' y='48' fill='#E5E7EB' font-size='28' font-family='Inter, system-ui, sans-serif'>Eidon — Key Indicators</text>
      <g transform='translate(40,80)'>
        <rect width='260' height='80' rx='12' fill='#111827'/>
        <text x='16' y='32' fill='#9CA3AF' font-size='16'>Projects</text>
        <text x='16' y='64' fill='#E5E7EB' font-size='28'>{p}</text>
      </g>
      <g transform='translate(320,80)'>
        <rect width='260' height='80' rx='12' fill='#111827'/>
        <text x='16' y='32' fill='#9CA3AF' font-size='16'>Open Risks</text>
        <text x='16' y='64' fill='#E5E7EB' font-size='28'>{r}</text>
      </g>
      <g transform='translate(600,80)'>
        <rect width='260' height='80' rx='12' fill='#111827'/>
        <text x='16' y='32' fill='#9CA3AF' font-size='16'>Budget Used</text>
        <text x='16' y='64' fill='#E5E7EB' font-size='28'>{b}</text>
      </g>
      <g transform='translate(880,80)'>
        <rect width='260' height='80' rx='12' fill='#111827'/>
        <text x='16' y='32' fill='#9CA3AF' font-size='16'>On-time</text>
        <text x='16' y='64' fill='#E5E7EB' font-size='28'>{o}</text>
      </g>
    </svg>"""


def _zip_dir_bytes(d: Path) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in d.glob("*.json"):
            z.writestr(p.name, p.read_text())
    return bio.getvalue()


def _rows_to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    fields = sorted({k for r in rows for k in r.keys()})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _download_csv_button(label: str, rows: List[Dict[str, Any]], filename: str) -> None:
    if rows:
        st.download_button(label, _rows_to_csv(rows), file_name=filename, mime="text/csv")


def _export_bar(k: Dict[str, Any], data_dir: Path) -> None:
    svg = _kpi_svg(k)
    svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    st_html(
        f"""
        <div style="display:flex;gap:8px;justify-content:flex-end;margin:6px 0 12px 0">
          <button onclick="window.print()" style="padding:8px 12px;border-radius:12px;border:0;cursor:pointer">Print to PDF</button>
          <button onclick="(function(){{
              const svgText = atob('{svg_b64}');
              const blob = new Blob([svgText], {{type:'image/svg+xml;charset=utf-8'}});
              const url = URL.createObjectURL(blob);
              const img = new Image();
              img.onload = function(){{
                const c = document.createElement('canvas');
                c.width = 2400; c.height = 360;
                const ctx = c.getContext('2d');
                ctx.fillStyle = '#0F172A';
                ctx.fillRect(0,0,c.width,c.height);
                ctx.drawImage(img,0,0,c.width,c.height);
                URL.revokeObjectURL(url);
                const a = document.createElement('a');
                a.download = 'eidon_kpis.png';
                a.href = c.toDataURL('image/png');
                a.click();
              }};
              img.src = url;
          }})()" style="padding:8px 12px;border-radius:12px;border:0;cursor:pointer">Download KPIs PNG</button>
        </div>
        """,
        height=60,
    )
    st.download_button(
        "Download demo-data.zip",
        data=_zip_dir_bytes(data_dir),
        file_name="eidon_demo_data.zip",
        mime="application/zip",
        help=f"All JSON files under {data_dir}",
    )


# ──────────────────────────────
# KPI add-ons for Portfolio
# ──────────────────────────────
def _open_risks_count(risks_list):
    return sum(1 for r in risks_list if str(r.get("status", "")).lower() not in {"closed", "resolved", "done"})


def _compute_velocity(sprints_list):
    pts = [s.get("completed_points", s.get("completed", 0)) for s in sprints_list if s is not None]
    if not pts:
        return 0
    last = pts[-2:] if len(pts) >= 2 else pts
    return round(sum(last) / len(last))


def _compute_health(projects_list, risks_list, on_time_pct: float, scope_delta_pct: float = 0.0) -> int:
    risk_penalty = max(0, 100 - 10 * _open_risks_count(risks_list))
    scope_stability = max(0, 100 - abs(scope_delta_pct))
    score = 0.5 * (on_time_pct or 0.0) + 0.25 * risk_penalty + 0.25 * scope_stability
    return int(max(0, min(100, score)))


def _chip(text: str):
    st.markdown(
        f"<span style='padding:4px 8px;border:1px solid #444;border-radius:12px;margin-right:6px'>{text}</span>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────
# Sprints helpers (burndown, WSJF, Inbox append)
# ──────────────────────────────
def _wsjf(item: Dict[str, Any]) -> float:
    bv = item.get("business_value", 5)
    tc = item.get("time_criticality", 3)
    rr = item.get("rr_o_e", 3)  # risk reduction / opportunity enablement
    js = item.get("job_size", item.get("points", 3)) or 1
    js = max(1, int(js))
    return (float(bv) + float(tc) + float(rr)) / float(js)


def _append_inbox(entry: Dict[str, Any]) -> None:
    data = _load_overlay(INBOX_PATH, [])
    if "id" not in entry:
        entry["id"] = _now_str()
    data.append(entry)
    _save_overlay(INBOX_PATH, data)


def _build_burndown_df(sprint: Dict[str, Any]) -> Dict[str, List[Any]]:
    start = sprint.get("start") or sprint.get("planned_start")
    end = sprint.get("end") or sprint.get("planned_end") or sprint.get("forecast_end")
    total = sprint.get("committed_points", sprint.get("planned_points", 20))
    if not (start and end):
        return {"date": [], "remaining_points": []}
    d0 = dt.date.fromisoformat(str(start))
    d1 = dt.date.fromisoformat(str(end))
    days = max(1, (d1 - d0).days + 1)
    rem = [max(0, int(total - total * i / (days - 1))) for i in range(days)]
    dates = [str(d0 + dt.timedelta(days=i)) for i in range(days)]
    return {"date": dates, "remaining_points": rem}


# ──────────────────────────────
# Risks helpers (detect + actions + history + recommendations + persist)
# ──────────────────────────────
def _detect_risks_from_features(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    today = dt.date.today()
    for f in features:
        why = []
        conf = 0
        if f.get("blocked"):
            why.append("Issue is blocked")
            conf += 40
        due = f.get("due_date")
        if due:
            try:
                days_over = (today - dt.date.fromisoformat(str(due))).days
                if days_over > 2:
                    why.append(f"Overdue by {days_over} days")
                    conf += min(60, 10 * days_over)
            except Exception:
                pass
        if why:
            out.append(
                {
                    "key": f.get("key", ""),
                    "title": f.get("title", ""),
                    "confidence": min(95, conf),
                    "why": "; ".join(why),
                    "project_id": f.get("project_id"),
                }
            )
    return out


def _log_risk_action(risk: Dict[str, Any], action: str) -> None:
    data = _load_overlay(RISK_LOG_PATH, [])
    data.append({"key": risk.get("key", ""), "action": action, "ts": _now_str()})
    _save_overlay(RISK_LOG_PATH, data)


def _build_risk_history(sprints: List[Dict[str, Any]], features: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    points = []
    detected = _detect_risks_from_features(features)
    count = len(detected)
    for s in sprints:
        label = s.get("planned_end") or s.get("end") or s.get("name", "Sprint")
        points.append({"sprint": label, "risk_count": count})
    return {
        "sprint": [p["sprint"] for p in points],
        "risk_count": [p["risk_count"] for p in points],
    }


def _recommended_action(why_text: str) -> str:
    t = (why_text or "").lower()
    rec = []
    if "blocked" in t:
        rec.append("Nudge owner or reassign.")
    if "overdue" in t:
        rec.append("Split scope and add buffer.")
    return " ".join(rec) or "Monitor and review in next stand-up."


def _save_feature_fields_by_key(feat_key: str, fields: Dict[str, Any]) -> None:
    data = _load_overlay(FEATURES_PATH, [])
    items = data.get("features") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return
    for it in items:
        if it.get("key") == feat_key:
            for k, v in fields.items():
                it[k] = v
            break
    if isinstance(data, dict):
        data["features"] = items
    else:
        data = items
    _save_overlay(FEATURES_PATH, data)


# ──────────────────────────────
# Guided pages
# ──────────────────────────────
def _init_selection() -> None:
    if "selected_project" not in st.session_state:
        qp = _get_qp()
        st.session_state["selected_project"] = (qp.get("project", [DEFAULT_PROJECT]) or [DEFAULT_PROJECT])[0]


def _project_options(all_json: Dict[str, Any]) -> List[Tuple[str, str]]:
    projs = _flatten_find(all_json, "projects")
    opts: List[Tuple[str, str]] = []
    for p in projs:
        pid = str(p.get("id", ""))
        name = str(p.get("name", pid))
        if pid:
            opts.append((f"{name} ({pid})", pid))
    return opts


def render_portfolio(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Portfolio Overview")
    _maybe_demo_help(
        demo_mode,
        "Story: 2 ARTs, 3 portfolio projects, risks manageable, budget used ≈ $444k. "
        "Pick a project and click Next to follow it.",
    )

    opts = _project_options(all_json)
    label_to_id = {label: pid for label, pid in opts}
    cur = st.session_state.get("selected_project", DEFAULT_PROJECT)
    cur_label = next((label for label, pid in opts if pid == cur), (opts[0][0] if opts else ""))
    sel = st.selectbox(
        "Choose a project to follow",
        [label for label, _ in opts],
        index=[label for label, _ in opts].index(cur_label) if opts else 0,
    )
    st.session_state["selected_project"] = label_to_id.get(sel, DEFAULT_PROJECT)
    _set_qp(page="Portfolio", project=st.session_state["selected_project"])

    # Portfolio extras
    projs_all = _flatten_find(all_json, "projects")
    sprints_all = _flatten_find(all_json, "sprints")
    risks_all = _flatten_find(all_json, "risks")
    feats_all = _flatten_find(all_json, "features")

    pid = st.session_state["selected_project"]
    sprints_sel = [s for s in sprints_all if str(s.get("project_id")) == pid]
    proj_sel = [p for p in projs_all if str(p.get("id")) == pid]
    scope_delta = sum(p.get("scope_delta", 0) for p in proj_sel) if proj_sel else 0
    velocity = _compute_velocity(sprints_sel or sprints_all)
    on_time_pct = float(st.session_state.get("kpi_on_time_pct", 50))
    health = _compute_health(projs_all, risks_all, on_time_pct, scope_delta)

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.metric("Velocity (pts)", velocity)
    with c2:
        border = "#16a34a" if health >= 80 else ("#f59e0b" if health >= 60 else "#ef4444")
        st_html(
            f"""
        <div style="
            border:2px solid {border};
            border-radius:12px;padding:8px 12px;line-height:1.2;
        ">
          <div style="font-size:12px;color:#9CA3AF">Health</div>
          <div style="font-size:24px">{health}%</div>
        </div>""",
            height=68,
        )
        st.caption("🟢 ≥80 • 🟠 60–79 • 🔴 <60")
    with c3:
        st.caption("Highlights")
        _chip(f"scope {'↑' if scope_delta > 0 else '↓'}{abs(scope_delta)}%")
        blockers = sum(1 for f in feats_all if f.get("blocked"))
        _chip(f"blockers {blockers}")
        st.markdown("[View blockers →](?page=Sprints)")

    # Data tables
    arts = _flatten_find(all_json, "arts")
    if arts:
        st.subheader("ARTs")
        st.dataframe(arts, use_container_width=True, hide_index=True)
        _download_csv_button("Download ARTs CSV", arts, "arts.csv")

    projs = _flatten_find(all_json, "projects")
    if projs:
        st.subheader("Projects")
        st.dataframe(projs, use_container_width=True, hide_index=True)
        _download_csv_button("Download Projects CSV", projs, "projects.csv")

    risks = _flatten_find(all_json, "risks")
    if risks:
        st.subheader("Risks")
        st.dataframe(risks, use_container_width=True, hide_index=True)
        _download_csv_button("Download Risks CSV", risks, "risks.csv")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Projects", use_container_width=True):
            _goto("Projects")


def _build_workload(features: List[Dict[str, Any]], project_id: str) -> Dict[str, List[Any]]:
    buckets: Dict[str, float] = {}
    for f in features:
        if str(f.get("project_id")) == str(project_id):
            assignee = f.get("assignee", "Unassigned")
            pts = f.get("points", f.get("story_points", 1)) or 0
            try:
                pts = float(pts)
            except Exception:
                pts = 0
            buckets[assignee] = buckets.get(assignee, 0) + pts
    return {"assignee": list(buckets.keys()), "points": list(buckets.values())}


def _recent_activity_for(features: List[Dict[str, Any]], project_id: str, limit: int = 10) -> List[Dict[str, str]]:
    acts = []
    for f in features:
        if str(f.get("project_id")) == str(project_id):
            when = f.get("updated_at") or f.get("created_at") or "—"
            acts.append({"when": str(when), "summary": f"{f.get('key','')} {f.get('title','')}".strip()})
    acts.sort(key=lambda a: a["when"], reverse=True)
    return acts[:limit]


def render_projects(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Projects & Features")
    _maybe_demo_help(demo_mode, "Show per-project health, workload, capacity alerts, and recent activity.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    projs = _flatten_find(all_json, "projects")
    feats = _flatten_find(all_json, "features")

    st.subheader("Project Health")
    for p in projs:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            st.markdown(f"### {p.get('name','Unnamed')} ({p.get('id','')})")
            st.metric("Health %", p.get("health", 72), delta="▲" if p.get("trend", 1) > 0 else "▼")
            mlist = [m.get("name") for m in p.get("milestones", []) if isinstance(m, dict)]
            st.caption("Milestones: " + (", ".join(mlist[:3]) if mlist else "—"))
        with col2:
            st.caption("Workload (pts)")
            data = _build_workload(feats, p.get("id"))
            if data["assignee"]:
                st.bar_chart(data)
                # Capacity overload alerts
                over = []
                for assignee, pts in zip(data["assignee"], data["points"]):
                    cap = _capacity_for(str(assignee))
                    try:
                        if float(pts) > float(cap):
                            over.append((assignee, pts, cap))
                    except Exception:
                        pass
                if over:
                    for name, pts, cap in over:
                        st.markdown(
                            f"<span style='color:#ef4444'>⚠️ {name} over capacity ({pts}/{cap} pts)</span>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("All members within capacity")
            else:
                st.info("No workload data")
        with col3:
            st.caption("Recent Activity")
            for a in _recent_activity_for(feats, p.get("id"), 10):
                st.write(f"- {a['when']} · {a['summary']}")
        st.divider()

    # Selected project backlog table
    sel_feats = [f for f in feats if str(f.get("project_id")) == pid]
    st.subheader(f"Features (Backlog) — Selected Project {pid}")
    if sel_feats:
        st.dataframe(sel_feats, use_container_width=True, hide_index=True)
        _download_csv_button("Download Selected Features CSV", sel_feats, f"features_{pid}.csv")
    else:
        st.write("No features detected for this project.")

    with st.expander("All Projects (reference)", expanded=False):
        if projs:
            st.dataframe(projs, use_container_width=True, hide_index=True)
            _download_csv_button("Download All Projects CSV", projs, "projects.csv")
        else:
            st.write("No project list detected in demo data.")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Sprints", use_container_width=True):
            _goto("Sprints")


def render_sprints(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Sprints")
    _maybe_demo_help(demo_mode, "Burndown + WSJF suggestions; nudges and publishing are simulated via Inbox.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    sprints = _flatten_find(all_json, "sprints")
    feats = _flatten_find(all_json, "features")

    # Burndown (current sprint)
    s_sel = [s for s in sprints if str(s.get("project_id")) == pid]
    current = (s_sel or sprints)[-1] if (s_sel or sprints) else {}
    st.subheader("Burndown")
    bd = _build_burndown_df(current)
    if bd["date"]:
        st.line_chart(bd)
    else:
        st.info("No sprint dates available")

    # WSJF suggestions + inline editors
    st.subheader("AI-Suggested Scope (WSJF)")
    feats_sel = [f for f in feats if (not f.get("done")) and (str(f.get("project_id")) == pid)]
    feats_sorted = sorted(feats_sel, key=_wsjf, reverse=True)[:10]
    for f in feats_sorted:
        st.write(f"• {f.get('title','')}  (WSJF={_wsjf(f):.2f})")

        safe_key = f.get("key") or ("id" + str(abs(hash(f.get("title", "")))))
        cols = st.columns(4)
        bv = cols[0].number_input("BV", min_value=0, value=int(f.get("business_value", 5)), key=f"bv_{safe_key}")
        tc = cols[1].number_input("TC", min_value=0, value=int(f.get("time_criticality", 3)), key=f"tc_{safe_key}")
        rr = cols[2].number_input("RR/OE", min_value=0, value=int(f.get("rr_o_e", 3)), key=f"rr_{safe_key}")
        js = cols[3].number_input(
            "Job Size", min_value=1, value=int(f.get("job_size", f.get("points", 3) or 1)), key=f"js_{safe_key}"
        )
        if st.button("Save WSJF", key=f"save_{safe_key}"):
            _save_feature_fields_by_key(
                safe_key,
                {
                    "business_value": int(bv),
                    "time_criticality": int(tc),
                    "rr_o_e": int(rr),
                    "job_size": int(js),
                },
            )
            st.success("WSJF updated")
            st.rerun()

        # Nudge owner
        fallback_id = "id" + str(abs(hash(f.get("title", ""))))
        btn_key = f"nudge_{f.get('key') or fallback_id}"
        if st.button(f"Nudge owner of {f.get('key','') or 'item'}", key=btn_key):
            _append_inbox(
                {
                    "id": _now_str(),
                    "type": "nudge",
                    "who": f.get("assignee", "unassigned"),
                    "issue": f.get("key", ""),
                    "title": f"Please check {f.get('key','item')}",
                    "project": pid,
                    "state": "open",
                    "ts": _now_str(),
                }
            )
            st.success("Nudge recorded (simulated Slack DM)")

    # Publish sprint summary (simulated)
    if st.button("Publish sprint summary"):
        _append_inbox(
            {
                "id": _now_str(),
                "type": "publish_summary",
                "sprint": current.get("name", "Sprint"),
                "title": f"Sprint summary posted for {current.get('name','Sprint')}",
                "project": pid,
                "state": "sent",
                "ts": _now_str(),
            }
        )
        st.success("Posted to Slack & Confluence (simulated)")

    # Table (for acceptance)
    st.subheader(f"Sprints — Project {pid}")
    if s_sel:
        st.dataframe(s_sel, use_container_width=True, hide_index=True)
        _download_csv_button("Download Sprints CSV", s_sel, f"sprints_{pid}.csv")
    else:
        st.write("No sprints detected for this project.")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Risks", use_container_width=True):
            _goto("Risks")


def render_risks(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Risks")
    _maybe_demo_help(demo_mode, "Auto-detected risks appear first; actions are recorded to overlay.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    risks = _flatten_find(all_json, "risks")
    feats = _flatten_find(all_json, "features")
    sprints = _flatten_find(all_json, "sprints")

    detected = [r for r in _detect_risks_from_features(feats) if str(r.get("project_id")) == pid]
    risks_top = sorted(detected, key=lambda r: r["confidence"], reverse=True)[:3]
    st.subheader("Detected Risks (Top 3)")
    if not risks_top:
        st.success("No risks detected 🎉")
    for r in risks_top:
        st.markdown(f"**{r['title']}** — {r['confidence']}%")
        st.caption(f"Why: {r['why']}")
        st.caption(f"Recommended: {_recommended_action(r['why'])}")
        c1, c2, c3 = st.columns(3)
        if c1.button(f"Reassign {r['key']}", key=f"ra_{r['key']}"):
            _log_risk_action(r, "reassign")
            st.success("Action recorded")
        if c2.button(f"Split {r['key']}", key=f"sp_{r['key']}"):
            _log_risk_action(r, "split")
            st.success("Action recorded")
        if c3.button(f"Add buffer {r['key']}", key=f"ab_{r['key']}"):
            _log_risk_action(r, "add_buffer")
            st.success("Action recorded")

    st.subheader("Risk history")
    hist = _build_risk_history(sprints, feats)
    if hist["sprint"]:
        st.line_chart(hist)
    else:
        st.info("No risk history available")

    # Existing risks table
    st.subheader(f"Risks — Project {pid}")

    def _is_open(r: Dict[str, Any]) -> bool:
        return str(r.get("status", "")).lower() not in {"closed", "resolved", "done"}

    sel = [r for r in risks if str(r.get("project_id")) == pid]
    sel_sorted = sorted(sel, key=lambda r: (not _is_open(r), str(r.get("title", "")).lower()))
    if sel_sorted:
        st.dataframe(sel_sorted, use_container_width=True, hide_index=True)
        _download_csv_button("Download Risks CSV", sel_sorted, f"risks_{pid}.csv")
    else:
        st.write("No risks detected for this project.")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Inbox", use_container_width=True):
            _goto("Inbox")


# ──────────────────────────────
# Inbox helpers & page
# ──────────────────────────────
def _blockers_count(features: List[Dict[str, Any]]) -> int:
    return sum(1 for f in features if f.get("blocked"))


def _iter_inbox(project_name="All", include_dismissed: bool = False) -> List[Dict[str, Any]]:
    data = _load_overlay(INBOX_PATH, [])
    now = dt.datetime.now()
    out = []
    for it in data:
        if not include_dismissed and it.get("deprioritized"):
            continue
        snoozed_until = it.get("snoozed_until")
        if snoozed_until:
            try:
                if now < dt.datetime.fromisoformat(str(snoozed_until)):
                    continue
            except Exception:
                pass
        if project_name != "All" and it.get("project") != project_name:
            continue
        out.append(it)
    out.sort(key=lambda x: x.get("deprioritized", False))  # put dismissed at bottom if included
    return out


def _update_inbox_item(id_ts: str, mutate) -> None:
    data = _load_overlay(INBOX_PATH, [])
    for it in data:
        if it.get("id") == id_ts:
            mutate(it)
            break
    _save_overlay(INBOX_PATH, data)


def _set_state(item: Dict[str, Any], state: str) -> None:
    _update_inbox_item(item["id"], lambda it: it.update({"state": state, "ts": _now_str()}))


def _snooze(item: Dict[str, Any], hours: int = 24) -> None:
    _update_inbox_item(
        item["id"],
        lambda it: it.update({"snoozed_until": (dt.datetime.now() + dt.timedelta(hours=hours)).isoformat()}),
    )


def _add_ask_why(item: Dict[str, Any]) -> None:
    _update_inbox_item(
        item["id"],
        lambda it: it.update(
            {"why_requested_at": _now_str(), "ai_note": "Flagged due to blockers and overdue items (demo)."}
        ),
    )


def _dismiss(item: Dict[str, Any]) -> None:
    _update_inbox_item(item["id"], lambda it: it.update({"deprioritized": True, "ts": _now_str()}))


def render_inbox(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Inbox")
    _maybe_demo_help(demo_mode, "Daily digest + Approve/Review/Snooze/Ask-Why/Dismiss. Nudges & summaries appear here.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    risks_all = _flatten_find(all_json, "risks")
    feats_all = _flatten_find(all_json, "features")

    st.subheader("Daily Digest")
    st.write(f"Open risks: {_open_risks_count(risks_all)} · Blockers: {_blockers_count(feats_all)}")

    pnames = ["All"] + [p.get("id", "") for p in _flatten_find(all_json, "projects")]
    sel = st.selectbox("Filter by project (ID)", pnames, index=(pnames.index(pid) if pid in pnames else 0))
    show_dismissed = st.checkbox("Show dismissed", value=False)

    items = _iter_inbox(sel, include_dismissed=show_dismissed)
    if not items:
        st.info("Inbox is empty")
    for it in items:
        st.write(f"- {it.get('title', it.get('type', 'item'))} · {it.get('state', 'open')}")
        c1, c2, c3, c4, c5 = st.columns(5)
        if c1.button("Approve", key=f"a_{it['id']}"):
            _set_state(it, "approved")
        if c2.button("Review", key=f"r_{it['id']}"):
            _set_state(it, "reviewed")
        if c3.button("Snooze 24h", key=f"s_{it['id']}"):
            _snooze(it, 24)
        if c4.button("Ask Why", key=f"w_{it['id']}"):
            _add_ask_why(it)
        if c5.button("Dismiss", key=f"d_{it['id']}"):
            _dismiss(it)

    if demo_mode:
        st.success("End of guided flow. Use the sidebar to jump anywhere.")


# ──────────────────────────────
# Settings page (mock integrations) & AI Insights
# ──────────────────────────────
def render_settings() -> None:
    st.header("Settings")
    st.caption("Mock integrations for demo. Tokens are stored locally in your overlay folder.")

    data = _load_overlay(
        SETTINGS_PATH,
        {"integrations": {"jira": "", "confluence": "", "slack": ""}, "last_sync": None, "feedback_count": 0},
    )

    cols = st.columns(3)
    for svc, col in zip(["jira", "confluence", "slack"], cols):
        with col:
            token = st.text_input(f"{svc.title()} token", value=data["integrations"].get(svc, ""), type="password")
            ok = bool(token)
            st.markdown("🟢 **Connected**" if ok else "🔴 **Expired/Missing**")
            if st.button(f"Save {svc.title()}", key=f"save_{svc}"):
                data["integrations"][svc] = token
                _save_overlay(SETTINGS_PATH, data)
                st.success(f"{svc.title()} saved")

    st.divider()
    if st.button("Sync Now"):
        data["last_sync"] = _now_str()
        _save_overlay(SETTINGS_PATH, data)
        st.success(f"Synced at {data['last_sync']}")
    st.caption(f"Last Sync: {data.get('last_sync') or '—'} · Next scheduled: +1h (simulated)")


def render_ai_insights() -> None:
    st.header("Adaptive AI Insights (Demo)")
    data = _load_overlay(
        SETTINGS_PATH,
        {"integrations": {"jira": "", "confluence": "", "slack": ""}, "last_sync": None, "feedback_count": 0},
    )
    suggestions = [
        "Shift 3 points from FEI-102 to FEI-108",
        "Split epic EID-200 into 3 stories",
        "Add 2d buffer to Sprint 7 due to holidays",
    ]
    for s in suggestions:
        c1, c2 = st.columns([6, 1])
        c1.write(f"• {s}")
        if c2.button("👍", key=f"up_{hash(s)}"):
            data["feedback_count"] = data.get("feedback_count", 0) + 1
            _save_overlay(SETTINGS_PATH, data)
            st.success("Thanks! We’ll adapt future suggestions.")
    progress = min(100, data.get("feedback_count", 0) * 10)
    st.metric("Learning progress", f"{progress}%")


# ──────────────────────────────
# Main entry
# ──────────────────────────────
def main() -> None:
    # Init from query params
    if "eidon_nav" not in st.session_state:
        qp = _get_qp()
        st.session_state["eidon_nav"] = (qp.get("page", [NAV[0]]) or [NAV[0]])[0]
    if "selected_project" not in st.session_state:
        qp = _get_qp()
        st.session_state["selected_project"] = (qp.get("project", [DEFAULT_PROJECT]) or [DEFAULT_PROJECT])[0]

    _app_header()
    page, demo_mode, reset_clicked = _sidebar_nav()

    # Locate defaults + ensure overlay
    default_dir = _find_default_demo_dir()
    if default_dir is None:
        st.error("Demo data defaults not found (expected under eidon/data/demo).")
        return
    data_dir = _ensure_overlay(default_dir)

    # Handle Reset Seed
    if reset_clicked:
        _reset_overlay(default_dir)
        st.success("Demo data reset. Rerunning…")
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

    # Load data (from overlay)
    all_json = _load_all_json(data_dir)

    # KPIs + exports
    kpis = _compute_kpis(all_json)
    _kpi_row(kpis)
    if kpis.get("on_time") is not None:
        st.session_state["kpi_on_time_pct"] = float(kpis["on_time"])
    _export_bar(kpis, data_dir)
    st.divider()

    # Route
    route = st.session_state.get("eidon_nav", page)
    if route == "Portfolio":
        render_portfolio(all_json, demo_mode)
    elif route == "Projects":
        render_projects(all_json, demo_mode)
    elif route == "Sprints":
        render_sprints(all_json, demo_mode)
    elif route == "Risks":
        render_risks(all_json, demo_mode)
    elif route == "Inbox":
        render_inbox(all_json, demo_mode)
    elif route == "Settings":
        render_settings()
    elif route == "AI Insights":
        render_ai_insights()
    else:
        st.write("Unknown page.")


if __name__ == "__main__":
    main()
