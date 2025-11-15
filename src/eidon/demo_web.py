"""
Eidon Demo Web (Phase 5 • Step 5, patched)
- Dark theme (from .streamlit/config.toml)
- SVG-safe logo
- Sidebar: Portfolio → Projects → Sprints → Risks → Inbox
- KPI row (Projects, Open Risks, Budget Used, On-time Delivery)
- Guided 'happy path' (Next buttons, query-param deep links, project persisted)
- Export bar: Print to PDF, KPIs PNG, demo-data.zip, CSV per table
- Editable overlay at ~/.eidon/demo-overlay + working Reset Seed

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

import streamlit as st
from streamlit.components.v1 import html as st_html

# ──────────────────────────────
# Page setup
# ──────────────────────────────
st.set_page_config(page_title="Eidon Demo", page_icon="📊", layout="wide")

NAV = ["Portfolio", "Projects", "Sprints", "Risks", "Inbox"]
DEFAULT_PROJECT = "P-1002"
OVERLAY_DIR = Path.home() / ".eidon" / "demo-overlay"  # editable copies of JSON live here


# ──────────────────────────────
# Query params helpers
# ──────────────────────────────
def _get_qp() -> Dict[str, List[str] | str]:
    try:
        qp = dict(st.query_params)
        return {k: ([v] if isinstance(v, str) else v) for k, v in qp.items()}
    except Exception:
        return st.experimental_get_query_params()


def _set_qp(**kwargs: str) -> None:
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
        return "${:,.2f}".format(float(v))
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

        # Radio has NO key (avoid "cannot modify after instantiated" error)
        page = st.radio(
            "Go to",
            NAV,
            index=NAV.index(current) if current in NAV else 0,
            label_visibility="collapsed",
            help="Pick a section. Use 'Demo Mode' to show helper text and Next buttons."
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
    """
    Ensure ~/.eidon/demo-overlay exists. Seed from packaged defaults if missing.
    Returns overlay path to be used for reading/writing demo data.
    """
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
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()):
                total_spend += float(v)
                found_any = True
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


# ✅ The function that was missing:
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
        help=f"All JSON files under {data_dir}"
    )


# ──────────────────────────────
# Guided pages
# ──────────────────────────────
def _maybe_demo_help(enabled: bool, text: str) -> None:
    if enabled:
        st.info(text, icon="💡")


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
        "Pick a project and click Next to follow it."
    )

    opts = _project_options(all_json)
    label_to_id = {label: pid for label, pid in opts}
    cur = st.session_state.get("selected_project", DEFAULT_PROJECT)
    cur_label = next((label for label, pid in opts if pid == cur), (opts[0][0] if opts else ""))
    sel = st.selectbox("Choose a project to follow", [label for label, _ in opts],
                       index=[label for label, _ in opts].index(cur_label) if opts else 0)
    st.session_state["selected_project"] = label_to_id.get(sel, DEFAULT_PROJECT)
    _set_qp(page="Portfolio", project=st.session_state["selected_project"])

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


def render_projects(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Projects & Features")
    _maybe_demo_help(demo_mode, "Start with the selected project, then show the full backlog.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    projs = _flatten_find(all_json, "projects")
    feats = _flatten_find(all_json, "features")

    sel_proj = [p for p in projs if str(p.get("id")) == pid]
    if sel_proj:
        st.subheader(f"Selected Project: {sel_proj[0].get('name','')} ({pid})")
        st.json(sel_proj[0], expanded=False)

    sel_feats = [f for f in feats if str(f.get("project_id")) == pid]
    st.subheader("Features (Backlog) — Selected Project")
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
    _maybe_demo_help(demo_mode, "On-time KPI = planned vs actual/forecast.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    sprints = _flatten_find(all_json, "sprints")
    sel = [s for s in sprints if str(s.get("project_id")) == pid]

    st.subheader(f"Sprints — Project {pid}")
    if sel:
        st.dataframe(sel, use_container_width=True, hide_index=True)
        _download_csv_button("Download Sprints CSV", sel, f"sprints_{pid}.csv")
    else:
        st.write("No sprints detected for this project.")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Risks", use_container_width=True):
            _goto("Risks")


def render_risks(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Risks")
    _maybe_demo_help(demo_mode, "Lead with open risks & mitigation.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    risks = _flatten_find(all_json, "risks")
    sel = [r for r in risks if str(r.get("project_id")) == pid]

    def _is_open(r: Dict[str, Any]) -> bool:
        return str(r.get("status","")).lower() not in {"closed","resolved","done"}

    sel_sorted = sorted(sel, key=lambda r: (not _is_open(r), str(r.get("title","")).lower()))

    st.subheader(f"Risks — Project {pid}")
    if sel_sorted:
        st.dataframe(sel_sorted, use_container_width=True, hide_index=True)
        _download_csv_button("Download Risks CSV", sel_sorted, f"risks_{pid}.csv")
    else:
        st.write("No risks detected for this project.")

    col_sp, col_btn = st.columns([6, 1])
    with col_btn:
        if st.button("Next → Inbox", use_container_width=True):
            _goto("Inbox")


def render_inbox(all_json: Dict[str, Any], demo_mode: bool) -> None:
    st.header("Inbox")
    _maybe_demo_help(demo_mode, "Close the loop with approvals and alerts.")

    pid = st.session_state.get("selected_project", DEFAULT_PROJECT)
    inbox = all_json.get("inbox")
    rows: List[Dict[str, Any]] = []
    if isinstance(inbox, list) and all(isinstance(x, dict) for x in inbox):
        rows = [x for x in inbox if str(x.get("project_id")) == pid]
    elif isinstance(inbox, dict):
        rows = [inbox] if str(inbox.get("project_id")) == pid else []

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        _download_csv_button("Download Inbox CSV", rows, f"inbox_{pid}.csv")
    else:
        st.write("No inbox items detected for this project.")

    if demo_mode:
        st.success("End of guided flow. Use the sidebar to jump anywhere.")


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
    else:
        st.write("Unknown page.")


if __name__ == "__main__":
    main()
