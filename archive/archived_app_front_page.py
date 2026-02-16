# ARCHIVED: Legacy front page (not used by current app variants).
# Pilot UI v1 — scope frozen; see docs/support/scope_statement.md
#
# Required environment variables:
# - SUPABASE_URL
# - SUPABASE_ANON_KEY

import base64
import os
import sys
from typing import Any, Dict, List, Optional

import streamlit as st

from ui_theme import TOKENS, inject_css

# Avoid local ./supabase directory shadowing the supabase client package.
_repo_root = os.path.dirname(__file__)
_cwd = os.getcwd()
for path in ("", _repo_root, _cwd):
    if path in sys.path:
        sys.path.remove(path)
try:
    try:
        from supabase import create_client  # type: ignore
    except ImportError:
        from supabase.client import create_client  # type: ignore
finally:
    for path in (_repo_root, _cwd):
        if path and path not in sys.path:
            sys.path.insert(0, path)


def init_state() -> None:
    defaults = {
        "role": None,
        "selected_resident": None,
        "carer_record_state": "idle",
        "family_record_state": "idle",
        "last_action": None,
        "user": None,
        "access_token": None,
        "family_residents": [],
        "active_file": "family",
        "home_view": "family",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_supabase_client() -> Optional[Any]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_authed_client(token: str) -> Optional[Any]:
    client = get_supabase_client()
    if not client:
        return None
    client.postgrest.auth(token)
    return client


def detect_role(user_id: str, token: str) -> str:
    client = get_authed_client(token)
    if not client:
        return "unknown"

    care_home = (
        client.table("care_home_users")
        .select("care_home_id,active")
        .eq("auth_user_id", user_id)
        .eq("active", True)
        .execute()
    )
    if care_home.data:
        return "care_home"

    family = (
        client.table("family_contacts")
        .select("id,active")
        .eq("auth_user_id", user_id)
        .eq("active", True)
        .execute()
    )
    if family.data:
        return "family"

    return "unknown"


def fetch_care_home_residents(token: str) -> List[Dict[str, str]]:
    client = get_authed_client(token)
    if not client:
        return []
    res = (
        client.table("residents")
        .select("id,preferred_display_name,care_home_reference")
        .eq("active", True)
        .order("preferred_display_name")
        .execute()
    )
    if not res.data:
        return []
    return [
        {
            "id": r["id"],
            "name": r["preferred_display_name"],
            "ref": r["care_home_reference"],
        }
        for r in res.data
    ]


def fetch_family_residents(user_id: str, token: str) -> List[Dict[str, str]]:
    client = get_authed_client(token)
    if not client:
        return []
    fc = (
        client.table("family_contacts")
        .select("id")
        .eq("auth_user_id", user_id)
        .eq("active", True)
        .execute()
    )
    if not fc.data:
        return []
    fc_id = fc.data[0]["id"]
    fca = (
        client.table("family_contact_access")
        .select("resident_id,active")
        .eq("family_contact_id", fc_id)
        .eq("active", True)
        .execute()
    )
    resident_ids = [r["resident_id"] for r in fca.data or []]
    if not resident_ids:
        return []
    res = (
        client.table("residents")
        .select("id,preferred_display_name,care_home_reference,active")
        .in_("id", resident_ids)
        .eq("active", True)
        .execute()
    )
    if not res.data:
        return []
    return [
        {
            "id": r["id"],
            "name": r["preferred_display_name"],
            "ref": r["care_home_reference"],
        }
        for r in res.data
    ]


def global_header() -> None:
    st.markdown(
        """
<div class="ui-header">
  <div class="ui-header__title">voice-message.com</div>
  <div class="ui-header__subtitle">Non-urgent social voice-messages</div>
  <div class="ui-header__subtitle">One-at-a-time</div>
  <div class="ui-header__subtitle">One message replaces the previous one</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="ui-caption">'
        "Messages may be played in shared care-home spaces; avoid anything you would not want others to hear."
        "</div>",
        unsafe_allow_html=True,
    )


def inject_home_tabs_css() -> None:
    logo_path = os.path.join("assets", "voice-message pilot logo.svg")
    logo_data = ""
    try:
        with open(logo_path, "r", encoding="utf-8") as handle:
            logo_svg = handle.read()
        logo_data = base64.b64encode(logo_svg.encode("utf-8")).decode("ascii")
    except OSError:
        logo_data = ""

    logo_css = ""
    if logo_data:
        logo_css = f"""
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button {{
    padding-left: 32px;
    padding-right: 32px;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button::before,
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button::after {{
    content: "";
    position: absolute;
    top: 50%;
    width: 16px;
    height: 16px;
    transform: translateY(-50%);
    background: url("data:image/svg+xml;base64,{logo_data}") no-repeat center;
    background-size: contain;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button::before {{
    left: 8px;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button::after {{
    right: 8px;
  }}
"""
    st.markdown(
        f"""
<style>
  .stApp {{
    background: {TOKENS["primary"]};
  }}
  .main .block-container {{
    padding-top: 0 !important;
  }}

  .vm-header {{
    width: 100vw;
    background: {TOKENS["cream"]};
    padding: 22px 16px;
    border-bottom: 1px solid rgba(31,31,31,0.12);
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
  }}
  .vm-header-inner {{
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .vm-logo {{
    width: 46px;
    height: 46px;
    display: block;
  }}
  .vm-logo svg {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .vm-brand {{
    font-weight: 800;
    color: {TOKENS["text"]};
    font-size: 18px;
  }}

  .vm-wrap {{
    max-width: 680px;
    margin: 0 auto;
    padding: 8px 16px 40px 16px;
  }}

  .vm-hero {{
    margin: 8px 0 10px 0;
    line-height: 0.95;
    font-weight: 900;
    letter-spacing: 0.5px;
    font-size: 52px;
  }}
  .vm-hero span {{
    display: inline-block;
    background: repeating-linear-gradient(
      90deg,
      {TOKENS["accent"]} 0px,
      {TOKENS["accent"]} 6px,
      transparent 6px,
      transparent 12px
    );
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    -webkit-text-stroke: 2px {TOKENS["accent"]};
  }}
  @media (max-width: 480px) {{
    .vm-hero {{ font-size: 36px; }}
  }}


  .vm-tabs {{
    margin-top: 8px;
    margin-bottom: 0px;
  }}

  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] {{
    margin-top: 8px;
    margin-bottom: 0px;
    gap: 12px;
    justify-content: flex-start;
    align-items: flex-end;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] > div {{
    flex: 0 0 240px !important;
    width: 240px !important;
    max-width: 240px !important;
    min-width: 240px !important;
  }}

  .vm-tabstate {{
    display: block;
    height: 0;
  }}

  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] .stButton > button {{
    border: 1px solid rgba(31,31,31,0.14);
    border-bottom: none;
    padding: 0 16px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    font-weight: 900;
    font-size: 16px;
    background: {TOKENS["tab_pale"]} !important;
    color: {TOKENS["inactive_text"]} !important;
    margin-top: 10px !important;
    z-index: 2;
    width: 100%;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
    position: relative;
    box-shadow: none !important;
    outline: none !important;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] .stButton > button:hover {{
    background: {TOKENS["tab_pale"]} !important;
    color: {TOKENS["inactive_text"]} !important;
    border-color: rgba(31,31,31,0.14) !important;
  }}
  .vm-tabs-wrap > div[data-testid="stHorizontalBlock"] .stButton > button:focus {{
    outline: none !important;
    box-shadow: none !important;
  }}

  .vm-tabstate.active + div .stButton > button {{
    background: {TOKENS["cream"]} !important;
    color: {TOKENS["text"]} !important;
    margin-top: 0 !important;
    z-index: 4;
  }}
  .vm-tabstate.active + div .stButton > button:hover {{
    background: {TOKENS["cream"]} !important;
    color: {TOKENS["text"]} !important;
    border-color: rgba(31,31,31,0.14) !important;
  }}

  .vm-tabstate.active + div .stButton > button::after {{
    content: "";
    position: absolute;
    left: -1px;
    right: -1px;
    top: 100%;
    height: 14px;
    background: {TOKENS["cream"]};
    border-left: 1px solid rgba(31,31,31,0.14);
    border-right: 1px solid rgba(31,31,31,0.14);
    z-index: 3;
  }}


  .vm-panel {{
    background: {TOKENS["cream"]};
    border: 1px solid rgba(31,31,31,0.14);
    border-radius: 14px;
    border-top-left-radius: 0px;
    padding: 18px 16px;
    box-shadow: 0 14px 30px rgba(0,0,0,0.12);
    margin-top: -16px;
    min-height: 420px;
  }}
  .vm-panel label {{
    color: {TOKENS["text"]} !important;
  }}
  .vm-panel .stTextInput input {{
    color: {TOKENS["text"]} !important;
  }}

  .vm-copy {{
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 8px;
    color: {TOKENS["text"]};
  }}
  .vm-muted {{
    font-size: 14px;
    color: rgba(31,31,31,0.60);
  }}

  .vm-login-marker + div .stButton > button {{
    width: 100%;
    background: {TOKENS["primary"]} !important;
    color: {TOKENS["cream"]} !important;
    border: 0 !important;
    padding: 14px 18px !important;
    border-radius: 14px !important;
    font-weight: 900 !important;
    margin-top: 14px !important;
  }}
  .vm-login-marker + div .stButton > button:active {{
    background: {TOKENS["cream"]} !important;
    color: {TOKENS["primary"]} !important;
    border: 1px solid {TOKENS["primary"]} !important;
  }}

{logo_css}

</style>
""",
        unsafe_allow_html=True,
    )


def _load_logo_svg() -> str:
    logo_path = os.path.join("assets", "icons", "voice-message pilot logo.svg")
    try:
        with open(logo_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""

def _set_home_view(view: str) -> None:
    st.session_state.home_view = view
    st.session_state.active_file = view


def render_home(active: str) -> None:
    inject_css()
    inject_home_tabs_css()

    logo_svg = _load_logo_svg()
    logo_html = (
        f'<div class="vm-logo">{logo_svg}</div>'
        if logo_svg
        else '<div class="vm-logo" style="border-radius:6px;'
        'background:rgba(31,31,31,0.08);"></div>'
    )
    st.markdown(
        f"""
  <div class="vm-header">
    <div class="vm-header-inner">
      {logo_html}
      <div class="vm-brand">voice-message.com</div>
    </div>
  </div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="vm-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="vm-hero"><span>ONE AT A TIME</span></div>', unsafe_allow_html=True)

    active_index = 1 if active == "family" else 2
    st.markdown(
        f"""
<style>
div[data-testid="stHorizontalBlock"] > div > div.stButton > button {{
  background: {TOKENS["tab_pale"]} !important;
  color: {TOKENS["inactive_text"]} !important;
  border: 1px solid rgba(31,31,31,0.14) !important;
  border-bottom: none !important;
  margin-top: 10px !important;
  height: 48px !important;
  box-shadow: none !important;
  outline: none !important;
}}
div[data-testid="stHorizontalBlock"] > div:nth-child({active_index}) > div.stButton > button {{
  background: {TOKENS["cream"]} !important;
  color: {TOKENS["text"]} !important;
  margin-top: 0 !important;
  position: relative;
  z-index: 4;
}}
div[data-testid="stHorizontalBlock"] > div:nth-child({active_index}) > div.stButton > button::after {{
  content: "";
  position: absolute;
  left: -1px;
  right: -1px;
  top: 100%;
  height: 14px;
  background: {TOKENS["cream"]};
  border-left: 1px solid rgba(31,31,31,0.14);
  border-right: 1px solid rgba(31,31,31,0.14);
  z-index: 3;
}}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="vm-tabs-wrap">', unsafe_allow_html=True)
    tab_cols = st.columns(2, gap="small")
    with tab_cols[0]:
        state_class = "active" if active == "family" else "inactive"
        st.markdown(f'<div class="vm-tabstate {state_class}"></div>', unsafe_allow_html=True)
        st.button(
            "Family & friends",
            key="tab_family",
            on_click=_set_home_view,
            args=("family",),
        )
    with tab_cols[1]:
        state_class = "active" if active == "care" else "inactive"
        st.markdown(f'<div class="vm-tabstate {state_class}"></div>', unsafe_allow_html=True)
        st.button(
            "Care hub",
            key="tab_care",
            on_click=_set_home_view,
            args=("care",),
        )
    st.markdown("</div>", unsafe_allow_html=True)

    panel_copy = (
        "Would you like to send a voice-message?"
        if active == "family"
        else "Care hub login"
    )
    panel_subcopy = (
        "Non-urgent messages, one at a time."
        if active == "family"
        else "For care-home staff."
    )
    st.markdown(
        f"""
  <div class="vm-panel">
    <div class="vm-copy">{panel_copy}</div>
    <div class="vm-muted">{panel_subcopy}</div>
""",
        unsafe_allow_html=True,
    )

    st.text_input("Email", key="home_email")
    st.text_input("Password", type="password", key="home_password")
    st.markdown('<div class="vm-login-marker"></div>', unsafe_allow_html=True)
    if st.button("Log in", key="home_login"):
        st.session_state["role"] = "family" if active == "family" else "care_home"
        st.switch_page(
            "pages/02_Family.py" if active == "family" else "pages/03_Carers.py"
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def home_screen() -> None:
    view = st.session_state.get("home_view", "family")
    if view not in ("family", "care"):
        view = "family"
    st.session_state.home_view = view
    st.session_state.active_file = view
    render_home(view)


def main() -> None:
    st.set_page_config(
        page_title="Care Home Pilot",
        page_icon="🗣️",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    init_state()
    home_screen()


if __name__ == "__main__":
    main()
