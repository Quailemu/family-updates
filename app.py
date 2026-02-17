# voice-message.com UI

import os
import base64
import time
import uuid
import secrets
import hashlib
from pathlib import Path

from dotenv import load_dotenv

import streamlit as st
import streamlit.components.v1 as components
from supabase.client import create_client
import pyotp
import qrcode

try:
    from st_audiorec import st_audiorec
except ModuleNotFoundError:  # pragma: no cover - runtime env mismatch
    st_audiorec = None

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

from ui_theme import TOKENS, inject_css

SESSION_TIMEOUT_SECONDS = 1800


def init_state() -> None:
    if "route" not in st.session_state:
        st.session_state.route = "/"


def set_route(route: str) -> None:
    st.session_state.route = route
    if hasattr(st, "query_params"):
        st.query_params["route"] = route
    else:
        st.experimental_set_query_params(route=route)
    st.rerun()

def get_supabase_client() -> tuple[object | None, str | None]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        if load_dotenv is None:
            return None, (
                "Missing SUPABASE_URL or SUPABASE_ANON_KEY. "
                "Install python-dotenv or set env vars in the terminal."
            )
        return None, "Missing SUPABASE_URL or SUPABASE_ANON_KEY."
    return create_client(url, key), None


def get_mapping_status() -> tuple[bool, bool, str | None, dict | None, dict | None]:
    supabase, error = get_supabase_client()
    if error:
        return False, False, error, None, None
    access_token = st.session_state.get("access_token")
    if not access_token:
        return False, False, "No access token in session.", None, None
    try:
        supabase.postgrest.auth(access_token)
        auth_uid = st.session_state.get("auth_uid")
        family_resp = (
            supabase.table("family_contacts")
            .select("id, care_home_id")
            .eq("auth_user_id", auth_uid)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        care_resp = (
            supabase.table("care_home_users")
            .select("id, care_home_id")
            .eq("auth_user_id", auth_uid)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        family_record = family_resp.data[0] if family_resp.data else None
        care_record = care_resp.data[0] if care_resp.data else None
        family_found = family_record is not None
        care_found = care_record is not None
        return family_found, care_found, None, family_record, care_record
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return False, False, str(exc), None, None


def get_authed_supabase(access_token: str | None) -> tuple[object | None, str | None]:
    supabase, error = get_supabase_client()
    if error:
        return None, error
    if not access_token:
        return None, "Missing access token."
    refresh_token = st.session_state.get("refresh_token")
    if refresh_token:
        try:
            supabase.auth.set_session(access_token, refresh_token)
        except Exception:
            pass
    supabase.postgrest.auth(access_token)
    return supabase, None


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_recovery_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        codes.append(secrets.token_hex(4))
    return codes


def get_care_hub_mfa_record(access_token: str | None, auth_uid: str | None) -> dict | None:
    if not auth_uid:
        return None
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        resp = (
            supabase.table("care_hub_mfa")
            .select("auth_user_id, totp_secret, recovery_code_hashes, enabled")
            .eq("auth_user_id", auth_uid)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def upsert_care_hub_mfa(
    access_token: str | None,
    auth_uid: str | None,
    totp_secret: str,
    recovery_code_hashes: list[str],
    enabled: bool,
) -> bool:
    if not auth_uid:
        return False
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False
    payload = {
        "auth_user_id": auth_uid,
        "totp_secret": totp_secret,
        "recovery_code_hashes": recovery_code_hashes,
        "enabled": enabled,
        "updated_at": "now()",
    }
    try:
        supabase.table("care_hub_mfa").upsert(payload).execute()
        return True
    except Exception:
        return False


def update_care_hub_mfa_codes(
    access_token: str | None,
    auth_uid: str | None,
    recovery_code_hashes: list[str],
) -> bool:
    if not auth_uid:
        return False
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False
    try:
        (
            supabase.table("care_hub_mfa")
            .update({"recovery_code_hashes": recovery_code_hashes, "updated_at": "now()"})
            .eq("auth_user_id", auth_uid)
            .execute()
        )
        return True
    except Exception:
        return False

def render_access_gate(message: str, login_route: str, role: str) -> None:
    render_page_header("Family page" if role == "family" else get_care_hub_label())
    st.markdown(
        f"""
<div style="max-width:640px;margin:32px auto;">
  <div style="font-size:18px;font-weight:700;margin-bottom:12px;">{message}</div>
  <div style="color:rgba(31,31,31,0.65);margin-bottom:20px;">
    If you refreshed the page, please sign in again.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    cols = st.columns(3, gap="small")
    with cols[0]:
        if st.button("Go to login", key=f"{role}_gate_login"):
            set_route(login_route)
    with cols[1]:
        back_label = (
            "Back to Family login"
            if role == "family"
            else f"Back to {get_care_hub_label()}"
        )
        if st.button(back_label, key=f"{role}_gate_home"):
            set_route("/family/login" if role == "family" else get_default_route(get_app_variant()))
    with cols[2]:
        if st.session_state.get("auth_uid"):
            if st.button("Sign out", key=f"{role}_gate_sign_out"):
                sign_out_user(role)


def render_wrong_variant(
    detail: str | None = None, expected_variants: list[str] | None = None
) -> None:
    app_variant = get_app_variant()
    variant_label = get_variant_label(app_variant)
    if app_variant == "public":
        render_page_header("Wrong app variant", show_menu=False, show_variant_subheading=False)
        st.markdown("This page belongs to a different app.")
        if st.button("Back to service overview", key="public_wrong_back"):
            set_route("/service-overview")
        if expected_variants:
            for variant in expected_variants:
                url = get_public_app_url(variant)
                label = get_variant_label(variant)
                if url:
                    if hasattr(st, "link_button"):
                        st.link_button(f"Open {label}", url, use_container_width=True)
                    else:
                        st.markdown(
                            f'<a href="{url}" target="_self"><button style="width:100%">Open {label}</button></a>',
                            unsafe_allow_html=True,
                        )
        return
    render_page_header("Wrong app variant")
    st.error("Wrong app variant")
    st.markdown(f"This app is running as **{variant_label}**.")
    if expected_variants:
        expected_labels = [get_variant_label(v) for v in expected_variants]
        expected_text = " or ".join(expected_labels)
        st.markdown(f"Expected: **{expected_text}**.")
    if detail:
        st.markdown(detail)
    if st.button("Go to login", key="wrong_variant_login"):
        set_route(get_default_route(get_app_variant()))


def render_family_info_nav() -> None:
    if get_app_variant() != "family":
        return
    # Info access now lives in the header hamburger menu.
    return


def render_family_info() -> None:
    render_how_it_works_family()


def render_family_introduction() -> None:
    render_how_it_works_family()


def render_family_instructions() -> None:
    render_how_it_works_family()


def render_safeguarding_block() -> None:
    st.markdown("### Safeguarding")
    st.markdown("Safeguarding duties remain with the care home.")
    st.markdown(
        "This service is not a safeguarding system and is not designed to provide alerts, monitoring, or risk detection."
    )


def render_how_it_works_family() -> None:
    render_page_header("How it works — Family")
    st.markdown(
        "Log in using your email access provided by the care home.\n\n"
        "Record and send a short voice message.\n\n"
        "This is not a live service. Messages are played and replies are recorded when staff are available.\n\n"
        "Only the most recent message is kept (one message in, one message out). There is no message history.\n\n"
        "The service is for non-urgent social contact only.\n\n"
        "For care or safeguarding concerns, contact the care home directly. The platform is not monitored in real time."
    )
    st.markdown("Links:")
    link_cols = st.columns(2, gap="small")
    with link_cols[0]:
        if st.button("Terms & conditions", key="family_links_terms"):
            set_route("/family/terms")
    with link_cols[1]:
        if st.button("Contact the care home", key="family_links_contact"):
            set_route("/family/contact")


def render_how_it_works_mobile() -> None:
    render_page_header("How it works — Care Hub – Mobile")
    st.markdown(
        "Only one message is kept between each family member and each resident, in each direction, with no threads."
    )
    st.markdown("An authorised contact is a person approved by the care home to send and receive messages.")
    st.markdown(
        "1. Log in using the shared PIN or password provided by the care home.\n"
        "2. Select a resident from the list.\n"
        "3. Select a family member and play their latest message to the resident.\n"
        "4. If appropriate, assist the resident to send a reply to that family member.\n"
        "5. The next message sent in either direction replaces the previous one."
    )
    st.markdown("Messages are for non-urgent, social contact only. This service is not monitored.")
    render_safeguarding_block()
    if st.button("Back to Care Hub – Mobile", key="mobile_how_it_works_back"):
        set_route("/care-hub/inbox")


def render_how_it_works_office_overview() -> None:
    render_page_header("How it works — Care Hub – Office")
    try:
        content = Path("docs/public/02_how_it_works.md").read_text(encoding="utf-8")
        content = inject_logo_into_markdown(content)
        st.markdown(content)
    except OSError:
        st.error("Document not found.")


def render_how_it_works_office() -> None:
    render_page_header("How it works — Care Hub – Office")
    st.markdown(
        "Only one message is kept between each family member and each resident, in each direction, with no threads."
    )
    st.markdown(
        "1. Log in using the care home’s office credentials.\n"
        "2. View residents and messages for oversight purposes where required.\n"
        "3. Confirm that the system is operating correctly:\n"
        "   - one message per family member → resident\n"
        "   - one message per resident → family member\n"
        "4. Manage documents and compliance."
    )
    st.markdown(
        "Documents available in Care Hub – Office only:\n"
        "- Care home responsibilities\n"
        "- Care home guide\n"
        "- Safeguarding & consent\n"
        "- Care Hub access summary\n"
        "- Care home onboarding script\n"
        "- Handover checklist"
    )
    st.markdown("Messages are for non-urgent, social contact only. This service is not monitored.")
    render_safeguarding_block()


def render_family_document(title: str, path: str) -> None:
    render_page_header(title)
    try:
        content = Path(path).read_text(encoding="utf-8")
        content = inject_logo_into_markdown(content)
    except OSError:
        st.error("Document not found.")
    else:
        st.markdown(content)
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        if st.button("Back", key="family_doc_back"):
            set_route("/how-it-works/family")
    with action_cols[1]:
        if st.button("Back to Family login", key="family_doc_home"):
            set_route("/family/login")
    with action_cols[2]:
        if st.button("Sign out", key="family_doc_sign_out"):
            sign_out_user("family")


def render_family_contact() -> None:
    render_page_header("Contact the care home")
    st.markdown("For access, questions, or support, contact the care home directly.")
    st.markdown(
        "For safeguarding concerns, contact the care home directly; the platform is not monitored in real time."
    )
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        if st.button("Back", key="family_contact_back"):
            set_route("/how-it-works/family")
    with action_cols[1]:
        if st.button("Back to Family login", key="family_contact_home"):
            set_route("/family/login")
    with action_cols[2]:
        if st.button("Sign out", key="family_contact_sign_out"):
            sign_out_user("family")


def render_care_hub_nav() -> None:
    app_variant = get_app_variant()
    if app_variant == "care_hub_mobile":
        nav_cols = st.columns(2, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_nav_inbox", use_container_width=True):
                set_route("/care-hub/inbox")
        with nav_cols[1]:
            if st.button("Sign out", key="care_hub_nav_sign_out", use_container_width=True):
                sign_out_user("care_hub")
    else:
        nav_cols = st.columns(4, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_nav_inbox", use_container_width=True):
                set_route("/care-hub/inbox")
        with nav_cols[1]:
            if st.button("Documents", key="care_hub_nav_docs", use_container_width=True):
                set_route("/docs")
        with nav_cols[2]:
            if st.button("Contracts", key="care_hub_nav_contracts", use_container_width=True):
                set_route("/contracts")
        with nav_cols[3]:
            if st.button("Sign out", key="care_hub_nav_sign_out", use_container_width=True):
                sign_out_user("care_hub")


def render_care_hub_instructions() -> None:
    app_variant = get_app_variant()
    if app_variant == "care_hub_office":
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def render_care_hub_training() -> None:
    app_variant = get_app_variant()
    if app_variant == "care_hub_office":
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def require_family_access() -> None:
    if not st.session_state.get("auth_uid"):
        render_access_gate("Please sign in to access Family.", "/family/login", "family")
        st.stop()
    family_found, care_found, error, family_record, _ = get_mapping_status()
    if family_found:
        if family_record:
            st.session_state["active_role"] = "family"
            st.session_state["active_care_home_id"] = family_record.get("care_home_id")
        return
    if care_found:
        render_wrong_variant("Your login details are for Care Hub.")
        st.stop()
    render_access_gate("Account not set up yet.", "/family/login", "family")
    st.stop()


def require_care_access() -> None:
    if not st.session_state.get("auth_uid"):
        render_access_gate(
            f"Please sign in to access {get_care_hub_label()}.",
            "/care-hub/login",
            "care_hub",
        )
        st.stop()
    family_found, care_found, error, _, care_record = get_mapping_status()
    if care_found:
        if care_record:
            st.session_state["active_role"] = "care_hub"
            st.session_state["active_care_home_id"] = care_record.get("care_home_id")
        if get_app_variant() == "care_hub_office" and is_office_mfa_required():
            if get_route() != "/care-hub/mfa":
                set_route("/care-hub/mfa")
            st.stop()
        return
    if family_found:
        render_wrong_variant("Your login details are for Family.")
        st.stop()
    render_access_gate("Account not set up yet.", "/care-hub/login", "care_hub")
    st.stop()


def is_office_mfa_required() -> bool:
    if get_app_variant() != "care_hub_office":
        return False
    if not st.session_state.get("auth_uid"):
        return False
    if st.session_state.get("mfa_verified"):
        return False
    access_token = st.session_state.get("access_token")
    auth_uid = st.session_state.get("auth_uid")
    record = get_care_hub_mfa_record(access_token, auth_uid)
    return bool(record and record.get("enabled"))


def log_audit_event(
    action: str,
    role: str,
    care_home_id: str | None = None,
    target_id: str | None = None,
) -> None:
    supabase, error = get_supabase_client()
    if error:
        return
    actor_user_id = st.session_state.get("auth_uid")
    if not actor_user_id:
        return
    access_token = st.session_state.get("access_token")
    if access_token:
        supabase.postgrest.auth(access_token)
    payload = {
        "actor_user_id": actor_user_id,
        "actor_role": role,
        "care_home_id": care_home_id,
        "action": action,
        "target_id": target_id,
    }
    try:
        supabase.table("audit_log").insert(payload).execute()
    except Exception:
        return


def clear_session_state() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]



def sign_out_user(role: str | None = None) -> None:
    supabase, error = get_supabase_client()
    if not error:
        try:
            access_token = st.session_state.get("access_token")
            refresh_token = st.session_state.get("refresh_token")
            if access_token and refresh_token:
                supabase.auth.set_session(access_token, refresh_token)
            supabase.auth.sign_out()
        except Exception:
            pass
    if role:
        log_audit_event(
            "logout",
            role,
            st.session_state.get("active_care_home_id"),
        )
    clear_session_state()
    set_route(get_default_route(get_app_variant()))


def enforce_session_timeout() -> None:
    last_active = st.session_state.get("last_active_at")
    now = time.time()
    if last_active and (now - last_active) > SESSION_TIMEOUT_SECONDS:
        role = st.session_state.get("active_role")
        if role:
            log_audit_event(
                "session_timeout",
                role,
                st.session_state.get("active_care_home_id"),
            )
        clear_session_state()
        set_route(get_default_route(get_app_variant()))
        st.stop()
    st.session_state["last_active_at"] = now


def get_linked_residents() -> list[dict]:
    return []


def fetch_family_residents(user_id: str, access_token: str) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    try:
        contact_resp = (
            supabase.table("family_contacts")
            .select("id, display_name")
            .eq("auth_user_id", user_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not contact_resp.data:
            return []
        contact_id = contact_resp.data[0]["id"]
        access_resp = (
            supabase.table("family_contact_access")
            .select(
                "resident_id, residents(id, preferred_display_name, care_home_reference, care_home_id)"
            )
            .eq("family_contact_id", contact_id)
            .eq("active", True)
            .execute()
        )
        residents = []
        for row in access_resp.data or []:
            resident = row.get("residents") or {}
            display_name = resident.get("preferred_display_name", "Resident")
            residents.append(
                {
                    "id": resident.get("id"),
                    "preferred_name": display_name,
                    "surname": "",
                    "room": resident.get("care_home_reference", ""),
                    "care_home_id": resident.get("care_home_id"),
                }
            )
        return residents
    except Exception:
        return []


def fetch_care_home_residents(access_token: str) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    auth_uid = st.session_state.get("auth_uid")
    if not auth_uid:
        return []
    try:
        care_resp = (
            supabase.table("care_home_users")
            .select("care_home_id")
            .eq("auth_user_id", auth_uid)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not care_resp.data:
            return []
        care_home_id = care_resp.data[0]["care_home_id"]
        resident_resp = (
            supabase.table("residents")
            .select("id, preferred_display_name, care_home_reference, care_home_id")
            .eq("care_home_id", care_home_id)
            .eq("active", True)
            .execute()
        )
        residents = []
        for resident in resident_resp.data or []:
            display_name = resident.get("preferred_display_name", "Resident")
            residents.append(
                {
                    "id": resident.get("id"),
                    "preferred_name": display_name,
                    "surname": "",
                    "room": resident.get("care_home_reference", ""),
                    "care_home": "",
                    "care_home_id": resident.get("care_home_id"),
                }
            )
        return residents
    except Exception:
        return []


def fetch_family_contacts_for_resident(
    resident_id: str, access_token: str
) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    try:
        contact_resp = (
            supabase.table("family_contact_access")
            .select(
                "family_contact_id, family_contacts(id, display_name, auth_user_id)"
            )
            .eq("resident_id", resident_id)
            .eq("active", True)
            .execute()
        )
        contacts = []
        for row in contact_resp.data or []:
            contact = row.get("family_contacts") or {}
            if not contact:
                continue
            contacts.append(
                {
                    "id": contact.get("id"),
                    "full_name": contact.get("display_name", "Family contact"),
                    "relationship": "",
                    "auth_user_id": contact.get("auth_user_id"),
                }
            )
        return contacts
    except Exception:
        return []


def fetch_latest_message(
    resident_id: str,
    direction: str,
    access_token: str,
    contact_user_id: str | None = None,
) -> dict | None:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        query = (
            supabase.table("messages")
            .select(
                "id, resident_id, contact_user_id, direction, audio_storage_path, audio_mime_type, audio_bytes, recorded_at"
            )
            .eq("resident_id", resident_id)
            .eq("direction", direction)
            .order("recorded_at", desc=True)
            .limit(1)
        )
        if contact_user_id:
            query = query.eq("contact_user_id", contact_user_id)
        resp = query.execute()
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def decode_audio_payload(message: dict) -> bytes | None:
    if not message:
        return None
    payload = message.get("audio_storage_path")
    if not payload:
        return None
    try:
        return base64.b64decode(payload)
    except Exception:
        return None


def global_header() -> None:
    return None


def load_logo_svg() -> str:
    logo_path = Path(__file__).resolve().parent / "assets" / "voice-message logo speech bubbles.drawio.svg"
    try:
        return logo_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_home_logo_svg() -> str:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo trio.drawio.svg"
    try:
        return logo_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def render_corner_logo() -> None:
    logo_svg = load_home_logo_svg()
    if not logo_svg:
        return
    st.markdown(
        """
<style>
  .vm-corner-logo {
    position: fixed !important;
    top: 12px !important;
    left: 16px !important;
    width: 44px !important;
    height: 44px !important;
    z-index: 99999 !important;
    pointer-events: none !important;
    display: block !important;
    opacity: 1 !important;
    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.25));
  }
  .vm-corner-logo svg {
    width: 100%;
    height: 100%;
    display: block;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="vm-corner-logo">{logo_svg}</div>', unsafe_allow_html=True)


def render_logo_row() -> None:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    if not logo_path.exists():
        st.write("Logo missing")
        return
    try:
        st.image(logo_path.read_bytes(), width=64)
    except OSError:
        st.write("Logo missing")


def get_logo_data_uri() -> str:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    try:
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{logo_b64}"


def inject_logo_into_markdown(content: str) -> str:
    if not content:
        return content
    logo_data = get_logo_data_uri()
    if not logo_data:
        return content.replace("![logo](../../assets/logo.png)", "")
    return content.replace("![logo](../../assets/logo.png)", f"![logo]({logo_data})")


def read_plans_section(heading: str) -> str:
    plans_path = Path(__file__).resolve().parent / "PLANS.md"
    try:
        text = plans_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    block = text[start + len(marker) :]
    next_sep = block.find("\n---")
    if next_sep != -1:
        block = block[:next_sep]
    return block.strip()


def render_header_menu(menu_key: str) -> None:
    app_variant = get_app_variant()
    current_route = st.session_state.get("current_page") or get_route()
    prev_route = st.session_state.get("prev_page") or "/"
    show_back_only = current_route.startswith("/how-it-works/") and prev_route in ("/", "", None)
    with st.popover("≡"):
        if prev_route and prev_route != current_route:
            if st.button("Back", key=f"{menu_key}_back"):
                set_route(prev_route)
                return
        if show_back_only:
            return
        if app_variant == "care_hub_office" and not st.session_state.get("auth_uid"):
            return
        if app_variant == "care_hub_office" and st.session_state.get("auth_uid"):
            if st.button("Inbox", key=f"{menu_key}_inbox"):
                set_route("/care-hub/inbox")
                return
            if st.button("Documents", key=f"{menu_key}_docs"):
                set_route("/docs")
                return
            if st.button("Contracts", key=f"{menu_key}_contracts"):
                set_route("/contracts")
                return
            if st.button("Subscription & Billing", key=f"{menu_key}_billing"):
                set_route("/billing")
                return
            if st.button("Account & Security", key=f"{menu_key}_security"):
                set_route("/care-hub/security")
                return
            if st.button("Sign out", key=f"{menu_key}_office_sign_out"):
                sign_out_user("care_hub")
                return
            return
        if app_variant != "care_hub_office" and app_variant != "care_hub_mobile":
            if st.button("How it works", key=f"{menu_key}_how_it_works"):
                set_route(get_how_it_works_route(app_variant))
                return
        if app_variant != "care_hub_office" and app_variant != "care_hub_mobile":
            if st.button("Public documents", key=f"{menu_key}_public_docs"):
                set_route("/public/service-overview")
                return
        if app_variant == "care_hub_mobile":
            if st.button("How it works", key=f"{menu_key}_mobile_how"):
                set_route(get_how_it_works_route(app_variant))
                return
            if st.button("Public documents", key=f"{menu_key}_mobile_public_docs"):
                set_route("/public/service-overview")
                return
            if st.button(
                "Safeguarding and Consent",
                key=f"{menu_key}_mobile_safeguarding",
            ):
                set_route("/public/safeguarding-and-consent")
                return
            if st.button("Privacy Notice", key=f"{menu_key}_mobile_privacy"):
                set_route("/public/privacy-notice")
                return
            if st.button(
                "Complaints & Concerns",
                key=f"{menu_key}_mobile_complaints",
            ):
                set_route("/public/complaints-and-concerns")
                return
            if st.session_state.get("auth_uid"):
                if st.button("Sign out", key=f"{menu_key}_mobile_sign_out"):
                    sign_out_user("care_hub")
                    return
            return
        if app_variant == "family":
            if st.button("Family page", key=f"{menu_key}_family_page"):
                if st.session_state.get("auth_uid"):
                    set_route("/family/send")
                else:
                    set_route("/family/login")
                return
            if st.button("Family Terms of Use", key=f"{menu_key}_terms_use"):
                set_route("/family/terms-use")
                return
            if st.button("Family Terms Summary", key=f"{menu_key}_terms_summary"):
                set_route("/family/terms-summary")
                return
            if st.button("Contact the care home", key=f"{menu_key}_contact"):
                set_route("/family/contact")
                return
        if st.session_state.get("auth_uid"):
            if st.button("Sign out", key=f"{menu_key}_sign_out"):
                role = "family" if app_variant == "family" else "care_hub"
                sign_out_user(role)


def render_page_header(
    page_title: str,
    brand_title: str | None = None,
    show_variant_subheading: bool = True,
    show_menu: bool = True,
) -> None:
    st.markdown(
        f"""
<style>
  [data-testid="stHeader"] {{
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
  }}
  .vm-header-strip {{
    background: #FFFFFF;
    border-bottom: 1px solid rgba(31,31,31,0.12);
    padding: 6px 0 10px;
  }}
  .vm-header-strip .stMarkdown {{
    margin-bottom: 0 !important;
  }}
  .vm-header-brand {{
    font-size: 28px;
    font-weight: 800;
    line-height: 1.1;
  }}
  .vm-header-title {{
    font-size: 20px;
    font-weight: 700;
    line-height: 1.2;
    color: rgba(31,31,31,0.75);
  }}
  .vm-header-menu button {{
    font-size: 26px !important;
    line-height: 1 !important;
    padding: 0 6px !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="vm-header-strip">', unsafe_allow_html=True)
    cols = st.columns([0.18, 0.72, 0.1], gap="small")
    with cols[0]:
        render_logo_row()
    with cols[1]:
        app_variant = get_app_variant()
        if app_variant in ("care_hub_mobile", "family"):
            show_variant_subheading = False
        variant_label = get_variant_label(app_variant)
        if variant_label and not variant_label.endswith("app"):
            variant_label = f"{variant_label} app"
        variant_line = (
            f'<div class="vm-header-title">{variant_label}</div>'
            if show_variant_subheading and variant_label
            else ""
        )
        if brand_title:
            st.markdown(
                f"""
<div class="vm-header-brand">{brand_title}</div>
<div class="vm-header-title">{page_title}</div>
{variant_line}
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="vm-header-brand">{page_title}</div>{variant_line}',
                unsafe_allow_html=True,
            )
    with cols[2]:
        if show_menu:
            st.markdown('<div class="vm-header-menu">', unsafe_allow_html=True)
            menu_key = page_title.lower().replace(" ", "_")
            render_header_menu(menu_key)
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_front_page_descriptor() -> None:
    st.markdown(
        "voice-message.com — for non-urgent social voice messages.  \n"
        "One message kept at a time in each direction, with no threads.\n\n"
        "Only one message is kept between each family member and each resident, in each direction.  \n"
        "Each new message deletes the previous message, to keep communication simple and up to date."
    )


def render_how_it_works_general() -> None:
    st.markdown(
        "Only one message is kept between each family member and each resident, in each direction, with no threads.  \n"
        "Each new message deletes the previous message.\n\n"
        "Messages are not private within the care home.  \n"
        "Care staff and office staff may read messages where required.  \n"
        "Security is in place to prevent access by members of the public."
    )


def render_how_it_works_button(button_key: str) -> None:
    if st.button("How it works", key=button_key):
        set_route(get_how_it_works_route(get_app_variant()))


def render_small_corner_logo() -> None:
    logo_svg = load_logo_svg()
    if not logo_svg:
        return
    st.markdown(
        f"""
<style>
  .vm-corner-logo {{
    position: fixed !important;
    top: 12px !important;
    left: 16px !important;
    width: 24px;
    height: 24px;
    z-index: 200000 !important;
    pointer-events: none !important;
    display: block !important;
    opacity: 1 !important;
    filter: drop-shadow(0 1px 2px rgba(0,0,0,0.25));
  }}
  .vm-corner-logo svg {{
    width: 100%;
    height: 100%;
    display: block;
  }}
</style>
<div class="vm-corner-logo">{logo_svg}</div>
""",
        unsafe_allow_html=True,
    )


def render_action_row(actions: list[tuple[str, str]]) -> None:
    if not actions:
        return
    cols = st.columns(len(actions), gap="small")
    for col, (label, key) in zip(cols, actions):
        with col:
            if st.button(label, key=key, use_container_width=True):
                if (
                    st.session_state.get("rec_state") == "recording"
                    and key.startswith("family_send")
                    and (key.endswith("_back") or key.endswith("_home") or key.endswith("_sign_out"))
                ):
                    st.warning("Stop recording to leave this page.")
                    return
                if key == "care_inbox_back":
                    set_route("/care-hub/login")
                    return
                if key.endswith("_home"):
                    if key.startswith("family_"):
                        if st.session_state.get("auth_uid"):
                            set_route("/family/send")
                        else:
                            st.session_state["force_family_login"] = True
                            set_route("/family/login")
                    else:
                        set_route(get_default_route(get_app_variant()))
                elif key.endswith("_back"):
                    if "family_send" in key:
                        set_route("/family/login")
                    elif "family_sent" in key:
                        set_route("/family/send")
                    elif "family_login" in key:
                        set_route(get_default_route(get_app_variant()))
                    elif "care_login" in key:
                        set_route(get_default_route(get_app_variant()))
                    elif "care_inbox" in key:
                        set_route("/care-hub/login")
                    elif "care_play" in key:
                        set_route("/care-hub/inbox")
                elif key.endswith("_sign_out"):
                    role = "family" if "family" in key else "care_hub"
                    sign_out_user(role)


def load_grandmother_svg() -> str:
    image_path = os.path.join("assets", "grandmother-9689448.svg")
    try:
        with open(image_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def load_family_login_svg() -> str:
    image_path = os.path.join("assets", "Active elderly people-rafiki (1).svg")
    try:
        with open(image_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def load_grandmother_alt_svg() -> str:
    image_path = os.path.join("assets", "grandmother-9701879.svg")
    try:
        with open(image_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def load_care_hub_svg() -> str:
    image_path = os.path.join("assets", "icons", "Active elderly people-cuate (2).svg")
    try:
        with open(image_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def render_right_image(
    path: str,
    height_px: int = 300,
    top_percent: int = 60,
    right_px: int = 30,
    shift_x_percent: int = 0,
    z_index: int = 1,
    shift_y_px: int = 0,
    shift_y_percent: int = 0,
    css_class: str = "",
) -> None:
    x_shift = f" translateX({shift_x_percent}%)" if shift_x_percent else ""
    y_shift = f" translateY({shift_y_px}px)" if shift_y_px else ""
    y_percent_shift = (
        f" translateY({shift_y_percent}%)" if shift_y_percent else ""
    )
    class_attr = f' class="{css_class}"' if css_class else ""
    wrapper_style = (
        "position:fixed;"
        f"right:{right_px}px;"
        f"top:{top_percent}%;"
        f"transform:translateY(-50%){x_shift}{y_shift}{y_percent_shift};"
        f"height:{height_px}px;width:auto;z-index:{z_index};pointer-events:none;"
    )
    if path.lower().endswith(".svg"):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                svg = handle.read()
        except OSError:
            return
        if "<svg" in svg:
            svg = svg.replace("<svg", f'<svg{class_attr} style="{wrapper_style}"', 1)
        st.markdown(svg, unsafe_allow_html=True)
        return
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gif":
        mime = "image/gif"
    elif ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    st.markdown(
        f'<img{class_attr} src="data:{mime};base64,{b64}" style="{wrapper_style}" alt="image"/>',
        unsafe_allow_html=True,
    )


def inject_home_css() -> None:
    hover_color = "#E3AFC0"
    st.markdown(
        f"""
<style>
  [data-testid="stSidebar"], [data-testid="stSidebarNav"] {{
    display: none !important;
  }}
  [data-testid="stToolbar"] {{
    display: none !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
  }}

  .stApp {{
    background: #FFFFFF;
  }}
  .main .block-container {{
    padding-top: 0 !important;
  }}
  .vm-stage {{
    position: relative;
    z-index: 2;
  }}
  .vm-right-graphic {{
    position: fixed;
    left: auto;
    right: 30px;
    top: 60%;
    transform: translateY(-50%);
    height: 360px;
    width: auto;
    z-index: 1;
    pointer-events: none;
  }}
  .vm-right-graphic svg {{
    height: 100%;
    width: auto;
    display: block;
  }}
  .vm-right-graphic svg [fill="#d25c5c"],
  .vm-right-graphic svg [fill="#c83737"] {{
    fill: #B1005F;
  }}

  .vm-header {{
    width: 100vw;
    height: 46px;
    background: #FFFFFF;
    border-bottom: 1px solid rgba(31,31,31,0.12);
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
    margin-top: -23px;
    display: flex;
    align-items: center;
  }}
  .vm-header-inner {{
    max-width: 900px;
    width: 100%;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    position: relative;
  }}
  .vm-brand-group {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .vm-logo {{
    width: 96px;
    height: 96px;
    display: block;
    margin-top: -10px;
  }}
  .vm-logo-fallback {{
    background: rgba(31,31,31,0.08);
    border-radius: 6px;
  }}
  .vm-logo-missing {{
    font-size: 12px;
    color: rgba(31,31,31,0.45);
  }}
  .vm-logo svg {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .vm-brand {{
    font-weight: 800;
    color: {TOKENS["text"]};
    font-size: 20px;
  }}
  .vm-header-inner::after {{
    content: "";
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 36px;
    height: 18px;
    background: linear-gradient(
      to bottom,
      {TOKENS["text"]} 0 3px,
      transparent 3px 7px,
      {TOKENS["text"]} 7px 10px,
      transparent 10px 14px,
      {TOKENS["text"]} 14px 17px
    );
    border-radius: 2px;
  }}

  .vm-wrap {{
    max-width: 680px;
    margin: 0 auto;
    padding: 0 16px 40px 16px;
  }}

  .vm-hero {{
    margin-top: 0.6vh;
    margin-bottom: 18px;
    line-height: 0.95;
    font-weight: 900;
    letter-spacing: 0.5px;
    font-size: 68px;
    text-align: left;
  }}
  .vm-hero-banner {{
    display: inline-block;
    background: transparent;
    padding: 8px 12px;
    border-radius: 10px;
    margin-left: 350px;
    transform: translateX(-50%);
    white-space: nowrap;
  }}
  .vm-hero span {{
    display: inline-block;
    color: #99FFFF;
  }}
  @media (max-width: 480px) {{
    .vm-hero {{ font-size: 36px; }}
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] {{
    margin-top: -20px;
    margin-bottom: 0px;
    gap: 12px;
    justify-content: flex-start;
    align-items: flex-end;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] > div {{
    flex: 0 0 260px !important;
    width: 260px !important;
    max-width: 260px !important;
    min-width: 260px !important;
  }}

  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] .stButton > button {{
    width: 100%;
    height: 48px;
    border: 1px solid rgba(31,31,31,0.14) !important;
    border-bottom: none !important;
    border-top-left-radius: 12px !important;
    border-top-right-radius: 12px !important;
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
    font-weight: 900 !important;
    font-size: 16px !important;
    box-shadow: 0 0 0 2px {TOKENS["accent"]} !important;
    outline: none !important;
    padding: 0 16px !important;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] .stButton > button:hover {{
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] .stButton > button:focus {{
    outline: none !important;
    box-shadow: none !important;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button {{
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
    box-shadow: 0 0 0 2px {TOKENS["accent"]} !important;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button:hover {{
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] button:hover {{
    background: #4FB7C2 !important;
    color: {TOKENS["text"]} !important;
  }}

  .vm-panel {{
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
    box-shadow: none;
    margin-top: 0;
    min-height: auto;
  }}

  .vm-copy {{
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 8px;
    color: {TOKENS["text"]};
    text-align: center;
  }}
  .vm-muted {{
    font-size: 14px;
    color: rgba(31,31,31,0.60);
    text-align: center;
    margin-bottom: 10px;
  }}
  .vm-forgot {{
    color: {TOKENS["cream"]};
    font-size: 0.9rem;
    margin-top: 8px;
    text-align: right;
  }}

  .vm-panel label {{
    color: {TOKENS["cream"]} !important;
  }}
  .vm-panel .stTextInput input {{
    color: {TOKENS["text"]} !important;
    border: 1px solid #4FB7C2 !important;
    border-radius: 8px !important;
  }}
  .vm-panel .stTextInput input::placeholder {{
    color: {TOKENS["text"]} !important;
    opacity: 0.75;
  }}
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] button:hover,
  #vm-tabs-marker + div[data-testid="stHorizontalBlock"] button:focus-visible {{
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
  }}

</style>
""",
        unsafe_allow_html=True,
    )


def inject_login_css() -> None:
    st.markdown(
        f"""
<style>
  [data-testid="stSidebar"], [data-testid="stSidebarNav"] {{
    display: none !important;
  }}
  [data-testid="stToolbar"] {{
    display: none !important;
  }}
  .vm-login {{
    max-width: 520px;
    margin: 0 auto;
  }}
  .vm-login .stTextInput input {{
    background: {TOKENS["primary"]} !important;
    color: {TOKENS["cream"]} !important;
    border: 1px solid rgba(31,31,31,0.2) !important;
    border-radius: 10px !important;
  }}
  .vm-login .stTextInput input::placeholder {{
    color: rgba(254,255,246,0.85) !important;
  }}
  .vm-login label {{
    color: {TOKENS["cream"]} !important;
  }}
  .vm-login .stButton > button {{
    background: #4FB7C2 !important;
    color: {TOKENS["cream"]} !important;
    border: 2px solid {TOKENS["accent"]} !important;
    border-radius: 12px !important;
    font-weight: 800 !important;
  }}
  #vm-login-actions + div[data-testid="stHorizontalBlock"] .stButton > button {{
    white-space: nowrap !important;
  }}
  .vm-right-graphic {{
    position: fixed;
    right: 24px;
    top: 60%;
    transform: translateY(-50%);
    height: 300px;
    width: auto;
    z-index: 1;
    pointer-events: none;
  }}
  .vm-right-graphic svg {{
    height: 100%;
    width: auto;
    display: block;
  }}
</style>
""",
        unsafe_allow_html=True,
    )


def render_home(active: str) -> None:
    inject_css()
    inject_home_css()

    if get_app_variant() == "public":
        st.markdown(
            """
            <style>
            /* Make Streamlit chrome blend into the page */
            [data-testid="stHeader"] {
              background: #ffffff !important;
              box-shadow: none !important;
              border-bottom: none !important;
            }
            [data-testid="stToolbar"] {
              background: transparent !important;
            }
            [data-testid="stDecoration"] {
              background: #ffffff !important;
              display: none !important; /* remove the thin coloured/blank bar */
            }
            /* Remove extra top padding that can create a “second bar” look */
            div.block-container {
              padding-top: 1rem !important;
            }
            /* Some Streamlit versions use this container name */
            .stMainBlockContainer {
              padding-top: 1rem !important;
            }
            .public-root {
                background: #FFFFFF;
                color: #2B2B2B;
            }
            #MainMenu {
                display: none !important;
            }
            .public-wrap {
                max-width: 980px;
                margin: 0 auto;
                padding: 0 22px 40px;
            }
            .public-header {
                display: flex;
                align-items: center;
                gap: 14px;
                background: #FFFFFF;
                padding: 10px 22px;
                border-radius: 0;
                margin: 0 -22px;
                border-bottom: 1px solid rgba(31,31,31,0.08);
            }
            .public-header-title {
                font-size: 24px;
                font-weight: 700;
                color: #708090;
            }
            .public-hero {
                padding: 22px 6px 8px;
            }
            .public-hero h1 {
                font-size: 38px;
                font-weight: 800;
                margin: 0 0 6px;
            }
            .hero-headline {
                color: #708090 !important;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }
            .public-hero p {
                margin: 6px 0 0;
                color: #4B5563;
                font-size: 1.05rem;
            }
            .public-grid {
                display: grid;
                gap: 14px;
            }
            .public-grid-3 {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .public-card {
                border-radius: 12px;
                padding: 14px 16px;
                border: 2px solid #C8E2EA;
                background: #F7FBFE;
            }
            .public-card.pink {
                background: #FBEFF3;
            }
            .public-card h3 {
                margin: 0 0 6px;
                font-size: 1.05rem;
            }
            .public-section {
                margin-top: 18px;
            }
            .public-section h2 {
                font-size: 1.2rem;
                margin: 0 0 10px;
            }
            .public-steps {
                display: grid;
                gap: 8px;
            }
            .public-step {
                padding: 10px 12px;
                border-radius: 10px;
                border: 2px solid #C8E2EA;
                background: #F9F4EC;
            }
            .public-roles {
                display: grid;
                gap: 12px;
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .public-footer {
                margin-top: 22px;
                color: #6B7280;
                font-size: 0.95rem;
            }
            .public-footer a {
                color: #6B7280;
                text-decoration: none;
            }
            @media (max-width: 900px) {
                .public-grid-3,
                .public-roles {
                    grid-template-columns: 1fr;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            .hero-headline {
              color: #708090 !important;
              font-weight: 600;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="public-root"><div class="public-wrap">', unsafe_allow_html=True)
        logo_data = get_logo_data_uri()
        if logo_data:
            header_html = (
                f'<div class="public-header">'
                f'<img src="{logo_data}" alt="logo" style="height:32px;width:auto;display:block;" />'
                f'<div class="public-header-title">voice-message.com</div>'
                f"</div>"
            )
        else:
            header_html = (
                '<div class="public-header">'
                '<div class="public-header-title">voice-message.com</div>'
                "</div>"
            )
        st.markdown(header_html, unsafe_allow_html=True)

        st.markdown('<div class="public-hero">', unsafe_allow_html=True)
        st.markdown(
            """
            <h1 class="hero-headline">
            One message in. One message out.
            </h1>
            <p>Simple voice messages between families and residents in care homes.</p>
            <p>A calm way to stay connected — without pressure or urgency.</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-grid public-grid-3">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-card">
              <h3>One message only</h3>
              <div>Only the latest message and reply are kept.</div>
            </div>
            <div class="public-card pink">
              <h3>Not live</h3>
              <div>Messages are played and recorded when staff are available.</div>
            </div>
            <div class="public-card">
              <h3>Not for care updates</h3>
              <div>For non-urgent social contact only.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>How it works</h2>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-steps">
              <div class="public-step">1) Family records a short voice message.</div>
              <div class="public-step">2) Staff play the message when convenient.</div>
              <div class="public-step">3) A reply is recorded with staff support.</div>
              <div class="public-step">4) The new message replaces the previous one.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>Roles</h2>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-roles">
              <div class="public-card">
                <h3>Family</h3>
                <div>Authorised contacts record and send messages.</div>
              </div>
              <div class="public-card pink">
                <h3>Care Hub – Mobile</h3>
                <div>Staff support playback and recording on site.</div>
              </div>
              <div class="public-card">
                <h3>Care Hub – Office</h3>
                <div>Oversight, access management, and governance.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-card">
              <h3>Contact</h3>
              <div>For information about voice-message.com, email
              <a href="mailto:support@voice-message.com">support@voice-message.com</a>.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="public-footer">
              <a href="?route=/public/privacy-notice">Privacy Notice</a> ·
              <a href="?route=/public/safeguarding-and-consent">Safeguarding &amp; Consent</a> ·
              <a href="?route=/public/complaints-and-concerns">Complaints &amp; Concerns</a> ·
              <a href="?route=/public/family-terms-of-use">Family Terms</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    st.markdown('<div class="vm-wrap vm-stage">', unsafe_allow_html=True)
    st.markdown("### Service overview")
    st.markdown(
        "voice-message.com  \n"
        "One message in. One message out.  \n"
        "No threads. No pressure.\n\n"
        "Only the most recent message from a family member and the most recent reply from the resident are kept.  \n"
        "When a new message is sent, the previous message from that sender is replaced.  \n"
        "This structure helps keep communication simple and manageable within care settings.\n\n"
        "This is not a live service. Messages are played and replies are recorded when staff are available, to fit around care routines."
    )

    button_cols = st.columns(3, gap="small")
    if get_app_variant() == "public":
        render_public_app_buttons(button_cols)
    else:
        with button_cols[0]:
            if st.button("Family", key="tab_family", use_container_width=True):
                set_route("/family/login")
        with button_cols[1]:
            if st.button("Care Hub – Mobile", key="tab_care_mobile", use_container_width=True):
                set_route("/care-hub/login")
        with button_cols[2]:
            if st.button("Care Hub – Office", key="tab_care_office", use_container_width=True):
                set_route("/care-hub/login")

    # Homepage buttons are handled above (Family / Care Hub – Mobile / Care Hub – Office).

    st.markdown('<div style="margin-top:-8px;"></div>', unsafe_allow_html=True)


def get_route() -> str:
    if hasattr(st, "query_params"):
        route = st.query_params.get("route", "")
    else:
        route = st.experimental_get_query_params().get("route", [""])[0]
    if isinstance(route, list):
        route = route[0] if route else ""
    return route or st.session_state.get("route", "/")


VARIANT_FAMILY = "family"
VARIANT_MOBILE = "care_hub_mobile"
VARIANT_OFFICE = "care_hub_office"
VARIANT_PUBLIC = "public"

VARIANT_CONFIG = {
    VARIANT_FAMILY: {
        "label": "Family app",
        "default_route": "/family/login",
        "how_it_works_route": "/family/how-it-works",
        "allowed_routes": {
            "/family/login",
            "/family/send",
            "/family/sent",
            "/family/privacy",
            "/family/terms",
            "/family/terms-use",
            "/family/terms-summary",
            "/family/contact",
            "/how-it-works/family",
            "/family/how-it-works",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/family-terms-summary",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_MOBILE: {
        "label": "Care Hub – Mobile",
        "default_route": "/care-hub/login",
        "how_it_works_route": "/care-hub-mobile/how-it-works",
        "allowed_routes": {
            "/care-hub/login",
            "/care-hub/inbox",
            "/care-hub/instructions",
            "/care-hub/training",
            "/how-it-works/mobile",
            "/care-hub-mobile/how-it-works",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/family-terms-summary",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_OFFICE: {
        "label": "Care Hub – Office",
        "default_route": "/care-hub/login",
        "how_it_works_route": "/care-hub-office/how-it-works",
        "allowed_routes": {
            "/care-hub/login",
            "/care-hub/inbox",
            "/care-hub/instructions",
            "/care-hub/training",
            "/care-hub/security",
            "/care-hub/mfa",
            "/how-it-works/office",
            "/care-hub-office/how-it-works",
            "/docs",
            "/contracts",
            "/billing",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/family-terms-summary",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_PUBLIC: {
        "label": "Public",
        "default_route": "/service-overview",
        "how_it_works_route": "/service-overview",
        "allowed_routes": {
            "/pr-home",
            "/service-overview",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/family-terms-summary",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
        },
    },
}


def get_app_variant() -> str:
    raw = __import__("os").getenv("APP_VARIANT", "")
    value = raw.strip().lower()
    if not value:
        return VARIANT_PUBLIC
    if value == "family":
        return VARIANT_FAMILY
    if value in ("mobile", "care_hub_mobile"):
        return VARIANT_MOBILE
    if value in ("office", "care_hub_office"):
        return VARIANT_OFFICE
    if value == "public":
        return VARIANT_PUBLIC
    return ""


def get_raw_app_variant() -> str:
    return __import__("os").getenv("APP_VARIANT", "").strip()


def get_variant_label(app_variant: str) -> str:
    return VARIANT_CONFIG.get(app_variant, {}).get("label", "Unknown")


def get_default_route(app_variant: str) -> str:
    return VARIANT_CONFIG.get(app_variant, {}).get("default_route", "/")


def get_public_app_url(variant: str) -> str:
    if variant == VARIANT_FAMILY:
        return os.getenv("FAMILY_APP_URL", "").strip()
    if variant == VARIANT_MOBILE:
        return os.getenv("CARE_MOBILE_APP_URL", "").strip()
    if variant == VARIANT_OFFICE:
        return os.getenv("CARE_OFFICE_APP_URL", "").strip()
    return ""


def render_public_app_buttons(cols: list) -> None:
    entries = [
        (VARIANT_FAMILY, "Family"),
        (VARIANT_MOBILE, "Care Hub – Mobile"),
        (VARIANT_OFFICE, "Care Hub – Office"),
    ]
    for idx, (variant, label) in enumerate(entries):
        url = get_public_app_url(variant)
        with cols[idx]:
            if url:
                if hasattr(st, "link_button"):
                    st.link_button(label, url, use_container_width=True)
                else:
                    st.markdown(
                        f'<a href="{url}" target="_self"><button style="width:100%">{label}</button></a>',
                        unsafe_allow_html=True,
                    )
            else:
                st.button(label, key=f"public_{variant}_disabled", disabled=True, use_container_width=True)
                st.caption(
                    f"This opens the {label} app (separate URL). Not configured in this environment."
                )


def get_how_it_works_route(app_variant: str) -> str:
    return VARIANT_CONFIG.get(app_variant, {}).get("how_it_works_route", "/")


def is_route_allowed(app_variant: str, route: str) -> bool:
    allowed = VARIANT_CONFIG.get(app_variant, {}).get("allowed_routes", set())
    return route in allowed


def get_expected_variants_for_route(route: str) -> list[str]:
    expected = []
    for variant, config in VARIANT_CONFIG.items():
        if route in config.get("allowed_routes", set()):
            expected.append(variant)
    return expected


def get_care_hub_label() -> str:
    app_variant = get_app_variant()
    if app_variant == "care_hub_mobile":
        return "Care Hub – Mobile"
    if app_variant == "care_hub_office":
        return "Care Hub – Office"
    return "Care Hub"


def render_family_login() -> None:
    inject_login_css()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  a[download], button[title="Download"] {{
    display: none !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header(
        "Family login",
        brand_title="voice-message.com",
        show_variant_subheading=False,
    )
    st.markdown("Non-urgent social voice messages. Not a live service.")
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)
    force_login = st.session_state.pop("force_family_login", False)
    if st.session_state.get("auth_uid") and not force_login:
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if family_found:
            if family_record:
                st.session_state["active_role"] = "family"
                st.session_state["active_care_home_id"] = family_record.get("care_home_id")
            set_route("/family/send")
        elif care_found:
            st.error("Wrong app variant")
            st.info("Your login details are for Care Hub.")
            if st.button("Log out", key="family_login_wrong_logout"):
                sign_out_user("family")
        else:
            st.error("Account not set up yet.")
        return

    email = st.text_input("Email", key="family_login_email")
    password = st.text_input("Password", type="password", key="family_login_password")
    st.markdown('<div id="vm-login-actions"></div>', unsafe_allow_html=True)
    action_cols = st.columns(2, gap="small")
    with action_cols[0]:
        submit_login = st.button("Log in", key="family_login_submit")
    with action_cols[1]:
        forgot_pressed = st.button("Forgot?", key="family_login_forgot")
    sign_out_pressed = False
    if st.session_state.get("auth_uid"):
        if st.button("Sign out", key="family_login_sign_out"):
            sign_out_pressed = True
    back_pressed = False

    if submit_login:
        supabase, error = get_supabase_client()
        if error:
            st.error(error)
        else:
            try:
                auth = supabase.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                st.error(str(exc))
            else:
                if not auth or not auth.user:
                    st.error("Invalid login.")
                else:
                    st.session_state["auth_uid"] = auth.user.id
                    st.session_state["access_token"] = auth.session.access_token
                    st.session_state["refresh_token"] = auth.session.refresh_token
                    st.session_state["auth_email"] = email.strip()
                    if email and "@" in email:
                        st.session_state["family_display_name"] = (
                            email.split("@", 1)[0].strip() or "Family member"
                        )
                    else:
                        st.session_state["family_display_name"] = "Family member"
                    family_found, care_found, mapping_error, family_record, care_record = (
                        get_mapping_status()
                    )
                    if family_found:
                        if family_record:
                            st.session_state["active_role"] = "family"
                            st.session_state["active_care_home_id"] = family_record.get(
                                "care_home_id"
                            )
                        residents = get_linked_residents()
                        st.session_state["linked_residents"] = residents
                        if len(residents) == 1:
                            st.session_state["selected_resident_id"] = residents[0]["id"]
                        else:
                            st.session_state["selected_resident_id"] = None
                        log_audit_event(
                            "login_success",
                            "family",
                            st.session_state.get("active_care_home_id"),
                        )
                        set_route("/family/send")
                    elif care_found:
                        st.error("Wrong app variant")
                        st.info("Your login details are for Care Hub.")
                        if st.button("Log out", key="family_login_wrong_logout_after"):
                            sign_out_user("family")
                    else:
                        st.error("Account not set up yet.")

    if sign_out_pressed:
        sign_out_user("family")
    if forgot_pressed:
        st.info("Password reset is not available yet. Please contact support.")


def render_family_send() -> None:
    require_family_access()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  a[download], button[title="Download"], [data-testid="stDownloadButton"] {{
    display: none !important;
  }}
  .vm-resident-card {{
    border: 1px solid rgba(31,31,31,0.12);
    border-radius: 12px;
    padding: 12px;
    margin: 12px 0;
    background: {TOKENS["cream"]};
  }}
  .vm-section-title {{
    font-weight: 700;
    margin: 8px 0 4px;
  }}
  .vm-muted-line {{
    color: rgba(31,31,31,0.6);
    font-size: 0.9rem;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header("Family page")
    render_front_page_descriptor()
    render_how_it_works_button("family_send_how_it_works")
    family_display_name = st.session_state.get("family_display_name", "Family member")
    st.markdown(f"**Hello {family_display_name}**")
    st.markdown(
        "**Messages are for non-urgent, social contact only. This is not a messaging service to carers or the care home.**"
    )

    access_token = st.session_state.get("access_token")
    residents = fetch_family_residents(
        st.session_state.get("auth_uid", ""), access_token
    )

    search_value = st.text_input("Search residents", key="family_resident_search")
    if search_value:
        search_lower = search_value.strip().lower()
        residents = [
            resident
            for resident in residents
            if search_lower in resident["preferred_name"].lower()
            or search_lower in resident["surname"].lower()
            or (resident.get("room") and search_lower in resident["room"])
        ]

    if not residents:
        if search_value:
            st.info("No residents match that search.")
        return

    send_state = st.session_state.setdefault("family_send_state", {})
    active_rec_id = st.session_state.get("family_active_rec_resident")
    manual_active = st.session_state.get("family_active_rec_manual", False)
    resident_ids = {resident["id"] for resident in residents}

    if len(residents) == 1:
        only_id = residents[0]["id"]
        if active_rec_id != only_id:
            if active_rec_id and active_rec_id in send_state:
                send_state[active_rec_id]["recording_bytes"] = None
                send_state[active_rec_id]["preview_confirmed"] = False
                send_state[active_rec_id]["last_message"] = None
            active_rec_id = only_id
            st.session_state["family_active_rec_resident"] = only_id
            st.session_state["family_active_rec_manual"] = False
            send_state.setdefault(
                only_id,
                {"recording_bytes": None, "preview_confirmed": False, "last_message": None},
            )
            send_state[only_id]["recording_bytes"] = None
            send_state[only_id]["preview_confirmed"] = False
            send_state[only_id]["last_message"] = None
    else:
        if manual_active and active_rec_id and active_rec_id not in resident_ids:
            active_rec_id = None
            st.session_state["family_active_rec_resident"] = None
        if not manual_active:
            active_rec_id = None
            st.session_state["family_active_rec_resident"] = None
    recorder_rendered = False
    for resident in residents:
        resident_id = resident["id"]
        state = send_state.setdefault(
            resident_id,
            {"recording_bytes": None, "preview_confirmed": False, "last_message": None},
        )
        full_name = f"{resident['preferred_name']} {resident['surname']}"
        room_label = f"Room {resident['room']}" if resident.get("room") else ""

        st.markdown('<div class="vm-resident-card">', unsafe_allow_html=True)
        st.markdown(f"**{full_name}**")
        if room_label:
            st.markdown(f"*{room_label}*")

        st.markdown('<div class="vm-section-title">Received</div>', unsafe_allow_html=True)
        latest = fetch_latest_message(
            resident_id,
            "from_resident",
            access_token,
            contact_user_id=st.session_state.get("auth_uid"),
        )
        audio_bytes = decode_audio_payload(latest)
        if audio_bytes:
            st.audio(audio_bytes, format=latest.get("audio_mime_type") or "audio/wav")
        else:
            st.markdown(
                '<div class="vm-muted-line">No new messages.</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="vm-section-title">Send</div>', unsafe_allow_html=True)
        if st.button(
            "Record for this resident",
            key=f"family_record_for_{resident_id}",
        ):
            prev_active = st.session_state.get("family_active_rec_resident")
            if prev_active and prev_active in send_state:
                send_state[prev_active]["recording_bytes"] = None
                send_state[prev_active]["preview_confirmed"] = False
            st.session_state["family_active_rec_resident"] = resident_id
            st.session_state["family_active_rec_manual"] = True
            active_rec_id = resident_id

        if resident_id == active_rec_id and not recorder_rendered:
            if st_audiorec is None:
                st.error(
                    "Audio recorder not available. Install with "
                    "`python -m pip install streamlit-audiorec` "
                    "in the same environment you run Streamlit."
                )
            else:
                wav_audio_data = st_audiorec()
                if wav_audio_data and wav_audio_data != state.get("recording_bytes"):
                    state["recording_bytes"] = wav_audio_data
                    state["preview_confirmed"] = False
                    state["last_message"] = None
            recorder_rendered = True
        else:
            st.markdown(
                '<div class="vm-muted-line">Recorder active on another resident.</div>',
                unsafe_allow_html=True,
            )

        if state.get("recording_bytes"):
            state["preview_confirmed"] = st.checkbox(
                "I have listened to this message.",
                value=state.get("preview_confirmed", False),
                key=f"family_listened_{resident_id}",
            )
        else:
            state["preview_confirmed"] = False

        confirmation_line = f"Sending to: {full_name}"
        if room_label:
            confirmation_line = f"{confirmation_line}, {room_label}"
        st.markdown(
            f'<div class="vm-muted-line">{confirmation_line}</div>',
            unsafe_allow_html=True,
        )

        can_send = bool(state.get("recording_bytes") and state.get("preview_confirmed"))
        if st.button(
            f"Send to {full_name}",
            key=f"family_send_{resident_id}",
            disabled=not can_send,
        ):
            if not can_send:
                st.info("Please record and listen before sending.")
            else:
                supabase, error = get_authed_supabase(access_token)
                if error:
                    st.error(error)
                else:
                    audio_bytes = state["recording_bytes"] or b""
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    now_iso = __import__("datetime").datetime.utcnow().isoformat()
                    payload = {
                        "resident_id": resident_id,
                        "contact_user_id": st.session_state.get("auth_uid"),
                        "direction": "to_resident",
                        "audio_storage_path": audio_b64,
                        "audio_mime_type": "audio/wav",
                        "audio_bytes": len(audio_bytes),
                        "recorded_at": now_iso,
                    }
                    try:
                        resp = (
                            supabase.rpc(
                                "insert_family_message",
                                {
                                    "p_resident_id": resident_id,
                                    "p_audio_storage_path": audio_b64,
                                    "p_audio_mime_type": "audio/wav",
                                    "p_audio_bytes": len(audio_bytes),
                                    "p_recorded_at": now_iso,
                                },
                            ).execute()
                        )
                    except Exception as exc:  # pragma: no cover - Supabase runtime error
                        st.error(str(exc))
                    else:
                        message_id = resp.data if resp.data else None
                        log_audit_event(
                            "message_sent",
                            "family",
                            resident["care_home_id"],
                            message_id,
                        )
                        state["recording_bytes"] = None
                        state["preview_confirmed"] = False
                        set_route("/family/sent")


    render_action_row(
        [
            ("Back", "family_send_back"),
            ("Sign out", "family_send_sign_out"),
        ]
    )


def render_family_sent() -> None:
    require_family_access()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header("Message sent")
    st.write("Your voice-message has been sent.")
    render_action_row(
        [
            ("Back", "family_sent_back"),
            ("Back to Family login", "family_sent_home"),
            ("Sign out", "family_sent_sign_out"),
        ]
    )


def render_docs() -> None:
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  .vm-doc-summary {{
    color: rgba(31,31,31,0.65);
    font-size: 0.95rem;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    require_care_access()
    render_page_header("Documents")
    st.write("Select a document to view.")
    st.write("Scroll to the end to read selected document.")

    docs = [
        {
            "title": "Care home responsibilities",
            "path": "docs/office/04_care_home_responsibilities.md",
            "summary": "Care home responsibilities and boundaries.",
        },
        {
            "title": "Care home guide",
            "path": "docs/office/05_care_home_guide.md",
            "summary": "Day-to-day Care Hub use (Office and Mobile).",
        },
        {
            "title": "Safeguarding and consent",
            "path": "docs/office/09_safeguarding_consent.md",
            "summary": "Consent, authority, and safeguarding guidance.",
        },
        {
            "title": "Care Hub access summary",
            "path": "docs/office/08_care_hub_access_summary.md",
            "summary": "Office-facing access summary and responsibilities.",
        },
        {
            "title": "Care home onboarding script",
            "path": "docs/office/care_home_onboarding_script.md",
            "summary": "Onboarding script for staff and families.",
        },
        {
            "title": "Handover checklist",
            "path": "docs/office/care_home_handover_checklist.md",
            "summary": "Handover checklist for the care home.",
        },
    ]

    if "docs_active" not in st.session_state:
        st.session_state["docs_active"] = ""

    for idx, doc in enumerate(docs):
        cols = st.columns([4, 1], gap="small")
        with cols[0]:
            st.markdown(f"**{doc['title']}**\n\n{doc['summary']}")
        with cols[1]:
            if st.button("Open", key=f"docs_open_{idx}"):
                st.session_state["docs_active"] = doc["path"]
        st.write("")
        st.write("")

    active_path = st.session_state.get("docs_active")
    if active_path:
        active_doc = next((doc for doc in docs if doc["path"] == active_path), None)
        st.markdown("---")
        st.markdown(f"## {(active_doc['title'] if active_doc else 'Document')}")
        try:
            content = Path(active_path).read_text(encoding="utf-8")
            content = inject_logo_into_markdown(content)
            st.markdown(content)
        except OSError:
            st.error("Document not found.")
        if st.button("Close", key="docs_close"):
            st.session_state["docs_active"] = ""

    if st.button("Back to Care Hub – Office", key="docs_home"):
        set_route("/care-hub/inbox")


def render_public_document(doc_path: str, back_route: str = "/service-overview") -> None:
    st.markdown(f"[← Back to Service overview](?route={back_route})")
    render_page_header("Public document", show_menu=False, show_variant_subheading=False)
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
        content = inject_logo_into_markdown(content)
        st.markdown(content)
    except OSError:
        st.error("Document not found.")


def render_public_docs() -> None:
    set_route("/public/service-overview")
    st.stop()


def render_public_page(page_title: str, heading: str) -> None:
    render_page_header(page_title)
    content = read_plans_section(heading)
    if not content:
        st.error("Content not available.")
        return
    st.markdown(content)


def render_pr_homepage() -> None:
    st.markdown(
        """
        <style>
        .pr-root {
            background: #FAF6EE;
            color: #2B2B2B;
        }
        .pr-wrap {
            max-width: 960px;
            margin: 0 auto;
            padding: 28px 20px 32px;
        }
        .pr-header {
            display: flex;
            align-items: center;
            gap: 16px;
            padding-bottom: 14px;
        }
        .pr-header-title {
            font-size: 26px;
            font-weight: 700;
            color: #2B2B2B;
        }
        .pr-hero {
            text-align: center;
            padding: 10px 0 18px;
        }
        .pr-hero h1 {
            font-size: 38px;
            font-weight: 800;
            margin: 8px 0 6px;
        }
        .pr-subheading {
            font-size: 18px;
            color: #2B2B2B;
            margin-bottom: 4px;
        }
        .pr-calm {
            font-size: 14px;
            color: #6B7280;
            margin-bottom: 14px;
        }
        .pr-explain {
            max-width: 720px;
            margin: 0 auto;
            font-size: 15px;
            color: #2B2B2B;
            line-height: 1.55;
        }
        .pr-buttons .stButton > button {
            background: #D6E8F5 !important;
            color: #2B2B2B !important;
            border: 1px solid #EDE6DC !important;
            font-weight: 600 !important;
        }
        .pr-buttons .stButton > button:hover {
            background: #C4DFF1 !important;
        }
        .pr-buttons .stButton > button:active {
            background: #BBD4E6 !important;
        }
        .pr-content {
            margin-top: 14px;
            margin-bottom: 22px;
            color: #2B2B2B;
            line-height: 1.6;
        }
        .pr-footer {
            text-align: center;
            color: #6B7280;
            font-size: 13px;
            margin-top: 12px;
        }
        .pr-footer a {
            color: #6B7280;
            text-decoration: none;
            padding: 0 4px;
        }
        .pr-footer a:hover {
            color: #2B2B2B;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pr-root">', unsafe_allow_html=True)
    st.markdown('<div class="pr-wrap">', unsafe_allow_html=True)

    logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    header_cols = st.columns([0.12, 0.88], gap="small")
    with header_cols[0]:
        if logo_path.exists():
            st.image(logo_path.read_bytes(), width=64)
    with header_cols[1]:
        st.markdown('<div class="pr-header-title">voice-message.com</div>', unsafe_allow_html=True)

    st.markdown('<div class="pr-hero">', unsafe_allow_html=True)
    st.markdown("<h1>One message in. One message out.</h1>", unsafe_allow_html=True)
    st.markdown(
        '<div class="pr-subheading">Non-urgent social voice messages in care settings.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="pr-calm">No threads. No pressure.</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="pr-explain">
Only the most recent message from an authorised contact and the most recent reply from the resident are kept.<br />
When a new message is sent, the previous message from that sender is replaced.<br />
This structure helps keep communication simple and manageable within care settings.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="pr-buttons">', unsafe_allow_html=True)
    button_cols = st.columns(3, gap="small")
    with button_cols[0]:
        if st.button("Family", key="pr_role_family"):
            st.session_state["pr_tab"] = "family"
    with button_cols[1]:
        if st.button("Care Hub – Mobile", key="pr_role_mobile"):
            st.session_state["pr_tab"] = "mobile"
    with button_cols[2]:
        if st.button("Care Hub – Office", key="pr_role_office"):
            st.session_state["pr_tab"] = "office"
    st.markdown("</div>", unsafe_allow_html=True)

    if "pr_tab" not in st.session_state:
        st.session_state["pr_tab"] = "family"
    active_tab = st.session_state.get("pr_tab", "family")

    st.markdown('<div class="pr-content">', unsafe_allow_html=True)
    if active_tab == "family":
        st.markdown(
            "Authorised contacts use the Family app to record short voice messages for residents. "
            "This is not a live service, and replies are not immediate. "
            "Only the most recent message and reply are kept. "
            "The service is for non-urgent social contact only. "
            "Safeguarding and care concerns must be directed to the care home."
        )
    elif active_tab == "mobile":
        st.markdown(
            "Care Hub – Mobile supports staff-assisted playback and recording for residents. "
            "It is non-real-time and uses a one message model to keep communication simple. "
            "This view focuses on operational clarity and calm, non-urgent use."
        )
    else:
        st.markdown(
            "Care Hub – Office provides governance oversight, access management, and document control. "
            "Role separation is maintained between Family, Mobile, and Office views. "
            "Subscriptions are provided on a per–care home basis."
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
<div class="pr-footer">
<a href="?route=/public/privacy-notice">Privacy Notice</a> ·
<a href="?route=/public/safeguarding-and-consent">Safeguarding &amp; Consent</a> ·
<a href="?route=/public/complaints-and-concerns">Complaints &amp; Concerns</a>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("</div></div>", unsafe_allow_html=True)


def render_care_hub_security() -> None:
    require_care_access()
    if get_app_variant() != "care_hub_office":
        render_wrong_variant("Security settings are only available in Care Hub – Office.")
        return
    render_page_header("Account & Security")
    access_token = st.session_state.get("access_token")
    auth_uid = st.session_state.get("auth_uid")
    auth_email = st.session_state.get("auth_email") or "office-user"
    record = get_care_hub_mfa_record(access_token, auth_uid)
    enabled = bool(record and record.get("enabled"))

    st.markdown("### Two-factor authentication (TOTP)")
    if enabled:
        st.success("Two-factor authentication is enabled.")
        if st.button("Disable 2FA", key="mfa_disable"):
            totp_secret = record.get("totp_secret") or pyotp.random_base32()
            ok = upsert_care_hub_mfa(access_token, auth_uid, totp_secret, [], False)
            if ok:
                st.session_state["mfa_verified"] = False
                st.info("2FA disabled.")
                st.rerun()
            else:
                st.error("Could not update 2FA settings.")
        st.markdown("Recovery codes are shown once at enrolment. Keep them safe.")
    else:
        st.info("2FA is optional but recommended for Care Hub – Office.")
        if st.button("Start 2FA setup", key="mfa_start"):
            st.session_state["mfa_enroll_secret"] = pyotp.random_base32()
            st.session_state["mfa_enroll_codes"] = generate_recovery_codes()

        secret = st.session_state.get("mfa_enroll_secret")
        codes = st.session_state.get("mfa_enroll_codes")
        if secret and codes:
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=auth_email,
                issuer_name="voice-message.com",
            )
            qr = qrcode.make(provisioning_uri)
            st.image(qr, caption="Scan this QR code with your authenticator app.")
            st.code(secret, language=None)
            st.write("Enter the 6-digit code from your authenticator to activate 2FA.")
            code_input = st.text_input("Authenticator code", key="mfa_enroll_code")
            if st.button("Verify and enable 2FA", key="mfa_enroll_verify"):
                if totp.verify(code_input.strip(), valid_window=1):
                    hashes = [hash_recovery_code(code) for code in codes]
                    ok = upsert_care_hub_mfa(access_token, auth_uid, secret, hashes, True)
                    if ok:
                        st.session_state["mfa_show_codes"] = codes
                        st.session_state.pop("mfa_enroll_secret", None)
                        st.session_state.pop("mfa_enroll_codes", None)
                        st.success("2FA enabled.")
                    else:
                        st.error("Could not enable 2FA.")
                else:
                    st.error("Invalid code. Please try again.")

        if st.session_state.get("mfa_show_codes"):
            st.markdown("### Recovery codes")
            st.write("Save these codes now. They will not be shown again.")
            for code in st.session_state["mfa_show_codes"]:
                st.code(code, language=None)
            if st.button("I have saved these codes", key="mfa_codes_saved"):
                st.session_state.pop("mfa_show_codes", None)

    if st.button("Back to Care Hub – Office", key="mfa_back_office"):
        set_route("/care-hub/inbox")


def render_care_hub_mfa() -> None:
    render_page_header("Two-factor verification")
    access_token = st.session_state.get("access_token")
    auth_uid = st.session_state.get("auth_uid")
    if not auth_uid:
        render_access_gate("Please sign in to access Care Hub – Office.", "/care-hub/login", "care_hub")
        return
    record = get_care_hub_mfa_record(access_token, auth_uid)
    if not record or not record.get("enabled"):
        st.info("Two-factor authentication is not enabled for this account.")
        if st.button("Continue", key="mfa_not_enabled_continue"):
            set_route("/care-hub/inbox")
        return

    st.write("Enter your authenticator code.")
    totp_code = st.text_input("Authenticator code", key="mfa_login_code")
    recovery_code = st.text_input("Recovery code", key="mfa_login_recovery")
    if st.button("Verify", key="mfa_login_verify"):
        totp_secret = record.get("totp_secret")
        recovery_hashes = record.get("recovery_code_hashes") or []
        verified = False
        if totp_code:
            totp = pyotp.TOTP(totp_secret)
            verified = totp.verify(totp_code.strip(), valid_window=1)
        elif recovery_code:
            hashed = hash_recovery_code(recovery_code)
            if hashed in recovery_hashes:
                recovery_hashes = [h for h in recovery_hashes if h != hashed]
                update_care_hub_mfa_codes(access_token, auth_uid, recovery_hashes)
                verified = True
        if verified:
            st.session_state["mfa_verified"] = True
            set_route("/care-hub/inbox")
        else:
            st.error("Invalid code.")
    if st.button("Sign out", key="mfa_login_sign_out"):
        sign_out_user("care_hub")


def render_contracts() -> None:
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  .vm-doc-summary {{
    color: rgba(31,31,31,0.65);
    font-size: 0.95rem;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    require_care_access()
    render_page_header("Contracts")
    st.write("Templates are available here. Signed contracts are stored securely outside this app.")

    docs = [
        {
            "title": "Care home contract template",
            "path": "docs/contracts/care_home_contract_template.md",
            "summary": "Template agreement for care home partners.",
        },
    ]

    if "contracts_active" not in st.session_state:
        st.session_state["contracts_active"] = ""

    for idx, doc in enumerate(docs):
        cols = st.columns([4, 1], gap="small")
        with cols[0]:
            st.markdown(f"**{doc['title']}**\n\n{doc['summary']}")
        with cols[1]:
            if st.button("Open", key=f"contracts_open_{idx}"):
                st.session_state["contracts_active"] = doc["path"]
        st.write("")
        st.write("")

    active_path = st.session_state.get("contracts_active")
    if active_path:
        active_doc = next((doc for doc in docs if doc["path"] == active_path), None)
        st.markdown("---")
        st.markdown(f"## {(active_doc['title'] if active_doc else 'Document')}")
        try:
            content = Path(active_path).read_text(encoding="utf-8")
            content = inject_logo_into_markdown(content)
            st.markdown(content)
        except OSError:
            st.error("Document not found.")
        if st.button("Close", key="contracts_close"):
            st.session_state["contracts_active"] = ""

    if st.button("Back to Care Hub – Office", key="contracts_home"):
        set_route("/care-hub/inbox")


def render_subscription_billing() -> None:
    require_care_access()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header("Subscription & Billing")

    st.markdown("## Current Status")
    st.write("Status: Pilot (example)")

    st.markdown("## Current Plan")
    st.write("Up to 50 residents: £195 + VAT per month")
    st.write("51+ residents: £295 + VAT per month")

    st.markdown("## Pilot Details (if applicable)")
    st.write("£75 + VAT one-time pilot fee")
    st.write("Credited against first month if continuing")

    st.markdown("## Billing Terms")
    st.write("Invoiced monthly in advance")
    st.write("Activation only after payment is received")
    st.write("Minimum 3-month commitment following pilot")

    st.markdown("## Invoices")
    st.write("Invoice reference: [placeholder]")
    st.write("Invoice download functionality will be available here.")

    if st.button("Back to Care Hub – Office", key="billing_home"):
        set_route("/care-hub/inbox")


def render_care_login() -> None:
    inject_login_css()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    app_variant = get_app_variant()
    render_page_header(
        f"{get_care_hub_label()} login",
        brand_title="voice-message.com",
        show_variant_subheading=False,
        show_menu=app_variant != "care_hub_office",
    )
    if app_variant == "care_hub_mobile":
        st.markdown("Non-urgent social voice messages. Not a live service.")
    elif app_variant == "care_hub_office":
        render_front_page_descriptor()
        st.markdown("Care Hub – Office provides full access and includes Care Hub – Mobile functionality.")
        st.markdown("Office users may carry out Mobile tasks as part of supervision or care delivery.")
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)
    if st.session_state.get("auth_uid"):
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if care_found:
            if care_record:
                st.session_state["active_role"] = "care_hub"
                st.session_state["active_care_home_id"] = care_record.get("care_home_id")
            if app_variant == "care_hub_office" and is_office_mfa_required():
                set_route("/care-hub/mfa")
            else:
                set_route("/care-hub/inbox")
        elif family_found:
            st.error("Wrong app variant")
            st.info("Your login details are for Family.")
            if st.button("Log out", key="care_login_wrong_logout"):
                sign_out_user("care_hub")
        else:
            st.error("Account not set up yet.")
        return

    email = st.text_input("Email", key="care_login_email")
    password = st.text_input("Password", type="password", key="care_login_password")

    st.markdown('<div id="vm-login-actions"></div>', unsafe_allow_html=True)
    app_variant = get_app_variant()
    show_sign_out = st.session_state.get("auth_uid")
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        submit_login = st.button("Log in", key="care_login_submit")
    with action_cols[1]:
        forgot_pressed = st.button("Forgot?", key="care_login_forgot")
    with action_cols[2]:
        sign_out_pressed = st.button("Sign out", key="care_login_sign_out") if show_sign_out else False
    back_pressed = False

    if app_variant == "care_hub_office":
        st.markdown("### Information (no login required)")
        st.markdown("[Public documents](?route=/public/service-overview)")
        st.markdown("[Privacy Notice](?route=/public/privacy-notice)")
        st.markdown("[Complaints & Concerns](?route=/public/complaints-and-concerns)")

    if submit_login:
        supabase, error = get_supabase_client()
        if error:
            st.error(error)
        else:
            try:
                auth = supabase.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                st.error(str(exc))
            else:
                if not auth or not auth.user:
                    st.error("Invalid login.")
                else:
                    st.session_state["auth_uid"] = auth.user.id
                    st.session_state["access_token"] = auth.session.access_token
                    st.session_state["refresh_token"] = auth.session.refresh_token
                    st.session_state["auth_email"] = email.strip()
                    family_found, care_found, mapping_error, family_record, care_record = (
                        get_mapping_status()
                    )
                    if care_found:
                        if care_record:
                            st.session_state["active_role"] = "care_hub"
                            st.session_state["active_care_home_id"] = care_record.get(
                                "care_home_id"
                            )
                        log_audit_event(
                            "login_success",
                            "care_hub",
                            st.session_state.get("active_care_home_id"),
                        )
                        if app_variant == "care_hub_office" and is_office_mfa_required():
                            set_route("/care-hub/mfa")
                        else:
                            set_route("/care-hub/inbox")
                    elif family_found:
                        st.error("Wrong app variant")
                        st.info("Your login details are for Family.")
                        if st.button("Log out", key="care_login_wrong_logout_after"):
                            sign_out_user("care_hub")
                    else:
                        st.error("Account not set up yet.")

    if back_pressed:
        set_route("/care-hub/login")
    if sign_out_pressed:
        sign_out_user("care_hub")
    if forgot_pressed:
        st.info("Password reset is not available yet. Please contact support.")


def render_care_hub() -> None:
    require_care_access()
    st.markdown(
        f"""
<style>
  .stApp {{
    background: #FFFFFF !important;
  }}
  section.main {{
    background: #FFFFFF !important;
  }}
  [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
  }}
  [data-testid="stHeader"] {{
    background: #FFFFFF !important;
  }}
  .vm-resident-card {{
    border: 1px solid rgba(31,31,31,0.12);
    border-radius: 12px;
    padding: 12px;
    margin: 12px 0;
    background: {TOKENS["cream"]};
  }}
  .vm-section-title {{
    font-weight: 700;
    margin: 8px 0 4px;
  }}
  .vm-muted-line {{
    color: rgba(31,31,31,0.6);
    font-size: 0.9rem;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header(f"{get_care_hub_label()} voice messages")
    render_front_page_descriptor()
    app_variant = get_app_variant()
    if app_variant == "care_hub_mobile":
        nav_cols = st.columns(3, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_inbox_top", use_container_width=True):
                set_route("/care-hub/inbox")
        with nav_cols[1]:
            if st.button("How it works", key="care_hub_how_it_works_top", use_container_width=True):
                set_route(get_how_it_works_route(app_variant))
        with nav_cols[2]:
            if st.button("Sign out", key="care_hub_sign_out_top", use_container_width=True):
                sign_out_user("care_hub")
    else:
        nav_cols = st.columns(7, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_inbox_top", use_container_width=True):
                set_route("/care-hub/inbox")
        with nav_cols[1]:
            if st.button("Documents", key="care_hub_docs_top", use_container_width=True):
                set_route("/docs")
        with nav_cols[2]:
            if st.button("Contracts", key="care_hub_contracts_top", use_container_width=True):
                set_route("/contracts")
        with nav_cols[3]:
            if st.button(
                "Subscription & Billing",
                key="care_hub_billing_top",
                use_container_width=True,
            ):
                set_route("/billing")
        with nav_cols[4]:
            if st.button("How it works", key="care_hub_how_it_works_top", use_container_width=True):
                set_route(get_how_it_works_route(app_variant))
        with nav_cols[5]:
            if st.button("Account & Security", key="care_hub_security_top", use_container_width=True):
                set_route("/care-hub/security")
        with nav_cols[6]:
            if st.button("Sign out", key="care_hub_sign_out_top", use_container_width=True):
                sign_out_user("care_hub")
    st.markdown(
        "**Messages are for non-urgent, social contact only. This is not a messaging service to carers or the care home.**"
    )
    # Action row already rendered at the top of the page.

    access_token = st.session_state.get("access_token")
    residents = fetch_care_home_residents(access_token)
    contacts_by_resident = {
        resident["id"]: fetch_family_contacts_for_resident(resident["id"], access_token)
        for resident in residents
    }

    search_value = st.text_input("Search residents", key="care_resident_search")
    if search_value:
        search_lower = search_value.strip().lower()
        residents = [
            resident
            for resident in residents
            if search_lower in resident["preferred_name"].lower()
            or search_lower in resident["surname"].lower()
            or (resident.get("room") and search_lower in resident["room"])
        ]

    if not residents:
        if search_value:
            st.info("No residents match that search.")
        return

    send_state = st.session_state.setdefault("care_send_state", {})
    active_rec_id = st.session_state.get("care_active_rec_resident")
    manual_active = st.session_state.get("care_active_rec_manual", False)
    resident_ids = {resident["id"] for resident in residents}

    if len(residents) == 1:
        only_id = residents[0]["id"]
        if active_rec_id != only_id:
            if active_rec_id and active_rec_id in send_state:
                send_state[active_rec_id]["recording_bytes"] = None
                send_state[active_rec_id]["preview_confirmed"] = False
            active_rec_id = only_id
            st.session_state["care_active_rec_resident"] = only_id
            st.session_state["care_active_rec_manual"] = False
            send_state.setdefault(
                only_id,
                {
                    "recording_bytes": None,
                    "preview_confirmed": False,
                    "selected_contact_id": None,
                    "last_message": None,
                },
            )
            send_state[only_id]["recording_bytes"] = None
            send_state[only_id]["preview_confirmed"] = False
    else:
        if manual_active and active_rec_id and active_rec_id not in resident_ids:
            active_rec_id = None
            st.session_state["care_active_rec_resident"] = None
        if not manual_active:
            active_rec_id = None
            st.session_state["care_active_rec_resident"] = None
    recorder_rendered = False
    for resident in residents:
        resident_id = resident["id"]
        state = send_state.setdefault(
            resident_id,
            {
                "recording_bytes": None,
                "preview_confirmed": False,
                "selected_contact_id": None,
                "last_message": None,
            },
        )
        full_name = f"{resident['preferred_name']} {resident['surname']}"
        room_label = f"Room {resident['room']}" if resident.get("room") else ""

        st.markdown('<div class="vm-resident-card">', unsafe_allow_html=True)
        st.markdown(f"**{full_name}**")
        if room_label:
            st.markdown(f"*{room_label}*")

        st.markdown('<div class="vm-section-title">Received</div>', unsafe_allow_html=True)
        latest = fetch_latest_message(resident_id, "to_resident", access_token)
        audio_bytes = decode_audio_payload(latest)
        if audio_bytes:
            st.audio(audio_bytes, format=latest.get("audio_mime_type") or "audio/wav")
        else:
            st.markdown(
                '<div class="vm-muted-line">No new messages.</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="vm-section-title">Send</div>', unsafe_allow_html=True)
        contacts = contacts_by_resident.get(resident_id, [])
        if contacts:
            contact_labels = [
                f"{contact['full_name']} ({contact['relationship']})"
                if contact.get("relationship")
                else contact["full_name"]
                for contact in contacts
            ]
            selected_label = st.selectbox(
                "Recipient",
                contact_labels,
                key=f"care_recipient_{resident_id}",
            )
            selected_contact = contacts[contact_labels.index(selected_label)]
            if selected_contact["id"] != state.get("selected_contact_id"):
                state["selected_contact_id"] = selected_contact["id"]
                state["selected_contact_user_id"] = selected_contact.get("auth_user_id")
                state["recording_bytes"] = None
                state["preview_confirmed"] = False
                state["last_message"] = None
        else:
            st.markdown(
                '<div class="vm-muted-line">No linked family contacts.</div>',
                unsafe_allow_html=True,
            )
            state["selected_contact_id"] = None
            state["selected_contact_user_id"] = None

        if st.button(
            "Record for this resident",
            key=f"care_record_for_{resident_id}",
        ):
            prev_active = st.session_state.get("care_active_rec_resident")
            if prev_active and prev_active in send_state:
                send_state[prev_active]["recording_bytes"] = None
                send_state[prev_active]["preview_confirmed"] = False
            st.session_state["care_active_rec_resident"] = resident_id
            st.session_state["care_active_rec_manual"] = True
            active_rec_id = resident_id

        if resident_id == active_rec_id and not recorder_rendered:
            if st_audiorec is None:
                st.error(
                    "Audio recorder not available. Install with "
                    "`python -m pip install streamlit-audiorec` "
                    "in the same environment you run Streamlit."
                )
            else:
                wav_audio_data = st_audiorec()
                if wav_audio_data and wav_audio_data != state.get("recording_bytes"):
                    state["recording_bytes"] = wav_audio_data
                    state["preview_confirmed"] = False
                    state["last_message"] = None
            recorder_rendered = True
        else:
            st.markdown(
                '<div class="vm-muted-line">Recorder active on another resident.</div>',
                unsafe_allow_html=True,
            )

        if state.get("recording_bytes"):
            state["preview_confirmed"] = st.checkbox(
                "I have listened to this message.",
                value=state.get("preview_confirmed", False),
                key=f"care_listened_{resident_id}",
            )
        else:
            state["preview_confirmed"] = False

        sent_now = False
        confirmation_line = f"Sending on behalf of: {full_name}"
        if room_label:
            confirmation_line = f"{confirmation_line}, {room_label}"
        if state.get("selected_contact_id"):
            selected_contact = next(
                (c for c in contacts if c["id"] == state["selected_contact_id"]),
                None,
            )
            if selected_contact:
                confirmation_line = (
                    f"{confirmation_line} → {selected_contact['full_name']}"
                )
        st.markdown(
            f'<div class="vm-muted-line">{confirmation_line}</div>',
            unsafe_allow_html=True,
        )
        last_sent = st.session_state.get("care_last_sent")
        if sent_now:
            st.success("Message sent.")
        elif last_sent and last_sent.get("resident_id") == resident_id:
            st.success(last_sent.get("message", "Message sent."))

        can_send = bool(
            state.get("recording_bytes")
            and state.get("preview_confirmed")
            and state.get("selected_contact_id")
        )
        if st.button(
            f"Send for {full_name}",
            key=f"care_send_{resident_id}",
            disabled=not can_send,
        ):
            if not can_send:
                st.info("Please select a recipient and record before sending.")
            else:
                supabase, error = get_authed_supabase(access_token)
                if error:
                    st.error(error)
                else:
                    audio_bytes = state.get("recording_bytes") or b""
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    now_iso = __import__("datetime").datetime.utcnow().isoformat()
                    payload = {
                        "resident_id": resident_id,
                        "contact_user_id": state.get("selected_contact_user_id"),
                        "direction": "from_resident",
                        "audio_storage_path": audio_b64,
                        "audio_mime_type": "audio/wav",
                        "audio_bytes": len(audio_bytes),
                        "recorded_at": now_iso,
                    }
                    try:
                        resp = (
                            supabase.rpc(
                                "insert_care_hub_message",
                                {
                                    "p_resident_id": resident_id,
                                    "p_contact_user_id": state.get(
                                        "selected_contact_user_id"
                                    ),
                                    "p_audio_storage_path": audio_b64,
                                    "p_audio_mime_type": "audio/wav",
                                    "p_audio_bytes": len(audio_bytes),
                                    "p_recorded_at": now_iso,
                                },
                            ).execute()
                        )
                    except Exception as exc:  # pragma: no cover - Supabase runtime error
                        st.error(str(exc))
                    else:
                        message_id = resp.data if resp.data else None
                        log_audit_event(
                            "message_sent",
                            "care_hub",
                            resident["care_home_id"],
                            message_id,
                        )
                        state["recording_bytes"] = None
                        state["preview_confirmed"] = False
                        sent_now = True
                        st.session_state["care_last_sent"] = {
                            "resident_id": resident_id,
                            "contact_id": state.get("selected_contact_id"),
                            "message": "Message sent.",
                        }


    # Navigation rendered at the top of the page.


def main() -> None:
    st.set_page_config(
        page_title="voice-message.com",
        page_icon="🗣️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        /* --- HARD FIX: REMOVE STREAMLIT TOP OFFSET --- */
        div[data-testid="stAppViewContainer"] {
            margin-top: -50px !important;
            padding-top: 0 !important;
        }
        .block-container {
            padding-top: 0.5rem !important;
        }
        header[data-testid="stHeader"] {
            display: none;
        }
        div[data-testid="stToolbar"] {
            display: none;
        }
        /* --- TOPBAR (true header) --- */
        .topbar {
            height: 104px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 16px;
            background: white;
            border-bottom: 1px solid rgba(0,0,0,0.08);
            box-sizing: border-box;
            margin: 0;
            position: relative;
        }
        .variant-banner {
            font-size: 13px;
            font-weight: 600;
            color: rgba(0, 0, 0, 0.6);
            margin: 6px 0 2px 0;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 4px;
        }
        .brand-logo {
            height: 72px;
            width: auto;
            display: block;
        }
        .brand-text {
            font-size: 34px;
            font-weight: 600;
            line-height: 1;
            margin: 0;
        }
        .hamburger {
            font-size: 26px;
            cursor: pointer;
        }
        /* Ensure hamburger popover is fully clickable */
        div[data-testid="stPopover"] {
            z-index: 20000 !important;
        }
        div[data-testid="stPopover"] > div {
            margin-top: 6px !important;
            padding-top: 6px !important;
        }
        div[data-testid="stPopoverBody"] {
            padding-top: 6px !important;
        }
        .hero-logo {
            margin-top: -40px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    app_variant = get_app_variant()
    # No raw variant banner in UI.
    init_state()
    if app_variant == "care_hub_mobile":
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    if app_variant == "public":
        st.markdown(
            """
            <style>
            [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    enforce_session_timeout()
    route = get_route()
    if not app_variant:
        expected_variants = get_expected_variants_for_route(route)
        render_wrong_variant("App variant is missing or invalid.", expected_variants)
        return
    default_route = get_default_route(app_variant)
    if route in ("/", ""):
        set_route(default_route)
        route = default_route
    if not is_route_allowed(app_variant, route):
        expected_variants = get_expected_variants_for_route(route)
        render_wrong_variant(f"Route `{route}` is not available in this app.", expected_variants)
        return
    if (
        app_variant == "care_hub_office"
        and is_office_mfa_required()
        and route not in ("/care-hub/mfa", "/care-hub/login")
    ):
        set_route("/care-hub/mfa")
        return
    prev_page = st.session_state.get("current_page")
    st.session_state["prev_page"] = prev_page
    st.session_state["current_page"] = route
    if (
        prev_page == "/family/send"
        and route != "/family/send"
        and st.session_state.get("rec_state") == "recording"
    ):
        st.session_state["rec_state"] = "idle"
        st.session_state["recording_bytes"] = None
        log_audit_event(
            "recording_aborted_page_leave",
            "family",
            st.session_state.get("active_care_home_id"),
        )
    st.session_state.route = route
    if route == "/family/login":
        render_family_login()
    elif route == "/family/send":
        render_family_send()
    elif route == "/family/sent":
        render_family_sent()
    elif route == "/family/introduction":
        set_route("/how-it-works/family")
    elif route == "/family/instructions":
        set_route("/how-it-works/family")
    elif route == "/family/info":
        render_how_it_works_family()
    elif route == "/family/privacy":
        render_family_document("Privacy Notice", "docs/public/privacy_policy.md")
    elif route == "/family/terms":
        set_route("/family/terms-summary")
    elif route == "/family/terms-use":
        render_family_document("Family Terms of Use", "docs/public/family_terms_of_use.md")
    elif route == "/family/terms-summary":
        render_family_document("Family Terms Summary", "docs/public/family_terms_summary.md")
    elif route == "/family/contact":
        render_family_contact()
    elif route == "/pr-home":
        set_route("/service-overview")
    elif route == "/service-overview":
        render_home("public")
    elif route == "/how-it-works/family":
        set_route("/family/how-it-works")
    elif route == "/family/how-it-works":
        render_how_it_works_family()
    elif route == "/how-it-works/mobile":
        render_how_it_works_mobile()
    elif route == "/care-hub-mobile/how-it-works":
        render_how_it_works_mobile()
    elif route == "/care-hub-office/how-it-works":
        render_how_it_works_office_overview()
    elif route == "/how-it-works/office":
        render_how_it_works_office_overview()
    elif route == "/care-hub/login":
        render_care_login()
    elif route == "/care-hub/inbox":
        render_care_hub()
    elif route == "/care-hub/instructions":
        render_care_hub_instructions()
    elif route == "/care-hub/training":
        render_care_hub_training()
    elif route == "/care-hub/security":
        render_care_hub_security()
    elif route == "/docs":
        render_docs()
    elif route == "/public-docs":
        render_public_docs()
    elif route == "/public/service-overview":
        render_public_document("docs/public/03_service_overview.md")
    elif route == "/public/how-it-works":
        render_public_document("docs/public/02_how_it_works.md")
    elif route == "/public/resident-participation":
        render_public_document("docs/public/07_resident_participation.md")
    elif route == "/public/family-guide":
        render_public_document("docs/public/06_family_guide.md")
    elif route == "/public/faq":
        render_public_document("docs/public/10_faq.md")
    elif route == "/public/privacy-notice":
        render_public_document("docs/public/privacy_policy.md")
    elif route == "/public/family-terms-of-use":
        render_public_document("docs/public/family_terms_of_use.md")
    elif route == "/public/family-terms-summary":
        render_public_document("docs/public/family_terms_summary.md")
    elif route == "/public/complaints-and-concerns":
        render_public_document("docs/public/complaints_and_concerns.md")
    elif route == "/public/safeguarding-and-consent":
        render_public_document("docs/public/safeguarding_and_consent.md")
    elif route == "/public-privacy":
        set_route("/public/privacy-notice")
    elif route == "/public-complaints":
        set_route("/public/complaints-and-concerns")
    elif route == "/public-safeguarding":
        set_route("/public/safeguarding-and-consent")
    elif route == "/contracts":
        render_contracts()
    elif route == "/billing":
        render_subscription_billing()
    elif route == "/care-hub/mfa":
        render_care_hub_mfa()
    else:
        st.header("Page not found")
        st.write(f"Unknown route: {route}")


if __name__ == "__main__":
    main()
