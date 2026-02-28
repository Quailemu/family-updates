# voice-message.com UI

import os
import base64
import time
import uuid
import secrets
import hashlib
import hmac
import json
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from supabase.client import create_client
import pyotp
import qrcode
from config import get_supabase_config, get_app_variant as resolve_app_variant

try:
    from st_audiorec import st_audiorec
except ModuleNotFoundError:  # pragma: no cover - runtime env mismatch
    st_audiorec = None

try:
    from streamlit_autorefresh import st_autorefresh
except ModuleNotFoundError:  # pragma: no cover - runtime env mismatch
    st_autorefresh = None

from ui_theme import TOKENS, inject_css

SESSION_TIMEOUT_SECONDS = 1800
APP_DEBUG = os.getenv("APP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
APP_LIVE_REFRESH = os.getenv("APP_LIVE_REFRESH", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

ALLOWED_VARIANT_VALUES_TEXT = "public, family, mobile, office"
AUTH_COOKIE_NAME = "vm_auth_rt"
AUTH_COOKIE_MAX_AGE_SECONDS = int(os.getenv("AUTH_COOKIE_MAX_AGE_SECONDS", str(60 * 60 * 24 * 14)))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "1").strip().lower() in {"1", "true", "yes", "on"}
AUTH_COOKIE_SIGNING_KEY = os.getenv("AUTH_COOKIE_SIGNING_KEY", "").strip()
AUTH_COOKIE_PERSISTENCE_ENABLED = os.getenv("AUTH_COOKIE_PERSISTENCE_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
AUTH_STATE_KEYS = (
    "auth_uid",
    "access_token",
    "refresh_token",
    "auth_email",
    "active_role",
    "active_care_home_id",
    "mfa_verified",
)


def normalize_route(route: str | None) -> str:
    value = (route or "").strip()
    if not value:
        return ""
    if not value.startswith("/"):
        value = f"/{value}"
    if len(value) > 1 and value.endswith("/"):
        value = value[:-1]
    return value


def _sign_cookie_payload(payload: str) -> str:
    secret = AUTH_COOKIE_SIGNING_KEY.encode("utf-8")
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def _encode_refresh_token_cookie(refresh_token: str) -> str:
    payload = base64.urlsafe_b64encode(refresh_token.encode("utf-8")).decode("ascii")
    signature = _sign_cookie_payload(payload)
    return f"{payload}.{signature}"


def _decode_refresh_token_cookie(cookie_value: str) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    payload, signature = cookie_value.rsplit(".", 1)
    expected = _sign_cookie_payload(payload)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
    except Exception:
        return None


def _get_request_cookie(name: str) -> str:
    try:
        context = getattr(st, "context", None)
        cookies = getattr(context, "cookies", {}) if context is not None else {}
        value = cookies.get(name, "")
        return str(value or "")
    except Exception:
        return ""


def _set_browser_cookie(name: str, value: str, max_age_seconds: int) -> None:
    # Streamlit exposes request cookies but not a native setter, so we set via client-side JS.
    cookie_parts = [
        f"{name}={value}",
        "path=/",
        f"max-age={max_age_seconds}",
        "SameSite=Lax",
    ]
    if AUTH_COOKIE_SECURE:
        cookie_parts.append("Secure")
    cookie_string = "; ".join(cookie_parts)
    components.html(
        f"""
<script>
document.cookie = {json.dumps(cookie_string)};
</script>
""",
        height=0,
        width=0,
    )


def persist_auth_cookie(refresh_token: str | None) -> None:
    if not AUTH_COOKIE_PERSISTENCE_ENABLED or not AUTH_COOKIE_SIGNING_KEY:
        return
    if not refresh_token:
        clear_auth_cookie()
        return
    encoded = _encode_refresh_token_cookie(refresh_token)
    _set_browser_cookie(AUTH_COOKIE_NAME, encoded, AUTH_COOKIE_MAX_AGE_SECONDS)


def clear_auth_cookie() -> None:
    if not AUTH_COOKIE_PERSISTENCE_ENABLED:
        return
    _set_browser_cookie(AUTH_COOKIE_NAME, "", 0)


def clear_auth_session_state() -> None:
    for key in AUTH_STATE_KEYS:
        st.session_state.pop(key, None)


def restore_auth_session_from_cookie() -> None:
    if not AUTH_COOKIE_PERSISTENCE_ENABLED:
        return
    if st.session_state.get("_auth_cookie_restored"):
        return
    st.session_state["_auth_cookie_restored"] = True
    # Keep a currently valid in-memory session; do not overwrite it on startup.
    if (
        st.session_state.get("auth_uid")
        and st.session_state.get("access_token")
        and st.session_state.get("refresh_token")
    ):
        return
    if not AUTH_COOKIE_SIGNING_KEY:
        return
    raw_cookie = _get_request_cookie(AUTH_COOKIE_NAME)
    refresh_token = _decode_refresh_token_cookie(raw_cookie)
    if not refresh_token:
        if raw_cookie:
            clear_auth_cookie()
        return
    supabase, error = get_supabase_client()
    if error:
        return
    try:
        try:
            auth_result = supabase.auth.refresh_session(refresh_token)
        except TypeError:
            auth_result = supabase.auth.refresh_session()
        session = getattr(auth_result, "session", None)
        user = getattr(auth_result, "user", None)
        if not session:
            clear_auth_cookie()
            return
        st.session_state["access_token"] = getattr(session, "access_token", "")
        st.session_state["refresh_token"] = getattr(session, "refresh_token", "")
        if user is None:
            user = getattr(session, "user", None)
        st.session_state["auth_uid"] = getattr(user, "id", "") if user is not None else ""
        email_value = getattr(user, "email", "") if user is not None else ""
        st.session_state["auth_email"] = email_value or ""
        if not st.session_state.get("access_token") or not st.session_state.get("refresh_token"):
            clear_auth_session_state()
            clear_auth_cookie()
            return
        # Rebuild role state from authoritative DB mappings.
        try:
            supabase.postgrest.auth(st.session_state["access_token"])
            auth_uid = st.session_state.get("auth_uid")
            family_resp = (
                supabase.table("family_contacts")
                .select("care_home_id")
                .eq("auth_user_id", auth_uid)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            care_resp = (
                supabase.table("care_home_users")
                .select("care_home_id")
                .eq("auth_user_id", auth_uid)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            family_row = family_resp.data[0] if family_resp.data else None
            care_row = care_resp.data[0] if care_resp.data else None
            if family_row:
                st.session_state["active_role"] = "family"
                st.session_state["active_care_home_id"] = family_row.get("care_home_id")
            elif care_row:
                st.session_state["active_role"] = "care_hub"
                st.session_state["active_care_home_id"] = care_row.get("care_home_id")
        except Exception:
            # Keep auth tokens; route-level access checks still fail closed if mapping is missing.
            pass
        # Rotate cookie to the latest refresh token to keep long-running sessions durable.
        persist_auth_cookie(st.session_state["refresh_token"])
    except Exception:
        clear_auth_session_state()
        clear_auth_cookie()


def is_family_authenticated() -> bool:
    return (
        bool(st.session_state.get("auth_uid"))
        and bool(st.session_state.get("access_token"))
        and bool(st.session_state.get("refresh_token"))
        and st.session_state.get("active_role") == "family"
    )


def is_care_authenticated() -> bool:
    return (
        bool(st.session_state.get("auth_uid"))
        and bool(st.session_state.get("access_token"))
        and bool(st.session_state.get("refresh_token"))
        and st.session_state.get("active_role") == "care_hub"
    )


def get_query_route_debug() -> str:
    if hasattr(st, "query_params"):
        route = st.query_params.get("route", "")
    else:
        route = st.experimental_get_query_params().get("route", [""])[0]
    if isinstance(route, list):
        route = route[0] if route else ""
    return normalize_route(route) or "(empty)"


def render_debug_panel(stage: str, app_variant: str, redirect_decision: str = "None") -> None:
    if not APP_DEBUG:
        return
    auth_state = is_family_authenticated() if app_variant == VARIANT_FAMILY else bool(st.session_state.get("auth_uid"))
    st.markdown(
        f"""
<div style="border:1px solid #d6d6d6;background:#fff9d9;border-radius:8px;padding:8px 10px;margin:6px 0 10px;">
  <div style="font-weight:700;">DEBUG: Reached top of app</div>
  <div>stage: <code>{stage}</code></div>
  <div>variant: <code>{app_variant or '(missing)'}</code></div>
  <div>logged_in: <code>{auth_state}</code></div>
  <div>query route: <code>{get_query_route_debug()}</code></div>
  <div>redirect decision: <code>{redirect_decision}</code></div>
</div>
""",
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "route" not in st.session_state:
        st.session_state.route = "/"


def set_route(route: str) -> None:
    target = normalize_route(route) or "/"
    st.session_state.route = target
    route_changed = False
    if hasattr(st, "query_params"):
        current = st.query_params.get("route", "")
        if isinstance(current, list):
            current = current[0] if current else ""
        current = normalize_route(current)
        if current != target:
            st.query_params["route"] = target
            route_changed = True
    else:
        current = normalize_route(st.experimental_get_query_params().get("route", [""])[0])
        route_changed = current != target
        st.experimental_set_query_params(route=target)
    if route_changed:
        st.session_state.pop("_route_transition_until", None)
        st.rerun()


def render_route_link(label: str, route: str, key: str, use_container_width: bool = True) -> None:
    target = normalize_route(route) or "/"
    if st.button(label, key=key, use_container_width=use_container_width):
        set_route(target)

def get_supabase_client() -> tuple[object | None, str | None]:
    url, key = get_supabase_config()
    if not url or not key:
        return None, "Missing SUPABASE_URL or SUPABASE_ANON_KEY."
    cached_bundle = st.session_state.get("_supabase_client_bundle")
    if (
        isinstance(cached_bundle, tuple)
        and len(cached_bundle) == 3
        and cached_bundle[0] == url
        and cached_bundle[1] == key
        and cached_bundle[2] is not None
    ):
        return cached_bundle[2], None
    try:
        client = create_client(url, key)
        st.session_state["_supabase_client_bundle"] = (url, key, client)
        return client, None
    except Exception as exc:  # pragma: no cover - environment/runtime mismatch
        message = str(exc) or exc.__class__.__name__
        if isinstance(exc, OSError):
            return (
                None,
                "Supabase client initialization failed (SSL setup error). "
                "Check Streamlit Cloud secrets and remove invalid SSL cert path overrides "
                "(for example SSL_CERT_FILE / SSL_CERT_DIR).",
            )
        return None, f"Supabase client initialization failed: {message}"


def get_admin_client() -> tuple[object | None, str | None]:
    url, _ = get_supabase_config()
    if not url:
        return None, "Missing SUPABASE_URL."
    if not SUPABASE_SERVICE_ROLE_KEY:
        return None, "Missing SUPABASE_SERVICE_ROLE_KEY for Office family registration."
    cached_bundle = st.session_state.get("_supabase_admin_client_bundle")
    if (
        isinstance(cached_bundle, tuple)
        and len(cached_bundle) == 2
        and cached_bundle[0] == url
        and cached_bundle[1] is not None
    ):
        return cached_bundle[1], None
    try:
        client = create_client(url, SUPABASE_SERVICE_ROLE_KEY)
        # Cache the client without persisting the service key in session state.
        st.session_state["_supabase_admin_client_bundle"] = (url, client)
        return client, None
    except Exception as exc:  # pragma: no cover - runtime/config mismatch
        return None, f"Supabase admin client initialization failed: {exc}"


def _extract_auth_user_id(auth_result: object) -> str:
    if auth_result is None:
        return ""
    user = getattr(auth_result, "user", None)
    if user is not None:
        user_id = getattr(user, "id", "") or ""
        if user_id:
            return str(user_id)
    direct_id = getattr(auth_result, "id", "") or ""
    if direct_id:
        return str(direct_id)
    if isinstance(auth_result, dict):
        payload_user = auth_result.get("user")
        if isinstance(payload_user, dict):
            payload_id = payload_user.get("id") or ""
            if payload_id:
                return str(payload_id)
        payload_id = auth_result.get("id") or ""
        if payload_id:
            return str(payload_id)
    return ""


def _resolve_auth_user_id_by_email(admin_client: object, email: str) -> str:
    try:
        users_response = admin_client.auth.admin.list_users()
    except Exception:
        return ""
    payload = getattr(users_response, "data", None)
    if payload is None and isinstance(users_response, dict):
        payload = users_response.get("data")
    users = []
    if isinstance(payload, dict):
        users = payload.get("users") or []
    elif isinstance(payload, list):
        users = payload
    for user in users:
        user_email = ""
        user_id = ""
        if isinstance(user, dict):
            user_email = str(user.get("email") or "").strip().lower()
            user_id = str(user.get("id") or "")
        else:
            user_email = str(getattr(user, "email", "") or "").strip().lower()
            user_id = str(getattr(user, "id", "") or "")
        if user_email == email and user_id:
            return user_id
    return ""


def invite_user(admin_client: object, email: str) -> tuple[bool, str | None, str | None]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return False, None, "Email is required."
    redirect_to = (
        os.getenv("FAMILY_INVITE_REDIRECT_URL", "").strip()
        or os.getenv("PASSWORD_RESET_REDIRECT_URL", "").strip()
    )
    if not redirect_to:
        return (
            False,
            None,
            "Missing FAMILY_INVITE_REDIRECT_URL (or PASSWORD_RESET_REDIRECT_URL) for invite redirect.",
        )
    try:
        try:
            invite_result = admin_client.auth.admin.invite_user_by_email(
                normalized_email,
                {"redirect_to": redirect_to},
            )
        except TypeError:
            return (
                False,
                None,
                "Supabase client does not support invite redirect options. Upgrade supabase-py.",
            )
    except Exception as exc:
        return False, None, str(exc)
    auth_user_id = _extract_auth_user_id(invite_result)
    if not auth_user_id:
        auth_user_id = _resolve_auth_user_id_by_email(admin_client, normalized_email)
    if not auth_user_id:
        return False, None, "Invite sent but auth user ID could not be resolved."
    return True, auth_user_id, None


def upsert_family_contact(
    access_token: str | None,
    *,
    care_home_id: str,
    auth_user_id: str,
    email: str,
    first_name: str,
    last_name: str,
) -> tuple[dict | None, str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None, error
    display_name = f"{first_name.strip()} {last_name.strip()}".strip()
    payload = {
        "care_home_id": care_home_id,
        "auth_user_id": auth_user_id,
        "email": email.strip().lower(),
        "display_name": display_name or "Family contact",
        "active": True,
    }
    try:
        # Older supabase-py versions do not support `.select()` chained after `.upsert()`.
        supabase.table("family_contacts").upsert(
            payload, on_conflict="auth_user_id"
        ).execute()
        resp = (
            supabase.table("family_contacts")
            .select("id, auth_user_id, care_home_id, email, display_name, active")
            .eq("auth_user_id", auth_user_id)
            .eq("care_home_id", care_home_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return None, str(exc)
    if not resp.data:
        return None, "Could not create family contact mapping."
    return resp.data[0], None


def grant_resident_access(
    access_token: str | None,
    *,
    resident_id: str,
    family_contact_id: str,
) -> tuple[dict | None, str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None, error
    payload = {
        "resident_id": resident_id,
        "family_contact_id": family_contact_id,
        "active": True,
    }
    try:
        # Older supabase-py versions do not support `.select()` chained after `.upsert()`.
        supabase.table("family_contact_access").upsert(
            payload, on_conflict="resident_id,family_contact_id"
        ).execute()
        resp = (
            supabase.table("family_contact_access")
            .select("id, resident_id, family_contact_id, active")
            .eq("resident_id", resident_id)
            .eq("family_contact_id", family_contact_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return None, str(exc)
    if not resp.data:
        return None, "Could not create resident access mapping."
    return resp.data[0], None


def _apply_family_registration_mapping(
    access_token: str | None, payload: dict
) -> tuple[bool, str | None]:
    contact_row, contact_error = upsert_family_contact(
        access_token,
        care_home_id=str(payload.get("care_home_id") or ""),
        auth_user_id=str(payload.get("auth_user_id") or ""),
        email=str(payload.get("email") or ""),
        first_name=str(payload.get("first_name") or ""),
        last_name=str(payload.get("last_name") or ""),
    )
    if contact_error or not contact_row:
        return False, contact_error or "Failed to upsert family contact."
    _, access_error = grant_resident_access(
        access_token,
        resident_id=str(payload.get("resident_id") or ""),
        family_contact_id=str(contact_row.get("id") or ""),
    )
    if access_error:
        return False, access_error
    return True, None


def render_office_family_registration_form(
    access_token: str | None, residents: list[dict]
) -> None:
    if get_app_variant() != VARIANT_OFFICE:
        return
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    auth_uid = str(st.session_state.get("auth_uid") or "").strip()
    if not care_home_id or not auth_uid:
        st.error("Office mapping is required before registering family members.")
        return
    supabase, auth_error = get_authed_supabase(access_token)
    if auth_error:
        st.error(auth_error)
        return
    try:
        mapping_resp = (
            supabase.table("care_home_users")
            .select("id")
            .eq("auth_user_id", auth_uid)
            .eq("care_home_id", care_home_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        st.error(str(exc))
        return
    if not mapping_resp.data:
        st.error("Your Office account is not mapped to an active care home.")
        return

    office_residents = [
        resident
        for resident in residents
        if str(resident.get("care_home_id") or "") == care_home_id
    ]
    if not office_residents:
        st.info("No active residents are available for family registration.")
        return

    pending_key = "office_family_registration_pending"
    pending_payload = st.session_state.get(pending_key)
    if isinstance(pending_payload, dict) and pending_payload.get("care_home_id") == care_home_id:
        st.warning(
            "Invite already sent. Retry mapping below without sending another invite."
        )
        if st.button(
            "Retry mapping without re-invite",
            key="office_family_register_retry_mapping",
        ):
            ok, mapping_error = _apply_family_registration_mapping(
                access_token, pending_payload
            )
            if ok:
                st.session_state.pop(pending_key, None)
                st.success(
                    f"Family member linked: {pending_payload.get('email', 'contact')}."
                )
                st.rerun()
            else:
                st.error(mapping_error or "Retry failed. Please try again.")

    st.markdown("### Register a Family Member")
    st.caption(
        "Register an authorised family contact for a resident. We will send them an email invitation to set up their account."
    )
    resident_options = []
    resident_by_id = {}
    resident_label_by_id = {}
    for resident in office_residents:
        resident_id = str(resident.get("id") or "")
        if not resident_id:
            continue
        label = resident.get("preferred_name", "Resident")
        room = str(resident.get("room") or "").strip()
        if room:
            label = f"{label} ({room})"
        resident_options.append(resident_id)
        resident_by_id[resident_id] = resident
        resident_label_by_id[resident_id] = label
    if not resident_options:
        st.info("No valid residents are available for family registration.")
        return

    with st.form("office_register_family_member_form"):
        st.markdown("#### Section 1 — Family Contact Details")
        first_name = st.text_input("First name", key="office_family_first_name")
        last_name = st.text_input("Last name", key="office_family_last_name")
        email = st.text_input("Email", key="office_family_email")
        relationship = st.text_input(
            "Relationship (optional)",
            key="office_family_relationship",
        )
        st.caption("Relationship is recorded for local workflow guidance only.")
        st.markdown("#### Section 2 — Link to Resident")
        resident_id = st.selectbox(
            "Resident",
            resident_options,
            format_func=lambda rid: resident_label_by_id.get(rid, "Resident"),
            key="office_family_resident_select",
        )
        st.markdown("#### Section 3 — Confirmation")
        authorised_confirmed = st.checkbox(
            "I confirm this person is authorised by the resident (or their representative) to receive and send social voice messages.",
            key="office_family_authorisation_confirm",
        )
        submitted = st.form_submit_button("Send invitation")

    if not submitted:
        return

    first_value = first_name.strip()
    last_value = last_name.strip()
    normalized_email = email.strip().lower()
    if not first_value or not last_value or not normalized_email:
        st.error("First name, last name, and email are required.")
        return
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        st.error("Enter a valid email address.")
        return
    if not authorised_confirmed:
        st.error("Please confirm authorisation before sending the invitation.")
        return

    resident = resident_by_id.get(resident_id)
    if not resident:
        st.error("Select a resident.")
        return

    try:
        existing_contact_resp = (
            supabase.table("family_contacts")
            .select("id")
            .eq("care_home_id", care_home_id)
            .eq("email", normalized_email)
            .eq("active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        st.error(str(exc))
        return
    if existing_contact_resp.data:
        st.error("That email is already registered for this care home.")
        return

    admin_client, admin_error = get_admin_client()
    if admin_error:
        st.error(admin_error)
        return
    invite_redirect_to = (
        os.getenv("FAMILY_INVITE_REDIRECT_URL", "").strip()
        or os.getenv("PASSWORD_RESET_REDIRECT_URL", "").strip()
    )
    debug = os.getenv("APP_DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")
    if debug:
        st.info(f"Invite redirect_to: {invite_redirect_to}")
    invited, auth_user_id, invite_error = invite_user(admin_client, normalized_email)
    if not invited or not auth_user_id:
        st.error(invite_error or "Invite failed.")
        return

    payload = {
        "care_home_id": care_home_id,
        "resident_id": resident_id,
        "auth_user_id": auth_user_id,
        "email": normalized_email,
        "first_name": first_value,
        "last_name": last_value,
        "relationship": relationship.strip(),
    }
    mapping_ok, mapping_error = _apply_family_registration_mapping(access_token, payload)
    if mapping_ok:
        st.session_state.pop(pending_key, None)
        st.success(
            "Invitation sent\n"
            f"We've emailed {normalized_email} with instructions to set up their account.\n"
            "Ask them to check spam/junk if they don't receive it."
        )
        return

    st.session_state[pending_key] = payload
    st.error(
        "Invite sent but mapping failed. Use 'Retry mapping without re-invite'."
    )
    if mapping_error:
        st.error(mapping_error)


def send_password_reset_email(email: str, app_variant: str = "") -> tuple[bool, str]:
    target_email = email.strip()
    if not target_email:
        return False, "Enter your email first."
    supabase, error = get_supabase_client()
    if error:
        return False, error
    try:
        if app_variant == VARIANT_FAMILY:
            redirect_to = os.getenv("PASSWORD_RESET_REDIRECT_URL", "").strip()
            debug = os.getenv("APP_DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")
            if debug:
                st.info(f"Reset redirect_to: {redirect_to}")
            print(f"[auth] Family forgot-password redirect_to={redirect_to!r}")
            supabase.auth.reset_password_email(target_email, {"redirect_to": redirect_to})
        else:
            supabase.auth.reset_password_email(target_email)
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return False, str(exc)
    return True, "If this email is registered, a password reset link has been sent."


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
            .select("id, care_home_id, display_name")
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
    if role == "family":
        render_page_header("Family page")
    else:
        render_page_header("Access required", show_variant_subheading=False)
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
    if role != "family":
        if st.button("Go to login", key=f"{role}_gate_login"):
            set_route(get_login_route(get_app_variant()))
        return
    cols = st.columns(3, gap="small")
    with cols[0]:
        if st.button("Go to login", key=f"{role}_gate_login"):
            set_route(login_route)
    with cols[1]:
        render_route_link(
            "Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key=f"{role}_gate_home_link",
        )
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
        render_route_link("Back to service overview", "/service-overview", key="public_wrong_back_link")
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


def wrong_variant_screen(route: str, detail: str | None = None) -> None:
    """
    Reusable wrong-variant screen used by route/page guards.
    Always stops execution after rendering to prevent partial page renders.
    """
    normalized_route = normalize_route(route) or "/"
    st.error("Wrong app variant")
    st.markdown("This page is not available in the current app configuration.")
    if detail:
        st.markdown(detail)
    st.caption(f"Blocked route: {normalized_route}")
    if st.button("Return to Public", key=f"wrong_variant_public_{normalized_route.replace('/', '_')}"):
        set_route(PUBLIC_HOME_ROUTE)
    st.stop()


def guard_route_access(route: str, app_variant: str | None = None) -> None:
    """
    Central route guard for app-level variant isolation.
    Every rendered route must be explicitly allowlisted for the active variant.
    """
    normalized_route = normalize_route(route) or "/"
    active_variant = app_variant or get_app_variant()
    if not is_route_allowed(active_variant, normalized_route):
        wrong_variant_screen(normalized_route)


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
        """
<style>
  .family-how-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    info_boxes = [
        "voice-message.com — for non-urgent social voice messages. One channel between each Family sender and each resident in a care home.",
        "One message kept at a time in each direction, i.e resident to Family and Family to resident. No threads.",
        "In this service, 'Family' means authorised contacts approved by the care home, such as family members or close friends.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)


def render_how_it_works_mobile() -> None:
    render_page_header("How it works — Care Hub – Mobile")
    st.markdown(
        """
<style>
  .family-how-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    info_boxes = [
        "voice-message.com — for non-urgent social voice messages. One channel between each Family sender and each resident in a care home.",
        "One message kept at a time in each direction, i.e resident to Family and Family to resident. No threads.",
        "In this service, 'Family' means authorised contacts approved by the care home, such as family members or close friends.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    render_route_link(
        "Back to Care Hub – Mobile",
        get_home_route(VARIANT_MOBILE),
        key="mobile_how_it_works_back_link",
    )


def render_how_it_works_office_overview() -> None:
    render_page_header("How it works — Care Hub – Office")
    st.markdown(
        """
<style>
  .family-how-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    info_boxes = [
        "voice-message.com — for non-urgent social voice messages. One channel between each Family sender and each resident in a care home.",
        "One message kept at a time in each direction, i.e resident to Family and Family to resident. No threads.",
        "In this service, 'Family' means authorised contacts approved by the care home, such as family members or close friends.",
        "Care Hub – Office provides full access and includes Care Hub – Mobile functionality.",
        "Office users may carry out Mobile tasks as part of supervision or care delivery.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)


def render_how_it_works_office() -> None:
    render_how_it_works_office_overview()


def render_family_document(title: str, path: str) -> None:
    render_page_header(title)
    try:
        content = Path(path).read_text(encoding="utf-8")
        content = re.sub(r"\A\s*#\s+.+?\n+", "", content, count=1)
    except OSError:
        st.error("Document not found.")
    else:
        st.markdown(content)
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", "/how-it-works/family", key="family_doc_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key="family_doc_home_link",
        )
    with action_cols[2]:
        if st.button("Sign out", key="family_doc_sign_out"):
            sign_out_user("family")


def render_family_terms() -> None:
    render_page_header("Family Terms of Use", show_variant_subheading=False)
    st.markdown("[Summary](#summary-non-binding) | [Full terms](#full-terms-binding)")
    st.markdown(
        """
<style>
  .family-terms-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div id="summary-non-binding"></div>', unsafe_allow_html=True)
    st.markdown("## Summary (Plain English - Non-binding)")
    st.markdown(
        '<div class="family-terms-box">This summary is provided for convenience only. '
        "The full Terms of Use below are legally binding and prevail in the event of any inconsistency.</div>",
        unsafe_allow_html=True,
    )
    render_document_boxes("docs/public/family_terms_summary.md", strip_first_heading=True)
    st.markdown("---")
    st.markdown('<div id="full-terms-binding"></div>', unsafe_allow_html=True)
    st.markdown("## Full Terms of Use (Binding)")
    render_document_boxes("docs/public/family_terms_of_use.md", strip_first_heading=True)
    family_back_route = (
        get_home_route(VARIANT_FAMILY)
        if st.session_state.get("auth_uid")
        else get_login_route(VARIANT_FAMILY)
    )
    render_route_link("Back to Family", family_back_route, key="family_terms_back_link")


def render_family_contact() -> None:
    render_page_header("Contact the care home")
    st.markdown(
        """
<style>
  .family-contact-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="family-contact-box">For access, questions, or support, contact the care home directly.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="family-contact-box">For safeguarding concerns, contact the care home directly; the platform is not monitored in real time.</div>',
        unsafe_allow_html=True,
    )
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", "/how-it-works/family", key="family_contact_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key="family_contact_home_link",
        )
    with action_cols[2]:
        if st.button("Sign out", key="family_contact_sign_out"):
            sign_out_user("family")


def render_care_hub_nav() -> None:
    app_variant = get_app_variant()
    if app_variant == VARIANT_MOBILE:
        nav_cols = st.columns(2, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_nav_inbox", use_container_width=True):
                set_route(get_home_route(app_variant))
        with nav_cols[1]:
            if st.button("Sign out", key="care_hub_nav_sign_out", use_container_width=True):
                sign_out_user("care_hub")
    else:
        nav_cols = st.columns(4, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_nav_inbox", use_container_width=True):
                set_route(get_home_route(app_variant))
        with nav_cols[1]:
            if st.button("Service overview", key="care_hub_nav_service_overview", use_container_width=True):
                set_route("/public/service-overview")
        with nav_cols[2]:
            if st.button("Contracts", key="care_hub_nav_contracts", use_container_width=True):
                set_route("/contracts")
        with nav_cols[3]:
            if st.button("Sign out", key="care_hub_nav_sign_out", use_container_width=True):
                sign_out_user("care_hub")


def render_care_hub_instructions() -> None:
    app_variant = get_app_variant()
    if app_variant == VARIANT_OFFICE:
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def render_care_hub_training() -> None:
    app_variant = get_app_variant()
    if app_variant == VARIANT_OFFICE:
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def require_family_access() -> None:
    if get_app_variant() != VARIANT_FAMILY:
        wrong_variant_screen(get_route(), "Family pages are not available in this app.")
    active_role = st.session_state.get("active_role")
    if st.session_state.get("auth_uid") and active_role and active_role != "family":
        wrong_variant_screen(get_route(), "This signed-in session belongs to Care Hub.")
    if not st.session_state.get("auth_uid"):
        render_access_gate("Please sign in to access Family.", get_login_route(VARIANT_FAMILY), "family")
        st.stop()
    family_found, care_found, error, family_record, _ = get_mapping_status()
    if error:
        if (
            st.session_state.get("active_role") == "family"
            and st.session_state.get("access_token")
        ):
            return
        render_access_gate(
            "Session check failed. Please sign in again.",
            get_login_route(VARIANT_FAMILY),
            "family",
        )
        st.stop()
    if family_found:
        if family_record:
            st.session_state["active_role"] = "family"
            st.session_state["active_care_home_id"] = family_record.get("care_home_id")
        return
    if care_found:
        render_wrong_variant("Your login details are for Care Hub.")
        st.stop()
    render_access_gate("Account not set up yet.", get_login_route(VARIANT_FAMILY), "family")
    st.stop()


def require_care_access() -> None:
    if get_app_variant() not in {VARIANT_MOBILE, VARIANT_OFFICE}:
        wrong_variant_screen(get_route(), "Care Hub pages are not available in this app.")
    active_role = st.session_state.get("active_role")
    if st.session_state.get("auth_uid") and active_role and active_role != "care_hub":
        wrong_variant_screen(get_route(), "This signed-in session belongs to Family.")
    if not st.session_state.get("auth_uid"):
        render_access_gate(
            f"Please sign in to access {get_care_hub_label()}.",
            get_login_route(get_app_variant()),
            "care_hub",
        )
        st.stop()
    family_found, care_found, error, _, care_record = get_mapping_status()
    if error:
        if (
            st.session_state.get("active_role") == "care_hub"
            and st.session_state.get("access_token")
        ):
            return
        render_access_gate(
            f"Session check failed. Please sign in to access {get_care_hub_label()}.",
            get_login_route(get_app_variant()),
            "care_hub",
        )
        st.stop()
    if care_found:
        if care_record:
            st.session_state["active_role"] = "care_hub"
            st.session_state["active_care_home_id"] = care_record.get("care_home_id")
        if get_app_variant() == VARIANT_OFFICE and is_office_mfa_required():
            if get_route() != "/care-hub/mfa":
                set_route("/care-hub/mfa")
            st.stop()
        return
    if family_found:
        render_wrong_variant("Your login details are for Family.")
        st.stop()
    render_access_gate("Account not set up yet.", get_login_route(get_app_variant()), "care_hub")
    st.stop()


def is_office_mfa_required() -> bool:
    if get_app_variant() != VARIANT_OFFICE:
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
    if not access_token:
        return
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
    clear_auth_cookie()
    clear_session_state()
    set_route(get_default_route(get_app_variant()))


def enforce_session_timeout() -> None:
    last_active = st.session_state.get("last_active_at")
    now = time.time()
    if not st.session_state.get("auth_uid"):
        st.session_state["last_active_at"] = now
        return
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


def trigger_live_message_refresh(key: str, disabled: bool) -> None:
    if disabled or st_autorefresh is None or not APP_LIVE_REFRESH:
        return
    st_autorefresh(interval=7000, key=key)


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
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        st.markdown(
            f"""
<style>
  .vm-logo-row {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .vm-logo-row img {{
    width: 70px;
    height: auto;
  }}
  .vm-logo-row .vm-logo-text {{
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.1;
    margin-left: 8px;
    white-space: nowrap;
  }}
  @media (max-width: 768px) {{
    .vm-logo-row {{
      gap: 8px;
    }}
    .vm-logo-row img {{
      width: 56px;
    }}
    .vm-logo-row .vm-logo-text {{
      font-size: 0.78rem;
      margin-left: 0;
    }}
  }}
</style>
<div class="vm-logo-row">
  <img src="data:image/png;base64,{logo_b64}" alt="logo" />
  <span class="vm-logo-text">voice-message.com</span>
</div>
""",
            unsafe_allow_html=True,
        )
    except OSError:
        st.write("Logo missing")


def get_logo_data_uri() -> str:
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    try:
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{logo_b64}"


def render_route_transition_loader(duration_ms: int = 700) -> None:
    logo_data = get_logo_data_uri()
    logo_html = (
        f'<img class="vm-wait-logo" src="{logo_data}" alt="logo" />' if logo_data else ""
    )
    st.markdown(
        f"""
<style>
  .vm-wait-overlay {{
    position: fixed;
    inset: 0;
    z-index: 999999;
    background: rgba(255,255,255,0.97);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
  }}
  .vm-wait-logo {{
    width: 92px;
    height: auto;
    display: block;
    animation: vm-logo-fade 2.4s ease-in-out infinite;
  }}
  @keyframes vm-logo-fade {{
    0%, 100% {{ opacity: 0.28; transform: scale(0.98); }}
    50% {{ opacity: 1; transform: scale(1.02); }}
  }}
</style>
<div class="vm-wait-overlay" id="vmWaitOverlay">
  {logo_html}
</div>
<script>
  setTimeout(function() {{
    const el = document.getElementById('vmWaitOverlay');
    if (el) el.remove();
  }}, {max(180, duration_ms)});
</script>
""",
        unsafe_allow_html=True,
    )


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
        if app_variant == VARIANT_OFFICE:
            is_authed = bool(st.session_state.get("auth_uid"))
            if not is_authed:
                if st.button("Complaints & Concerns", key=f"{menu_key}_office_complaints_public"):
                    set_route("/public/complaints-and-concerns")
                    return
                if st.button("Go to login", key=f"{menu_key}_office_login"):
                    set_route(get_login_route(app_variant))
                    return
                if st.button("Privacy Notice", key=f"{menu_key}_office_privacy_public"):
                    set_route("/public/privacy-notice")
                    return
                if st.button("Service overview", key=f"{menu_key}_office_service_overview_public"):
                    set_route("/public/service-overview")
                    return
                return
        if app_variant not in (VARIANT_OFFICE, VARIANT_FAMILY, VARIANT_MOBILE) and prev_route and prev_route != current_route:
            render_route_link("Back", prev_route, key=f"{menu_key}_back_link")
            return
        if show_back_only and app_variant not in (VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE):
            return
        if app_variant == VARIANT_OFFICE:
            st.markdown("**Care Hub – Office**")
            clicked_action = None
            if st.button("Inbox", key=f"{menu_key}_inbox"):
                clicked_action = ("route", get_home_route(app_variant))
            if st.button("Register family member", key=f"{menu_key}_register_family"):
                clicked_action = ("route", "/care-hub/register-family")
            if st.button("Account & Security", key=f"{menu_key}_security"):
                clicked_action = ("route", "/care-hub/security")
            if st.button("Subscription & Billing", key=f"{menu_key}_billing"):
                clicked_action = ("route", "/billing")
            if st.button("Sign out", key=f"{menu_key}_office_sign_out"):
                clicked_action = ("sign_out", "care_hub")

            st.markdown("— Daily Use —")
            if st.button("Care Hub handbook", key=f"{menu_key}_office_doc_handbook"):
                clicked_action = ("doc", "docs/office/05_care_home_guide.md")
            if st.button("Registering a family member", key=f"{menu_key}_office_doc_register_family"):
                clicked_action = ("doc", "docs/office/10_registering_family_member.md")
            if st.button("Access summary (1 page)", key=f"{menu_key}_office_doc_access_summary"):
                clicked_action = ("doc", "docs/office/08_care_hub_access_summary.md")
            if st.button("Handover checklist", key=f"{menu_key}_office_doc_handover"):
                clicked_action = ("doc", "docs/office/care_home_handover_checklist.md")
            if st.button("Office Q&A", key=f"{menu_key}_office_doc_qa"):
                clicked_action = ("route", "/care-hub/office/qa")

            st.markdown("— Governance —")
            if st.button("Service overview", key=f"{menu_key}_office_service_overview"):
                clicked_action = ("route", "/public/service-overview")
            if st.button("Care home responsibilities", key=f"{menu_key}_office_doc_responsibilities"):
                clicked_action = ("doc", "docs/office/04_care_home_responsibilities.md")
            if st.button("Safeguarding & consent", key=f"{menu_key}_office_doc_safeguarding"):
                clicked_action = ("doc", "docs/office/09_safeguarding_consent.md")
            if st.button("Privacy notice", key=f"{menu_key}_office_privacy"):
                clicked_action = ("route", "/public/privacy-notice")

            st.markdown("— Formal —")
            if st.button("Complaints & concerns", key=f"{menu_key}_office_complaints"):
                clicked_action = ("route", "/public/complaints-and-concerns")
            if st.button("Contracts & templates", key=f"{menu_key}_contracts"):
                clicked_action = ("route", "/contracts")
            if clicked_action:
                action_type, payload = clicked_action
                if action_type == "route":
                    set_route(payload)
                elif action_type == "doc":
                    st.session_state["docs_active"] = payload
                    set_route("/docs")
                elif action_type == "sign_out":
                    sign_out_user(payload)
                return
            return
        if app_variant not in (VARIANT_OFFICE, VARIANT_MOBILE, VARIANT_FAMILY):
            if st.button("How it works", key=f"{menu_key}_how_it_works"):
                set_route(get_how_it_works_route(app_variant))
                return
        if app_variant not in (VARIANT_OFFICE, VARIANT_MOBILE, VARIANT_FAMILY):
            if st.button("Public documents", key=f"{menu_key}_public_docs"):
                set_route("/public/service-overview")
                return
        if app_variant == VARIANT_MOBILE:
            if st.button("Public documents", key=f"{menu_key}_mobile_public_docs"):
                set_route("/public/service-overview")
                return
            if st.button("Mobile Q&A", key=f"{menu_key}_mobile_qa"):
                set_route("/care-hub/mobile/qa")
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
            else:
                if st.button("Go to login", key=f"{menu_key}_mobile_login"):
                    set_route(get_login_route(app_variant))
                    return
            return
        if app_variant == "family":
            st.markdown("**Family**")
            is_authed = bool(st.session_state.get("auth_uid"))
            login_route = get_login_route(app_variant)
            back_target = get_home_route(app_variant)
            if (
                is_authed
                and prev_route
                and prev_route != current_route
                and prev_route != login_route
            ):
                back_target = prev_route
            render_route_link("Back", back_target, key=f"{menu_key}_family_back_link")
            render_route_link(
                "How it works",
                get_how_it_works_route(app_variant),
                key=f"{menu_key}_family_how_link",
            )
            render_route_link(
                "Service overview",
                "/public/service-overview",
                key=f"{menu_key}_family_service_overview_link",
            )
            render_route_link("Family Q&A", "/family/qa", key=f"{menu_key}_family_qa_link")
            render_route_link(
                "Family Terms of Use",
                "/family/terms-use",
                key=f"{menu_key}_family_terms_link",
            )
            render_route_link(
                "Contact the care home",
                "/family/contact",
                key=f"{menu_key}_family_contact_link",
            )
            render_route_link(
                "Family login",
                get_login_route(app_variant),
                key=f"{menu_key}_family_login_link",
            )
            return
        if st.session_state.get("auth_uid") and app_variant != "family":
            if st.button("Sign out", key=f"{menu_key}_sign_out"):
                role = "family" if app_variant == "family" else "care_hub"
                sign_out_user(role)


def render_page_header(
    page_title: str,
    brand_title: str | None = None,
    show_variant_subheading: bool = True,
    show_menu: bool = True,
) -> None:
    if get_app_variant() == "family" and not is_family_authenticated():
        show_menu = False
    if get_app_variant() == VARIANT_MOBILE and not is_care_authenticated():
        show_menu = False
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
  .vm-header-menu button {{
    font-size: 26px !important;
    line-height: 1 !important;
    padding: 0 6px !important;
  }}
  .vm-page-title {{
    margin: 12px 0 10px;
    font-size: 1.65rem !important;
    line-height: 1.2;
    font-weight: 700 !important;
  }}
  @media (max-width: 768px) {{
    .vm-header-strip {{
      padding: 4px 0 6px;
    }}
    .vm-header-menu button {{
      font-size: 22px !important;
      padding: 0 3px !important;
    }}
    .vm-page-title {{
      margin: 10px 0 8px;
      font-size: 1.22rem !important;
    }}
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="vm-header-strip">', unsafe_allow_html=True)
    cols = st.columns([0.82, 0.18], gap="small")
    with cols[0]:
        render_logo_row()
    with cols[1]:
        if show_menu:
            st.markdown('<div class="vm-header-menu">', unsafe_allow_html=True)
            menu_key = page_title.lower().replace(" ", "_")
            render_header_menu(menu_key)
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<h2 class="vm-page-title">{page_title}</h2>', unsafe_allow_html=True)


def render_front_page_descriptor() -> None:
    st.markdown(
        """
<style>
  .front-page-info-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">voice-message.com — for non-urgent social voice messages.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">One message kept at a time in each direction (between each authorised contact and each resident), with no threads.</div>',
        unsafe_allow_html=True,
    )


def render_how_it_works_general() -> None:
    st.markdown(
        "Only one message is kept between each authorised contact and each resident, in each direction, with no threads.  \n"
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
                    set_route(get_login_route(get_app_variant()))
                    return
                if key.endswith("_home"):
                    if key.startswith("family_"):
                        if st.session_state.get("auth_uid"):
                            set_route(get_home_route(VARIANT_FAMILY))
                        else:
                            st.session_state["force_family_login"] = True
                            set_route(get_login_route(VARIANT_FAMILY))
                    else:
                        set_route(get_home_route(get_app_variant()))
                elif key.endswith("_back"):
                    if "family_send" in key:
                        set_route(get_login_route(VARIANT_FAMILY))
                    elif "family_sent" in key:
                        set_route(get_home_route(VARIANT_FAMILY))
                    elif "family_login" in key:
                        set_route(get_home_route(VARIANT_FAMILY))
                    elif "care_login" in key:
                        set_route(get_login_route(get_app_variant()))
                    elif "care_inbox" in key:
                        set_route(get_login_route(get_app_variant()))
                    elif "care_play" in key:
                        set_route(get_home_route(get_app_variant()))
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
    background: rgba(255, 204, 230, 0.25) !important;
    color: {TOKENS["text"]} !important;
    border: 1px solid rgba(31,31,31,0.2) !important;
    border-radius: 10px !important;
  }}
  .vm-login .stTextInput input::placeholder {{
    color: rgba(31,31,31,0.55) !important;
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
                f'<img src="{logo_data}" alt="logo" style="height:84px;width:auto;display:block;" />'
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
            <p>Non-urgent voice messaging between residents in care homes and Family.</p>
            <p>In this service, 'Family' means authorised contacts approved by the care home, such as family members or close friends.</p>
            <p>Each Family channel is 1:1 with the resident. This is not a shared thread.</p>
            <p>Within each channel, only two messages are kept: the latest in each direction.</p>
            <p>No archive, no message history, and no scrolling thread.</p>
            <p>Not live messaging. Staff play and record messages when available within normal care routines.</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-grid public-grid-3">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-card">
              <h3>1:1 channels</h3>
              <div>Each Family sender has a separate channel with the resident.</div>
            </div>
            <div class="public-card pink">
              <h3>Two messages kept</h3>
              <div>Only the latest Family message and latest resident reply are stored in each channel.</div>
            </div>
            <div class="public-card">
              <h3>Role-based access</h3>
              <div>Family and Care Hub are separate role-based experiences.</div>
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
              <div class="public-step">1) A Family sender records a short message for the resident.</div>
              <div class="public-step">2) Staff play the message when available within normal routines.</div>
              <div class="public-step">3) A resident reply is recorded with staff support.</div>
              <div class="public-step">4) A new message replaces the previous message in that direction.</div>
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

        st.markdown('<div class="public-footer">', unsafe_allow_html=True)
        footer_cols = st.columns(4, gap="small")
        with footer_cols[0]:
            render_route_link(
                "Privacy Notice",
                "/public/privacy-notice",
                key="public_footer_privacy_link",
            )
        with footer_cols[1]:
            render_route_link(
                "Safeguarding & Consent",
                "/public/safeguarding-and-consent",
                key="public_footer_safeguarding_link",
            )
        with footer_cols[2]:
            render_route_link(
                "Complaints & Concerns",
                "/public/complaints-and-concerns",
                key="public_footer_complaints_link",
            )
        with footer_cols[3]:
            render_route_link(
                "Family Terms",
                "/public/family-terms-of-use",
                key="public_footer_family_terms_link",
            )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    st.markdown('<div class="vm-wrap vm-stage">', unsafe_allow_html=True)
    st.markdown("### Service overview")
    st.markdown(
        "voice-message.com  \n"
        "One message in. One message out.  \n"
        "No threads. No pressure.\n\n"
        "Only the most recent message from an approved family member or friend and the most recent reply from the resident are kept.  \n"
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
                set_route(get_login_route(VARIANT_FAMILY))
        with button_cols[1]:
            if st.button("Care Hub – Mobile", key="tab_care_mobile", use_container_width=True):
                set_route(get_login_route(VARIANT_MOBILE))
        with button_cols[2]:
            if st.button("Care Hub – Office", key="tab_care_office", use_container_width=True):
                set_route(get_login_route(VARIANT_OFFICE))

    # Homepage buttons are handled above (Family / Care Hub – Mobile / Care Hub – Office).

    st.markdown('<div style="margin-top:-8px;"></div>', unsafe_allow_html=True)


def get_route() -> str:
    if hasattr(st, "query_params"):
        route = st.query_params.get("route", "")
    else:
        route = st.experimental_get_query_params().get("route", [""])[0]
    if isinstance(route, list):
        route = route[0] if route else ""
    return normalize_route(route) or "/"


# Canonical runtime variants. These must stay aligned with config.get_app_variant().
VARIANT_PUBLIC = "public"
VARIANT_FAMILY = "family"
VARIANT_MOBILE = "mobile"
VARIANT_OFFICE = "office"

FAMILY_LOGIN_ROUTE = "/family/login"
FAMILY_HOME_ROUTE = "/family/send"
OFFICE_LOGIN_ROUTE = "/care-hub/login"
OFFICE_HOME_ROUTE = "/care-hub/inbox"
MOBILE_LOGIN_ROUTE = "/care-hub/mobile/login"
MOBILE_HOME_ROUTE = "/care-hub/mobile/inbox"
PUBLIC_HOME_ROUTE = "/service-overview"
FAMILY_PUBLIC_ROUTES = {
    "/family/login",
}
OFFICE_PUBLIC_ROUTES = {
    "/care-hub/login",
    "/public/service-overview",
    "/public/how-it-works",
    "/public/resident-participation",
    "/public/family-guide",
    "/public/qa",
    "/public/faq",
    "/public/privacy-notice",
    "/public/family-terms-of-use",
    "/public/complaints-and-concerns",
    "/public/safeguarding-and-consent",
    "/care-hub/mobile/qa",
}
MOBILE_PUBLIC_ROUTES = {
    "/care-hub/mobile/login",
    "/care-hub/login",
    "/care-hub-mobile/how-it-works",
    "/how-it-works/mobile",
    "/public/service-overview",
    "/public/how-it-works",
    "/public/resident-participation",
    "/public/family-guide",
    "/public/qa",
    "/public/faq",
    "/public/privacy-notice",
    "/public/family-terms-of-use",
    "/public/complaints-and-concerns",
    "/public/safeguarding-and-consent",
}

VARIANT_CONFIG = {
    VARIANT_FAMILY: {
        "label": "Family app",
        "default_route": FAMILY_LOGIN_ROUTE,
        "how_it_works_route": "/family/how-it-works",
        "allowed_routes": {
            FAMILY_LOGIN_ROUTE,
            FAMILY_HOME_ROUTE,
            "/family/sent",
            "/family/privacy",
            "/family/terms-use",
            "/family/contact",
            "/family/qa",
            "/how-it-works/family",
            "/family/how-it-works",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_MOBILE: {
        "label": "Care Hub – Mobile",
        "default_route": MOBILE_LOGIN_ROUTE,
        "how_it_works_route": "/care-hub-mobile/how-it-works",
        "allowed_routes": {
            MOBILE_LOGIN_ROUTE,
            MOBILE_HOME_ROUTE,
            OFFICE_LOGIN_ROUTE,
            OFFICE_HOME_ROUTE,
            "/care-hub/instructions",
            "/care-hub/training",
            "/how-it-works/mobile",
            "/care-hub-mobile/how-it-works",
            "/care-hub/mobile/qa",
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_OFFICE: {
        "label": "Care Hub – Office",
        "default_route": OFFICE_LOGIN_ROUTE,
        "how_it_works_route": "/care-hub-office/how-it-works",
        "allowed_routes": {
            OFFICE_LOGIN_ROUTE,
            OFFICE_HOME_ROUTE,
            "/care-hub/register-family",
            "/care-hub/instructions",
            "/care-hub/training",
            "/care-hub/security",
            "/care-hub/mfa",
            "/care-hub/office/qa",
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
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_PUBLIC: {
        "label": "Public",
        "default_route": PUBLIC_HOME_ROUTE,
        "how_it_works_route": PUBLIC_HOME_ROUTE,
        "allowed_routes": {
            "/pr-home",
            PUBLIC_HOME_ROUTE,
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
        },
    },
}


def get_app_variant() -> str:
    return resolve_app_variant()


def get_raw_app_variant() -> str:
    return __import__("os").getenv("APP_VARIANT", "").strip()


def get_variant_label(app_variant: str) -> str:
    return VARIANT_CONFIG.get(app_variant, {}).get("label", "Unknown")


def get_default_route(app_variant: str) -> str:
    return VARIANT_CONFIG.get(app_variant, {}).get("default_route", "/")


def get_login_route(app_variant: str) -> str:
    if app_variant == VARIANT_FAMILY:
        return FAMILY_LOGIN_ROUTE
    if app_variant == VARIANT_MOBILE:
        return MOBILE_LOGIN_ROUTE
    if app_variant == VARIANT_OFFICE:
        return OFFICE_LOGIN_ROUTE
    return PUBLIC_HOME_ROUTE


def get_home_route(app_variant: str) -> str:
    if app_variant == VARIANT_FAMILY:
        return FAMILY_HOME_ROUTE
    if app_variant == VARIANT_MOBILE:
        return MOBILE_HOME_ROUTE
    if app_variant == VARIANT_OFFICE:
        return OFFICE_HOME_ROUTE
    return PUBLIC_HOME_ROUTE


def variant_requires_auth(app_variant: str) -> bool:
    return app_variant in {VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}


def is_login_route_for_variant(app_variant: str, route: str) -> bool:
    if route == get_login_route(app_variant):
        return True
    if app_variant == VARIANT_MOBILE and route == OFFICE_LOGIN_ROUTE:
        return True
    return False


def is_public_route_for_variant(app_variant: str, route: str) -> bool:
    route = normalize_route(route)
    if app_variant == VARIANT_FAMILY:
        return route in FAMILY_PUBLIC_ROUTES
    if app_variant == VARIANT_OFFICE:
        return route in OFFICE_PUBLIC_ROUTES
    if app_variant == VARIANT_MOBILE:
        return route in MOBILE_PUBLIC_ROUTES
    if app_variant == VARIANT_PUBLIC:
        return True
    return False


def redirect_if_not_authenticated(app_variant: str, current_route: str) -> bool:
    if app_variant == VARIANT_FAMILY:
        return False
    if not variant_requires_auth(app_variant):
        return False
    is_variant_authed = (
        is_family_authenticated()
        if app_variant == VARIANT_FAMILY
        else is_care_authenticated()
    )
    is_authed = bool(st.session_state.get("auth_uid"))
    login_route = get_login_route(app_variant)
    home_route = get_home_route(app_variant)
    if (
        not is_authed
        and not is_login_route_for_variant(app_variant, current_route)
        and not is_public_route_for_variant(app_variant, current_route)
    ):
        set_route(login_route)
        st.stop()
        return True
    if is_variant_authed and is_login_route_for_variant(app_variant, current_route):
        set_route(home_route)
        st.stop()
        return True
    return False


def get_office_home_route(is_authed: bool) -> str:
    return get_home_route(VARIANT_OFFICE) if is_authed else get_login_route(VARIANT_OFFICE)


def validate_supabase_config_for_variant(app_variant: str) -> None:
    auth_required_variants = {VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}
    if app_variant not in auth_required_variants:
        return
    url, anon_key = get_supabase_config()
    if url and anon_key:
        return
    st.error(
        "Supabase configuration is missing.\n\n"
        "For Streamlit Community Cloud, set secrets in:\n"
        "Settings -> Secrets\n\n"
        'SUPABASE_URL="..."\n'
        'SUPABASE_ANON_KEY="..."\n\n'
        "Only the anon key is supported in Streamlit apps."
    )
    st.stop()


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
    if app_variant == VARIANT_MOBILE:
        return "Care Hub – Mobile"
    if app_variant == VARIANT_OFFICE:
        return "Care Hub – Office"
    return "Care Hub"


def render_family_login_hub() -> None:
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
  [data-testid="collapsedControl"] {{
    display: none !important;
  }}
  [data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
  }}
  [data-testid="stSidebar"] {{
    display: none !important;
  }}
  [data-testid="stSidebarNav"] {{
    display: none !important;
  }}
  [data-testid="stPopover"] {{
    display: none !important;
  }}
  .vm-header-menu {{
    display: none !important;
  }}
  button[kind="header"] {{
    display: none !important;
  }}
  a[download], button[title="Download"] {{
    display: none !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header(
        "Voice Message — Family",
        brand_title="voice-message.com",
        show_variant_subheading=False,
        show_menu=False,
    )
    st.markdown(
        """
<style>
  .family-login-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    login_info_boxes = [
        "Send one social voice message to a resident. The care team manages playback and support.",
        "Only the latest message is kept.",
        "For urgent matters or safeguarding concerns, contact the care home directly.",
    ]
    for box in login_info_boxes:
        st.markdown(f'<div class="family-login-box">{box}</div>', unsafe_allow_html=True)
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)

    st.markdown("### Login")
    email = st.text_input("Email", key="family_login_email")
    password = st.text_input("Password", type="password", key="family_login_password")
    normalized_email = email.strip().lower()
    normalized_password = password.strip()
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
        elif not normalized_email or not normalized_password:
            st.error("Please enter both email and password.")
        else:
            try:
                auth = supabase.auth.sign_in_with_password(
                    {"email": normalized_email, "password": normalized_password}
                )
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                st.error(str(exc))
            else:
                if not auth or not auth.user:
                    st.error("Invalid login credentials.")
                    st.caption(f"Tried email: {normalized_email}")
                else:
                    st.session_state["auth_uid"] = auth.user.id
                    st.session_state["access_token"] = auth.session.access_token
                    st.session_state["refresh_token"] = auth.session.refresh_token
                    persist_auth_cookie(st.session_state.get("refresh_token"))
                    st.session_state["auth_email"] = normalized_email
                    family_found, care_found, mapping_error, family_record, care_record = (
                        get_mapping_status()
                    )
                    if family_found:
                        if family_record:
                            st.session_state["active_role"] = "family"
                            st.session_state["active_care_home_id"] = family_record.get(
                                "care_home_id"
                            )
                            st.session_state["family_display_name"] = (
                                (family_record.get("display_name") or "").strip()
                                or "Family member"
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
                        set_route(get_home_route(VARIANT_FAMILY))
                    elif care_found:
                        st.error("Wrong app variant")
                        st.info("Your login details are for Care Hub.")
                        if st.button("Log out", key="family_login_wrong_logout_after"):
                            sign_out_user("family")
                    else:
                        if mapping_error:
                            st.error(mapping_error)
                            st.info("Please sign in again.")
                        else:
                            st.error("Account not set up yet.")

    if sign_out_pressed:
        sign_out_user("family")
    if forgot_pressed:
        ok, message = send_password_reset_email(normalized_email, app_variant=VARIANT_FAMILY)
        if ok:
            st.success(message)
        else:
            st.error(message)

    # Logged-out Family view is intentionally login-only to avoid pre-login routing issues.


def render_family_login() -> None:
    force_login = st.session_state.pop("force_family_login", False)
    if st.session_state.get("auth_uid") and not force_login:
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if family_found:
            if family_record:
                st.session_state["active_role"] = "family"
                st.session_state["active_care_home_id"] = family_record.get("care_home_id")
                st.session_state["family_display_name"] = (
                    (family_record.get("display_name") or "").strip()
                    or st.session_state.get("family_display_name")
                    or "Family member"
                )
            set_route(get_home_route(VARIANT_FAMILY))
        elif care_found:
            st.error("Wrong app variant")
            st.info("Your login details are for Care Hub.")
            if st.button("Log out", key="family_login_wrong_logout"):
                sign_out_user("family")
        else:
            if error:
                st.error(error)
                st.info("Please sign in again.")
            else:
                st.error("Account not set up yet.")
        return
    render_family_login_hub()


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
    has_pending_recording = any(
        bool((entry or {}).get("recording_bytes"))
        for entry in send_state.values()
        if isinstance(entry, dict)
    )
    trigger_live_message_refresh("family_live_refresh", disabled=has_pending_recording)
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
    else:
        if manual_active and active_rec_id and active_rec_id not in resident_ids:
            active_rec_id = None
            st.session_state["family_active_rec_resident"] = None
        if not manual_active:
            active_rec_id = None
            st.session_state["family_active_rec_resident"] = None
    for resident in residents:
        resident_id = resident["id"]
        state = send_state.setdefault(
            resident_id,
            {
                "recording_bytes": None,
                "recording_mime_type": "audio/wav",
                "preview_confirmed": False,
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
        latest_sent = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            contact_user_id=st.session_state.get("auth_uid"),
        )
        if not latest_sent:
            latest_sent = fetch_latest_message(
                resident_id,
                "to_resident",
                access_token,
            )
        latest_sent_audio = decode_audio_payload(latest_sent)
        if latest_sent and not state.get("recording_bytes"):
            st.caption("Latest sent message:")
            if latest_sent_audio:
                st.audio(
                    latest_sent_audio,
                    format=latest_sent.get("audio_mime_type") or "audio/wav",
                )
            else:
                st.success("Latest sent message is saved.")
            latest_sent_at = latest_sent.get("recorded_at")
            if latest_sent_at:
                st.caption(f"Sent at: {latest_sent_at}")
        last_message = state.get("last_message") or {}
        if last_message and not state.get("recording_bytes"):
            sent_at = last_message.get("sent_at")
            sent_display = sent_at or "Unknown time"
            if sent_at:
                try:
                    sent_display = (
                        __import__("datetime")
                        .datetime.fromisoformat(sent_at.replace("Z", ""))
                        .strftime("%Y-%m-%d %H:%M")
                    )
                except Exception:
                    sent_display = sent_at
            st.success("Message sent")
            st.caption(f"Sent at: {sent_display}")
            if st.button(
                "Record new message (replaces previous)",
                key=f"family_record_new_{resident_id}",
            ):
                state["recording_bytes"] = None
                state["recording_mime_type"] = "audio/wav"
                state["preview_confirmed"] = False
                state["last_message"] = None
                st.session_state.pop(f"family_upload_{resident_id}", None)
                st.session_state.pop(f"family_audio_input_{resident_id}", None)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        native_recording_available = hasattr(st, "audio_input")
        if native_recording_available:
            recorded_from_native = st.audio_input(
                "Record voice message",
                key=f"family_audio_input_{resident_id}",
            )
            if recorded_from_native is not None:
                native_bytes = recorded_from_native.getvalue()
                if native_bytes and native_bytes != state.get("recording_bytes"):
                    state["recording_bytes"] = native_bytes
                    state["recording_mime_type"] = (
                        getattr(recorded_from_native, "type", None) or "audio/wav"
                    )
                    state["preview_confirmed"] = False
                    state["last_message"] = None
        else:
            st.warning(
                "Recording is unavailable in this browser. Please allow microphone access."
            )
        if state.get("recording_bytes"):
            st.caption("Captured message preview:")
            st.audio(
                state["recording_bytes"],
                format=state.get("recording_mime_type") or "audio/wav",
            )
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
            "Send message",
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
                    audio_mime_type = state.get("recording_mime_type") or "audio/wav"
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    now_iso = __import__("datetime").datetime.utcnow().isoformat()
                    payload = {
                        "resident_id": resident_id,
                        "contact_user_id": st.session_state.get("auth_uid"),
                        "direction": "to_resident",
                        "audio_storage_path": audio_b64,
                        "audio_mime_type": audio_mime_type,
                        "audio_bytes": len(audio_bytes),
                        "recorded_at": now_iso,
                    }
                    try:
                        try:
                            resp = (
                                supabase.rpc(
                                    "insert_family_message",
                                    {
                                        "p_resident_id": resident_id,
                                        "p_audio_storage_path": audio_b64,
                                        "p_audio_mime_type": audio_mime_type,
                                        "p_audio_bytes": len(audio_bytes),
                                        "p_recorded_at": now_iso,
                                    },
                                ).execute()
                            )
                        except Exception as rpc_exc:
                            # If RPC is unavailable or fails in this environment,
                            # fall back to direct upsert so Family->Resident writes still succeed.
                            try:
                                resp = (
                                    supabase.table("messages")
                                    .upsert(
                                        payload,
                                        on_conflict="resident_id,contact_user_id,direction",
                                    )
                                    .select("*")
                                    .execute()
                                )
                            except Exception:
                                raise rpc_exc
                    except Exception as exc:  # pragma: no cover - Supabase runtime error
                        st.error(str(exc))
                    else:
                        message_id = (
                            (resp.data[0].get("id") if isinstance(resp.data, list) and resp.data else None)
                            if resp is not None
                            else None
                        )
                        log_audit_event(
                            "message_sent",
                            "family",
                            resident["care_home_id"],
                            message_id,
                        )
                        state["recording_bytes"] = None
                        state["recording_mime_type"] = "audio/wav"
                        state["preview_confirmed"] = False
                        state["last_message"] = {"sent_at": now_iso}
                        st.session_state.pop(f"family_upload_{resident_id}", None)
                        st.session_state.pop(f"family_audio_input_{resident_id}", None)
                        st.rerun()


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
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", get_home_route(VARIANT_FAMILY), key="family_sent_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key="family_sent_home_link",
        )
    with action_cols[2]:
        if st.button("Sign out", key="family_sent_sign_out"):
            sign_out_user("family")


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
            "title": "Registering a family member",
            "path": "docs/office/10_registering_family_member.md",
            "summary": "How to invite and link an authorised family contact.",
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

    active_path = st.session_state.get("docs_active")
    if active_path:
        active_doc = next((doc for doc in docs if doc["path"] == active_path), None)
        st.markdown(f"## {(active_doc['title'] if active_doc else 'Document')}")
        if active_path.endswith("common_questions_qa.md"):
            render_qa_document(active_path, search_key="office_common_qa_search")
        else:
            render_document_boxes(active_path, strip_first_heading=True)
    else:
        for idx, doc in enumerate(docs):
            cols = st.columns([4, 1], gap="small")
            with cols[0]:
                st.markdown(f"**{doc['title']}**\n\n{doc['summary']}")
            with cols[1]:
                if st.button("Open", key=f"docs_open_{idx}"):
                    st.session_state["docs_active"] = doc["path"]
                    st.rerun()
            st.write("")
            st.write("")

    render_route_link(
        "Back to Care Hub – Office",
        get_office_home_route(bool(st.session_state.get("auth_uid"))),
        key="docs_home_link",
    )


def render_document_content(
    doc_path: str, include_logo: bool = True, strip_first_heading: bool = False
) -> None:
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
        # Remove one or more leading markdown logo image lines.
        content = re.sub(r"\A(?:\s*!\[[^\]]*\]\([^)]+\)\s*\n+)+", "", content, count=1)
        if strip_first_heading:
            content = re.sub(r"\A\s*#\s+.+?\n+", "", content, count=1)
        if include_logo:
            content = inject_logo_into_markdown(content)
        st.markdown(content)
    except OSError:
        st.error("Document not found.")


def render_document_boxes(doc_path: str, strip_first_heading: bool = True) -> None:
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
    except OSError:
        st.error("Document not found.")
        return
    content = re.sub(r"\A(?:\s*!\[[^\]]*\]\([^)]+\)\s*\n+)+", "", content, count=1)
    if strip_first_heading:
        content = re.sub(r"\A\s*#\s+.+?\n+", "", content, count=1)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    st.markdown(
        """
<style>
  .service-overview-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
    white-space: pre-line;
  }
  .service-overview-box input[type="checkbox"] {
    transform: scale(1.35);
    margin-right: 10px;
    accent-color: #4aa7a0;
    vertical-align: middle;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    def _render_box(markdown_text: str) -> None:
        raw_text = markdown_text.strip()
        if re.fullmatch(r"[-*_]{3,}", raw_text):
            return
        text = re.sub(r"^\s*[-*]\s+", "• ", raw_text, flags=re.M).strip()
        if re.fullmatch(r"[•\-\*\s]+", text):
            return
        if not text:
            return
        st.markdown(f'<div class="service-overview-box">{text}</div>', unsafe_allow_html=True)

    for block in blocks:
        lines = block.splitlines()
        if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
            st.markdown(lines[0])
            _render_box("\n".join(lines[1:]))
            continue
        _render_box(block)


def render_qa_document(doc_path: str, search_key: str, strip_first_heading: bool = True) -> None:
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
    except OSError:
        st.error("Document not found.")
        return

    content = re.sub(r"\A(?:\s*!\[[^\]]*\]\([^)]+\)\s*\n+)+", "", content, count=1)
    if strip_first_heading:
        content = re.sub(r"\A\s*#\s+.+?\n+", "", content, count=1)

    qa_pairs = re.findall(r"(?ms)^Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:\s*|\Z)", content)
    if not qa_pairs:
        render_document_boxes(doc_path, strip_first_heading=strip_first_heading)
        return

    query = st.text_input(
        "Search questions and answers",
        key=search_key,
        placeholder="Type a keyword (e.g. urgent, privacy, consent)",
    ).strip()
    query_lower = query.lower()
    effective_query = query_lower
    if "urgent" in query_lower:
        # Treat all urgent-related search phrases the same as "urgent".
        effective_query = "urgent"

    if effective_query:
        filtered_pairs = [
            (question, answer)
            for question, answer in qa_pairs
            if effective_query in question.lower() or effective_query in answer.lower()
        ]
    else:
        filtered_pairs = qa_pairs

    st.caption(f"Showing {len(filtered_pairs)} of {len(qa_pairs)} questions")
    if not filtered_pairs:
        st.info("No matching questions found.")
        return

    for idx, (question, answer) in enumerate(filtered_pairs, start=1):
        with st.expander(f"{idx}. {question.strip()}"):
            st.markdown(answer.strip())


def get_public_document_title(doc_path: str) -> str:
    mapping = {
        "03_service_overview.md": "Service overview",
        "02_how_it_works.md": "How it works",
        "07_resident_participation.md": "Resident participation",
        "06_family_guide.md": "Family guide",
        "10_faq.md": "Public Q&A",
        "privacy_policy.md": "Privacy notice",
        "family_terms_of_use.md": "Family Terms of Use",
        "complaints_and_concerns.md": "Complaints & Concerns",
        "safeguarding_and_consent.md": "Safeguarding and Consent",
    }
    for suffix, title in mapping.items():
        if doc_path.endswith(suffix):
            return title
    return "Service overview"


def render_public_document(doc_path: str, back_route: str = "/service-overview") -> None:
    # Render all public documents in the boxed style for consistency.
    use_boxes = True
    use_qa_search = doc_path.endswith("10_faq.md")
    app_variant = get_app_variant()
    if app_variant == VARIANT_PUBLIC:
        st.markdown(f"[← Back to Service overview](?route={back_route})")
        render_page_header(get_public_document_title(doc_path), show_menu=False, show_variant_subheading=False)
        if use_qa_search:
            render_qa_document(doc_path, search_key="public_faq_search")
        elif use_boxes:
            render_document_boxes(doc_path, strip_first_heading=True)
        else:
            render_document_content(doc_path)
        return
    if app_variant == VARIANT_FAMILY:
        render_page_header(get_public_document_title(doc_path), show_variant_subheading=False)
        render_route_link(
            "← Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key="public_doc_back_family_login_link",
        )
        if use_qa_search:
            render_qa_document(doc_path, search_key="family_faq_search")
        elif use_boxes:
            render_document_boxes(doc_path, strip_first_heading=True)
        else:
            render_document_content(doc_path, include_logo=False, strip_first_heading=True)
        return
    if app_variant == VARIANT_OFFICE:
        is_authed = bool(st.session_state.get("auth_uid"))
        office_home_route = get_office_home_route(is_authed)
        render_page_header(get_public_document_title(doc_path), show_variant_subheading=False)
        render_route_link(
            "← Back to dashboard",
            office_home_route,
            key="public_doc_back_office_dashboard_link",
        )
        if use_qa_search:
            render_qa_document(doc_path, search_key="office_faq_search")
        elif use_boxes:
            render_document_boxes(doc_path, strip_first_heading=True)
        else:
            render_document_content(doc_path, include_logo=False)
        return
    if app_variant == VARIANT_MOBILE:
        render_page_header(get_public_document_title(doc_path))
        render_route_link(
            "Back",
            get_home_route(app_variant),
            key="public_doc_back_mobile_link",
        )
        if use_qa_search:
            render_qa_document(doc_path, search_key="mobile_faq_search")
        elif use_boxes:
            render_document_boxes(doc_path, strip_first_heading=True)
        else:
            render_document_content(doc_path)
        return
    render_route_link(
        "← Back to Service overview",
        back_route,
        key="public_doc_back_service_overview_top",
    )
    render_page_header(get_public_document_title(doc_path), show_menu=False, show_variant_subheading=False)
    if use_qa_search:
        render_qa_document(doc_path, search_key="fallback_faq_search")
    elif use_boxes:
        render_document_boxes(doc_path, strip_first_heading=True)
    else:
        render_document_content(doc_path)
    render_route_link(
        "← Back to Service overview",
        back_route,
        key="public_doc_back_service_overview_bottom",
    )


def render_public_docs() -> None:
    app_variant = get_app_variant()
    if app_variant == VARIANT_PUBLIC:
        set_route("/public/service-overview")
        st.stop()

    render_page_header("Public Documents")
    if app_variant == VARIANT_FAMILY:
        render_route_link(
            "← Back to Family login",
            get_login_route(VARIANT_FAMILY),
            key="public_docs_back_family_login_link",
        )
    if app_variant == VARIANT_OFFICE:
        render_route_link(
            "← Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="public_docs_back_office_dashboard_link",
        )
    st.write("Select a public document to view.")

    public_docs = [
        ("Service overview", "/public/service-overview"),
        ("How it works", "/public/how-it-works"),
        ("Resident participation", "/public/resident-participation"),
        ("Family guide", "/public/family-guide"),
        ("Public Q&A", "/public/qa"),
        ("Privacy notice", "/public/privacy-notice"),
        ("Family terms of use", "/public/family-terms-of-use"),
        ("Complaints and concerns", "/public/complaints-and-concerns"),
        ("Safeguarding and consent", "/public/safeguarding-and-consent"),
    ]

    for idx, (label, route) in enumerate(public_docs):
        if st.button(label, key=f"public_docs_open_{idx}", use_container_width=True):
            set_route(route)

    if app_variant == VARIANT_OFFICE:
        is_authed = bool(st.session_state.get("auth_uid"))
        render_route_link(
            "Back to Care Hub – Office",
            get_office_home_route(is_authed),
            key="public_docs_back_office_link",
        )
    elif app_variant == VARIANT_MOBILE:
        render_route_link(
            "Back to Care Hub – Mobile",
            get_home_route(app_variant),
            key="public_docs_back_mobile_link",
        )


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
        '<div class="pr-subheading">Non-urgent social voice messages between residents in care homes and their authorised contacts (such as family members or close friends).</div>',
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
            "Family use the Family app to record short voice messages for residents. "
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
    if get_app_variant() != VARIANT_OFFICE:
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
            qr_image = qr.get_image() if hasattr(qr, "get_image") else qr
            st.image(qr_image, caption="Scan this QR code with your authenticator app.")
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

    render_route_link(
        "Back to Care Hub – Office",
        get_office_home_route(bool(st.session_state.get("auth_uid"))),
        key="mfa_back_office_link",
    )


def render_care_hub_mfa() -> None:
    render_page_header("Two-factor verification")
    access_token = st.session_state.get("access_token")
    auth_uid = st.session_state.get("auth_uid")
    if not auth_uid:
        render_access_gate(
            "Please sign in to access Care Hub – Office.",
            get_login_route(get_app_variant()),
            "care_hub",
        )
        return
    record = get_care_hub_mfa_record(access_token, auth_uid)
    if not record or not record.get("enabled"):
        st.info("Two-factor authentication is not enabled for this account.")
        if st.button("Continue", key="mfa_not_enabled_continue"):
            set_route(get_home_route(get_app_variant()))
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
            set_route(get_home_route(get_app_variant()))
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
    render_page_header("Contracts & templates")
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
        render_document_boxes(active_path, strip_first_heading=True)
        if st.button("Close", key="contracts_close"):
            st.session_state["contracts_active"] = ""

    render_route_link(
        "Back to Care Hub – Office",
        get_office_home_route(bool(st.session_state.get("auth_uid"))),
        key="contracts_home_link",
    )


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
  .billing-box {{
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header("Subscription & Billing")

    def billing_box(text: str) -> None:
        st.markdown(f'<div class="billing-box">{text}</div>', unsafe_allow_html=True)

    st.markdown("## Current Status")
    billing_box("Status: Pilot (example)")

    st.markdown("## Current Plan")
    billing_box("Up to 50 residents: £195 + VAT per month")
    billing_box("51+ residents: £295 + VAT per month")

    st.markdown("## Pilot Details (if applicable)")
    billing_box("£75 + VAT one-time pilot fee")
    billing_box("Credited against first month if continuing")

    st.markdown("## Billing Terms")
    billing_box("Invoiced monthly in advance")
    billing_box("Activation only after payment is received")
    billing_box("Minimum 3-month commitment following pilot")

    st.markdown("## Invoices")
    billing_box("Invoice reference: [placeholder]")
    billing_box("Invoice download functionality will be available here.")

    render_route_link(
        "Back to Care Hub – Office",
        get_office_home_route(bool(st.session_state.get("auth_uid"))),
        key="billing_home_link",
    )


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
        show_menu=app_variant != VARIANT_OFFICE,
    )
    if app_variant == VARIANT_MOBILE:
        st.markdown(
            """
<style>
  .care-login-box {
    width: 100%;
    background: rgba(153, 255, 255, 0.25);
    border: 1px solid #b7ddd7;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 0 0 12px 0;
    box-sizing: border-box;
    line-height: 1.5;
  }
</style>
""",
            unsafe_allow_html=True,
        )
        mobile_login_boxes = [
            "Care Hub - Mobile supports non-urgent social voice messages between residents and families.",
            "Not a live service. Messages are played and recorded when staff are available.",
        ]
        for box in mobile_login_boxes:
            st.markdown(f'<div class="care-login-box">{box}</div>', unsafe_allow_html=True)
    elif app_variant == VARIANT_OFFICE:
        pass
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)
    if st.session_state.get("auth_uid"):
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if care_found:
            if care_record:
                st.session_state["active_role"] = "care_hub"
                st.session_state["active_care_home_id"] = care_record.get("care_home_id")
            if app_variant == VARIANT_OFFICE and is_office_mfa_required():
                set_route("/care-hub/mfa")
            else:
                set_route(get_home_route(app_variant))
        elif family_found:
            st.error("Wrong app variant")
            st.info("Your login details are for Family.")
            if st.button("Log out", key="care_login_wrong_logout"):
                sign_out_user("care_hub")
        else:
            if error:
                st.error(error)
                st.info("Please sign in again.")
            else:
                st.error("Account not set up yet.")
        return

    email = st.text_input("Email", key="care_login_email")
    password = st.text_input("Password", type="password", key="care_login_password")
    normalized_email = email.strip().lower()
    normalized_password = password.strip()

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

    if submit_login:
        supabase, error = get_supabase_client()
        if error:
            st.error(error)
        elif not normalized_email or not normalized_password:
            st.error("Please enter both email and password.")
        else:
            try:
                auth = supabase.auth.sign_in_with_password(
                    {"email": normalized_email, "password": normalized_password}
                )
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                st.error(str(exc))
            else:
                if not auth or not auth.user:
                    st.error("Invalid login credentials.")
                    st.caption(f"Tried email: {normalized_email}")
                else:
                    st.session_state["auth_uid"] = auth.user.id
                    st.session_state["access_token"] = auth.session.access_token
                    st.session_state["refresh_token"] = auth.session.refresh_token
                    persist_auth_cookie(st.session_state.get("refresh_token"))
                    st.session_state["auth_email"] = normalized_email
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
                        if app_variant == VARIANT_OFFICE and is_office_mfa_required():
                            set_route("/care-hub/mfa")
                        else:
                            set_route(get_home_route(app_variant))
                    elif family_found:
                        st.error("Wrong app variant")
                        st.info("Your login details are for Family.")
                        if st.button("Log out", key="care_login_wrong_logout_after"):
                            sign_out_user("care_hub")
                    else:
                        if mapping_error:
                            st.error(mapping_error)
                            st.info("Please sign in again.")
                        else:
                            st.error("Account not set up yet.")

    if back_pressed:
        set_route(get_login_route(app_variant))
    if sign_out_pressed:
        sign_out_user("care_hub")
    if forgot_pressed:
        ok, message = send_password_reset_email(normalized_email)
        if ok:
            st.success(message)
        else:
            st.error(message)


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
    # Top action buttons removed; navigation is handled through the header menu.
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
    has_pending_recording = any(
        bool((entry or {}).get("recording_bytes"))
        for entry in send_state.values()
        if isinstance(entry, dict)
    )
    trigger_live_message_refresh("care_live_refresh", disabled=has_pending_recording)
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
                    "recording_mime_type": "audio/wav",
                    "preview_confirmed": False,
                    "selected_contact_id": None,
                    "selected_contact_user_id": None,
                    "last_message": None,
                },
            )
    else:
        if manual_active and active_rec_id and active_rec_id not in resident_ids:
            active_rec_id = None
            st.session_state["care_active_rec_resident"] = None
        if not manual_active:
            active_rec_id = None
            st.session_state["care_active_rec_resident"] = None
    for resident in residents:
        resident_id = resident["id"]
        state = send_state.setdefault(
            resident_id,
            {
                "recording_bytes": None,
                "recording_mime_type": "audio/wav",
                "preview_confirmed": False,
                "selected_contact_id": None,
                "selected_contact_user_id": None,
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
                state["recording_mime_type"] = "audio/wav"
                state["preview_confirmed"] = False
                state["last_message"] = None
        else:
            st.markdown(
                '<div class="vm-muted-line">No linked family contacts.</div>',
                unsafe_allow_html=True,
            )
            state["selected_contact_id"] = None
            state["selected_contact_user_id"] = None

        latest_sent = None
        latest_sent_audio = None
        if state.get("selected_contact_user_id"):
            latest_sent = fetch_latest_message(
                resident_id,
                "from_resident",
                access_token,
                contact_user_id=state.get("selected_contact_user_id"),
            )
        if not latest_sent:
            latest_sent = fetch_latest_message(
                resident_id,
                "from_resident",
                access_token,
            )
        latest_sent_audio = decode_audio_payload(latest_sent)
        if latest_sent and not state.get("recording_bytes"):
            st.caption("Latest sent message:")
            if latest_sent_audio:
                st.audio(
                    latest_sent_audio,
                    format=latest_sent.get("audio_mime_type") or "audio/wav",
                )
            else:
                st.success("Latest sent message is saved.")
            latest_sent_at = latest_sent.get("recorded_at")
            if latest_sent_at:
                st.caption(f"Sent at: {latest_sent_at}")

        if hasattr(st, "audio_input"):
            recorded_from_native = st.audio_input(
                "Record voice message",
                key=f"care_audio_input_{resident_id}",
            )
            if recorded_from_native is not None:
                native_bytes = recorded_from_native.getvalue()
                if native_bytes and native_bytes != state.get("recording_bytes"):
                    state["recording_bytes"] = native_bytes
                    state["recording_mime_type"] = (
                        getattr(recorded_from_native, "type", None) or "audio/wav"
                    )
                    state["preview_confirmed"] = False
                    state["last_message"] = None
        else:
            st.warning("Native microphone recording is unavailable in this environment.")

        st.caption(
            "Mobile recording needs a secure browser context (HTTPS) and microphone permission."
        )

        if state.get("recording_bytes"):
            st.caption("Captured message preview:")
            st.audio(
                state["recording_bytes"],
                format=state.get("recording_mime_type") or "audio/wav",
            )
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
                    audio_mime_type = state.get("recording_mime_type") or "audio/wav"
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    now_iso = __import__("datetime").datetime.utcnow().isoformat()
                    payload = {
                        "resident_id": resident_id,
                        "contact_user_id": state.get("selected_contact_user_id"),
                        "direction": "from_resident",
                        "audio_storage_path": audio_b64,
                        "audio_mime_type": audio_mime_type,
                        "audio_bytes": len(audio_bytes),
                        "recorded_at": now_iso,
                    }
                    try:
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
                                        "p_audio_mime_type": audio_mime_type,
                                        "p_audio_bytes": len(audio_bytes),
                                        "p_recorded_at": now_iso,
                                    },
                                ).execute()
                            )
                        except Exception as rpc_exc:
                            rpc_msg = str(rpc_exc)
                            rpc_msg_l = rpc_msg.lower()
                            rpc_missing = (
                                "insert_care_hub_message" in rpc_msg
                                and (
                                    "pgrst202" in rpc_msg_l
                                    or "not found" in rpc_msg_l
                                    or "does not exist" in rpc_msg_l
                                    or "could not find the function" in rpc_msg_l
                                )
                            )
                            if not rpc_missing:
                                raise
                            resp = (
                                supabase.table("messages")
                                .upsert(
                                    payload,
                                    on_conflict="resident_id,contact_user_id,direction",
                                )
                                .select("*")
                                .execute()
                            )
                    except Exception as exc:  # pragma: no cover - Supabase runtime error
                        st.error(str(exc))
                    else:
                        message_id = (
                            (resp.data[0].get("id") if isinstance(resp.data, list) and resp.data else None)
                            if resp is not None
                            else None
                        )
                        log_audit_event(
                            "message_sent",
                            "care_hub",
                            resident["care_home_id"],
                            message_id,
                        )
                        state["recording_bytes"] = None
                        state["recording_mime_type"] = "audio/wav"
                        state["preview_confirmed"] = False
                        sent_now = True
                        st.session_state["care_last_sent"] = {
                            "resident_id": resident_id,
                            "contact_id": state.get("selected_contact_id"),
                            "message": "Message sent.",
                        }


    # Navigation rendered at the top of the page.


def render_care_hub_register_family() -> None:
    require_care_access()
    if get_app_variant() != VARIANT_OFFICE:
        render_wrong_variant(
            "Family registration is only available in Care Hub – Office."
        )
        return
    render_page_header("Register a Family Member")
    access_token = st.session_state.get("access_token")
    residents = fetch_care_home_residents(access_token)
    render_office_family_registration_form(access_token, residents)


def main() -> None:
    st.set_page_config(
        page_title="voice-message.com",
        page_icon="🗣️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    raw_variant = get_raw_app_variant()
    if not raw_variant:
        st.error(
            "Configuration error: APP_VARIANT is required.\n\n"
            f"Allowed values: {ALLOWED_VARIANT_VALUES_TEXT}."
        )
        st.stop()
    try:
        app_variant = get_app_variant()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    if variant_requires_auth(app_variant) and AUTH_COOKIE_PERSISTENCE_ENABLED:
        if not AUTH_COOKIE_SIGNING_KEY:
            st.error("Configuration error: AUTH_COOKIE_SIGNING_KEY is required for secure session cookies.")
            st.stop()
        restore_auth_session_from_cookie()
    init_state()
    route = get_route()
    st.session_state.route = route
    default_route = normalize_route(get_default_route(app_variant)) or "/"
    if route in ("/", ""):
        target_route = FAMILY_LOGIN_ROUTE if app_variant == VARIANT_FAMILY else default_route
        set_route(target_route)
        return
    route_allowlisted = is_route_allowed(app_variant, route)
    print(
        f"[startup] variant={app_variant} route={route} allowlisted={route_allowlisted}",
        flush=True,
    )
    guard_route_access(route, app_variant)
    if APP_DEBUG:
        st.info(
            f"DEBUG startup: variant={app_variant}, route={route}, allowlisted={route_allowlisted}"
        )
    st.markdown(
        """
<style>
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
  display: none !important;
}
</style>
""",
        unsafe_allow_html=True,
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
        /* Keep Streamlit popover defaults to avoid clipping/truncation issues. */
        .hero-logo {
            margin-top: -40px;
        }
        section.main h2,
        section.main div[data-testid="stMarkdownContainer"] h2 {
            font-size: 0.92rem !important;
            font-weight: 700 !important;
            line-height: 1.3 !important;
            margin: 0.35rem 0 0.2rem !important;
        }
        section.main h3,
        section.main div[data-testid="stMarkdownContainer"] h3 {
            font-size: 0.88rem !important;
            font-weight: 700 !important;
            line-height: 1.3 !important;
            margin: 0.3rem 0 0.2rem !important;
        }
        section.main h4,
        section.main div[data-testid="stMarkdownContainer"] h4 {
            font-size: 0.84rem !important;
            font-weight: 700 !important;
            line-height: 1.3 !important;
            margin: 0.25rem 0 0.15rem !important;
        }
        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.7rem !important;
                padding-right: 0.7rem !important;
                padding-top: 0.35rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.45rem !important;
            }
            .front-page-info-box,
            .family-how-box,
            .family-login-box,
            .care-login-box,
            .family-terms-box,
            .family-contact-box,
            .service-overview-box {
                padding: 11px 12px !important;
                margin: 0 0 9px 0 !important;
                border-radius: 7px !important;
                line-height: 1.42 !important;
            }
            .stButton > button,
            button[kind="primary"],
            button[kind="secondary"],
            button[kind="tertiary"] {
                min-height: 42px !important;
                font-size: 0.96rem !important;
            }
            .stTextInput input,
            .stTextArea textarea {
                font-size: 0.98rem !important;
            }
        }
</style>
""",
        unsafe_allow_html=True,
    )
    render_debug_panel("top", app_variant, "none")
    if app_variant == VARIANT_FAMILY and not is_family_authenticated():
        render_debug_panel("family_unauth", app_variant, "render_family_login_hub + st.stop")
        render_family_login_hub()
        st.stop()
    validate_supabase_config_for_variant(app_variant)
    # No raw variant banner in UI.
    if app_variant == VARIANT_MOBILE:
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
    if app_variant == VARIANT_PUBLIC:
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
    if redirect_if_not_authenticated(app_variant, route):
        render_debug_panel("auth_redirect", app_variant, "redirect_if_not_authenticated -> return")
        return
    if (
        app_variant == VARIANT_OFFICE
        and is_office_mfa_required()
        and route not in ("/care-hub/mfa", get_login_route(VARIANT_OFFICE))
    ):
        set_route("/care-hub/mfa")
        return
    prev_page = st.session_state.get("current_page")
    st.session_state["prev_page"] = prev_page
    st.session_state["current_page"] = route
    if (
        prev_page == FAMILY_HOME_ROUTE
        and route != FAMILY_HOME_ROUTE
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
    if route == FAMILY_LOGIN_ROUTE:
        render_family_login()
    elif route == FAMILY_HOME_ROUTE:
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
        set_route("/family/terms-use")
    elif route == "/family/terms-use":
        render_family_terms()
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
    elif route in (OFFICE_LOGIN_ROUTE, MOBILE_LOGIN_ROUTE):
        render_care_login()
    elif route in (OFFICE_HOME_ROUTE, MOBILE_HOME_ROUTE):
        render_care_hub()
    elif route == "/care-hub/register-family":
        render_care_hub_register_family()
    elif route == "/care-hub/instructions":
        render_care_hub_instructions()
    elif route == "/care-hub/training":
        render_care_hub_training()
    elif route == "/care-hub/security":
        render_care_hub_security()
    elif route == "/care-hub/office/qa":
        render_page_header("Office Q&A", show_variant_subheading=False)
        render_route_link(
            "← Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="office_qa_back_dashboard_link",
        )
        render_qa_document("docs/office/common_questions_qa.md", search_key="office_qa_search")
    elif route == "/care-hub/mobile/qa":
        render_page_header("Mobile Q&A", show_variant_subheading=False)
        render_route_link("Back", get_home_route(VARIANT_MOBILE), key="mobile_qa_back_link")
        render_qa_document("docs/public/12_mobile_qa.md", search_key="mobile_qa_search")
    elif route == "/family/qa":
        render_page_header("Family Q&A", show_variant_subheading=False)
        render_route_link("Back", get_home_route(VARIANT_FAMILY), key="family_qa_back_link")
        render_qa_document("docs/public/11_family_qa.md", search_key="family_qa_search")
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
    elif route == "/public/qa":
        render_public_document("docs/public/10_faq.md")
    elif route == "/public/faq":
        render_public_document("docs/public/10_faq.md")
    elif route == "/public/privacy-notice":
        render_public_document("docs/public/privacy_policy.md")
    elif route == "/public/family-terms-of-use":
        render_public_document("docs/public/family_terms_of_use.md")
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
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime safety net
        st.error("Application error while rendering.")
        st.error(str(exc))
        st.exception(exc)
