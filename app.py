# familyupdates.care UI

import os
import base64
import time
import uuid
import secrets
import hashlib
import hmac
import json
import re
import html
import io
from pathlib import Path
import urllib.request
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse, unquote

import streamlit as st
import streamlit.components.v1 as components
from supabase.client import create_client
import pyotp
import qrcode
from config import get_supabase_config, get_app_variant as resolve_app_variant
try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    OpenAI = None

try:
    from st_audiorec import st_audiorec
except ModuleNotFoundError:  # pragma: no cover - runtime env mismatch
    st_audiorec = None

try:
    from streamlit_autorefresh import st_autorefresh
except ModuleNotFoundError:  # pragma: no cover - runtime env mismatch
    st_autorefresh = None

from ui_theme import TOKENS, inject_css

FAMILY_SESSION_TIMEOUT_SECONDS = int(
    os.getenv("FAMILY_SESSION_TIMEOUT_SECONDS", str(60 * 30))
)
# Guard against accidental very-low timeout values in deployment config.
# Care Hub sessions should not expire during normal short pauses in workflow.
CARE_HUB_SESSION_TIMEOUT_SECONDS = max(
    int(os.getenv("CARE_HUB_SESSION_TIMEOUT_SECONDS", str(60 * 90))),
    60 * 60,
)
CARE_HUB_IDLE_TIMEOUT_OPTIONS_SECONDS = (60 * 60, 60 * 90, 60 * 120)
TRANSCRIPT_POLICY_MODES = ("off", "assist", "precheck")
APP_DEBUG = os.getenv("APP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
DEV_AUTH_BYPASS_ENABLED = os.getenv("DEV_AUTH_BYPASS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DEV_AUTH_BYPASS_TOKEN = "__local_dev_auth_bypass__"
APP_LIVE_REFRESH = os.getenv("APP_LIVE_REFRESH", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
APP_LIVE_REFRESH_INTERVAL_MS = max(
    int(os.getenv("APP_LIVE_REFRESH_INTERVAL_MS", "30000")),
    7000,
)
APP_MESSAGE_CACHE_SECONDS = max(
    int(os.getenv("APP_MESSAGE_CACHE_SECONDS", "15")),
    0,
)
APP_FAMILY_LIVE_REFRESH = os.getenv("APP_FAMILY_LIVE_REFRESH", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
APP_MOBILE_LIVE_REFRESH = os.getenv("APP_MOBILE_LIVE_REFRESH", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
APP_OFFICE_LIVE_REFRESH = os.getenv("APP_OFFICE_LIVE_REFRESH", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()
SUPABASE_AUDIO_BUCKET = os.getenv("SUPABASE_AUDIO_BUCKET", "voice-messages").strip() or "voice-messages"
MEDIA_BASE_URL = (
    str(os.getenv("MEDIA_BASE_URL", "https://media.familyupdates.care") or "").strip().rstrip("/")
)
CARE_HOME_BANNER_OBJECT_PATH = (
    str(os.getenv("CARE_HOME_BANNER_OBJECT_PATH", "banners/office/care-home-banner.png") or "")
    .strip()
    .lstrip("/")
)
LEGACY_MEDIA_HOST_SUBSTRINGS = (
    "voice-message.com",
    "voicemailcare-main.onrender.com",
)
CANONICAL_PUBLIC_HOST = str(os.getenv("CANONICAL_PUBLIC_HOST", "familyupdates.care") or "").strip().lower()
CANONICAL_PUBLIC_HOST_ALIASES = tuple(
    host.strip().lower()
    for host in str(os.getenv("CANONICAL_PUBLIC_HOST_ALIASES", "www.familyupdates.care") or "").split(",")
    if host.strip()
)
NON_CANONICAL_REDIRECT_HOST_SUFFIXES = tuple(
    suffix.strip().lower()
    for suffix in str(
        os.getenv("NON_CANONICAL_REDIRECT_HOST_SUFFIXES", ".streamlit.app,.onrender.com") or ""
    ).split(",")
    if suffix.strip()
)
NON_CANONICAL_HOST_REDIRECT_ENABLED = str(
    os.getenv("NON_CANONICAL_HOST_REDIRECT_ENABLED", "1") or ""
).strip().lower() in {"1", "true", "yes", "on"}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TRANSCRIPTION_MODEL = (
    os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe").strip()
    or "gpt-4o-mini-transcribe"
)
OPENAI_TRANSCRIPTION_TIMEOUT_SECONDS = max(
    int(os.getenv("OPENAI_TRANSCRIPTION_TIMEOUT_SECONDS", "25")),
    5,
)
OPENAI_TRANSCRIPTION_MAX_BYTES = max(
    int(os.getenv("OPENAI_TRANSCRIPTION_MAX_BYTES", str(25 * 1024 * 1024))),
    1024 * 1024,
)
OFFICE_UPDATE_CATEGORIES = (
    "General reassurance",
    "Daily life",
    "Activities",
    "Meals",
)
OFFICE_PRACTICAL_CHECKBOX_OPTIONS = (
    "I will sort this out",
    "I can attend",
    "I cannot attend",
)
OFFICE_PRACTICAL_CONTEXT_GENERAL = "general"
OFFICE_PRACTICAL_CONTEXT_VISIT = "visit"
OFFICE_PRACTICAL_TARGET_ALL_FAMILY = "all_family"
OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY = "directed_family"
OFFICE_PRACTICAL_TARGET_MOBILE = "mobile"
STRUCTURED_RESPONSE_CHOICES = ("no_response", "yes", "no", "maybe")
STRUCTURED_RESPONSE_LABELS = {
    "no_response": "No response",
    "yes": "Yes",
    "no": "No",
    "maybe": "Maybe",
}
STRUCTURED_RESPONSE_VALUES_BY_LABEL = {
    label: value for value, label in STRUCTURED_RESPONSE_LABELS.items()
}
SENSITIVE_DATA_BOUNDARY_WARNING = (
    "Keep sensitive records outside the app. Use this only for simple communication and coordination."
)
LIFE_FILE_GUIDE_SECTIONS = (
    (
        "prep",
        "Suggested external file names",
        "Recommended order",
        (
            "1. [Person's name] - Life Log",
            "2. [Person's name] - Contacts",
            "3. [Person's name] - Admin and Key Documents",
            "4. [Person's name] - Private Finance",
            "5. [Person's name] - Private Health Notes",
            "6. [Person's name] - Carer and Housekeeping Notes",
        ),
    ),
    (
        "life_log",
        "Life Log",
        "What this is for",
        (
            "day-to-day notes and observations",
            "changes in health or mood",
            "missed medication or concerns",
            "appointment notes",
            "things to remember",
            "questions for family, GP, or carer",
            "emergency contacts",
        ),
    ),
    (
        "contacts",
        "Contacts",
        "What this is for",
        (
            "family and close contacts",
            "GP / doctor",
            "pharmacy",
            "dentist, optician, audiology, or other regular services",
            "carer, cleaner, gardener, or trusted helper",
            "emergency contacts",
            "solicitor, accountant, financial adviser, or other professional contacts",
        ),
    ),
    (
        "admin_key_documents",
        "Admin and Key Documents",
        "What this is for",
        (
            "where important documents are kept",
            "property, tenancy, insurance, pension, benefit, and utility references",
            "solicitor / LPA or LPOA contact details",
            "who is authorised to help with admin",
            "renewal dates, reference numbers, and useful instructions",
            "do not include passwords or full identity document copies",
        ),
    ),
    (
        "private_finance",
        "Private Finance",
        "What this is for",
        (
            "bank, pension, investment, and benefit overview",
            "bills, subscriptions, direct debits, and regular payments",
            "insurance and tax information",
            "financial adviser and bank contact details",
            "who has financial LPA/LPOA or similar authority, where relevant",
            "keep detailed statements, account numbers, passwords, and access codes secure and separate",
        ),
    ),
    (
        "private_health_notes",
        "Private Health Notes",
        "What this is for",
        (
            "health summary and key conditions",
            "current medication list",
            "allergies and important risks",
            "appointments, questions, and observations",
            "GP, pharmacy, hospital, and clinic contacts",
            "who has health and welfare LPA/LPOA or similar authority, where relevant",
            "keep formal medical records outside familyupdates.care",
        ),
    ),
    (
        "carer_housekeeping",
        "Carer and Housekeeping Notes",
        "What this is for",
        (
            "first page: important information for helpers",
            "emergency contacts",
            "house access instructions",
            "allergies",
            "medication schedule summary",
            "daily routine",
            "mobility / falls risk notes",
            "food and drink preferences",
            "housekeeping notes, deliveries, bins, pets, or keys",
            "what to do if something changes",
        ),
    ),
    (
        "authority",
        "Authority and professional advice",
        "Useful reminder",
        (
            "you may want to consider whether formal authority, such as financial or health/welfare LPA, LPOA, or similar arrangements, is relevant",
            "people coordinating care or paid support may need to know who has authority to make decisions or arrange costs",
            "keep authority documents outside familyupdates.care and share only with people who need them",
            "this is not legal or financial advice; seek professional advice where needed",
        ),
    ),
    (
        "care_home",
        "If a care home becomes involved",
        "What this is for",
        (
            "care home contact details",
            "Family Organiser contact",
            "preferences and routines",
            "financial / admin contacts",
            "visiting arrangements",
            "important family updates",
            "notes of care home meetings",
            "questions for care home staff",
        ),
    ),
)
OPERATING_MODE_CARE_ORGANISATION = "care_organisation"
OPERATING_MODE_PERSONAL_USE = "personal_use"
LEGACY_OPERATING_MODE_CARE_HOME = "care_home"
LEGACY_OPERATING_MODE_FAMILY_LED = "family_led"
DEFAULT_OPERATING_MODE = str(
    os.getenv("DEFAULT_OPERATING_MODE", OPERATING_MODE_CARE_ORGANISATION)
    or OPERATING_MODE_CARE_ORGANISATION
).strip().lower()
DEFAULT_MAIN_CONTACT_NAME = str(os.getenv("DEFAULT_MAIN_CONTACT_NAME", "") or "").strip()
DEFAULT_LIFECYCLE_STAGE = max(
    1,
    min(int(os.getenv("DEFAULT_LIFECYCLE_STAGE", "3")), 4),
)
SEND_ACTION_GUARD_SECONDS = max(
    int(os.getenv("SEND_ACTION_GUARD_SECONDS", "5")),
    3,
)

ALLOWED_VARIANT_VALUES_TEXT = "public, family, mobile, office"
AUTH_COOKIE_NAME = "vm_auth_rt"
AUTH_COOKIE_MAX_AGE_SECONDS = int(os.getenv("AUTH_COOKIE_MAX_AGE_SECONDS", str(60 * 60 * 24 * 14)))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "1").strip().lower() in {"1", "true", "yes", "on"}
AUTH_COOKIE_SIGNING_KEY = os.getenv("AUTH_COOKIE_SIGNING_KEY", "").strip()
AUTH_COOKIE_PERSISTENCE_MODE = os.getenv("AUTH_COOKIE_PERSISTENCE_ENABLED", "").strip().lower()
if AUTH_COOKIE_PERSISTENCE_MODE in {"1", "true", "yes", "on"}:
    AUTH_COOKIE_PERSISTENCE_ENABLED = True
elif AUTH_COOKIE_PERSISTENCE_MODE in {"0", "false", "no", "off"}:
    AUTH_COOKIE_PERSISTENCE_ENABLED = False
else:
    # Auto-enable durable auth cookies when a signing key is configured.
    AUTH_COOKIE_PERSISTENCE_ENABLED = bool(AUTH_COOKIE_SIGNING_KEY)
AUTH_STATE_KEYS = (
    "auth_uid",
    "access_token",
    "refresh_token",
    "auth_email",
    "active_role",
    "active_care_home_id",
    "care_access_level",
    "mfa_verified",
)


def normalize_route(route: str | None) -> str:
    value = (route or "").strip()
    if not value:
        return ""
    # Supabase redirects can carry the route inside an encoded redirect_to URL.
    # Decode a couple of times so both /family/login and %2Ffamily%2Flogin resolve.
    for _ in range(2):
        decoded = unquote(value).strip()
        if decoded == value:
            break
        value = decoded
    if "&" in value:
        base, suffix = value.split("&", 1)
        suffix_lower = suffix.lower()
        if "=" in suffix and any(
            f"{key}=" in suffix_lower
            for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token")
        ):
            value = base or "/"
    if not value.startswith("/"):
        value = f"/{value}"
    normalized_lower = value.lower()
    if normalized_lower == "/mobile/login":
        value = "/care-hub/mobile/login"
    elif normalized_lower == "/office/login":
        value = "/care-hub/login"
    else:
        legacy_direct_aliases = {
            "/care_hub_-_mobile": "/care-hub/mobile/login",
            "/care_hub_mobile": "/care-hub/mobile/login",
            "/care_hub_-_office": "/care-hub/login",
            "/care_hub_office": "/care-hub/login",
            "/family_terms": "/public/family-terms-of-use",
            "/privacy_notice": "/public/privacy-notice",
            "/safeguarding_and_consent": "/public/safeguarding-and-consent",
            "/complaints": "/public/complaints-and-concerns",
            "/pricing": "/pr-home",
        }
        if normalized_lower in legacy_direct_aliases:
            value = legacy_direct_aliases[normalized_lower]
        else:
            legacy_candidate = normalized_lower.lstrip("/")
            if legacy_candidate.startswith("pages/"):
                legacy_candidate = legacy_candidate.split("/", 1)[1]
            if legacy_candidate.endswith(".py"):
                legacy_candidate = legacy_candidate[:-3]
            legacy_slug = re.sub(r"[^a-z0-9]+", "_", legacy_candidate).strip("_")
            if legacy_slug.startswith("pages_"):
                legacy_slug = legacy_slug[len("pages_") :]
            if legacy_slug.startswith("page_"):
                legacy_slug = legacy_slug[len("page_") :]
            legacy_slug_aliases = {
                "family": "/family/login",
                "care_hub_mobile": "/care-hub/mobile/login",
                "care_hub_office": "/care-hub/login",
                "family_terms": "/public/family-terms-of-use",
                "privacy_notice": "/public/privacy-notice",
                "safeguarding_and_consent": "/public/safeguarding-and-consent",
                "complaints": "/public/complaints-and-concerns",
                "pricing": "/pr-home",
            }
            mapped = legacy_slug_aliases.get(legacy_slug, "")
            if mapped:
                value = mapped
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
    # Keep a currently valid in-memory session; do not overwrite it on startup.
    if (
        st.session_state.get("auth_uid")
        and st.session_state.get("access_token")
        and st.session_state.get("refresh_token")
    ):
        st.session_state["_auth_cookie_restored"] = True
        return
    if not AUTH_COOKIE_SIGNING_KEY:
        return
    raw_cookie = _get_request_cookie(AUTH_COOKIE_NAME)
    refresh_token = _decode_refresh_token_cookie(raw_cookie)
    if not refresh_token:
        if raw_cookie:
            clear_auth_cookie()
        st.session_state["_auth_cookie_restored"] = True
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
            st.session_state["_auth_cookie_restored"] = True
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
            st.session_state["_auth_cookie_restored"] = True
            return
        # Rebuild role state from authoritative DB mappings.
        try:
            supabase.postgrest.auth(st.session_state["access_token"])
            auth_uid = st.session_state.get("auth_uid")
            family_table = _family_user_table_name(supabase)
            family_resp = (
                supabase.table(family_table)
                .select("care_home_id")
                .eq("auth_user_id", auth_uid)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            try:
                care_resp = (
                    supabase.table("care_home_users")
                    .select("care_home_id, care_access_level")
                    .eq("auth_user_id", auth_uid)
                    .eq("active", True)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                if not _is_missing_column_error(exc, "care_access_level"):
                    raise
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
                st.session_state["care_access_level"] = normalize_care_access_level(
                    care_row.get("care_access_level")
                )
        except Exception:
            # Keep auth tokens; route-level access checks still fail closed if mapping is missing.
            pass
        # Rotate cookie to the latest refresh token to keep long-running sessions durable.
        persist_auth_cookie(st.session_state["refresh_token"])
        st.session_state["_auth_cookie_restored"] = True
    except Exception:
        # Transient auth backend failures should not force immediate logout.
        st.session_state.pop("_auth_cookie_restored", None)


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
    return


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


def set_public_document_route(route: str) -> None:
    current_route = normalize_route(st.session_state.get("current_page") or get_route())
    if current_route and not current_route.startswith("/public"):
        st.session_state["public_doc_return_route"] = current_route
    set_route(route)


def get_public_landing_url() -> str:
    # Prefer an explicit override, then current app host, so "Back to hub selection"
    # stays inside the active app and avoids legacy cross-site flash redirects.
    configured_url = str(os.getenv("PUBLIC_LANDING_URL", "") or "").strip()
    if configured_url:
        return configured_url
    try:
        context = getattr(st, "context", None)
        current_url = str(getattr(context, "url", "") or "").strip() if context is not None else ""
        parsed = urlparse(current_url) if current_url else None
        if parsed and parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/?route=%2Fpr-home"
    except Exception:
        pass
    # Final fallback must stay on the current host (no cross-domain redirect).
    return "/?route=%2Fpr-home"


def _join_media_base_url(object_path: str) -> str:
    base = str(MEDIA_BASE_URL or "").strip().rstrip("/")
    path = quote(str(object_path or "").strip().lstrip("/"), safe="/")
    if not path:
        return ""
    if not base:
        return f"/{path}"
    return f"{base}/{path}"


def normalize_banner_artwork_url(raw_value: object) -> str:
    raw = str(raw_value or "").strip()
    if not raw:
        return ""
    if re.match(r"^https?://", raw, re.IGNORECASE):
        parsed = urlparse(raw)
        host = str(parsed.netloc or "").strip().lower()
        if any(part in host for part in LEGACY_MEDIA_HOST_SUBSTRINGS):
            legacy_path = unquote(str(parsed.path or "").strip().lstrip("/"))
            if legacy_path:
                return _join_media_base_url(legacy_path)
        return raw
    return _join_media_base_url(unquote(raw))


def redirect_to_public_landing() -> None:
    url = get_public_landing_url()
    url_js = json.dumps(url)
    components.html(
        f"""
<script>
(function () {{
  try {{
    var target = {url_js};
    var topWin = window.parent && window.parent.location ? window.parent : window;
    topWin.location.replace(target);
  }} catch (e) {{
    window.location.replace({url_js});
  }}
}})();
</script>
""",
        height=0,
        width=0,
    )
    st.stop()


def render_public_landing_link(label: str, key: str) -> None:
    url = get_public_landing_url()
    safe_url = html.escape(url, quote=True)
    safe_label = html.escape(label)
    st.markdown(
        f'<a href="{safe_url}" target="_self">{safe_label}</a>',
        unsafe_allow_html=True,
    )

def render_public_landing_button(label: str) -> None:
    url = get_public_landing_url()
    try:
        st.link_button(label, url, use_container_width=True)
    except Exception:
        render_public_landing_link(label, key=f"fallback_{label}")


def render_route_link(label: str, route: str, key: str, use_container_width: bool = True) -> None:
    target = normalize_route(route) or "/"
    if st.button(label, key=key, use_container_width=use_container_width):
        set_route(target)


def get_send_guard_remaining_seconds(scope_key: str) -> int:
    guard_until = st.session_state.get(f"{scope_key}_guard_until", 0.0)
    try:
        remaining = float(guard_until) - time.time()
    except Exception:
        return 0
    if remaining <= 0:
        return 0
    return int(remaining) if remaining.is_integer() else int(remaining) + 1


def activate_send_guard(scope_key: str) -> None:
    st.session_state[f"{scope_key}_guard_until"] = time.time() + float(SEND_ACTION_GUARD_SECONDS)


def _get_message_cache_store() -> dict:
    cache = st.session_state.get("_messages_query_cache")
    if not isinstance(cache, dict):
        cache = {}
        st.session_state["_messages_query_cache"] = cache
    return cache


def _get_message_cache_epoch() -> int:
    try:
        return int(st.session_state.get("_messages_cache_epoch", 0))
    except Exception:
        return 0


def bump_message_cache_epoch() -> None:
    st.session_state["_messages_cache_epoch"] = _get_message_cache_epoch() + 1


def _get_cached_message_query_result(cache_key: tuple):
    if APP_MESSAGE_CACHE_SECONDS <= 0:
        return None
    cache = _get_message_cache_store()
    payload = cache.get(cache_key)
    if not isinstance(payload, tuple) or len(payload) != 3:
        return None
    cached_epoch, cached_at, cached_value = payload
    if cached_epoch != _get_message_cache_epoch():
        return None
    if (time.time() - float(cached_at)) > float(APP_MESSAGE_CACHE_SECONDS):
        return None
    return cached_value


def _set_cached_message_query_result(cache_key: tuple, value) -> None:
    if APP_MESSAGE_CACHE_SECONDS <= 0:
        return
    cache = _get_message_cache_store()
    cache[cache_key] = (_get_message_cache_epoch(), time.time(), value)
    if len(cache) > 800:
        try:
            for key in list(cache.keys())[:200]:
                cache.pop(key, None)
        except Exception:
            pass
    st.session_state["_messages_query_cache"] = cache


def _is_missing_conflict_constraint_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return (
        "42p10" in message
        or "no unique or exclusion constraint matching the on conflict specification" in message
    )


def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
    message = str(exc or "").lower()
    column_key = str(column_name or "").strip().lower()
    if not column_key:
        return False
    return column_key in message and (
        "does not exist" in message
        or "could not find the" in message
        or "schema cache" in message
        or "undefined column" in message
        or "42703" in message
    )


def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
    message = str(exc or "").lower()
    table_key = str(table_name or "").strip().lower()
    if not table_key:
        return False
    return table_key in message and (
        "could not find the table" in message
        or "schema cache" in message
        or "does not exist" in message
        or "42p01" in message
        or "pgrst205" in message
    )


def _resolve_table_name(supabase: object, cache_key: str, candidates: list[str]) -> str:
    cache = st.session_state.setdefault("_schema_name_cache", {})
    cached = str(cache.get(cache_key) or "").strip()
    if cached:
        return cached
    for candidate in candidates:
        try:
            supabase.table(candidate).select("id").limit(1).execute()
            cache[cache_key] = candidate
            st.session_state["_schema_name_cache"] = cache
            return candidate
        except Exception as exc:
            if _is_missing_table_error(exc, candidate):
                continue
            # For non-missing-table errors (for example transient permission/runtime),
            # keep the preferred candidate to avoid blocking auth flow entirely.
            cache[cache_key] = candidate
            st.session_state["_schema_name_cache"] = cache
            return candidate
    fallback = candidates[-1] if candidates else ""
    cache[cache_key] = fallback
    st.session_state["_schema_name_cache"] = cache
    return fallback


def _family_user_table_name(supabase: object) -> str:
    return _resolve_table_name(supabase, "family_user_table", ["family_user", "family_contacts"])


def _resident_access_table_name(supabase: object) -> str:
    return _resolve_table_name(
        supabase, "resident_access_table", ["resident_access", "family_contact_access"]
    )


def _family_user_relation_name(supabase: object) -> str:
    table_name = _family_user_table_name(supabase)
    return "family_user" if table_name == "family_user" else "family_contacts"


def _resident_access_family_user_column(supabase: object) -> str:
    access_table = _resident_access_table_name(supabase)
    return "family_user_id" if access_table == "resident_access" else "family_contact_id"


def _office_practical_family_user_column(supabase: object) -> str:
    cache = st.session_state.setdefault("_schema_name_cache", {})
    cache_key = "office_practical_family_user_column"
    cached = str(cache.get(cache_key) or "").strip()
    if cached:
        return cached
    try:
        supabase.table("office_practical_responses").select("id, family_user_id").limit(1).execute()
        resolved = "family_user_id"
    except Exception as exc:
        resolved = "family_contact_id" if _is_missing_column_error(exc, "family_user_id") else "family_user_id"
    cache[cache_key] = resolved
    st.session_state["_schema_name_cache"] = cache
    return resolved


def _strip_optional_message_audio_columns(
    payload: dict,
    *,
    strip_storage_columns: bool = True,
    strip_transcript_columns: bool = True,
) -> dict:
    cleaned = dict(payload or {})
    # Legacy schemas may miss optional storage/transcript columns.
    # Preserve a playable payload in audio_storage_path before stripping storage pointers.
    if strip_storage_columns:
        audio_storage_path = str(cleaned.get("audio_storage_path") or "").strip()
        audio_object_path = str(cleaned.get("audio_object_path") or "").strip()
        if not audio_storage_path and audio_object_path:
            downloaded = _download_audio_from_storage(audio_object_path)
            if downloaded:
                cleaned["audio_storage_path"] = base64.b64encode(downloaded).decode("ascii")
                cleaned["audio_source"] = "inline"
            else:
                # Keep legacy pointer fallback for environments that can read storage by path.
                cleaned["audio_storage_path"] = audio_object_path
        cleaned.pop("audio_object_path", None)
        cleaned.pop("audio_source", None)
    if strip_transcript_columns:
        cleaned.pop("transcript_text", None)
        cleaned.pop("transcript_status", None)
        cleaned.pop("transcript_model", None)
        cleaned.pop("transcript_generated_at", None)
    return cleaned


def _looks_like_base64_payload(value: str) -> bool:
    normalized = str(value or "").strip()
    if len(normalized) < 32:
        return False
    if len(normalized) % 4 != 0:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", normalized))


def _try_decode_base64_audio(payload: str) -> bytes | None:
    normalized = str(payload or "").strip()
    if not normalized:
        return None
    compact = "".join(normalized.split())
    if not compact:
        return None
    padded = compact + ("=" * ((4 - (len(compact) % 4)) % 4))
    try:
        decoded = base64.b64decode(padded, validate=False)
        if isinstance(decoded, (bytes, bytearray)) and decoded:
            return bytes(decoded)
    except Exception:
        pass
    try:
        decoded = base64.urlsafe_b64decode(padded)
        if isinstance(decoded, (bytes, bytearray)) and decoded:
            return bytes(decoded)
    except Exception:
        pass
    return None


def _message_select_fields(
    include_audio: bool,
    include_optional_storage_columns: bool = True,
    include_optional_transcript_columns: bool = True,
    include_optional_text_columns: bool = True,
) -> str:
    fields = "id, resident_id, contact_user_id, family_id, channel, direction, recorded_at"
    text_fields = ["message_kind", "text_title", "text_body"] if include_optional_text_columns else []
    if include_audio:
        audio_fields = ["audio_storage_path", "audio_mime_type", "audio_bytes"]
        if include_optional_storage_columns:
            audio_fields.extend(["audio_object_path", "audio_source"])
        if include_optional_transcript_columns:
            audio_fields.extend(
                [
                    "transcript_text",
                    "transcript_status",
                    "transcript_model",
                    "transcript_generated_at",
                ]
            )
        fields = (
            "id, resident_id, contact_user_id, family_id, channel, direction, "
            + ", ".join(audio_fields)
            + (", " + ", ".join(text_fields) if text_fields else "")
            + ", recorded_at"
        )
    elif text_fields:
        fields = fields + ", " + ", ".join(text_fields)
    return fields


def _message_missing_optional_columns(exc: Exception) -> tuple[bool, bool]:
    missing_audio_columns = bool(
        _is_missing_column_error(exc, "audio_object_path")
        or _is_missing_column_error(exc, "audio_source")
    )
    missing_transcript_columns = bool(
        _is_missing_column_error(exc, "transcript_text")
        or _is_missing_column_error(exc, "transcript_status")
        or _is_missing_column_error(exc, "transcript_model")
        or _is_missing_column_error(exc, "transcript_generated_at")
    )
    return missing_audio_columns, missing_transcript_columns


def _message_missing_text_columns(exc: Exception) -> bool:
    return bool(
        _is_missing_column_error(exc, "message_kind")
        or _is_missing_column_error(exc, "text_title")
        or _is_missing_column_error(exc, "text_body")
    )


def is_text_update_message(message: dict | None) -> bool:
    if not isinstance(message, dict):
        return False
    kind = str(message.get("message_kind") or "").strip().lower()
    body = str(message.get("text_body") or "").strip()
    return kind == "text" or bool(body)


def render_text_update_message(message: dict | None) -> bool:
    if not is_text_update_message(message):
        return False
    title = str((message or {}).get("text_title") or "").strip()
    body = str((message or {}).get("text_body") or "").strip()
    if title:
        st.markdown(f"**{title}**")
    if body:
        st.markdown(body)
    return True


def _flag_transcript_persistence_fallback(payload: dict | None) -> None:
    st.session_state["_messages_missing_transcript_columns"] = True
    if not isinstance(payload, dict):
        return
    status_value = str(payload.get("transcript_status") or "").strip().lower()
    text_value = str(payload.get("transcript_text") or "").strip()
    if status_value in {"ready", "failed"} or bool(text_value):
        st.session_state["_transcript_persist_warning"] = (
            "Transcript could not be saved because this deployment is missing transcript columns. "
            "Apply Supabase migration 0023_messages_transcript_columns.sql."
        )


def consume_transcript_persist_warning() -> str | None:
    warning = st.session_state.get("_transcript_persist_warning")
    if warning:
        st.session_state.pop("_transcript_persist_warning", None)
        return str(warning)
    return None


def upload_audio_to_storage(
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    resident_id: str,
    direction: str,
) -> tuple[str | None, str | None]:
    if not audio_bytes:
        return None, "No audio bytes to upload."
    admin_client, admin_error = get_admin_client()
    if admin_error or admin_client is None:
        return None, admin_error or "Supabase admin client is unavailable."
    mime = str(audio_mime_type or "audio/wav").strip().lower()
    extension = "wav"
    if "mpeg" in mime or "mp3" in mime:
        extension = "mp3"
    elif "webm" in mime:
        extension = "webm"
    elif "ogg" in mime:
        extension = "ogg"
    elif "mp4" in mime or "m4a" in mime:
        extension = "m4a"
    now = __import__("datetime").datetime.utcnow()
    resident_key = str(resident_id or "unknown").strip() or "unknown"
    direction_key = str(direction or "unknown").strip() or "unknown"
    object_path = (
        f"messages/{now.strftime('%Y/%m/%d')}/{resident_key}/{direction_key}/{uuid.uuid4().hex}.{extension}"
    )
    try:
        try:
            admin_client.storage.from_(SUPABASE_AUDIO_BUCKET).upload(
                object_path,
                audio_bytes,
                {"content-type": mime, "cache-control": "3600", "upsert": "false"},
            )
        except TypeError:
            admin_client.storage.from_(SUPABASE_AUDIO_BUCKET).upload(
                object_path,
                audio_bytes,
                {"contentType": mime, "cacheControl": "3600", "upsert": False},
            )
        return object_path, None
    except Exception as exc:
        return None, str(exc)


def _audio_extension_from_mime(audio_mime_type: str) -> str:
    mime = str(audio_mime_type or "audio/wav").strip().lower()
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "webm" in mime:
        return "webm"
    if "ogg" in mime:
        return "ogg"
    if "mp4" in mime or "m4a" in mime:
        return "m4a"
    return "wav"


def transcribe_audio_bytes(audio_bytes: bytes, audio_mime_type: str) -> tuple[str | None, str | None]:
    if not audio_bytes:
        return None, "No audio bytes."
    if len(audio_bytes) > OPENAI_TRANSCRIPTION_MAX_BYTES:
        max_mb = round(OPENAI_TRANSCRIPTION_MAX_BYTES / (1024 * 1024), 1)
        return None, f"Audio is too large for transcript generation (limit {max_mb} MB)."
    if not OPENAI_API_KEY:
        return None, "OPENAI_API_KEY is not configured."
    if OpenAI is None:
        return None, "OpenAI SDK is not installed."
    extension = _audio_extension_from_mime(audio_mime_type)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = f"message.{extension}"
    try:
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=float(OPENAI_TRANSCRIPTION_TIMEOUT_SECONDS),
            max_retries=0,
        )
        result = client.audio.transcriptions.create(
            model=OPENAI_TRANSCRIPTION_MODEL,
            file=audio_file,
        )
        text = str(getattr(result, "text", "") or "").strip()
        if text:
            return text, None
        return None, "Transcription returned no text."
    except Exception as exc:
        return None, str(exc)


def build_transcript_fields(
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    requested: bool,
) -> tuple[dict, str | None]:
    if not requested:
        return {
            "transcript_text": None,
            "transcript_status": "not_requested",
            "transcript_model": None,
            "transcript_generated_at": None,
        }, None

    transcript_text, transcript_error = transcribe_audio_bytes(audio_bytes, audio_mime_type)
    if transcript_text:
        return {
            "transcript_text": transcript_text,
            "transcript_status": "ready",
            "transcript_model": OPENAI_TRANSCRIPTION_MODEL,
            "transcript_generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        }, None
    return {
        "transcript_text": None,
        "transcript_status": "failed",
        "transcript_model": OPENAI_TRANSCRIPTION_MODEL,
        "transcript_generated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }, transcript_error or "Transcription failed."


def clear_transcript_preview_state(state: dict, prefix: str = "") -> None:
    if not isinstance(state, dict):
        return
    for key in (
        "transcript_preview_fingerprint",
        "transcript_preview_text",
        "transcript_preview_status",
        "transcript_preview_model",
        "transcript_preview_generated_at",
        "transcript_preview_error",
        "transcript_preview_visible",
    ):
        state.pop(f"{prefix}{key}", None)


def ensure_transcript_preview_state(
    state: dict,
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    requested: bool,
    prefix: str = "",
) -> None:
    if not isinstance(state, dict):
        return
    if not requested:
        clear_transcript_preview_state(state, prefix=prefix)
        return
    if not audio_bytes:
        clear_transcript_preview_state(state, prefix=prefix)
        return
    fingerprint = __import__("hashlib").sha1(audio_bytes).hexdigest()
    fp_key = f"{prefix}transcript_preview_fingerprint"
    status_key = f"{prefix}transcript_preview_status"
    if (
        str(state.get(fp_key) or "").strip() == fingerprint
        and str(state.get(status_key) or "").strip() in {"ready", "failed"}
    ):
        return
    transcript_text, transcript_error = transcribe_audio_bytes(audio_bytes, audio_mime_type)
    state[fp_key] = fingerprint
    state[f"{prefix}transcript_preview_model"] = OPENAI_TRANSCRIPTION_MODEL
    state[f"{prefix}transcript_preview_generated_at"] = (
        __import__("datetime").datetime.utcnow().isoformat()
    )
    if transcript_text:
        state[f"{prefix}transcript_preview_text"] = transcript_text
        state[status_key] = "ready"
        state[f"{prefix}transcript_preview_error"] = None
    else:
        state[f"{prefix}transcript_preview_text"] = None
        state[status_key] = "failed"
        state[f"{prefix}transcript_preview_error"] = (
            transcript_error or "Transcription failed."
        )


def build_transcript_fields_from_preview(
    state: dict,
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    requested: bool,
    prefix: str = "",
) -> tuple[dict, str | None]:
    if not requested:
        return {
            "transcript_text": None,
            "transcript_status": "not_requested",
            "transcript_model": None,
            "transcript_generated_at": None,
        }, None
    if isinstance(state, dict) and audio_bytes:
        fingerprint = __import__("hashlib").sha1(audio_bytes).hexdigest()
        stored_fingerprint = str(
            state.get(f"{prefix}transcript_preview_fingerprint") or ""
        ).strip()
        stored_status = str(state.get(f"{prefix}transcript_preview_status") or "").strip()
        if stored_fingerprint == fingerprint and stored_status in {"ready", "failed"}:
            generated_at = (
                str(state.get(f"{prefix}transcript_preview_generated_at") or "").strip()
                or __import__("datetime").datetime.utcnow().isoformat()
            )
            if stored_status == "ready":
                return {
                    "transcript_text": state.get(f"{prefix}transcript_preview_text"),
                    "transcript_status": "ready",
                    "transcript_model": state.get(f"{prefix}transcript_preview_model")
                    or OPENAI_TRANSCRIPTION_MODEL,
                    "transcript_generated_at": generated_at,
                }, None
            return {
                "transcript_text": None,
                "transcript_status": "failed",
                "transcript_model": state.get(f"{prefix}transcript_preview_model")
                or OPENAI_TRANSCRIPTION_MODEL,
                "transcript_generated_at": generated_at,
            }, str(state.get(f"{prefix}transcript_preview_error") or "Transcription failed.")
    return build_transcript_fields(
        audio_bytes,
        audio_mime_type,
        requested=requested,
    )


def render_transcript_preview_controls(
    state: dict,
    audio_bytes: bytes,
    audio_mime_type: str,
    *,
    policy_mode: str,
    key_scope: str,
    prefix: str = "",
) -> None:
    if not isinstance(state, dict) or not audio_bytes:
        return
    requested_key = f"{prefix}transcribe_requested"
    visible_key = f"{prefix}transcript_preview_visible"
    mode = normalize_transcript_policy_mode(policy_mode)
    if mode == "precheck":
        state[requested_key] = True

    transcript_preview_text = str(state.get(f"{prefix}transcript_preview_text") or "").strip()
    transcript_preview_status = str(
        state.get(f"{prefix}transcript_preview_status") or ""
    ).strip().lower()
    transcript_preview_error = str(
        state.get(f"{prefix}transcript_preview_error") or ""
    ).strip()
    transcript_preview_visible = bool(state.get(visible_key, False))

    if transcript_preview_text and transcript_preview_status == "ready":
        transcript_button_label = (
            "Hide transcript" if transcript_preview_visible else "View transcript"
        )
    elif transcript_preview_status == "failed":
        transcript_button_label = "Retry transcript"
    else:
        transcript_button_label = "View transcript"

    if st.button(
        transcript_button_label,
        key=f"{key_scope}_{prefix or 'main'}_transcript_preview_toggle",
    ):
        if transcript_preview_text and transcript_preview_status == "ready":
            state[visible_key] = not transcript_preview_visible
            st.rerun()
        else:
            state[requested_key] = True
            with st.spinner("Generating transcript..."):
                ensure_transcript_preview_state(
                    state,
                    audio_bytes,
                    audio_mime_type,
                    requested=True,
                    prefix=prefix,
                )
            transcript_preview_text = str(state.get(f"{prefix}transcript_preview_text") or "").strip()
            transcript_preview_status = str(
                state.get(f"{prefix}transcript_preview_status") or ""
            ).strip().lower()
            if transcript_preview_text and transcript_preview_status == "ready":
                state[visible_key] = True
                st.rerun()
            transcript_preview_visible = bool(state.get(visible_key, False))

    if bool(state.get(requested_key)) and transcript_preview_status not in {"ready", "failed"}:
        with st.spinner("Refreshing transcript..."):
            ensure_transcript_preview_state(
                state,
                audio_bytes,
                audio_mime_type,
                requested=True,
                prefix=prefix,
            )
        transcript_preview_text = str(state.get(f"{prefix}transcript_preview_text") or "").strip()
        transcript_preview_status = str(
            state.get(f"{prefix}transcript_preview_status") or ""
        ).strip().lower()
        transcript_preview_error = str(
            state.get(f"{prefix}transcript_preview_error") or ""
        ).strip()

    if transcript_preview_text and transcript_preview_status == "ready" and bool(
        state.get(visible_key, False)
    ):
        st.markdown("**Transcript preview (before send)**")
        st.caption("Transcript may contain errors. Voice remains the source of truth.")
        st.markdown(transcript_preview_text)
    elif bool(state.get(requested_key)) and transcript_preview_status == "failed":
        st.warning(
            "Transcript preview is unavailable. Voice can still be sent unless a transcript precheck policy is required."
            + (f" {transcript_preview_error}" if transcript_preview_error else "")
        )


def _download_audio_from_storage(
    object_path: str, access_token: str | None = None
) -> bytes | None:
    raw_path = str(object_path or "").strip()
    if not raw_path:
        return None
    path_candidates = _candidate_audio_storage_paths(raw_path)
    if not path_candidates:
        return None
    cache = st.session_state.get("_audio_storage_blob_cache")
    if not isinstance(cache, dict):
        cache = {}
    for path in path_candidates:
        cached = cache.get(path)
        if isinstance(cached, (bytes, bytearray)):
            return bytes(cached)

    clients: list[object] = []
    if access_token:
        authed_client, authed_error = get_authed_supabase(access_token)
        if not authed_error and authed_client is not None:
            clients.append(authed_client)
    anon_client, anon_error = get_supabase_client()
    if not anon_error and anon_client is not None:
        clients.append(anon_client)
    admin_client, admin_error = get_admin_client()
    if not admin_error and admin_client is not None:
        clients.append(admin_client)

    for path in path_candidates:
        for client in clients:
            try:
                data = client.storage.from_(SUPABASE_AUDIO_BUCKET).download(path)
                if isinstance(data, bytearray):
                    data = bytes(data)
                if isinstance(data, bytes) and data:
                    cache[path] = data
                    st.session_state["_audio_storage_blob_cache"] = cache
                    return data
            except Exception:
                continue
    return None


def _create_signed_audio_url(
    object_path: str, access_token: str | None = None, *, expires_in: int = 600
) -> str | None:
    raw_path = str(object_path or "").strip()
    if not raw_path:
        return None
    path_candidates = _candidate_audio_storage_paths(raw_path)
    if not path_candidates:
        return None
    clients: list[object] = []
    if access_token:
        authed_client, authed_error = get_authed_supabase(access_token)
        if not authed_error and authed_client is not None:
            clients.append(authed_client)
    anon_client, anon_error = get_supabase_client()
    if not anon_error and anon_client is not None:
        clients.append(anon_client)
    admin_client, admin_error = get_admin_client()
    if not admin_error and admin_client is not None:
        clients.append(admin_client)

    for path in path_candidates:
        for client in clients:
            try:
                signed = client.storage.from_(SUPABASE_AUDIO_BUCKET).create_signed_url(path, expires_in)
            except Exception:
                continue
            if not isinstance(signed, dict):
                continue
            signed_url = str(
                signed.get("signedURL")
                or signed.get("signedUrl")
                or signed.get("signed_url")
                or ""
            ).strip()
            if not signed_url:
                continue
            if signed_url.startswith("http://") or signed_url.startswith("https://"):
                return signed_url
            base_url = str(SUPABASE_URL or "").rstrip("/")
            if base_url and signed_url.startswith("/"):
                return f"{base_url}{signed_url}"
            if base_url and not signed_url.startswith("/"):
                return f"{base_url}/{signed_url}"
            return signed_url
    return None


def _create_public_audio_url(object_path: str) -> str | None:
    raw_path = str(object_path or "").strip()
    if not raw_path:
        return None
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        return raw_path
    base_url = str(SUPABASE_URL or "").rstrip("/")
    if not base_url:
        return None
    path_candidates = _candidate_audio_storage_paths(raw_path)
    if not path_candidates:
        return None
    for candidate in path_candidates:
        clean_path = str(candidate or "").strip().lstrip("/")
        if not clean_path:
            continue
        encoded_path = quote(clean_path, safe="/")
        return f"{base_url}/storage/v1/object/public/{SUPABASE_AUDIO_BUCKET}/{encoded_path}"
    return None


def _candidate_audio_storage_paths(raw_value: str) -> list[str]:
    raw = str(raw_value or "").strip()
    if not raw:
        return []

    candidates: list[str] = []

    def _push(value: str) -> None:
        candidate = str(value or "").strip()
        if not candidate:
            return
        candidate = candidate.strip("\"'")
        if candidate.startswith("/"):
            candidate = candidate.lstrip("/")
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    _push(raw)

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        path_only = unquote(str(parsed.path or "").strip())
        _push(path_only)
        marker = f"/{SUPABASE_AUDIO_BUCKET}/"
        if marker in path_only:
            _push(path_only.split(marker, 1)[1])
        if "/storage/v1/object/" in path_only:
            parts = [part for part in path_only.split("/") if part]
            # Expected patterns include:
            # storage/v1/object/public/<bucket>/<key...>
            # storage/v1/object/sign/<bucket>/<key...>
            if len(parts) >= 6 and parts[0] == "storage" and parts[1] == "v1" and parts[2] == "object":
                bucket = parts[4]
                key_parts = parts[5:]
                if bucket == SUPABASE_AUDIO_BUCKET and key_parts:
                    _push("/".join(key_parts))

    bucket_prefix = f"{SUPABASE_AUDIO_BUCKET}/"
    for existing in list(candidates):
        if existing.startswith(bucket_prefix):
            _push(existing[len(bucket_prefix) :])

    return candidates


def resolve_audio_playback_source(
    message: dict, access_token: str | None = None
) -> tuple[bytes | str | None, str]:
    audio_bytes = decode_audio_payload(message, access_token=access_token)
    if audio_bytes:
        return audio_bytes, "bytes"
    if not message:
        return None, "none"
    object_path = str(message.get("audio_object_path") or "").strip()
    if object_path:
        signed_url = _create_signed_audio_url(object_path, access_token=access_token)
        if signed_url:
            return signed_url, "url"
        public_url = _create_public_audio_url(object_path)
        if public_url:
            return public_url, "url"
    payload = str(message.get("audio_storage_path") or "").strip()
    if payload:
        if payload.startswith("http://") or payload.startswith("https://"):
            return payload, "url"
        if not _looks_like_base64_payload(payload):
            signed_url = _create_signed_audio_url(payload, access_token=access_token)
            if signed_url:
                return signed_url, "url"
            public_url = _create_public_audio_url(payload)
            if public_url:
                return public_url, "url"
    return None, "none"


def resolve_audio_playback_source_lazy(
    message: dict, access_token: str | None = None
) -> tuple[bytes | str | None, str]:
    """Prefer URL-based playback and avoid eager storage downloads on page load."""
    if not message:
        return None, "none"
    object_path = str(message.get("audio_object_path") or "").strip()
    if object_path:
        signed_url = _create_signed_audio_url(object_path, access_token=access_token)
        if signed_url:
            return signed_url, "url"
        public_url = _create_public_audio_url(object_path)
        if public_url:
            return public_url, "url"
    payload = str(message.get("audio_storage_path") or "").strip()
    if payload:
        if payload.startswith("http://") or payload.startswith("https://"):
            return payload, "url"
        if not _looks_like_base64_payload(payload):
            signed_url = _create_signed_audio_url(payload, access_token=access_token)
            if signed_url:
                return signed_url, "url"
            public_url = _create_public_audio_url(payload)
            if public_url:
                return public_url, "url"
    audio_bytes = decode_audio_payload(message, access_token=access_token)
    if audio_bytes:
        return audio_bytes, "bytes"
    return None, "none"


def upsert_latest_message_with_fallback(
    supabase: object,
    payload: dict,
    conflict_columns: str,
    lookup_filters: dict,
) -> tuple[object | None, str | None]:
    conflict_supported = st.session_state.get("_messages_conflict_upsert_supported")
    if conflict_supported is not False:
        try:
            response = supabase.table("messages").upsert(payload, on_conflict=conflict_columns).execute()
            st.session_state["_messages_conflict_upsert_supported"] = True
            return response, None
        except Exception as exc:
            missing_audio_columns, missing_transcript_columns = _message_missing_optional_columns(exc)
            if missing_audio_columns or missing_transcript_columns:
                if missing_transcript_columns:
                    _flag_transcript_persistence_fallback(payload)
                legacy_payload = _strip_optional_message_audio_columns(
                    payload,
                    strip_storage_columns=missing_audio_columns,
                    strip_transcript_columns=missing_transcript_columns,
                )
                try:
                    response = (
                        supabase.table("messages")
                        .upsert(legacy_payload, on_conflict=conflict_columns)
                        .execute()
                    )
                    st.session_state["_messages_conflict_upsert_supported"] = True
                    return response, None
                except Exception as legacy_exc:
                    if not _is_missing_conflict_constraint_error(legacy_exc):
                        return None, str(legacy_exc)
                    st.session_state["_messages_conflict_upsert_supported"] = False
            if not _is_missing_conflict_constraint_error(exc):
                return None, str(exc)
            st.session_state["_messages_conflict_upsert_supported"] = False

    try:
        existing_query = supabase.table("messages").select("id")
        for key, value in lookup_filters.items():
            if value is None:
                existing_query = existing_query.is_(key, "null")
            else:
                existing_query = existing_query.eq(key, value)
        existing_response = existing_query.order("recorded_at", desc=True).limit(1).execute()
        existing_id = (
            existing_response.data[0].get("id")
            if hasattr(existing_response, "data")
            and isinstance(existing_response.data, list)
            and existing_response.data
            else None
        )
        write_payload = dict(payload)
        if existing_id:
            try:
                response = supabase.table("messages").update(write_payload).eq("id", existing_id).execute()
            except Exception as exc:
                missing_audio_columns, missing_transcript_columns = _message_missing_optional_columns(exc)
                if missing_audio_columns or missing_transcript_columns:
                    if missing_transcript_columns:
                        _flag_transcript_persistence_fallback(write_payload)
                    write_payload = _strip_optional_message_audio_columns(
                        write_payload,
                        strip_storage_columns=missing_audio_columns,
                        strip_transcript_columns=missing_transcript_columns,
                    )
                    response = (
                        supabase.table("messages").update(write_payload).eq("id", existing_id).execute()
                    )
                else:
                    raise
        else:
            try:
                response = supabase.table("messages").insert(write_payload).execute()
            except Exception as exc:
                missing_audio_columns, missing_transcript_columns = _message_missing_optional_columns(exc)
                if missing_audio_columns or missing_transcript_columns:
                    if missing_transcript_columns:
                        _flag_transcript_persistence_fallback(write_payload)
                    write_payload = _strip_optional_message_audio_columns(
                        write_payload,
                        strip_storage_columns=missing_audio_columns,
                        strip_transcript_columns=missing_transcript_columns,
                    )
                    response = supabase.table("messages").insert(write_payload).execute()
                else:
                    raise
        return response, None
    except Exception as exc:
        return None, str(exc)

def get_supabase_client() -> tuple[object | None, str | None]:
    url, key = get_supabase_config()
    if not url or not key:
        return None, "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY."
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
    url = os.getenv("SUPABASE_URL", "").strip()
    if not url:
        return None, "Missing SUPABASE_URL."
    if not SUPABASE_SECRET_KEY:
        return None, "Missing SUPABASE_SECRET_KEY for Office family registration."
    cached_bundle = st.session_state.get("_supabase_admin_client_bundle")
    if (
        isinstance(cached_bundle, tuple)
        and len(cached_bundle) == 2
        and cached_bundle[0] == url
        and cached_bundle[1] is not None
    ):
        return cached_bundle[1], None
    try:
        client = create_client(url, SUPABASE_SECRET_KEY)
        # Cache the client without persisting the service key in session state.
        st.session_state["_supabase_admin_client_bundle"] = (url, client)
        return client, None
    except Exception as exc:  # pragma: no cover - runtime/config mismatch
        return None, f"Supabase admin client initialization failed: {exc}"


def is_local_request() -> bool:
    host = _get_request_host()
    if not host:
        # Streamlit can lack request context during early startup/rerun.
        # DEV_AUTH_BYPASS still requires an explicit env var and a secret key.
        return True
    return host in {"localhost", "127.0.0.1", "::1"}


def is_dev_auth_bypass_active() -> bool:
    return bool(DEV_AUTH_BYPASS_ENABLED and is_local_request())


def _apply_dev_auth_bypass_session(app_variant: str) -> tuple[bool, str | None]:
    if not is_dev_auth_bypass_active() or not variant_requires_auth(app_variant):
        return False, None
    if st.session_state.get("access_token") == DEV_AUTH_BYPASS_TOKEN:
        return True, None
    admin_client, admin_error = get_admin_client()
    if admin_error or admin_client is None:
        return False, admin_error or "Supabase admin client unavailable."
    role = "family" if app_variant == VARIANT_FAMILY else "care_hub"
    care_home_id = str(os.getenv("DEV_AUTH_BYPASS_CARE_HOME_ID", "") or "").strip()
    auth_uid = str(os.getenv("DEV_AUTH_BYPASS_AUTH_UID", "") or "").strip()
    family_email = str(os.getenv("DEV_AUTH_BYPASS_FAMILY_EMAIL", "") or "").strip().lower()
    try:
        if role == "family":
            family_table = _family_user_table_name(admin_client)
            query = (
                admin_client.table(family_table)
                .select("auth_user_id, email, care_home_id, display_name, created_at")
                .eq("active", True)
            )
            if care_home_id:
                query = query.eq("care_home_id", care_home_id)
            if auth_uid:
                query = query.eq("auth_user_id", auth_uid)
            if family_email:
                query = query.eq("email", family_email)
            try:
                response = query.order("created_at", desc=True).limit(1).execute()
            except Exception:
                response = query.limit(1).execute()
            record = response.data[0] if response.data else None
        else:
            query = (
                admin_client.table("care_home_users")
                .select("auth_user_id, care_home_id, care_access_level")
                .eq("active", True)
            )
            if care_home_id:
                query = query.eq("care_home_id", care_home_id)
            if auth_uid:
                query = query.eq("auth_user_id", auth_uid)
            response = query.limit(1).execute()
            record = response.data[0] if response.data else None
        if not record:
            return False, "No active user mapping row found for the selected variant."
        st.session_state["auth_uid"] = str(record.get("auth_user_id") or auth_uid or "")
        st.session_state["auth_email"] = str(record.get("email") or "dev-auth-bypass@localhost")
        st.session_state["access_token"] = DEV_AUTH_BYPASS_TOKEN
        st.session_state["refresh_token"] = DEV_AUTH_BYPASS_TOKEN
        st.session_state["active_role"] = role
        st.session_state["active_care_home_id"] = record.get("care_home_id")
        if role == "care_hub":
            st.session_state["care_access_level"] = normalize_care_access_level(
                record.get("care_access_level")
            )
        if app_variant == VARIANT_MOBILE:
            mark_mobile_pin_verified()
        if app_variant == VARIANT_OFFICE:
            st.session_state["office_login_explicit"] = True
            st.session_state["mfa_verified"] = True
        return True, None
    except Exception as exc:
        return False, str(exc)


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


def invite_user(
    admin_client: object,
    email: str,
    redirect_to_override: str = "",
) -> tuple[bool, str | None, str | None]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return False, None, "Email is required."
    redirect_to = (
        str(redirect_to_override or "").strip()
        or os.getenv("FAMILY_INVITE_REDIRECT_URL", "").strip()
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


CARE_ACCESS_OFFICE = "office"
CARE_ACCESS_MOBILE = "mobile"


def normalize_care_access_level(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if candidate == CARE_ACCESS_MOBILE:
        return CARE_ACCESS_MOBILE
    return CARE_ACCESS_OFFICE


def current_care_access_level() -> str:
    return normalize_care_access_level(st.session_state.get("care_access_level"))


def current_user_can_access_office() -> bool:
    return current_care_access_level() == CARE_ACCESS_OFFICE


def get_magic_link_redirect_url(app_variant: str) -> str:
    if app_variant == VARIANT_FAMILY:
        return (
            os.getenv("FAMILY_MAGIC_LINK_REDIRECT_URL", "").strip()
            or os.getenv("PASSWORD_RESET_REDIRECT_URL", "").strip()
            or os.getenv("FAMILY_APP_URL", "").strip()
        )
    if app_variant == VARIANT_MOBILE:
        return (
            os.getenv("CARE_MOBILE_MAGIC_LINK_REDIRECT_URL", "").strip()
            or os.getenv("CARE_MOBILE_APP_URL", "").strip()
            or os.getenv("CARE_OFFICE_APP_URL", "").strip()
        )
    if app_variant == VARIANT_OFFICE:
        return (
            os.getenv("CARE_OFFICE_MAGIC_LINK_REDIRECT_URL", "").strip()
            or os.getenv("CARE_OFFICE_APP_URL", "").strip()
            or os.getenv("CARE_MOBILE_APP_URL", "").strip()
        )
    return ""


def _normalize_magic_link_redirect_url_for_variant(redirect_to: str, app_variant: str) -> str:
    value = str(redirect_to or "").strip()
    if not value:
        return value
    try:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return value
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        query_map: dict[str, str] = {}
        for key, raw_value in query_pairs:
            key_text = str(key or "").strip()
            if not key_text:
                continue
            query_map[key_text] = str(raw_value or "")
        canonical_login_route = get_login_route(app_variant)
        if canonical_login_route:
            query_map["route"] = canonical_login_route
        normalized_path = "/"
        normalized_query = urlencode(query_map)
        target_scheme = parsed.scheme or "https"
        target_netloc = parsed.netloc
        if CANONICAL_PUBLIC_HOST:
            target_scheme = "https"
            target_netloc = CANONICAL_PUBLIC_HOST
        return urlunparse(
            parsed._replace(
                scheme=target_scheme,
                netloc=target_netloc,
                path=normalized_path,
                query=normalized_query,
            )
        )
    except Exception:
        return value


def send_magic_link_email(
    email: str, *, app_variant: str, should_create_user: bool = False
) -> tuple[bool, str]:
    target_email = email.strip().lower()
    if not target_email:
        return False, "Enter an email address first."
    supabase, error = get_supabase_client()
    if error:
        return False, error
    redirect_to = get_magic_link_redirect_url(app_variant).strip()
    redirect_to = _normalize_magic_link_redirect_url_for_variant(redirect_to, app_variant)
    if not redirect_to:
        return (
            False,
            "Missing magic-link redirect URL configuration for this app variant.",
        )
    redirect_to_lower = redirect_to.lower()
    if app_variant == VARIANT_MOBILE and "/family/login" in redirect_to_lower:
        return (
            False,
            "Mobile magic-link redirect is misconfigured (currently pointing to Family). "
            "Update CARE_MOBILE_MAGIC_LINK_REDIRECT_URL and CARE_MOBILE_APP_URL to the mobile URL.",
        )
    if app_variant == VARIANT_FAMILY and "/care-hub/mobile" in redirect_to_lower:
        return (
            False,
            "Family magic-link redirect is misconfigured (currently pointing to Mobile). "
            "Update FAMILY_MAGIC_LINK_REDIRECT_URL/FAMILY_APP_URL to the family URL.",
        )
    print(
        f"[auth] send_magic_link_email variant={app_variant!r} redirect_to={redirect_to!r}",
        flush=True,
    )
    try:
        options = {
            "email_redirect_to": redirect_to,
            "should_create_user": bool(should_create_user),
        }
        supabase.auth.sign_in_with_otp({"email": target_email, "options": options})
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        raw_error = str(exc or "").strip()
        normalized = raw_error.lower()
        if "email rate limit" in normalized or "rate limit" in normalized:
            return (
                False,
                "Too many email links have been requested in a short time. Please wait a few minutes and try again.",
            )
        if (
            "signups not allowed" in normalized
            or "user not found" in normalized
            or "no user" in normalized
            or "email not confirmed" in normalized
        ):
            return (
                False,
                "This email has not been registered yet. Ask the Family Organiser or Office user to register/invite you first.",
            )
        return False, raw_error
    return (
        True,
        "Check your inbox and click the secure login link to sign in. No password required.",
    )


def consume_magic_link_callback() -> None:
    if not hasattr(st, "query_params"):
        return
    params = st.query_params
    auth_code = str(params.get("code", "") or "").strip()
    token_hash = str(params.get("token_hash", "") or "").strip()
    token = str(params.get("token", "") or "").strip()
    otp_type = str(params.get("type", "") or "").strip().lower()
    raw_access_token = str(params.get("access_token", "") or "").strip()
    raw_refresh_token = str(params.get("refresh_token", "") or "").strip()
    if not auth_code and not token_hash and not token and not (raw_access_token and raw_refresh_token):
        recovered = _recover_auth_callback_params_from_path()
        auth_code = auth_code or str(recovered.get("code", "") or "").strip()
        token_hash = token_hash or str(recovered.get("token_hash", "") or "").strip()
        token = token or str(recovered.get("token", "") or "").strip()
        otp_type = otp_type or str(recovered.get("type", "") or "").strip().lower()
        raw_access_token = raw_access_token or str(recovered.get("access_token", "") or "").strip()
        raw_refresh_token = raw_refresh_token or str(recovered.get("refresh_token", "") or "").strip()
        if recovered and hasattr(st, "query_params"):
            try:
                for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token"):
                    value = str(recovered.get(key, "") or "").strip()
                    if value and not str(st.query_params.get(key, "") or "").strip():
                        st.query_params[key] = value
            except Exception:
                pass
    if not auth_code and not token_hash and not token and not (raw_access_token and raw_refresh_token):
        return
    callback_sig = "|".join(
        [
            auth_code,
            token_hash,
            token,
            otp_type,
            raw_access_token[:24],
            raw_refresh_token[:24],
        ]
    )
    if callback_sig and st.session_state.get("_last_magiclink_callback_sig") == callback_sig:
        has_tokens = bool(
            st.session_state.get("access_token")
            and st.session_state.get("refresh_token")
        )
        if has_tokens:
            return

    supabase, error = get_supabase_client()
    if error:
        if APP_DEBUG:
            print(f"[auth-callback] Supabase client error: {error}", flush=True)
        return

    auth_result = None
    try:
        if raw_access_token and raw_refresh_token:
            # Some auth providers/routes can return raw tokens directly in query params.
            st.session_state["access_token"] = raw_access_token
            st.session_state["refresh_token"] = raw_refresh_token
            raw_auth_uid = ""
            raw_auth_email = ""
            try:
                user_result = supabase.auth.get_user(raw_access_token)
                user_obj = getattr(user_result, "user", None)
                if user_obj is None and isinstance(user_result, dict):
                    user_obj = user_result.get("user")
                if user_obj is not None:
                    raw_auth_uid = str(getattr(user_obj, "id", "") or "")
                    raw_auth_email = str(getattr(user_obj, "email", "") or "")
                    if isinstance(user_obj, dict):
                        raw_auth_uid = raw_auth_uid or str(user_obj.get("id") or "")
                        raw_auth_email = raw_auth_email or str(user_obj.get("email") or "")
            except Exception:
                pass
            st.session_state["auth_uid"] = raw_auth_uid or str(st.session_state.get("auth_uid") or "")
            if raw_auth_email:
                st.session_state["auth_email"] = raw_auth_email
            persist_auth_cookie(raw_refresh_token)
            if APP_DEBUG:
                print(
                    "[auth-callback] Accepted raw access/refresh tokens from query params. "
                    f"auth_uid={st.session_state.get('auth_uid') or '(missing)'}",
                    flush=True,
                )
            for key in ("access_token", "refresh_token", "code", "token_hash", "token", "type"):
                try:
                    if key in st.query_params:
                        del st.query_params[key]
                except Exception:
                    pass
            if callback_sig:
                st.session_state["_last_magiclink_callback_sig"] = callback_sig
            return
        if auth_code:
            try:
                auth_result = supabase.auth.exchange_code_for_session(auth_code)
            except TypeError:
                auth_result = supabase.auth.exchange_code_for_session({"auth_code": auth_code})
        elif token_hash or token:
            token_payload_key = "token_hash" if token_hash else "token"
            token_value = token_hash or token
            candidate_types = []
            if otp_type:
                candidate_types.append(otp_type)
            # Be permissive across Supabase/Gotrue variants.
            for fallback in ("magiclink", "email", "signup", "invite", "recovery"):
                if fallback not in candidate_types:
                    candidate_types.append(fallback)
            last_exc = None
            for verify_type in candidate_types:
                try:
                    auth_result = supabase.auth.verify_otp(
                        {token_payload_key: token_value, "type": verify_type}
                    )
                    if APP_DEBUG:
                        print(
                            f"[auth-callback] verify_otp succeeded using {token_payload_key} + type={verify_type}.",
                            flush=True,
                        )
                    break
                except Exception as exc:
                    last_exc = exc
                    continue
            if auth_result is None and last_exc and APP_DEBUG:
                print(f"[auth-callback] verify_otp failed for all candidate types: {last_exc}", flush=True)
    except Exception:
        if APP_DEBUG:
            print("[auth-callback] Exception while consuming callback.", flush=True)
        return

    session = getattr(auth_result, "session", None)
    user = getattr(auth_result, "user", None)
    if session is None and isinstance(auth_result, dict):
        session = auth_result.get("session")
        user = auth_result.get("user")
    if not session:
        if APP_DEBUG:
            print("[auth-callback] No session returned from callback exchange.", flush=True)
        return

    access_token = getattr(session, "access_token", "") if session is not None else ""
    refresh_token = getattr(session, "refresh_token", "") if session is not None else ""
    if isinstance(session, dict):
        access_token = access_token or str(session.get("access_token") or "")
        refresh_token = refresh_token or str(session.get("refresh_token") or "")
        if user is None:
            user = session.get("user")
    if not access_token or not refresh_token:
        if APP_DEBUG:
            print("[auth-callback] Missing access/refresh token in callback session.", flush=True)
        return

    auth_uid = ""
    auth_email = ""
    if user is not None:
        auth_uid = str(getattr(user, "id", "") or "")
        auth_email = str(getattr(user, "email", "") or "")
        if isinstance(user, dict):
            auth_uid = auth_uid or str(user.get("id") or "")
            auth_email = auth_email or str(user.get("email") or "")
    if not auth_uid:
        try:
            user_result = supabase.auth.get_user(access_token)
            user_obj = getattr(user_result, "user", None)
            if user_obj is None and isinstance(user_result, dict):
                user_obj = user_result.get("user")
            if user_obj is not None:
                auth_uid = str(getattr(user_obj, "id", "") or "")
                auth_email = auth_email or str(getattr(user_obj, "email", "") or "")
                if isinstance(user_obj, dict):
                    auth_uid = auth_uid or str(user_obj.get("id") or "")
                    auth_email = auth_email or str(user_obj.get("email") or "")
        except Exception:
            pass

    st.session_state["access_token"] = access_token
    st.session_state["refresh_token"] = refresh_token
    st.session_state["auth_uid"] = auth_uid
    st.session_state["auth_email"] = auth_email
    persist_auth_cookie(refresh_token)
    if APP_DEBUG:
        print(
            f"[auth-callback] Session established. auth_uid={auth_uid or '(missing)'} auth_email={auth_email or '(missing)'}",
            flush=True,
        )
    for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token"):
        try:
            if key in st.query_params:
                del st.query_params[key]
        except Exception:
            pass
    if callback_sig:
        st.session_state["_last_magiclink_callback_sig"] = callback_sig


def normalize_auth_hash_fragment_on_login_routes() -> None:
    # Some Supabase confirmation links return tokens in URL hash (#access_token=...).
    # Streamlit server code cannot read hash fragments, so convert once to query params.
    components.html(
        """
<script>
(function () {
  try {
    var topWin = window.parent && window.parent.location ? window.parent : window;
    var allowedKeys = ["access_token", "refresh_token", "token_hash", "token", "type", "code"];
    var currentUrl = new URL(topWin.location.href);
    var routeFromPath = "";
    var normalizedPath = (currentUrl.pathname || "").toLowerCase();
    if (normalizedPath === "/mobile/login") routeFromPath = "/care-hub/mobile/login";
    else if (normalizedPath === "/office/login") routeFromPath = "/care-hub/login";
    else if (normalizedPath === "/family/login") routeFromPath = "/family/login";
    var hasAuthSearchParam = false;
    allowedKeys.forEach(function (k) {
      if (currentUrl.searchParams.get(k)) hasAuthSearchParam = true;
    });
    if (routeFromPath && currentUrl.pathname !== "/" && (hasAuthSearchParam || currentUrl.searchParams.get("route"))) {
      if (!currentUrl.searchParams.get("route")) {
        currentUrl.searchParams.set("route", routeFromPath);
      }
      currentUrl.pathname = "/";
      topWin.location.replace(currentUrl.toString());
      return;
    }
    var path = currentUrl.pathname || "";
    var ampIndex = path.indexOf("&");
    if (ampIndex > -1) {
      var cleanPath = path.slice(0, ampIndex);
      var suffix = path.slice(ampIndex + 1);
      if (suffix && suffix.indexOf("=") > -1) {
        var misplacedParams = new URLSearchParams(suffix);
        allowedKeys.forEach(function (k) {
          var v = misplacedParams.get(k);
          if (v && !currentUrl.searchParams.get(k)) {
            currentUrl.searchParams.set(k, v);
          }
        });
        currentUrl.pathname = cleanPath || "/";
        topWin.location.replace(currentUrl.toString());
        return;
      }
    }
    var hash = topWin.location.hash || "";
    if (!hash || hash.length < 2) return;
    var raw = hash.substring(1);
    if (raw.indexOf("access_token=") === -1 && raw.indexOf("refresh_token=") === -1) return;

    var url = new URL(topWin.location.href);
    var hashParams = new URLSearchParams(raw);
    allowedKeys.forEach(function (k) {
      var v = hashParams.get(k);
      if (v && !url.searchParams.get(k)) {
        url.searchParams.set(k, v);
      }
    });
    url.hash = "";
    topWin.location.replace(url.toString());
  } catch (e) {
    // Fail closed: keep current URL if parsing fails.
  }
})();
</script>
""",
        height=0,
        width=0,
    )


def _mobile_pin_hash_legacy(pin_value: str, auth_uid: str, care_home_id: str) -> str:
    material = f"vm_mobile_pin_v1:{care_home_id}:{auth_uid}:{pin_value}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _mobile_pin_hash(pin_value: str, care_home_id: str) -> str:
    # v2 hash scope is per care home so PIN uniqueness can be enforced per home.
    material = f"vm_mobile_pin_v2:{care_home_id}:{pin_value}"
    return "v2:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _is_valid_mobile_pin(pin_value: str) -> bool:
    return bool(re.fullmatch(r"\d{4,8}", pin_value or ""))


def get_mobile_pin_record(access_token: str | None) -> tuple[dict | None, str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None, error
    auth_uid = str(st.session_state.get("auth_uid") or "").strip()
    if not auth_uid:
        return None, "Missing authenticated user."
    try:
        resp = (
            supabase.table("care_home_users")
            .select("id, care_home_id, mobile_pin_hash, active")
            .eq("auth_user_id", auth_uid)
            .eq("active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return None, str(exc)
    if not resp.data:
        return None, "No active care-home staff mapping found."
    return resp.data[0], None


def is_mobile_pin_verified_for_session() -> bool:
    auth_uid = str(st.session_state.get("auth_uid") or "")
    return bool(
        auth_uid
        and st.session_state.get("mobile_pin_verified") is True
        and str(st.session_state.get("mobile_pin_verified_uid") or "") == auth_uid
    )


def mark_mobile_pin_verified() -> None:
    st.session_state["mobile_pin_verified"] = True
    st.session_state["mobile_pin_verified_uid"] = str(st.session_state.get("auth_uid") or "")


def render_mobile_pin_gate(access_token: str | None) -> bool:
    record, record_error = get_mobile_pin_record(access_token)
    if record_error or not record:
        st.error(record_error or "Could not load mobile PIN settings.")
        return False
    auth_uid = str(st.session_state.get("auth_uid") or "").strip()
    care_home_id = str(record.get("care_home_id") or "").strip()
    stored_hash = str(record.get("mobile_pin_hash") or "").strip()
    supabase, error = get_authed_supabase(access_token)
    if error:
        st.error(error)
        return False

    if not stored_hash:
        st.info("Set your individual 4-8 digit Mobile PIN to continue.")
        with st.form("mobile_pin_set_form", clear_on_submit=False):
            new_pin = st.text_input("Create your Mobile PIN", type="password", key="mobile_pin_create")
            confirm_pin = st.text_input(
                "Confirm Mobile PIN", type="password", key="mobile_pin_confirm"
            )
            submitted = st.form_submit_button("Set PIN and continue")
        if submitted:
            if not _is_valid_mobile_pin(new_pin):
                st.error("PIN must be 4-8 digits.")
                return False
            if new_pin != confirm_pin:
                st.error("PIN values do not match.")
                return False
            pin_hash = _mobile_pin_hash(new_pin, care_home_id)
            try:
                supabase.rpc("set_mobile_pin_hash", {"p_pin_hash": pin_hash}).execute()
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                msg = str(exc or "")
                msg_l = msg.lower()
                if (
                    "duplicate key value violates unique constraint" in msg_l
                    or "idx_care_home_users_unique_mobile_pin_per_home" in msg_l
                ):
                    st.error(
                        "This Mobile PIN is already used by another Mobile Support user in this workspace. Choose a different PIN."
                    )
                else:
                    st.error(msg)
                return False
            mark_mobile_pin_verified()
            st.session_state["mobile_pin_just_accepted"] = True
            set_route(MOBILE_HOME_ROUTE)
            return True
        return False

    st.caption("PIN access is individual to each Mobile Support user.")
    with st.expander("Change Mobile PIN"):
        st.caption("Use this if you know your current PIN. If forgotten, ask Family Office to reset it.")
        with st.form("mobile_pin_change_form", clear_on_submit=False):
            current_pin = st.text_input(
                "Current Mobile PIN",
                type="password",
                key="mobile_pin_change_current",
            )
            new_pin = st.text_input(
                "New Mobile PIN",
                type="password",
                key="mobile_pin_change_new",
            )
            confirm_new_pin = st.text_input(
                "Confirm new Mobile PIN",
                type="password",
                key="mobile_pin_change_confirm",
            )
            change_submitted = st.form_submit_button("Change PIN")
        if change_submitted:
            if not _is_valid_mobile_pin(current_pin):
                st.error("Enter your current 4-8 digit PIN.")
                return False
            if not _is_valid_mobile_pin(new_pin):
                st.error("New PIN must be 4-8 digits.")
                return False
            if new_pin != confirm_new_pin:
                st.error("New PIN values do not match.")
                return False
            current_candidate_hash = _mobile_pin_hash(current_pin, care_home_id)
            current_legacy_hash = _mobile_pin_hash_legacy(current_pin, auth_uid, care_home_id)
            if current_candidate_hash != stored_hash and current_legacy_hash != stored_hash:
                st.error("Current PIN is incorrect.")
                return False
            new_hash = _mobile_pin_hash(new_pin, care_home_id)
            try:
                supabase.rpc("set_mobile_pin_hash", {"p_pin_hash": new_hash}).execute()
            except Exception as exc:  # pragma: no cover - Supabase runtime error
                msg = str(exc or "")
                msg_l = msg.lower()
                if (
                    "duplicate key value violates unique constraint" in msg_l
                    or "idx_care_home_users_unique_mobile_pin_per_home" in msg_l
                ):
                    st.error(
                        "This Mobile PIN is already used by another Mobile Support user in this workspace. Choose a different PIN."
                    )
                else:
                    st.error(msg)
                return False
            mark_mobile_pin_verified()
            st.session_state["mobile_pin_just_accepted"] = True
            st.success("Mobile PIN changed.")
            set_route(MOBILE_HOME_ROUTE)
            return True
    with st.form("mobile_pin_unlock_form", clear_on_submit=False):
        pin_value = st.text_input(
            "Enter your individual Mobile PIN",
            type="password",
            key="mobile_pin_unlock_form_value",
        )
        unlock_submitted = st.form_submit_button("Unlock Mobile")
    if unlock_submitted:
        if not _is_valid_mobile_pin(pin_value):
            st.error("Enter your 4-8 digit PIN.")
            return False
        candidate_hash = _mobile_pin_hash(pin_value, care_home_id)
        legacy_hash = _mobile_pin_hash_legacy(pin_value, auth_uid, care_home_id)
        if candidate_hash != stored_hash and legacy_hash != stored_hash:
            st.error("Incorrect PIN.")
            return False
        mark_mobile_pin_verified()
        st.session_state["mobile_pin_just_accepted"] = True
        set_route(MOBILE_HOME_ROUTE)
        return True
    return is_mobile_pin_verified_for_session()


def fetch_care_home_staff_mobile_pin_status(
    access_token: str | None,
) -> tuple[list[dict], str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return [], error
    try:
        response = supabase.rpc("list_care_home_staff_mobile_pin_status").execute()
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return [], str(exc)
    rows = response.data if isinstance(response.data, list) else []
    return rows, None


def reset_care_home_staff_mobile_pin(
    access_token: str | None, staff_auth_user_id: str
) -> tuple[bool, str]:
    target_user_id = str(staff_auth_user_id or "").strip()
    if not target_user_id:
        return False, "Select a Mobile Support user first."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    try:
        supabase.rpc(
            "reset_staff_mobile_pin", {"p_staff_auth_user_id": target_user_id}
        ).execute()
        return True, "Mobile PIN reset. The Mobile Support user must set a new PIN at next Mobile login."
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return False, str(exc)


def upsert_family_user(
    access_token: str | None,
    *,
    care_home_id: str,
    auth_user_id: str,
    email: str,
    first_name: str,
    last_name: str,
    relationship: str = "",
) -> tuple[dict | None, str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None, error
    display_name = f"{first_name.strip()} {last_name.strip()}".strip()
    payload = {
        "care_home_id": care_home_id,
        "auth_user_id": auth_user_id,
        "email": email.strip().lower(),
        "display_name": display_name or "Family Member",
        "relationship": relationship.strip(),
        "active": True,
    }
    try:
        family_table = _family_user_table_name(supabase)
        # Older supabase-py versions do not support `.select()` chained after `.upsert()`.
        supabase.table(family_table).upsert(
            payload, on_conflict="auth_user_id"
        ).execute()
        resp = (
            supabase.table(family_table)
            .select("id, auth_user_id, care_home_id, email, display_name, relationship, active")
            .eq("auth_user_id", auth_user_id)
            .eq("care_home_id", care_home_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return None, str(exc)
    if not resp.data:
        return None, "Could not create Family Member mapping."
    return resp.data[0], None


def grant_resident_access(
    access_token: str | None,
    *,
    resident_id: str,
    family_user_id: str,
) -> tuple[dict | None, str | None]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None, error
    access_table = _resident_access_table_name(supabase)
    family_col = _resident_access_family_user_column(supabase)
    payload = {
        "resident_id": resident_id,
        family_col: family_user_id,
        "active": True,
    }
    try:
        # Older supabase-py versions do not support `.select()` chained after `.upsert()`.
        supabase.table(access_table).upsert(
            payload, on_conflict=f"resident_id,{family_col}"
        ).execute()
        resp = (
            supabase.table(access_table)
            .select(f"id, resident_id, {family_col}, active")
            .eq("resident_id", resident_id)
            .eq(family_col, family_user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return None, str(exc)
    if not resp.data:
        return None, "Could not create family member mapping."
    return resp.data[0], None


def _apply_family_registration_mapping(
    access_token: str | None, payload: dict
) -> tuple[bool, str | None]:
    contact_row, contact_error = upsert_family_user(
        access_token,
        care_home_id=str(payload.get("care_home_id") or ""),
        auth_user_id=str(payload.get("auth_user_id") or ""),
        email=str(payload.get("email") or ""),
        first_name=str(payload.get("first_name") or ""),
        last_name=str(payload.get("last_name") or ""),
        relationship=str(payload.get("relationship") or ""),
    )
    if contact_error or not contact_row:
        return False, contact_error or "Failed to upsert Family Member."
    _, access_error = grant_resident_access(
        access_token,
        resident_id=str(payload.get("resident_id") or ""),
        family_user_id=str(contact_row.get("id") or ""),
    )
    if access_error:
        return False, access_error
    return True, None


def render_office_family_registration_form(
    access_token: str | None, residents: list[dict]
) -> None:
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
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
    mode_value = get_operating_mode(access_token)
    lifecycle_stage_number = normalize_lifecycle_stage(get_lifecycle_stage(access_token))
    at_home_lifecycle_stage = lifecycle_stage_number in {1, 2, 3}
    workspace_labels = get_workspace_labels_for_lifecycle_stage(lifecycle_stage_number)
    organisation_label = str(workspace_labels.get("setup_label") or "Setup")
    subject_singular = str(workspace_labels.get("subject_singular") or "person")
    subject_singular_title = str(workspace_labels.get("subject_singular_title") or "Person")
    subject_plural = str(workspace_labels.get("subject_plural") or "people")
    decision_owner_label = (
        "organiser / family"
        if at_home_lifecycle_stage
        else str(workspace_labels.get("coordinator_label") or contact_label(mode_value))
    )

    office_residents = [
        resident
        for resident in residents
        if str(resident.get("care_home_id") or "") == care_home_id
    ]
    if not office_residents:
        st.info(f"No active {subject_plural} are available for family registration.")
        return

    active_care_home_name = str(
        st.session_state.get("active_care_home_name")
        or st.session_state.get("care_home_name")
        or ("this setup" if at_home_lifecycle_stage else "this care home")
    ).strip()
    if active_care_home_name.lower() in {"this care home", "this setup"}:
        resolved_care_home_name = fetch_active_care_home_name(access_token)
        if resolved_care_home_name:
            active_care_home_name = resolved_care_home_name
    registering_staff_name = str(
        st.session_state.get("auth_email")
        or st.session_state.get("auth_uid")
        or "Office staff"
    ).strip()
    registration_date = time.strftime("%d %b %Y")

    pending_key = "office_family_registration_pending"
    pending_payload = st.session_state.get(pending_key)
    if isinstance(pending_payload, dict) and pending_payload.get("care_home_id") == care_home_id:
        st.warning(
            "The invitation email was already sent, but the final app link may not have completed."
        )
        st.caption("Click below once to finish linking this Family Member without sending another email.")
        if st.button(
            "Finish linking Family Member",
            key="office_family_register_retry_mapping",
        ):
            ok, mapping_error = _apply_family_registration_mapping(
                access_token, pending_payload
            )
            if ok:
                st.session_state.pop(pending_key, None)
                st.success(
                    f"Family member linked to {subject_singular} access\n"
                    f"{organisation_label}: {active_care_home_name}\n"
                    f"Registered by: {registering_staff_name}\n"
                    f"Date: {registration_date}\n"
                    f"Family email: {pending_payload.get('email', 'contact')}"
                )
                st.rerun()
            else:
                st.error(mapping_error or "Could not finish the link. Please try again.")

    st.markdown("#### What to do")
    st.markdown(
        f"""
1. Choose the {subject_singular} this Family Member is linked to.
2. Enter the Family Member's name, email, and relationship.
3. Confirm that the right person or organisation has agreed they can be added.
4. Send the invitation.
5. The Family Member then signs in from the Family login page using the same email.
"""
    )
    if at_home_lifecycle_stage:
        st.caption(
            "For at-home use, the organiser / family decides who should be added. "
            "Keep any private records outside the app."
        )
    else:
        st.caption(
            f"For care-home use, {active_care_home_name} decides who should be added and keeps the registration record."
        )
    st.markdown("#### This registration")
    st.markdown(
        f"{organisation_label}: **{active_care_home_name}**  \n"
        f"Registered by: **{registering_staff_name}**  \n"
        f"Date: **{registration_date}**"
    )
    resident_options = []
    resident_by_id = {}
    resident_label_by_id = {}
    for resident in office_residents:
        resident_id = str(resident.get("id") or "")
        if not resident_id:
            continue
        label = format_resident_identity_label(
            resident,
            operating_mode=mode_value,
            include_room=bool(workspace_labels.get("show_room")),
            include_care_home=False,
            separator=" | ",
        )
        resident_options.append(resident_id)
        resident_by_id[resident_id] = resident
        resident_label_by_id[resident_id] = label
    if not resident_options:
        st.info(f"No valid {subject_plural} are available for family registration.")
        return

    invite_cooldown_key = "office_register_invite_cooldown_until"
    cooldown_until = float(st.session_state.get(invite_cooldown_key, 0.0) or 0.0)
    cooldown_remaining = max(0, int(cooldown_until - time.time()))
    if cooldown_remaining > 0:
        st.info(
            "For security, invitations are rate-limited. "
            f"Please wait {cooldown_remaining} seconds before sending another invite."
        )
        st.caption(
            "If you click repeatedly, the wait time can restart. Please click once and wait."
        )

    with st.form("office_register_family_member_form"):
        st.markdown("#### Family Member details")
        st.caption("Use the email address they will use to sign in.")
        first_name = st.text_input("First name", key="office_family_first_name")
        last_name = st.text_input("Last name", key="office_family_last_name")
        email = st.text_input("Email", key="office_family_email")
        relationship = st.text_input(
            f"Relationship to {subject_singular} (for example: daughter, cousin)",
            key="office_family_relationship",
        )
        st.markdown(f"#### Link to {subject_singular_title}")
        resident_id = st.selectbox(
            subject_singular_title,
            resident_options,
            format_func=lambda rid: resident_label_by_id.get(rid, subject_singular_title),
            key="office_family_resident_select",
        )
        st.markdown("#### Permission to add them")
        confirmation_copy = (
            f"I confirm that the organiser / family has decided this person may be added "
            f"as a Family Member for this {subject_singular} and is responsible for determining, "
            f"granting, and maintaining their access to the {subject_singular}."
            if at_home_lifecycle_stage
            else (
                f"I confirm that {active_care_home_name} has decided this person may be added "
                f"as a Family Member for this {subject_singular} and is solely responsible "
                f"for determining, granting, and maintaining their access to the {subject_singular}."
            )
        )
        resident_access_confirmed = st.checkbox(
            confirmation_copy,
            key="office_family_authorisation_confirm",
        )
        st.caption(
            f"familyupdates.care does not decide who may be added. The {decision_owner_label} is responsible for that decision."
        )
        st.caption(
            "Security note: after sending an invite, wait for the countdown before retrying."
        )
        submitted = st.form_submit_button(
            "Send invitation",
            disabled=cooldown_remaining > 0,
        )

    if not submitted:
        return

    first_value = first_name.strip()
    last_value = last_name.strip()
    normalized_email = email.strip().lower()
    relationship_value = relationship.strip()
    if not first_value or not last_value or not normalized_email:
        st.error("First name, last name, and email are required.")
        return
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        st.error("Enter a valid email address.")
        return
    if not resident_access_confirmed:
        st.error(f"Please confirm {decision_owner_label} authorisation before sending the invitation.")
        return

    resident = resident_by_id.get(resident_id)
    if not resident:
        st.error(f"Select a {subject_singular}.")
        return

    try:
        family_table = _family_user_table_name(supabase)
        existing_contact_resp = (
            supabase.table(family_table)
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
        st.error(f"That email is already registered for this {decision_owner_label}.")
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
        invite_error_text = str(invite_error or "Invite failed.")
        invite_error_lower = invite_error_text.lower()
        if (
            "security" in invite_error_lower
            or "too many requests" in invite_error_lower
            or "rate" in invite_error_lower
            or "60 seconds" in invite_error_lower
            or "1 minute" in invite_error_lower
        ):
            seconds_match = re.search(r"(\d+)\s*second", invite_error_text, re.IGNORECASE)
            cooldown_seconds = int(seconds_match.group(1)) if seconds_match else 60
            st.session_state[invite_cooldown_key] = time.time() + cooldown_seconds
            st.error(
                f"Invite blocked by security cooldown. Please wait {cooldown_seconds} seconds, then try once."
            )
            st.info(
                "The countdown resets if clicked repeatedly. Please do not click multiple times."
            )
        else:
            st.error(invite_error_text)
        return

    payload = {
        "care_home_id": care_home_id,
        "resident_id": resident_id,
        "auth_user_id": auth_user_id,
        "email": normalized_email,
        "first_name": first_value,
        "last_name": last_value,
        "relationship": relationship_value,
    }
    mapping_ok, mapping_error = _apply_family_registration_mapping(access_token, payload)
    if mapping_ok:
        st.session_state.pop(pending_key, None)
        st.success(
            "Invitation sent\n"
            f"{organisation_label}: {active_care_home_name}\n"
            f"Registered by: {registering_staff_name}\n"
            f"Date: {registration_date}\n"
            f"Family email: {normalized_email}\n"
            "Ask them to check spam/junk if they don't receive it."
        )
        return

    st.session_state[pending_key] = payload
    st.error(
        "The invitation email was sent, but the app did not finish linking this Family Member. Click 'Finish linking Family Member' above; do not send another invitation yet."
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
        redirect_to = ""
        if app_variant == VARIANT_FAMILY:
            redirect_to = os.getenv("PASSWORD_RESET_REDIRECT_URL", "").strip()
        elif app_variant in {VARIANT_MOBILE, VARIANT_OFFICE}:
            redirect_to = get_magic_link_redirect_url(app_variant).strip()

        if redirect_to:
            debug = os.getenv("APP_DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")
            if debug:
                st.info(f"Reset redirect_to: {redirect_to}")
            print(f"[auth] Password reset redirect_to={redirect_to!r} for variant={app_variant!r}")
            supabase.auth.reset_password_email(target_email, {"redirect_to": redirect_to})
        else:
            supabase.auth.reset_password_email(target_email)
    except Exception as exc:  # pragma: no cover - Supabase runtime error
        return False, str(exc)
    return True, "If this email is registered, a password reset link has been sent."


def try_refresh_session_from_state() -> bool:
    refresh_token = str(st.session_state.get("refresh_token") or "").strip()
    if not refresh_token:
        return False
    supabase, error = get_supabase_client()
    if error:
        return False
    try:
        try:
            auth_result = supabase.auth.refresh_session(refresh_token)
        except TypeError:
            auth_result = supabase.auth.refresh_session()
        session = getattr(auth_result, "session", None)
        user = getattr(auth_result, "user", None)
        if not session:
            return False
        access_token = str(getattr(session, "access_token", "") or "")
        new_refresh_token = str(getattr(session, "refresh_token", "") or "")
        if isinstance(session, dict):
            access_token = access_token or str(session.get("access_token") or "")
            new_refresh_token = new_refresh_token or str(session.get("refresh_token") or "")
            if user is None:
                user = session.get("user")
        if not access_token or not new_refresh_token:
            return False
        st.session_state["access_token"] = access_token
        st.session_state["refresh_token"] = new_refresh_token
        if user is not None:
            user_id = str(getattr(user, "id", "") or "")
            user_email = str(getattr(user, "email", "") or "")
            if isinstance(user, dict):
                user_id = user_id or str(user.get("id") or "")
                user_email = user_email or str(user.get("email") or "")
            if user_id:
                st.session_state["auth_uid"] = user_id
            if user_email:
                st.session_state["auth_email"] = user_email
        persist_auth_cookie(new_refresh_token)
        return True
    except Exception:
        return False


def get_mapping_status() -> tuple[bool, bool, str | None, dict | None, dict | None]:
    using_dev_bypass = st.session_state.get("access_token") == DEV_AUTH_BYPASS_TOKEN and is_dev_auth_bypass_active()
    if using_dev_bypass:
        supabase, error = get_admin_client()
    else:
        supabase, error = get_supabase_client()
    if error:
        return False, False, error, None, None
    for attempt in range(2):
        access_token = st.session_state.get("access_token")
        if not access_token:
            if attempt == 0 and try_refresh_session_from_state():
                continue
            return False, False, "No access token in session.", None, None
        try:
            if not using_dev_bypass:
                supabase.postgrest.auth(access_token)
            auth_uid = str(st.session_state.get("auth_uid") or "").strip()
            if not auth_uid:
                try:
                    user_result = supabase.auth.get_user(access_token)
                    user_obj = getattr(user_result, "user", None)
                    if user_obj is None and isinstance(user_result, dict):
                        user_obj = user_result.get("user")
                    if user_obj is not None:
                        auth_uid = str(getattr(user_obj, "id", "") or "")
                        auth_email = str(getattr(user_obj, "email", "") or "")
                        if isinstance(user_obj, dict):
                            auth_uid = auth_uid or str(user_obj.get("id") or "")
                            auth_email = auth_email or str(user_obj.get("email") or "")
                        if auth_uid:
                            st.session_state["auth_uid"] = auth_uid
                        if auth_email:
                            st.session_state["auth_email"] = auth_email
                except Exception:
                    pass
            if not auth_uid:
                return False, False, "Authenticated user identity could not be resolved.", None, None
            auth_email = str(st.session_state.get("auth_email") or "").strip().lower()
            family_table = _family_user_table_name(supabase)
            family_resp = (
                supabase.table(family_table)
                .select("id, care_home_id, display_name, auth_user_id, email")
                .eq("auth_user_id", auth_uid)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            family_record = family_resp.data[0] if family_resp.data else None
            if not family_record and auth_email:
                email_resp = (
                    supabase.table(family_table)
                    .select("id, care_home_id, display_name, auth_user_id, email")
                    .eq("email", auth_email)
                    .eq("active", True)
                    .limit(1)
                    .execute()
                )
                if not email_resp.data:
                    # Some legacy rows may have non-normalized email casing.
                    email_resp = (
                        supabase.table(family_table)
                        .select("id, care_home_id, display_name, auth_user_id, email")
                        .ilike("email", auth_email)
                        .eq("active", True)
                        .limit(1)
                        .execute()
                    )
                if email_resp.data:
                    family_record = email_resp.data[0]
                    existing_uid = str(family_record.get("auth_user_id") or "").strip()
                    if existing_uid != auth_uid:
                        try:
                            supabase.table(family_table).update({"auth_user_id": auth_uid}).eq(
                                "id", family_record.get("id")
                            ).execute()
                            family_record["auth_user_id"] = auth_uid
                        except Exception:
                            pass
            try:
                care_resp = (
                    supabase.table("care_home_users")
                    .select("id, care_home_id, care_access_level")
                    .eq("auth_user_id", auth_uid)
                    .eq("active", True)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                if not _is_missing_column_error(exc, "care_access_level"):
                    raise
                care_resp = (
                    supabase.table("care_home_users")
                    .select("id, care_home_id")
                    .eq("auth_user_id", auth_uid)
                    .eq("active", True)
                    .limit(1)
                    .execute()
                )
            care_record = care_resp.data[0] if care_resp.data else None
            family_found = family_record is not None
            care_found = care_record is not None
            return family_found, care_found, None, family_record, care_record
        except Exception as exc:  # pragma: no cover - Supabase runtime error
            if attempt == 0 and try_refresh_session_from_state():
                continue
            return False, False, str(exc), None, None
    return False, False, "Session mapping check failed.", None, None


def get_authed_supabase(access_token: str | None) -> tuple[object | None, str | None]:
    if access_token == DEV_AUTH_BYPASS_TOKEN:
        if not is_dev_auth_bypass_active():
            return None, "Local developer auth bypass is not active."
        return get_admin_client()
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


def normalize_totp_code(raw_code: str) -> str:
    return "".join(ch for ch in (raw_code or "") if ch.isdigit())


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
        st.session_state["mfa_last_error"] = "Missing authenticated user id."
        return False
    supabase, error = get_authed_supabase(access_token)
    if error:
        st.session_state["mfa_last_error"] = error
        return False
    payload = {
        "auth_user_id": auth_uid,
        "totp_secret": totp_secret,
        "recovery_code_hashes": recovery_code_hashes,
        "enabled": enabled,
    }
    try:
        supabase.table("care_hub_mfa").upsert(payload).execute()
        st.session_state.pop("mfa_last_error", None)
        return True
    except Exception as exc:
        st.session_state["mfa_last_error"] = str(exc)
        return False


def update_care_hub_mfa_codes(
    access_token: str | None,
    auth_uid: str | None,
    recovery_code_hashes: list[str],
) -> bool:
    if not auth_uid:
        st.session_state["mfa_last_error"] = "Missing authenticated user id."
        return False
    supabase, error = get_authed_supabase(access_token)
    if error:
        st.session_state["mfa_last_error"] = error
        return False
    try:
        (
            supabase.table("care_hub_mfa")
            .update({"recovery_code_hashes": recovery_code_hashes})
            .eq("auth_user_id", auth_uid)
            .execute()
        )
        st.session_state.pop("mfa_last_error", None)
        return True
    except Exception as exc:
        st.session_state["mfa_last_error"] = str(exc)
        return False

def render_access_gate(message: str, login_route: str, role: str) -> None:
    if role == "family":
        render_page_header("Family Hub")
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
            "Back to Family Hub login",
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
        render_route_link(
            "Back to hub selection",
            "/pr-home",
            key="public_wrong_back_link",
        )
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
    if st.button("Return", key=f"wrong_variant_public_{normalized_route.replace('/', '_')}"):
        route_variant = resolve_runtime_variant(route_hint=normalized_route)
        has_auth_tokens = bool(
            st.session_state.get("auth_uid")
            and st.session_state.get("access_token")
            and st.session_state.get("refresh_token")
        )
        care_session = bool(
            is_care_authenticated()
            or (
                has_auth_tokens
                and st.session_state.get("active_role") != "family"
            )
        )
        if care_session:
            if route_variant == VARIANT_OFFICE:
                set_route(get_home_route(VARIANT_OFFICE))
            elif route_variant == VARIANT_MOBILE:
                set_route(get_home_route(VARIANT_MOBILE))
            else:
                set_route(
                    get_home_route(
                        VARIANT_OFFICE
                        if bool(st.session_state.get("office_login_explicit"))
                        else VARIANT_MOBILE
                    )
                )
        elif route_variant == VARIANT_FAMILY:
            set_route(get_login_route(VARIANT_FAMILY))
        elif route_variant in {VARIANT_MOBILE, VARIANT_OFFICE}:
            redirect_to_public_landing()
            return
        else:
            set_route("/pr-home")
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


def is_current_at_home_lifecycle_stage(access_token: str | None = None) -> bool:
    token = access_token if access_token is not None else st.session_state.get("access_token")
    if not token or not str(st.session_state.get("active_care_home_id") or "").strip():
        return False
    return normalize_lifecycle_stage(get_lifecycle_stage(token)) in {1, 2, 3}


def _surname_from_display_name(display_name: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(display_name or "").strip())
    if not cleaned:
        return ""
    cleaned = re.sub(r"'s\s+home\Z", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+home\Z", "", cleaned, flags=re.IGNORECASE).strip()
    parts = [part.strip(" ,.;:()[]{}") for part in cleaned.split(" ") if part.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return ""


def get_at_home_voicemail_label(access_token: str | None = None) -> str:
    token = access_token if access_token is not None else st.session_state.get("access_token")
    known_person_name = str(st.session_state.get("circle_person_display_name") or "").strip()
    surname = _surname_from_display_name(known_person_name)
    if is_current_at_home_lifecycle_stage(token) and not surname and token:
        for person in fetch_care_home_residents(token):
            surname = _surname_from_display_name(get_resident_full_name(person))
            if surname:
                break
    workspace_type = (
        WORKSPACE_TYPE_FAMILY
        if is_current_at_home_lifecycle_stage(token)
        else WORKSPACE_TYPE_CARE_HOME
    )
    return str(get_workspace_labels(workspace_type, surname=surname).get("office_label") or "")


def render_how_it_works_diagram_and_notes() -> None:
    if is_current_at_home_lifecycle_stage():
        office_label = get_at_home_voicemail_label()
        st.markdown(
            f"- The diagram shows the main parts of the Family system: Family Hub, Mobile Support, and {office_label}.\n"
            "- Each Family Member has their own individual communication channel to the person.\n"
            "- Requests collect quick structured family responses to support simple coordination.\n"
            "- The person, organiser, or family can use the replies to make the decision.\n"
            "- Each channel keeps only the latest message, and a new message replaces the previous one in that channel."
        )
    else:
        st.markdown(
            "- The diagram shows the Care Home system: Care Home Family Hub, Care Home Mobile, and Care Home Office.\n"
            "- Each Family Member has their own individual communication channel to the resident.\n"
            "- Requests collect quick structured family responses to support efficient, inclusive decision-making.\n"
            "- The care home reviews responses and makes the final operational decision.\n"
            "- Each channel keeps only the latest message, and a new message replaces the previous one in that channel."
        )


def resolve_cartoon_asset() -> Path | None:
    preferred_names = [
        "familyupdates.png",
        "cartoon-familyupdates.png",
        "cartoon-voicemailcare.png",
        "cartoon-voicemailcare.png.png",
    ]
    for name in preferred_names:
        matched = resolve_asset_file(name)
        if matched is not None:
            return matched
    return None


def render_how_it_works_cartoon() -> None:
    cartoon_path = resolve_cartoon_asset()
    if cartoon_path is None:
        return
    try:
        st.image(str(cartoon_path), use_container_width=True)
    except TypeError:
        st.image(str(cartoon_path), use_column_width=True)


def get_how_it_works_access_copy(access_token: str | None, variant: str) -> list[str]:
    if is_current_at_home_lifecycle_stage(access_token):
        if variant == VARIANT_FAMILY:
            return [
                "Family Hub uses secure email login links. Family Members use Family Hub for family communication, not Mobile Support.",
            ]
        if variant == VARIANT_MOBILE:
            return [
                "Mobile Support may be used by the person providing practical support, paid or unpaid.",
                "Mobile uses individual PIN access for day-to-day use.",
                "Secure email link is used only for first sign-in or expired-session recovery.",
            ]
        return [
            "Family Office is the organiser access path for setup, Family Member registration, organiser updates, practical requests, and oversight.",
            "Mobile Support may be invited where a distinct practical support role is needed.",
            "Family Hub, Mobile, and Family Office use separate access routes.",
        ]
    if variant == VARIANT_FAMILY:
        return ["Family access uses secure email login links. No SMS and no phone-number login."]
    if variant == VARIANT_MOBILE:
        return [
            "Mobile uses individual PIN access for day-to-day use.",
            "Secure email link is used only for first sign-in or expired-session recovery.",
            "Family Office is a separate organiser access path.",
            "Office authentication is distinct from Family email links and Mobile PIN access.",
        ]
    return [
        "Family Office is a separate organiser access path.",
        "Office authentication is distinct from Family email links and Mobile PIN access.",
        "If Office 2FA is enabled, users complete Office verification after login.",
    ]


def render_how_it_works_family() -> None:
    render_page_header("How it works - Family Hub")
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
    access_token = st.session_state.get("access_token")
    render_stage_level_capability_tables(access_token)
    access_boxes = get_how_it_works_access_copy(access_token, VARIANT_FAMILY)
    if access_boxes:
        st.markdown("### Access")
        for box in access_boxes:
            st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    family_back_route = (
        get_home_route(VARIANT_FAMILY)
        if st.session_state.get("auth_uid")
        else get_login_route(VARIANT_FAMILY)
    )
    render_route_link("Back to Family Hub", family_back_route, key="family_how_it_works_back_link")


def render_how_it_works_mobile() -> None:
    render_page_header("How it works - Mobile")
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    mobile_session = bool(
        st.session_state.get("auth_uid")
        and str(st.session_state.get("active_role") or "").strip().lower() == "care_hub"
        and not bool(st.session_state.get("office_login_explicit"))
    )
    if runtime_variant == VARIANT_MOBILE or mobile_session:
        render_route_link(
            "Back to Mobile Hub messages",
            get_home_route(VARIANT_MOBILE),
            key="mobile_how_it_works_back_messages_link",
        )
    else:
        render_route_link(
            "Back to hub selection",
            get_home_route(VARIANT_PUBLIC),
            key="mobile_how_it_works_back_hubs_link",
        )
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
    access_token = st.session_state.get("access_token")
    render_stage_level_capability_tables(access_token)
    access_boxes = get_how_it_works_access_copy(access_token, VARIANT_MOBILE)
    if access_boxes:
        st.markdown("### Access")
        for box in access_boxes:
            st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)


def render_how_it_works_office_overview() -> None:
    access_token = st.session_state.get("access_token")
    office_label = get_at_home_voicemail_label(access_token)
    render_page_header(f"How it works - {office_label}")
    if get_app_variant() == VARIANT_PUBLIC:
        office_back_label = "Back to hub selection"
        office_back_route = get_home_route(VARIANT_PUBLIC)
    else:
        office_back_label = f"Back to {office_label}"
        office_back_route = get_home_route(VARIANT_OFFICE)
    render_route_link(
        office_back_label,
        office_back_route,
        key="office_how_it_works_back_top_link",
    )
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
    render_stage_level_capability_tables(access_token)
    access_boxes = get_how_it_works_access_copy(access_token, VARIANT_OFFICE)
    if access_boxes:
        st.markdown("### Access")
        for box in access_boxes:
            st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    render_route_link(
        office_back_label,
        office_back_route,
        key="office_how_it_works_back_bottom_link",
    )


def render_how_it_works_office() -> None:
    render_how_it_works_office_overview()


def render_family_document(title: str, path: str) -> None:
    render_page_header(title)
    access_token = st.session_state.get("access_token")
    resolved_path = resolve_mode_doc_path(path, access_token=access_token)
    try:
        content = Path(resolved_path).read_text(encoding="utf-8")
        content = re.sub(r"\A\s*#\s+.+?\n+", "", content, count=1)
    except OSError:
        st.error("Document not found.")
    else:
        st.markdown(content)
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", "/family/how-it-works", key="family_doc_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family Hub login",
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
    access_token = st.session_state.get("access_token")
    render_document_boxes(
        resolve_mode_doc_path(
            "docs/public/family_terms_summary.md",
            access_token=access_token,
        ),
        strip_first_heading=True,
    )
    st.markdown("---")
    st.markdown('<div id="full-terms-binding"></div>', unsafe_allow_html=True)
    st.markdown("## Full Terms of Use (Binding)")
    render_document_boxes(
        resolve_mode_doc_path(
            "docs/public/family_terms_of_use.md",
            access_token=access_token,
        ),
        strip_first_heading=True,
    )
    family_back_route = (
        get_home_route(VARIANT_FAMILY)
        if st.session_state.get("auth_uid")
        else get_login_route(VARIANT_FAMILY)
    )
    render_route_link("Back to Family Hub", family_back_route, key="family_terms_back_link")


def render_family_contact() -> None:
    access_token = st.session_state.get("access_token")
    mode_value = get_operating_mode(access_token)
    workspace_labels = get_workspace_labels_for_lifecycle_stage(get_lifecycle_stage(access_token))
    contact_party = (
        "coordinator"
        if is_current_at_home_lifecycle_stage(access_token)
        else str(workspace_labels.get("coordinator_label") or contact_label(mode_value))
    )
    render_page_header(f"Contact the {contact_party}")
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
        (
            f'<div class="family-contact-box">For access, questions, or support, '
            f'contact the {contact_party} directly.</div>'
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        (
            f'<div class="family-contact-box">For safeguarding concerns, contact the '
            f'{contact_party} directly; the platform is not monitored in real time.</div>'
        ),
        unsafe_allow_html=True,
    )
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", "/family/how-it-works", key="family_contact_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family Hub login",
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
        nav_cols = st.columns(3, gap="small")
        with nav_cols[0]:
            if st.button("Inbox", key="care_hub_nav_inbox", use_container_width=True):
                set_route(get_home_route(app_variant))
        with nav_cols[1]:
            if st.button("Contracts", key="care_hub_nav_contracts", use_container_width=True):
                set_route("/contracts")
        with nav_cols[2]:
            if st.button("Sign out", key="care_hub_nav_sign_out", use_container_width=True):
                sign_out_user("care_hub")


def render_care_hub_instructions() -> None:
    render_care_home_identity_banner(st.session_state.get("access_token"))
    app_variant = get_app_variant()
    if app_variant == VARIANT_OFFICE:
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def render_care_hub_training() -> None:
    render_care_home_identity_banner(st.session_state.get("access_token"))
    app_variant = get_app_variant()
    if app_variant == VARIANT_OFFICE:
        render_how_it_works_office()
    else:
        render_how_it_works_mobile()


def require_family_access() -> None:
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant != VARIANT_FAMILY:
        wrong_variant_screen(get_route(), "Family pages are not available in this app.")
    active_role = st.session_state.get("active_role")
    if st.session_state.get("auth_uid") and active_role and active_role != "family":
        wrong_variant_screen(get_route(), "This signed-in session belongs to the Care Home system.")
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
        render_wrong_variant("Your login details are for the Care Home system.")
        st.stop()
    render_access_gate("Account not set up yet.", get_login_route(VARIANT_FAMILY), "family")
    st.stop()


def require_care_access() -> None:
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant not in {VARIANT_MOBILE, VARIANT_OFFICE}:
        wrong_variant_screen(get_route(), "Care Home system pages are not available in this app.")
    if (
        runtime_variant == VARIANT_OFFICE
        and not bool(st.session_state.get("office_login_explicit"))
        and not bool(st.session_state.get("auth_uid"))
    ):
        if get_route() != get_login_route(VARIANT_OFFICE):
            set_route(get_login_route(VARIANT_OFFICE))
        st.stop()
    active_role = st.session_state.get("active_role")
    if st.session_state.get("auth_uid") and active_role and active_role != "care_hub":
        wrong_variant_screen(get_route(), "This signed-in session belongs to Family.")
    if not st.session_state.get("auth_uid"):
        render_access_gate(
            f"Please sign in to access {get_care_hub_label()}.",
            get_login_route(runtime_variant),
            "care_hub",
        )
        st.stop()
    family_found, care_found, error, _, care_record = get_mapping_status()
    if error:
        normalized_error = str(error).strip().lower()
        transient_session_error = (
            "resource temporarily unavailable" in normalized_error
            or "errno 11" in normalized_error
        )
        if transient_session_error:
            # Keep active sessions on transient backend/runtime errors instead of forcing logout.
            if (
                st.session_state.get("active_role") == "care_hub"
                and st.session_state.get("access_token")
            ):
                return
            render_access_gate(
                "Temporary session check issue. Please retry.",
                get_login_route(runtime_variant),
                "care_hub",
            )
            st.stop()
        if (
            st.session_state.get("active_role") == "care_hub"
            and st.session_state.get("access_token")
        ):
            return
        render_access_gate(
            f"Session check failed. Please sign in to access {get_care_hub_label()}.",
            get_login_route(runtime_variant),
            "care_hub",
        )
        st.stop()
    if care_found:
        if care_record:
            st.session_state["active_role"] = "care_hub"
            st.session_state["active_care_home_id"] = care_record.get("care_home_id")
            st.session_state["care_access_level"] = normalize_care_access_level(
                care_record.get("care_access_level")
            )
        if runtime_variant == VARIANT_OFFICE and not current_user_can_access_office():
            render_wrong_variant(
                "This account has Mobile access. It cannot use Family Office setup, registration, setup variables, or Account & Security."
            )
            st.stop()
        if runtime_variant == VARIANT_OFFICE:
            st.session_state["office_login_explicit"] = True
        if runtime_variant == VARIANT_OFFICE and is_office_mfa_required():
            if get_route() != "/care-hub/mfa":
                set_route("/care-hub/mfa")
            st.stop()
        return
    if family_found:
        render_access_gate(
            "This browser is signed in to Family Hub. Sign out of Family Hub before using Mobile or Family Office.",
            get_login_route(runtime_variant),
            "family",
        )
        st.stop()
    render_access_gate("Account not set up yet.", get_login_route(runtime_variant), "care_hub")
    st.stop()


def is_office_mfa_required() -> bool:
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant != VARIANT_OFFICE:
        return False
    if not st.session_state.get("auth_uid"):
        return False
    if st.session_state.get("mfa_verified"):
        return False
    if os.getenv("OFFICE_MFA_REQUIRED", "1").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    access_token = st.session_state.get("access_token")
    auth_uid = st.session_state.get("auth_uid")
    record = get_care_hub_mfa_record(access_token, auth_uid)
    return bool(record and record.get("enabled"))


def log_audit_event(
    action: str,
    role: str,
    care_home_id: str | None = None,
    target_id: str | None = None,
    resident_id: str | None = None,
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
    if resident_id:
        payload["resident_id"] = resident_id
    try:
        supabase.table("audit_log").insert(payload).execute()
    except Exception:
        return


def audit_event_exists(
    action: str,
    *,
    target_id: str | None = None,
    resident_id: str | None = None,
    care_home_id: str | None = None,
    actor_user_id: str | None = None,
) -> bool:
    supabase, error = get_supabase_client()
    if error:
        return False
    effective_actor_user_id = actor_user_id or st.session_state.get("auth_uid")
    if not effective_actor_user_id:
        return False
    access_token = st.session_state.get("access_token")
    if not access_token:
        return False
    try:
        supabase.postgrest.auth(access_token)
        query = (
            supabase.table("audit_log")
            .select("id")
            .eq("action", action)
            .eq("actor_user_id", effective_actor_user_id)
            .limit(1)
        )
        if target_id:
            query = query.eq("target_id", target_id)
        if resident_id:
            query = query.eq("resident_id", resident_id)
        if care_home_id:
            query = query.eq("care_home_id", care_home_id)
        resp = query.execute()
        return bool(resp.data)
    except Exception:
        return False


def audit_event_exists_any_actor(
    action: str,
    *,
    target_id: str | None = None,
    resident_id: str | None = None,
    care_home_id: str | None = None,
) -> bool:
    supabase, error = get_supabase_client()
    if error:
        return False
    access_token = st.session_state.get("access_token")
    if not access_token:
        return False
    try:
        supabase.postgrest.auth(access_token)
        query = supabase.table("audit_log").select("id").eq("action", action).limit(1)
        if target_id:
            query = query.eq("target_id", target_id)
        if resident_id:
            query = query.eq("resident_id", resident_id)
        if care_home_id:
            query = query.eq("care_home_id", care_home_id)
        resp = query.execute()
        return bool(resp.data)
    except Exception:
        return False


def audit_event_count_any_actor(
    action: str,
    *,
    target_id: str | None = None,
    resident_id: str | None = None,
    care_home_id: str | None = None,
) -> int:
    supabase, error = get_supabase_client()
    if error:
        return 0
    access_token = st.session_state.get("access_token")
    if not access_token:
        return 0
    try:
        supabase.postgrest.auth(access_token)
        query = supabase.table("audit_log").select("id", count="exact").eq("action", action)
        if target_id:
            query = query.eq("target_id", target_id)
        if resident_id:
            query = query.eq("resident_id", resident_id)
        if care_home_id:
            query = query.eq("care_home_id", care_home_id)
        resp = query.execute()
        if getattr(resp, "count", None) is not None:
            return int(resp.count or 0)
        return len(resp.data or [])
    except Exception:
        return 0


def get_message_play_counts_any_actor(
    message_ids: list[str],
    *,
    resident_id: str | None = None,
    care_home_id: str | None = None,
) -> dict[str, int]:
    normalized_ids: list[str] = []
    for value in message_ids:
        message_id = str(value or "").strip()
        if message_id and message_id not in normalized_ids:
            normalized_ids.append(message_id)
    if not normalized_ids:
        return {}

    cache = st.session_state.get("_message_play_count_cache")
    if not isinstance(cache, dict):
        cache = {}
        st.session_state["_message_play_count_cache"] = cache

    counts: dict[str, int] = {}
    uncached_ids: list[str] = []
    for message_id in normalized_ids:
        cache_key = f"{care_home_id or ''}::{resident_id or ''}::{message_id}"
        cached_value = cache.get(cache_key)
        if isinstance(cached_value, int):
            counts[message_id] = max(cached_value, 0)
        else:
            uncached_ids.append(message_id)

    if not uncached_ids:
        return counts

    supabase, error = get_supabase_client()
    access_token = st.session_state.get("access_token")
    if error or not access_token:
        for message_id in uncached_ids:
            count_value = audit_event_count_any_actor(
                "message_played",
                target_id=message_id,
                resident_id=resident_id,
                care_home_id=care_home_id,
            )
            counts[message_id] = count_value
            cache[f"{care_home_id or ''}::{resident_id or ''}::{message_id}"] = count_value
        return counts

    try:
        supabase.postgrest.auth(access_token)
        query = (
            supabase.table("audit_log")
            .select("target_id")
            .eq("action", "message_played")
            .in_("target_id", uncached_ids)
        )
        if resident_id:
            query = query.eq("resident_id", resident_id)
        if care_home_id:
            query = query.eq("care_home_id", care_home_id)
        resp = query.execute()
        for message_id in uncached_ids:
            counts[message_id] = 0
        for row in (resp.data or []):
            target_id = str((row or {}).get("target_id") or "").strip()
            if target_id in counts:
                counts[target_id] = int(counts.get(target_id, 0)) + 1
    except Exception:
        for message_id in uncached_ids:
            count_value = audit_event_count_any_actor(
                "message_played",
                target_id=message_id,
                resident_id=resident_id,
                care_home_id=care_home_id,
            )
            counts[message_id] = count_value

    for message_id in uncached_ids:
        cache[f"{care_home_id or ''}::{resident_id or ''}::{message_id}"] = int(
            counts.get(message_id, 0)
        )
    st.session_state["_message_play_count_cache"] = cache
    return counts


def has_message_been_played_since_recorded(
    message: dict | None,
    *,
    resident_id: str | None = None,
    care_home_id: str | None = None,
) -> bool:
    message_id = str((message or {}).get("id") or "").strip()
    message_contact_user_id = str((message or {}).get("contact_user_id") or "").strip()
    message_recorded_at = str((message or {}).get("recorded_at") or "").strip()
    if not message_id and not (message_contact_user_id and message_recorded_at):
        return False
    supabase, error = get_supabase_client()
    if error:
        return False
    access_token = st.session_state.get("access_token")
    if not access_token:
        return False
    try:
        supabase.postgrest.auth(access_token)
        if not (resident_id and care_home_id):
            return False
        if message_contact_user_id and message_recorded_at:
            last_played_recorded_at = get_contact_last_played_recorded_at(
                resident_id,
                care_home_id,
                message_contact_user_id,
                access_token,
            )
            if last_played_recorded_at:
                return last_played_recorded_at >= message_recorded_at

        # Fast path: if this exact message id has a played audit row after recorded_at,
        # it is read regardless of any historical target_id noise.
        if message_id:
            exact_query = (
                supabase.table("audit_log")
                .select("created_at")
                .eq("action", "message_played")
                .eq("resident_id", resident_id)
                .eq("care_home_id", care_home_id)
                .eq("target_id", message_id)
                .order("created_at", desc=True)
                .limit(1)
            )
            exact_resp = exact_query.execute()
            if exact_resp.data:
                latest_played_at = str(exact_resp.data[0].get("created_at") or "").strip()
                if not latest_played_at or not message_recorded_at:
                    return True
                dt_mod = __import__("datetime")
                played_dt = dt_mod.datetime.fromisoformat(latest_played_at.replace("Z", "+00:00"))
                recorded_dt = dt_mod.datetime.fromisoformat(message_recorded_at.replace("Z", "+00:00"))
                if played_dt.tzinfo is None:
                    played_dt = played_dt.replace(tzinfo=dt_mod.timezone.utc)
                if recorded_dt.tzinfo is None:
                    recorded_dt = recorded_dt.replace(tzinfo=dt_mod.timezone.utc)
                if played_dt >= recorded_dt:
                    return True
        return False
    except Exception:
        return False


def has_message_been_played_in_mobile_session_since_recorded(
    message: dict | None,
    *,
    resident_id: str | None = None,
) -> bool:
    resident_key = str(resident_id or "").strip()
    contact_user_id = str((message or {}).get("contact_user_id") or "").strip()
    recorded_at = str((message or {}).get("recorded_at") or "").strip()
    if not resident_key or not contact_user_id or not recorded_at:
        return False
    cache_key = f"care_mobile_played_cache_{resident_key}"
    cache = st.session_state.get(cache_key)
    if not isinstance(cache, dict):
        return False
    cached_recorded_at = str(cache.get(contact_user_id) or "").strip()
    if not cached_recorded_at:
        return False
    try:
        dt_mod = __import__("datetime")
        cached_dt = dt_mod.datetime.fromisoformat(cached_recorded_at.replace("Z", "+00:00"))
        recorded_dt = dt_mod.datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if cached_dt.tzinfo is None:
            cached_dt = cached_dt.replace(tzinfo=dt_mod.timezone.utc)
        if recorded_dt.tzinfo is None:
            recorded_dt = recorded_dt.replace(tzinfo=dt_mod.timezone.utc)
        return cached_dt >= recorded_dt
    except Exception:
        return cached_recorded_at >= recorded_at


def sort_contacts_for_playback(contacts: list[dict]) -> list[dict]:
    return sorted(
        contacts,
        key=lambda c: (
            str(c.get("id") or ""),
            str(c.get("full_name") or "").strip().casefold(),
            str(c.get("auth_user_id") or "").strip(),
        ),
    )


def dedupe_contacts_by_auth_user_id(contacts: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_user_ids: set[str] = set()
    for contact in sort_contacts_for_playback(contacts):
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not contact_user_id:
            continue
        if contact_user_id in seen_user_ids:
            continue
        seen_user_ids.add(contact_user_id)
        deduped.append(contact)
    return deduped


def _message_has_audio_pointer(message: dict | None) -> bool:
    if not isinstance(message, dict):
        return False
    return bool(
        str(message.get("audio_object_path") or "").strip()
        or str(message.get("audio_storage_path") or "").strip()
    )


def _fetch_latest_message_for_contact_strict(
    resident_id: str,
    access_token: str,
    contact: dict,
    *,
    channel: str = "resident_family",
    include_audio: bool = True,
) -> dict | None:
    contact_user_id = str(contact.get("auth_user_id") or "").strip()
    contact_id = str(contact.get("id") or "").strip()
    if contact_user_id:
        latest = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            contact_user_id=contact_user_id,
            channel=channel,
            include_audio=include_audio,
        )
        if latest:
            return latest
    if contact_id:
        latest = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            family_id=contact_id,
            channel=channel,
            include_audio=include_audio,
        )
        if latest:
            return latest
    contact_email = str(contact.get("email") or "").strip().lower()
    if contact_email:
        resolved_user_id = _get_contact_auth_user_id_via_email(contact_email).strip()
        if resolved_user_id:
            contact["auth_user_id"] = resolved_user_id
            latest = fetch_latest_message(
                resident_id,
                "to_resident",
                access_token,
                contact_user_id=resolved_user_id,
                channel=channel,
                include_audio=include_audio,
            )
            if latest:
                return latest
    return None


def get_next_contact_user_id_in_order(
    contacts_sorted: list[dict],
    current_contact_user_id: str | None,
) -> str | None:
    if not contacts_sorted:
        return None
    ordered_user_ids = [
        str(c.get("auth_user_id") or "").strip()
        for c in contacts_sorted
        if str(c.get("auth_user_id") or "").strip()
    ]
    if not ordered_user_ids:
        return None
    current = str(current_contact_user_id or "").strip()
    if current and current in ordered_user_ids:
        idx = ordered_user_ids.index(current)
        return ordered_user_ids[(idx + 1) % len(ordered_user_ids)]
    return ordered_user_ids[0]


def get_next_contact_user_id_with_message(
    resident_id: str,
    contacts: list[dict],
    access_token: str,
    current_contact_user_id: str | None,
) -> str | None:
    contacts_sorted = sort_contacts_for_playback(contacts)
    resolved_contact_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not contact_user_id:
            contact_email = str(contact.get("email") or "").strip().lower()
            if contact_email:
                contact_user_id = _get_contact_auth_user_id_via_email(contact_email).strip()
                if contact_user_id:
                    contact["auth_user_id"] = contact_user_id
        if contact_user_id:
            resolved_contact_user_ids.append(contact_user_id)
    latest_by_contact = fetch_latest_messages_for_contact_user_ids(
        resident_id,
        access_token,
        resolved_contact_user_ids,
        channel="resident_family",
        include_audio=True,
    )
    ordered_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
            latest = _fetch_latest_message_for_contact_strict(
                resident_id,
                access_token,
                contact,
                channel="resident_family",
                include_audio=True,
            )
            contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not latest:
            continue
        if not _message_has_audio_pointer(latest):
            continue
        if contact_user_id not in ordered_user_ids:
            ordered_user_ids.append(contact_user_id)
    if not ordered_user_ids:
        return None
    current = str(current_contact_user_id or "").strip()
    if current and current in ordered_user_ids:
        idx = ordered_user_ids.index(current)
        return ordered_user_ids[(idx + 1) % len(ordered_user_ids)]
    return ordered_user_ids[0]


def get_resident_playback_pointer(
    resident_id: str,
    care_home_id: str,
    access_token: str | None,
) -> str | None:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        resp = (
            supabase.table("resident_playback_state")
            .select("next_contact_user_id")
            .eq("resident_id", resident_id)
            .eq("care_home_id", care_home_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if not resp.data:
        return None
    return str(resp.data[0].get("next_contact_user_id") or "").strip() or None


def set_resident_playback_pointer(
    resident_id: str,
    care_home_id: str,
    next_contact_user_id: str | None,
    access_token: str | None,
) -> None:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return
    payload = {
        "resident_id": resident_id,
        "care_home_id": care_home_id,
        "next_contact_user_id": next_contact_user_id,
        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("resident_playback_state").upsert(
            payload,
            on_conflict="resident_id,care_home_id",
        ).execute()
    except Exception:
        try:
            supabase.table("resident_playback_state").upsert(
                payload,
                on_conflict="resident_id",
            ).execute()
        except Exception:
            return


def get_contact_last_played_recorded_at(
    resident_id: str,
    care_home_id: str,
    contact_user_id: str,
    access_token: str | None,
) -> str:
    if not resident_id or not care_home_id or not contact_user_id:
        return ""
    cache_key = f"contact_last_played_cache::{resident_id}::{care_home_id}::{contact_user_id}"
    cache = st.session_state.get(cache_key, None)
    if isinstance(cache, str):
        return cache
    supabase, error = get_authed_supabase(access_token)
    if error:
        return ""
    try:
        resp = (
            supabase.table("resident_contact_playback_state")
            .select("last_played_recorded_at")
            .eq("resident_id", resident_id)
            .eq("care_home_id", care_home_id)
            .eq("contact_user_id", contact_user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        return ""
    if not resp.data:
        st.session_state[cache_key] = ""
        return ""
    last_played = str(resp.data[0].get("last_played_recorded_at") or "").strip()
    st.session_state[cache_key] = last_played
    return last_played


def set_contact_last_played_recorded_at(
    resident_id: str,
    care_home_id: str,
    contact_user_id: str,
    played_recorded_at: str | None,
    access_token: str | None,
) -> None:
    played_value = str(played_recorded_at or "").strip()
    if not resident_id or not care_home_id or not contact_user_id or not played_value:
        return
    supabase, error = get_authed_supabase(access_token)
    if error:
        return
    payload = {
        "resident_id": resident_id,
        "care_home_id": care_home_id,
        "contact_user_id": contact_user_id,
        "last_played_recorded_at": played_value,
        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    try:
        supabase.table("resident_contact_playback_state").upsert(
            payload,
            on_conflict="resident_id,contact_user_id",
        ).execute()
        cache_key = f"contact_last_played_cache::{resident_id}::{care_home_id}::{contact_user_id}"
        st.session_state[cache_key] = played_value
    except Exception:
        return


def clear_resident_contact_playback_state(
    resident_id: str,
    care_home_id: str,
    access_token: str | None,
) -> bool:
    if not resident_id or not care_home_id:
        return False
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False
    try:
        supabase.table("resident_contact_playback_state").delete().eq(
            "resident_id", resident_id
        ).eq("care_home_id", care_home_id).execute()
        cache_prefix = f"contact_last_played_cache::{resident_id}::{care_home_id}::"
        for key in list(st.session_state.keys()):
            if str(key).startswith(cache_prefix):
                st.session_state.pop(key, None)
        return True
    except Exception:
        return False


def select_next_family_message_for_mobile(
    resident_id: str,
    care_home_id: str,
    contacts: list[dict],
    access_token: str,
) -> tuple[dict | None, dict | None, str]:
    contacts_sorted = sort_contacts_for_playback(contacts)
    if not contacts_sorted:
        return None, None, "No linked family contacts."

    resolved_contact_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not contact_user_id:
            contact_email = str(contact.get("email") or "").strip().lower()
            if contact_email:
                contact_user_id = _get_contact_auth_user_id_via_email(contact_email).strip()
                if contact_user_id:
                    contact["auth_user_id"] = contact_user_id
        if contact_user_id:
            resolved_contact_user_ids.append(contact_user_id)
    latest_by_contact = fetch_latest_messages_for_contact_user_ids(
        resident_id,
        access_token,
        resolved_contact_user_ids,
        channel="resident_family",
        include_audio=True,
    )

    queued_items: list[dict] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
            latest = _fetch_latest_message_for_contact_strict(
                resident_id,
                access_token,
                contact,
                channel="resident_family",
                include_audio=True,
            )
            contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not latest:
            continue
        if not _message_has_audio_pointer(latest):
            continue
        if not contact_user_id:
            continue
        if str(latest.get("contact_user_id") or "").strip() != contact_user_id:
            latest = dict(latest)
            latest["contact_user_id"] = contact_user_id
        contact["auth_user_id"] = contact_user_id
        message_id = str(latest.get("id") or "").strip()
        queued_items.append(
            {
                "contact": contact,
                "message": latest,
                "message_id": message_id,
                "contact_user_id": contact_user_id,
            }
        )

    if not queued_items:
        fallback_latest = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            channel="resident_family",
            include_audio=True,
        )
        if fallback_latest and not _message_has_audio_pointer(fallback_latest):
            fallback_latest = None
        if fallback_latest:
            fallback_contact = None
            fallback_contact_user_id = str(fallback_latest.get("contact_user_id") or "").strip()
            if fallback_contact_user_id:
                fallback_contact = next(
                    (
                        contact
                        for contact in contacts_sorted
                        if str(contact.get("auth_user_id") or "").strip() == fallback_contact_user_id
                    ),
                    None,
                )
            if fallback_contact is None and len(contacts_sorted) == 1:
                fallback_contact = contacts_sorted[0]
            if fallback_contact is not None:
                return fallback_contact, fallback_latest, "Fallback latest"
        return None, None, "No family messages available."

    last_played_cache = st.session_state.get(f"care_mobile_last_played_{resident_id}")
    if isinstance(last_played_cache, dict):
        last_played_contact_user_id = str(last_played_cache.get("contact_user_id") or "").strip()
        last_played_recorded_at = str(last_played_cache.get("recorded_at") or "").strip()
    else:
        last_played_contact_user_id = ""
        last_played_recorded_at = ""

    pointer = get_resident_playback_pointer(resident_id, care_home_id, access_token)
    # Prefer session pointer for active runtime progression; DB pointer can be stale.
    session_pointer_key = f"care_mobile_pointer_{resident_id}"
    session_pointer = str(st.session_state.get(session_pointer_key) or "").strip()
    if session_pointer:
        pointer = session_pointer
    by_contact_user_id = {
        str(item.get("contact_user_id") or "").strip(): item for item in queued_items
    }
    ordered_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if contact_user_id and contact_user_id in by_contact_user_id and contact_user_id not in ordered_user_ids:
            ordered_user_ids.append(contact_user_id)
    if not ordered_user_ids:
        return queued_items[0]["contact"], queued_items[0]["message"], "Played cycle"

    play_counts_by_message_id = get_message_play_counts_any_actor(
        [str(item.get("message_id") or "").strip() for item in queued_items],
        resident_id=resident_id,
        care_home_id=care_home_id,
    )
    for item in queued_items:
        message_id = str(item.get("message_id") or "").strip()
        item["play_count"] = int(play_counts_by_message_id.get(message_id, 0))

    min_play_count = min(int(item.get("play_count") or 0) for item in queued_items)
    active_round_user_ids = {
        str(item.get("contact_user_id") or "").strip()
        for item in queued_items
        if int(item.get("play_count") or 0) == min_play_count
    }
    if active_round_user_ids:
        # Unread round uses fixed contact order, but continue from saved pointer.
        start_idx = 0
        if pointer and pointer in ordered_user_ids:
            start_idx = ordered_user_ids.index(pointer)
        for offset in range(len(ordered_user_ids)):
            candidate_user_id = ordered_user_ids[(start_idx + offset) % len(ordered_user_ids)]
            if candidate_user_id in active_round_user_ids:
                chosen = by_contact_user_id.get(candidate_user_id)
                if chosen:
                    chosen_recorded_at = str(
                        ((chosen.get("message") or {}).get("recorded_at") or "")
                    ).strip()
                    if (
                        len(active_round_user_ids) > 1
                        and candidate_user_id == last_played_contact_user_id
                        and chosen_recorded_at
                        and chosen_recorded_at == last_played_recorded_at
                    ):
                        continue
                    queue_label = (
                        "Unplayed first (round 0)"
                        if min_play_count == 0
                        else f"Play-count round {min_play_count}"
                    )
                    return (
                        chosen["contact"],
                        chosen["message"],
                        queue_label,
                    )

    start_idx = 0
    if pointer and pointer in ordered_user_ids:
        start_idx = ordered_user_ids.index(pointer)
    chosen_user_id = ordered_user_ids[start_idx]
    chosen = by_contact_user_id.get(chosen_user_id)
    if not chosen:
        chosen = queued_items[0]
    return chosen["contact"], chosen["message"], "Played cycle"


def find_next_playable_family_message_in_order(
    resident_id: str,
    contacts: list[dict],
    access_token: str,
    *,
    start_after_contact_user_id: str | None = None,
    channel: str = "resident_family",
) -> tuple[dict | None, dict | None, bytes | str | None, str]:
    contacts_sorted = sort_contacts_for_playback(contacts)
    if not contacts_sorted:
        return None, None, None, "none"

    start_idx = 0
    start_after = str(start_after_contact_user_id or "").strip()
    if start_after:
        for idx, contact in enumerate(contacts_sorted):
            contact_user_id = str(contact.get("auth_user_id") or "").strip()
            if not contact_user_id:
                contact_email = str(contact.get("email") or "").strip().lower()
                if contact_email:
                    contact_user_id = _get_contact_auth_user_id_via_email(contact_email).strip()
                    if contact_user_id:
                        contact["auth_user_id"] = contact_user_id
            if contact_user_id and contact_user_id == start_after:
                start_idx = (idx + 1) % len(contacts_sorted)
                break

    fallback_contact: dict | None = None
    fallback_latest: dict | None = None
    for offset in range(len(contacts_sorted)):
        contact = contacts_sorted[(start_idx + offset) % len(contacts_sorted)]
        latest = fetch_latest_message_for_contact_with_mapping_repair(
            resident_id,
            access_token,
            contact,
            channel=channel,
            include_audio=True,
        )
        if not latest:
            continue
        if not _message_has_audio_pointer(latest):
            continue
        if fallback_contact is None:
            fallback_contact = contact
            fallback_latest = latest
        playback_source, playback_source_kind = resolve_audio_playback_source(
            latest,
            access_token=access_token,
        )
        if playback_source:
            return contact, latest, playback_source, playback_source_kind
    if fallback_contact is not None and fallback_latest is not None:
        return fallback_contact, fallback_latest, None, "none"
    return None, None, None, "none"


def get_family_queue_status_for_resident(
    resident_id: str,
    care_home_id: str,
    contacts: list[dict],
    access_token: str,
) -> tuple[int, dict | None, list[dict]]:
    contacts_sorted = sort_contacts_for_playback(contacts)
    if not contacts_sorted:
        return 0, None, []
    resolved_contact_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not contact_user_id:
            contact_email = str(contact.get("email") or "").strip().lower()
            if contact_email:
                contact_user_id = _get_contact_auth_user_id_via_email(contact_email).strip()
                if contact_user_id:
                    contact["auth_user_id"] = contact_user_id
        if contact_user_id:
            resolved_contact_user_ids.append(contact_user_id)
    latest_by_contact = fetch_latest_messages_for_contact_user_ids(
        resident_id,
        access_token,
        resolved_contact_user_ids,
        channel="resident_family",
        include_audio=True,
    )
    unread_count = 0
    unread_contacts: list[dict] = []
    next_contact: dict | None = None
    queued_items: list[dict] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
            latest = _fetch_latest_message_for_contact_strict(
                resident_id,
                access_token,
                contact,
                channel="resident_family",
                include_audio=True,
            )
            contact_user_id = str(contact.get("auth_user_id") or "").strip()
        if not latest:
            continue
        if not _message_has_audio_pointer(latest):
            continue
        if contact_user_id and str(latest.get("contact_user_id") or "").strip() != contact_user_id:
            latest = dict(latest)
            latest["contact_user_id"] = contact_user_id
        queued_items.append(
            {
                "contact": contact,
                "message_id": str(latest.get("id") or "").strip(),
            }
        )

    play_counts_by_message_id = get_message_play_counts_any_actor(
        [str(item.get("message_id") or "").strip() for item in queued_items],
        resident_id=resident_id,
        care_home_id=care_home_id,
    )

    min_play_count: int | None = None
    for item in queued_items:
        contact = item.get("contact")
        if not isinstance(contact, dict):
            continue
        message_id = str(item.get("message_id") or "").strip()
        play_count = int(play_counts_by_message_id.get(message_id, 0))
        if min_play_count is None or play_count < min_play_count:
            min_play_count = play_count
            next_contact = contact
        if play_count == 0:
            unread_count += 1
            unread_contacts.append(contact)

    if unread_contacts:
        next_contact = unread_contacts[0]
    return unread_count, next_contact, unread_contacts


def run_daily_audit_log_retention_purge() -> None:
    if st.session_state.get("active_role") != "care_hub":
        return
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id:
        return
    today = __import__("datetime").datetime.utcnow().date().isoformat()
    session_key = f"audit_purge_checked_{care_home_id}"
    if st.session_state.get(session_key) == today:
        return
    st.session_state[session_key] = today

    supabase, error = get_supabase_client()
    if error:
        return
    actor_user_id = st.session_state.get("auth_uid")
    access_token = st.session_state.get("access_token")
    if not actor_user_id or not access_token:
        return
    try:
        supabase.postgrest.auth(access_token)
        today_start_iso = f"{today}T00:00:00"
        already_ran = (
            supabase.table("audit_log")
            .select("id")
            .eq("action", "maintenance_purge")
            .eq("care_home_id", care_home_id)
            .gte("created_at", today_start_iso)
            .limit(1)
            .execute()
        )
        if already_ran.data:
            return
        cutoff_iso = (
            __import__("datetime").datetime.utcnow()
            - __import__("datetime").timedelta(days=90)
        ).isoformat()
        supabase.table("audit_log").delete().eq("care_home_id", care_home_id).eq(
            "action", "message_played"
        ).lt("created_at", cutoff_iso).execute()
        supabase.table("audit_log").delete().eq("care_home_id", care_home_id).eq(
            "action", "message_sent"
        ).lt("created_at", cutoff_iso).execute()
        log_audit_event("maintenance_purge", "care_hub", care_home_id)
    except Exception:
        return


def clear_session_state(*, preserve_keys: set[str] | None = None) -> None:
    preserved = preserve_keys or set()
    for key in list(st.session_state.keys()):
        if key in preserved:
            continue
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
    active_role = st.session_state.get("active_role")
    if active_role == "family":
        timeout_seconds = FAMILY_SESSION_TIMEOUT_SECONDS
    else:
        timeout_seconds = get_care_hub_idle_timeout_seconds(st.session_state.get("access_token"))
    if last_active and (now - last_active) > timeout_seconds:
        role = st.session_state.get("active_role")
        if role:
            log_audit_event(
                "session_timeout",
                role,
                st.session_state.get("active_care_home_id"),
            )
        timeout_notice = (
            "Your session timed out after inactivity. Please sign in again."
        )
        clear_session_state()
        st.session_state["session_timeout_notice"] = timeout_notice
        set_route(get_default_route(get_app_variant()))
        st.stop()
    st.session_state["last_active_at"] = now


def trigger_live_message_refresh(key: str, disabled: bool) -> None:
    if disabled or st_autorefresh is None or not APP_LIVE_REFRESH:
        return
    st_autorefresh(interval=APP_LIVE_REFRESH_INTERVAL_MS, key=key)


def is_variant_live_refresh_enabled(app_variant: str) -> bool:
    if app_variant == VARIANT_FAMILY:
        return APP_FAMILY_LIVE_REFRESH
    if app_variant == VARIANT_MOBILE:
        return APP_MOBILE_LIVE_REFRESH
    if app_variant == VARIANT_OFFICE:
        return APP_OFFICE_LIVE_REFRESH
    return False


def reset_outbox_state_on_new_recording(
    state: dict | None,
    ack_widget_key: str | None = None,
    clear_care_last_sent_for_resident: str | None = None,
    update_widget_state: bool = True,
) -> None:
    if isinstance(state, dict):
        state["preview_confirmed"] = False
        state["last_message"] = None
        clear_transcript_preview_state(state)
    if ack_widget_key and update_widget_state:
        st.session_state[ack_widget_key] = False
    if clear_care_last_sent_for_resident:
        last_sent = st.session_state.get("care_last_sent")
        if (
            isinstance(last_sent, dict)
            and last_sent.get("resident_id") == clear_care_last_sent_for_resident
        ):
            st.session_state.pop("care_last_sent", None)


def get_linked_residents() -> list[dict]:
    return []


def fetch_family_residents(user_id: str, access_token: str) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    try:
        family_table = _family_user_table_name(supabase)
        access_table = _resident_access_table_name(supabase)
        family_col = _resident_access_family_user_column(supabase)
        contact_resp = (
            supabase.table(family_table)
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
            supabase.table(access_table)
            .select(
                "resident_id, residents(id, preferred_display_name, care_home_reference, care_home_id)"
            )
            .eq(family_col, contact_id)
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
                    "family_id": resident.get("id"),
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
        care_home_name = ""
        try:
            care_home_resp = (
                supabase.table("care_homes")
                .select("name")
                .eq("id", care_home_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            care_home_name = str(((care_home_resp.data or [{}])[0].get("name") or "")).strip()
        except Exception:
            care_home_name = ""
        residents = []
        for resident in resident_resp.data or []:
            display_name = resident.get("preferred_display_name", "Resident")
            residents.append(
                {
                    "id": resident.get("id"),
                    "preferred_name": display_name,
                    "surname": "",
                    "room": resident.get("care_home_reference", ""),
                    "care_home": care_home_name,
                    "family_id": resident.get("id"),
                    "care_home_id": resident.get("care_home_id"),
                }
            )
        return residents
    except Exception:
        return []


def update_person_display_names(
    access_token: str | None,
    person_name_updates: dict[str, str],
) -> tuple[bool, str | None]:
    cleaned_updates = {
        str(person_id or "").strip(): str(person_name or "").strip()
        for person_id, person_name in (person_name_updates or {}).items()
        if str(person_id or "").strip() and str(person_name or "").strip()
    }
    if not cleaned_updates:
        return True, None
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    try:
        for person_id, person_name in cleaned_updates.items():
            supabase.table("residents").update(
                {"preferred_display_name": person_name[:160]}
            ).eq("id", person_id).execute()
        return True, None
    except Exception as exc:
        return False, str(exc)


def fetch_active_care_home_name(access_token: str | None) -> str:
    profile = fetch_active_care_home_profile(access_token)
    return str(profile.get("name") or "").strip()


def normalize_care_hub_idle_timeout_seconds(timeout_value: object) -> int:
    try:
        parsed = int(timeout_value)
    except (TypeError, ValueError):
        parsed = CARE_HUB_SESSION_TIMEOUT_SECONDS
    allowed_values = set(CARE_HUB_IDLE_TIMEOUT_OPTIONS_SECONDS)
    return parsed if parsed in allowed_values else CARE_HUB_SESSION_TIMEOUT_SECONDS


def normalize_transcript_policy_mode(policy_value: object) -> str:
    candidate = str(policy_value or "").strip().lower()
    if candidate in TRANSCRIPT_POLICY_MODES:
        return candidate
    return "assist"


def normalize_operating_mode(mode_value: object) -> str:
    candidate = str(mode_value or "").strip().lower()
    if candidate == LEGACY_OPERATING_MODE_CARE_HOME:
        return OPERATING_MODE_CARE_ORGANISATION
    if candidate == LEGACY_OPERATING_MODE_FAMILY_LED:
        return OPERATING_MODE_PERSONAL_USE
    if candidate in {OPERATING_MODE_CARE_ORGANISATION, OPERATING_MODE_PERSONAL_USE}:
        return candidate
    fallback = str(DEFAULT_OPERATING_MODE or OPERATING_MODE_CARE_ORGANISATION).strip().lower()
    if fallback in {OPERATING_MODE_CARE_ORGANISATION, OPERATING_MODE_PERSONAL_USE}:
        return fallback
    return OPERATING_MODE_CARE_ORGANISATION


def normalize_lifecycle_stage(stage_value: object) -> int:
    try:
        parsed = int(stage_value)
    except Exception:
        parsed = int(DEFAULT_LIFECYCLE_STAGE)
    return max(1, min(parsed, 4))


WORKSPACE_TYPE_FAMILY = "family"
WORKSPACE_TYPE_CARE_HOME = "care_home"


def normalize_workspace_type(workspace_type: object) -> str:
    candidate = str(workspace_type or "").strip().lower()
    if candidate in {WORKSPACE_TYPE_FAMILY, WORKSPACE_TYPE_CARE_HOME}:
        return candidate
    return WORKSPACE_TYPE_CARE_HOME


def get_workspace_type_for_lifecycle_stage(stage_value: object) -> str:
    stage = normalize_lifecycle_stage(stage_value)
    if stage in {1, 2, 3}:
        return WORKSPACE_TYPE_FAMILY
    return WORKSPACE_TYPE_CARE_HOME


def get_workspace_labels(
    workspace_type: object,
    *,
    surname: str = "",
    setup_name: str = "",
) -> dict[str, object]:
    normalized_type = normalize_workspace_type(workspace_type)
    cleaned_surname = str(surname or "").strip()
    cleaned_setup_name = str(setup_name or "").strip()
    family_office_label = f"{cleaned_surname} Family Office" if cleaned_surname else "Family Office"
    family_setup_label = cleaned_setup_name or family_office_label
    if normalized_type == WORKSPACE_TYPE_FAMILY:
        return {
            "workspace_type": WORKSPACE_TYPE_FAMILY,
            "workspace_type_label": "Family system",
            "workspace_name": family_setup_label,
            "setup_label": "Family setup",
            "setup_context_label": "family setup",
            "office_label": family_office_label,
            "mobile_label": "Family Mobile",
            "hub_label": "Family Hub",
            "subject_singular": "person",
            "subject_singular_title": "Person",
            "subject_plural": "people",
            "subject_plural_title": "People",
            "coordinator_label": "Family Organiser",
            "main_contact_label": "Main supporter / organiser (optional)",
            "organisation_label": "Family system",
            "show_room": False,
            "room_label": "",
            "governance_label": "Family-managed",
            "transcript_help_context": "Family system",
        }
    care_home_setup_label = cleaned_setup_name or "Care Home system"
    return {
        "workspace_type": WORKSPACE_TYPE_CARE_HOME,
        "workspace_type_label": "Care Home system",
        "workspace_name": care_home_setup_label,
        "setup_label": "Care home",
        "setup_context_label": "care home",
        "office_label": "Care Home Office",
        "mobile_label": "Care Home Mobile",
        "hub_label": "Care Home Family Hub",
        "subject_singular": "resident",
        "subject_singular_title": "Resident",
        "subject_plural": "residents",
        "subject_plural_title": "Residents",
        "coordinator_label": "Care home coordinator",
        "main_contact_label": "Care home contact / coordinator (optional)",
        "organisation_label": "Care home",
        "show_room": True,
        "room_label": "Room",
        "governance_label": "Care-home-managed",
        "transcript_help_context": "Care Home system",
    }


def get_workspace_labels_for_lifecycle_stage(
    stage_value: object,
    *,
    surname: str = "",
    setup_name: str = "",
) -> dict[str, object]:
    return get_workspace_labels(
        get_workspace_type_for_lifecycle_stage(stage_value),
        surname=surname,
        setup_name=setup_name,
    )


def get_lifecycle_stage_label(stage_value: object) -> str:
    stage = normalize_lifecycle_stage(stage_value)
    labels = {
        1: "At home",
        2: "At home",
        3: "At home",
        4: "Care home",
    }
    return labels.get(stage, "At home")


def get_lifecycle_stage_setup_note(stage_value: object) -> str:
    stage = normalize_lifecycle_stage(stage_value)
    notes = {
        1: "At home: communication structure is needed to help the Family Organiser provide essential support, family communication, and life-admin structure. Mobile Support can be added if another person also provides practical support.",
        2: "At home: communication structure is needed to help the Family Organiser provide essential support, family communication, and life-admin structure. Mobile Support can be added if another person also provides practical support.",
        3: "At home: communication structure is needed to help the Family Organiser provide essential support, family communication, and life-admin structure. Mobile Support can be added if another person also provides practical support.",
        4: "Care home: the person is living in a care home, but family organisation continues. The care home handles care operations; familyupdates.care handles family-side non-urgent focussed communications where needed. Mobile Support can be added if another person also provides family-side practical support.",
    }
    return notes.get(stage, "")


def render_stage_level_status(
    lifecycle_policy: dict[str, object],
    *,
    context: str = "",
) -> None:
    lifecycle_stage_label = str(lifecycle_policy.get("lifecycle_stage_label") or "").strip()
    if not lifecycle_stage_label:
        return
    parts = []
    if lifecycle_stage_label:
        parts.append(lifecycle_stage_label)
    if context:
        parts.append(context)
    st.info(" | ".join(parts))


def render_dev_stage_level_status(access_token: str | None = None) -> None:
    token = access_token if access_token is not None else st.session_state.get("access_token")
    if not token:
        return
    lifecycle_policy = get_lifecycle_policy(
        get_lifecycle_stage(token),
        get_operating_mode(token),
        get_communication_level(token),
    )
    render_stage_level_status(lifecycle_policy)


def render_stage_level_capability_tables(access_token: str | None = None) -> None:
    token = access_token if access_token is not None else st.session_state.get("access_token")
    current_policy: dict[str, object] | None = None
    if token:
        current_policy = get_lifecycle_policy(
            get_lifecycle_stage(token),
            get_operating_mode(token),
            get_communication_level(token),
        )
        render_stage_level_status(current_policy)

    st.markdown(
        """
familyupdates.care helps structure communication when someone needs support and one family member or trusted friend has become the organiser.

It is for moments when a person becomes temporarily or permanently unable to manage part of their own life, for example elderly parent support, dementia, serious illness, recovery after surgery, stroke, accident or injury, temporary incapacity, long-term disability, mental health crisis, or another situation where family and friends need to coordinate around one person.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care keeps communication current, and as in real life conversation there are no threads or stored history, just one message at a time.

Families use the app for non-urgent support management: structured requests, updates, noticeboard-style information, and simple current messages. The Family Organiser gets the app, introduces it to Family Members, and may choose to tell the family when and how frequently they will check messages.

familyupdates.care does not remove the need for care, support, or professional help. But where repeated updates, questions, and practical coordination are adding to the organiser's strain, it can help by making communication calmer, more current, and more bounded.

Where someone else is helping with practical support, Mobile Support gives that person a simpler way to share quick updates or practical requests.

#### What the app does

- One current update from the Family Organiser to the family group.
- One current specific message each way between the Family Organiser and each Family Member.
- One current update/request each way between the Family Organiser and Mobile Support, if required.
- One practical request from the Family Organiser, with structured responses from Family Members.
- One current noticeboard note from each Family Member, visible to the family group.

Each person's new message replaces their own previous message in that channel. One sender does not overwrite another sender's message. There are no threads, no archive, and no live chat.

The Family Organiser is not agreeing to be available all the time, solve everything, or act as everyone's private messenger. The Family Organiser is offering to keep a small number of family communication channels current. The general update is not a discussion thread and does not take direct replies.

familyupdates.care is for situations where communication structure is needed to help the Family Organiser provide essential support to a family member or friend.

#### Where the app may be used

There are two settings: at home, and care home.

**At home** - The person is at home and a Family Organiser is using the app to help provide essential support, family communication, and life-admin structure. The organiser is usually hands-on too. If another person is also providing practical support, paid or unpaid, Mobile Support can be used by that person to share quick updates or practical requests.

**Care home** - The person is living in a care home, but family organisation continues. The care home handles care operations. familyupdates.care handles family-side non-urgent focussed communications where needed. If another person is also providing family-side practical support, paid or unpaid, Mobile Support can be used by that person.

#### Not for urgent matters

familyupdates.care is non-urgent and not live. Requests and structured replies are for non-urgent, non-essential coordination only.

Family requests remain visible to all linked Family Members and may specify that a message is relevant to a named person - but is viewable by all. All linked Family Members can see the request and any structured responses.

Family Members may reply to requests using fixed structured choices, optional fixed tick-boxes, and an optional short context note. There are no private chats, threads, or back-and-forth conversations.

For essential, urgent, sensitive, medical, safeguarding, privacy-related, legal, financial, time-critical, or emergency matters, use normal direct communication outside familyupdates.care, such as phone, text, WhatsApp, email, or existing care-home channels. Seek appropriate professional advice where needed.

#### Starting simply

##### Getting organised

In preparation for using the app, your external filing system should be organised and for data security use your own secure file management and storage system. The information should be organised, separated, and accessible to the right person when needed. The six files we recommend that you prepare are:

- Life Log
- Contacts
- Admin and Key Documents
- Private Finance
- Private Health Notes
- Carer and Housekeeping Notes

You may also want to consider Lasting Powers of Attorney for property and financial affairs, and for health and welfare. Where finances, investments, or legal authority are involved, consider suitable legal or financial advice.

Once the external filing system is in place, start small: one calm update to registered Family Members. There are no replies in that update channel, no thread, and the next update replaces the previous one.

Then add only the communication tools that are useful: specific organiser messages to individual Family Members, practical requests, family noticeboard notes, and structured replies.
"""
    )


COMMUNICATION_LEVEL_MIN = 1
COMMUNICATION_LEVEL_MAX = 5
DEFAULT_COMMUNICATION_LEVEL = 4


def normalize_communication_level(level_value: object) -> int:
    try:
        parsed = int(level_value)
    except Exception:
        parsed = DEFAULT_COMMUNICATION_LEVEL
    return max(COMMUNICATION_LEVEL_MIN, min(parsed, COMMUNICATION_LEVEL_MAX))


def get_communication_level_policy(level_value: object) -> dict[str, object]:
    level = normalize_communication_level(level_value)
    return {
        "communication_level": level,
        "enable_one_way_updates": True,
        "enable_family_voice_messages": level >= 2,
        "enable_mobile_listen_and_record": level >= 2,
        "enable_practical_requests": level >= 3,
        "enable_structured_replies": level >= 3,
        "enable_full_coordination": level >= 4,
        "enable_optional_care_home_system": level >= 5,
    }


def get_operating_mode_for_lifecycle_stage(stage_value: object, fallback_mode: object) -> str:
    return normalize_operating_mode(fallback_mode)


def get_lifecycle_policy(
    lifecycle_stage: object,
    operating_mode: object | None = None,
    communication_level: object | None = None,
) -> dict[str, object]:
    stage = normalize_lifecycle_stage(lifecycle_stage)
    mode_value = normalize_operating_mode(
        operating_mode if operating_mode is not None else OPERATING_MODE_CARE_ORGANISATION
    )
    communication_policy = get_communication_level_policy(
        communication_level if communication_level is not None else DEFAULT_COMMUNICATION_LEVEL
    )
    base_policy: dict[int, dict[str, bool]] = {
        1: {
            "enable_notepad": False,
            "enable_life_management_file": False,
            "enable_office_channel": True,
            "enable_mobile_channel": True,
            "enable_family_messaging": True,
            "enable_requests": True,
            "enable_family_coordination": True,
            "enable_second_office": False,
            "show_external_notepad_guidance": True,
            "show_life_file_guide": True,
        },
        2: {
            "enable_notepad": False,
            "enable_life_management_file": False,
            "enable_office_channel": True,
            "enable_mobile_channel": True,
            "enable_family_messaging": True,
            "enable_requests": True,
            "enable_family_coordination": True,
            "enable_second_office": False,
            "show_external_notepad_guidance": True,
            "show_life_file_guide": True,
        },
        3: {
            "enable_notepad": False,
            "enable_life_management_file": False,
            "enable_office_channel": True,
            "enable_mobile_channel": True,
            "enable_family_messaging": True,
            "enable_requests": True,
            "enable_family_coordination": True,
            "enable_second_office": False,
            "show_external_notepad_guidance": True,
            "show_life_file_guide": True,
        },
        4: {
            "enable_notepad": False,
            "enable_life_management_file": False,
            "enable_office_channel": True,
            "enable_mobile_channel": True,
            "enable_family_messaging": True,
            "enable_requests": True,
            "enable_family_coordination": True,
            "enable_second_office": True,
            "show_external_notepad_guidance": True,
            "show_life_file_guide": True,
        },
    }
    return {
        "lifecycle_stage": stage,
        "lifecycle_stage_label": get_lifecycle_stage_label(stage),
        "operating_mode": mode_value,
        **communication_policy,
        **base_policy.get(stage, base_policy[3]),
    }


def get_mode_copy(operating_mode: object) -> dict[str, object]:
    mode_value = normalize_operating_mode(operating_mode)
    if mode_value == OPERATING_MODE_PERSONAL_USE:
        return {
            "mode": OPERATING_MODE_PERSONAL_USE,
            "organisation_heading": "Personal setup",
            "subject_label": "person",
            "subject_plural_label": "people",
            "contact_label": "main contact",
            "location_label": "Home",
            "room_label": "Room",
            "room_visible": False,
            "urgent_contact_copy": (
                "For urgent or medical matters, use your direct contact routes. "
                "Messages sent here are not monitored for emergencies."
            ),
        }
    return {
        "mode": OPERATING_MODE_CARE_ORGANISATION,
        "organisation_heading": "Care organisation",
        "subject_label": "resident",
        "subject_plural_label": "residents",
        "contact_label": "care home",
        "location_label": "Care home",
        "room_label": "Room",
        "room_visible": True,
        "urgent_contact_copy": (
            "For urgent or medical matters, families should call the care home directly. "
            "Messages sent here are not monitored for emergencies."
        ),
    }


def subject_label(operating_mode: object, *, plural: bool = False, title: bool = False) -> str:
    mode_copy = get_mode_copy(operating_mode)
    label = str(
        mode_copy.get("subject_plural_label" if plural else "subject_label") or "resident"
    )
    return label.title() if title else label


def location_label(operating_mode: object, *, title: bool = False) -> str:
    label = str(get_mode_copy(operating_mode).get("location_label") or "Care home")
    return label.title() if title else label


def contact_label(operating_mode: object, *, title: bool = False) -> str:
    label = str(get_mode_copy(operating_mode).get("contact_label") or "care home")
    return label.title() if title else label


def organisation_heading(operating_mode: object) -> str:
    return str(get_mode_copy(operating_mode).get("organisation_heading") or "Care organisation")


def room_label(operating_mode: object, *, title: bool = False) -> str:
    if not bool(get_mode_copy(operating_mode).get("room_visible")):
        return ""
    label = str(get_mode_copy(operating_mode).get("room_label") or "Room")
    return label.title() if title else label


def urgent_contact_copy(operating_mode: object) -> str:
    return str(
        get_mode_copy(operating_mode).get("urgent_contact_copy")
        or "For urgent or medical matters, use direct contact routes."
    )


def practical_checkbox_options(operating_mode: object) -> tuple[str, ...]:
    options = list(OFFICE_PRACTICAL_CHECKBOX_OPTIONS)
    if normalize_operating_mode(operating_mode) == OPERATING_MODE_PERSONAL_USE:
        options = [
            "I will call directly" if opt == "I will call the care home" else opt
            for opt in options
        ]
    return tuple(options)


def normalize_practical_option_label_for_mode(
    option_label: str, operating_mode: object, *, person_first_name: str = ""
) -> str:
    label = str(option_label or "").strip()
    first_name = str(person_first_name or "").strip()
    if label == "I will book and take them" and first_name:
        return f"I will take {first_name}"
    if (
        normalize_operating_mode(operating_mode) == OPERATING_MODE_PERSONAL_USE
        and label == "I will call the care home"
    ):
        return "I will call directly"
    return label


def format_structured_response_choice(value: object) -> str:
    choice = str(value or "").strip().lower()
    return STRUCTURED_RESPONSE_LABELS.get(choice, "")


def validate_personal_mode_runtime(operating_mode: object) -> tuple[bool, list[str]]:
    mode_value = normalize_operating_mode(operating_mode)
    if mode_value != OPERATING_MODE_PERSONAL_USE:
        return True, []
    failures: list[str] = []
    if subject_label(mode_value) != "person":
        failures.append("subject label is not 'person'")
    if subject_label(mode_value, plural=True) != "people":
        failures.append("subject plural label is not 'people'")
    if location_label(mode_value).lower() == "care home":
        failures.append("location label still resolves to 'care home'")
    if room_label(mode_value):
        failures.append("room label should be hidden in personal mode")
    return not failures, failures


def _derive_family_workspace_title(context_phrase: str, person_name: str = "") -> str:
    person = str(person_name or "").strip()
    phrase = str(context_phrase or "").strip()
    if not person and phrase:
        lowered = phrase.lower()
        marker = "for "
        if marker in lowered:
            idx = lowered.rfind(marker)
            candidate = phrase[idx + len(marker) :].strip()
            candidate = re.split(r"[,.;:]", candidate)[0].strip()
            person = candidate
    if person:
        if person.endswith("s"):
            return f"{person}' Family"
        return f"{person}'s Family"
    return "Family"


def _family_display_name_without_legacy_circle(value: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    if not cleaned:
        return ""
    cleaned = re.sub(r"\bCare\s+Circle\b", "Family", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bCircle\b", "Family", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _family_title_from_person_display_name(person_name: object) -> str:
    person = re.sub(r"\s+", " ", str(person_name or "").strip())
    if not person:
        return ""
    return f"{person}' Family" if person.endswith("s") else f"{person}'s Family"


def _resolve_person_display_name_from_residents(
    residents: list[dict] | None,
    *,
    selected_resident_id: str = "",
) -> str:
    rows = residents if isinstance(residents, list) else []
    if not rows:
        return ""
    selected_id = str(selected_resident_id or "").strip()
    if selected_id:
        for resident in rows:
            if str(resident.get("id") or "").strip() == selected_id:
                return get_resident_full_name(resident, operating_mode=OPERATING_MODE_PERSONAL_USE)
    return get_resident_full_name(rows[0], operating_mode=OPERATING_MODE_PERSONAL_USE)


MODE_DOC_OVERRIDES: dict[str, dict[str, str]] = {
    # The earlier "Circle" document set is legacy and no longer drives public/help copy.
    OPERATING_MODE_PERSONAL_USE: {}
}


def resolve_mode_doc_path(
    doc_path: str,
    *,
    access_token: str | None = None,
    operating_mode: object | None = None,
    lifecycle_stage: object | None = None,
) -> str:
    normalized = str(doc_path or "").strip()
    if not normalized:
        return normalized
    stage_value = (
        normalize_lifecycle_stage(lifecycle_stage)
        if lifecycle_stage is not None
        else (get_lifecycle_stage(access_token) if access_token else None)
    )
    if stage_value in {1, 2, 3}:
        target = MODE_DOC_OVERRIDES.get(OPERATING_MODE_PERSONAL_USE, {}).get(
            normalized, normalized
        )
        if target != normalized and not Path(target).exists():
            return normalized
        return target
    mode_value = (
        normalize_operating_mode(operating_mode)
        if operating_mode is not None
        else get_operating_mode(access_token)
    )
    target = MODE_DOC_OVERRIDES.get(mode_value, {}).get(normalized, normalized)
    if target != normalized and not Path(target).exists():
        return normalized
    return target


def get_transcript_policy_mode(access_token: str | None) -> str:
    profile = fetch_active_care_home_profile(access_token)
    return normalize_transcript_policy_mode(profile.get("transcript_policy_mode"))


def get_care_hub_idle_timeout_seconds(access_token: str | None) -> int:
    profile = fetch_active_care_home_profile(access_token)
    timeout_value = profile.get("care_hub_idle_timeout_seconds")
    return normalize_care_hub_idle_timeout_seconds(timeout_value)


def get_operating_mode(access_token: str | None) -> str:
    profile = fetch_active_care_home_profile(access_token)
    return normalize_operating_mode(profile.get("operating_mode"))


def get_lifecycle_stage(access_token: str | None) -> int:
    profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    return normalize_lifecycle_stage(profile.get("lifecycle_stage"))


def get_communication_level(access_token: str | None) -> int:
    profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    return normalize_communication_level(profile.get("communication_level"))


def get_main_contact_name(access_token: str | None) -> str:
    profile = fetch_active_care_home_profile(access_token)
    configured = str(profile.get("main_contact_name") or "").strip()
    if configured:
        return configured
    return str(DEFAULT_MAIN_CONTACT_NAME or "").strip()


def is_family_led_mode(access_token: str | None) -> bool:
    return get_operating_mode(access_token) == OPERATING_MODE_PERSONAL_USE


def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
    message = str(exc or "").lower()
    column_key = str(column_name or "").strip().lower()
    if not column_key:
        return False
    return column_key in message and (
        "does not exist" in message
        or "could not find the" in message
        or "schema cache" in message
        or "undefined column" in message
        or "42703" in message
        or "pgrst204" in message
    )


def fetch_active_care_home_profile(access_token: str | None, *, force_refresh: bool = False) -> dict:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id or not access_token:
        return {}
    cache_key = f"care_home_profile_{care_home_id}"
    cache_ts_key = f"{cache_key}_ts"
    cached_profile = st.session_state.get(cache_key)
    cached_profile_ts = float(st.session_state.get(cache_ts_key) or 0.0)
    cache_age_seconds = max(time.time() - cached_profile_ts, 0.0)
    # Keep cache short-lived so external DB updates (for example manual SQL fixes)
    # are reflected quickly without requiring a full app/session reset.
    if (
        not force_refresh
        and
        isinstance(cached_profile, dict)
        and str(cached_profile.get("name") or "").strip()
        and "communication_level" in cached_profile
        and cache_age_seconds < 20.0
    ):
        return cached_profile
    supabase, error = get_authed_supabase(access_token)
    if error:
        return {}
    select_fields = (
        "name, branding_banner_title, branding_banner_text, "
        "branding_banner_artwork_url, care_hub_idle_timeout_seconds, transcript_policy_mode, "
        "operating_mode, main_contact_name, message_check_note, lifecycle_stage, communication_level"
    )
    fallback_select_fields = (
        "name, branding_banner_title, branding_banner_text, branding_banner_artwork_url, "
        "operating_mode, main_contact_name, lifecycle_stage, communication_level"
    )
    legacy_fallback_select_fields = (
        "name, branding_banner_title, branding_banner_text, branding_banner_artwork_url, "
        "operating_mode, main_contact_name, lifecycle_stage"
    )
    try:
        try:
            resp = (
                supabase.table("care_homes")
                .select(select_fields)
                .eq("id", care_home_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if not (
                _is_missing_column_error(exc, "care_hub_idle_timeout_seconds")
                or _is_missing_column_error(exc, "transcript_policy_mode")
                or _is_missing_column_error(exc, "operating_mode")
                or _is_missing_column_error(exc, "main_contact_name")
                or _is_missing_column_error(exc, "message_check_note")
                or _is_missing_column_error(exc, "lifecycle_stage")
                or _is_missing_column_error(exc, "communication_level")
            ):
                raise
            if _is_missing_column_error(exc, "lifecycle_stage"):
                st.session_state["_care_homes_missing_lifecycle_stage"] = True
            if _is_missing_column_error(exc, "lifecycle_stage"):
                fallback_fields = (
                    "name, branding_banner_title, branding_banner_text, branding_banner_artwork_url, "
                    "operating_mode, main_contact_name, communication_level"
                )
            elif _is_missing_column_error(exc, "communication_level"):
                fallback_fields = legacy_fallback_select_fields
            else:
                fallback_fields = fallback_select_fields
            resp = (
                supabase.table("care_homes")
                .select(fallback_fields)
                .eq("id", care_home_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
        row = (resp.data or [None])[0]
        if not row:
            # Some datasets may not have the care_home `active` flag set consistently.
            # Fall back to id-only lookup so the identity banner can still render.
            try:
                fallback_resp = (
                    supabase.table("care_homes")
                    .select(select_fields)
                    .eq("id", care_home_id)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                if not (
                    _is_missing_column_error(exc, "care_hub_idle_timeout_seconds")
                    or _is_missing_column_error(exc, "transcript_policy_mode")
                    or _is_missing_column_error(exc, "operating_mode")
                    or _is_missing_column_error(exc, "main_contact_name")
                    or _is_missing_column_error(exc, "message_check_note")
                    or _is_missing_column_error(exc, "lifecycle_stage")
                    or _is_missing_column_error(exc, "communication_level")
                ):
                    raise
                if _is_missing_column_error(exc, "lifecycle_stage"):
                    st.session_state["_care_homes_missing_lifecycle_stage"] = True
                if _is_missing_column_error(exc, "lifecycle_stage"):
                    fallback_fields = (
                        "name, branding_banner_title, branding_banner_text, branding_banner_artwork_url, "
                        "operating_mode, main_contact_name, communication_level"
                    )
                elif _is_missing_column_error(exc, "communication_level"):
                    fallback_fields = legacy_fallback_select_fields
                else:
                    fallback_fields = fallback_select_fields
                fallback_resp = (
                    supabase.table("care_homes")
                    .select(fallback_fields)
                    .eq("id", care_home_id)
                    .limit(1)
                    .execute()
                )
            row = (fallback_resp.data or [{}])[0]
        profile = {
            "name": str(row.get("name") or "").strip(),
            "branding_banner_title": str(row.get("branding_banner_title") or "").strip(),
            "branding_banner_text": str(row.get("branding_banner_text") or "").strip(),
            "branding_banner_artwork_url": normalize_banner_artwork_url(
                row.get("branding_banner_artwork_url")
            ),
            "care_hub_idle_timeout_seconds": normalize_care_hub_idle_timeout_seconds(
                row.get("care_hub_idle_timeout_seconds")
            ),
            "transcript_policy_mode": normalize_transcript_policy_mode(
                row.get("transcript_policy_mode")
            ),
            "operating_mode": normalize_operating_mode(row.get("operating_mode")),
            "main_contact_name": str(row.get("main_contact_name") or "").strip(),
            "message_check_note": str(row.get("message_check_note") or "").strip(),
            "lifecycle_stage": normalize_lifecycle_stage(row.get("lifecycle_stage")),
            "communication_level": normalize_communication_level(row.get("communication_level")),
        }
        if profile["name"]:
            st.session_state[cache_key] = profile
            st.session_state[cache_ts_key] = time.time()
        return profile
    except Exception:
        return {}


def update_active_care_home_branding(
    access_token: str | None,
    *,
    care_home_name: str,
    operating_mode: str,
    lifecycle_stage: int,
    communication_level: int,
    main_contact_name: str,
    message_check_note: str,
    banner_title: str,
    banner_text: str,
    banner_artwork_url: str,
    care_hub_idle_timeout_seconds: int,
    transcript_policy_mode: str,
) -> tuple[bool, str]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id:
        return False, "No active care home is linked to this session."
    if not access_token:
        return False, "Session is missing access credentials. Please sign in again."
    name_value = str(care_home_name or "").strip()
    title_value = str(banner_title or "").strip()
    text_value = str(banner_text or "").strip()
    mode_value = normalize_operating_mode(operating_mode)
    lifecycle_stage_value = normalize_lifecycle_stage(lifecycle_stage)
    communication_level_value = normalize_communication_level(communication_level)
    main_contact_value = str(main_contact_name or "").strip()
    message_check_note_value = str(message_check_note or "").strip()
    artwork_value = normalize_banner_artwork_url(banner_artwork_url)
    timeout_value = normalize_care_hub_idle_timeout_seconds(care_hub_idle_timeout_seconds)
    transcript_policy_value = normalize_transcript_policy_mode(transcript_policy_mode)
    if not name_value:
        return False, "Care home name is required."
    if len(name_value) > 160:
        return False, "Care home name must be 160 characters or fewer."
    if len(title_value) > 120:
        return False, "Banner title must be 120 characters or fewer."
    if len(main_contact_value) > 120:
        return False, "Main contact name must be 120 characters or fewer."
    if len(message_check_note_value) > 500:
        return False, "Message check note must be 500 characters or fewer."
    if len(text_value) > 800:
        return False, "Banner text must be 800 characters or fewer."
    if len(artwork_value) > 1000:
        return False, "Artwork URL must be 1000 characters or fewer."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    update_payload = {
        "name": name_value,
        "operating_mode": mode_value,
        "lifecycle_stage": lifecycle_stage_value,
        "communication_level": communication_level_value,
        "main_contact_name": main_contact_value or None,
        "message_check_note": message_check_note_value or None,
        "branding_banner_title": title_value or None,
        "branding_banner_text": text_value or None,
        "branding_banner_artwork_url": artwork_value or None,
        "care_hub_idle_timeout_seconds": timeout_value,
        "transcript_policy_mode": transcript_policy_value,
    }
    try:
        try:
            (
                supabase.table("care_homes")
                .update(update_payload)
                .eq("id", care_home_id)
                .execute()
            )
        except Exception as exc:
            if _is_missing_column_error(exc, "lifecycle_stage"):
                st.session_state["_care_homes_missing_lifecycle_stage"] = True
                return (
                    False,
                    "Current situation cannot be saved because the Supabase database is missing care_homes.lifecycle_stage. Apply migration 0029_care_homes_lifecycle_stage.sql, then try again.",
                )
            if not (
                _is_missing_column_error(exc, "care_hub_idle_timeout_seconds")
                or _is_missing_column_error(exc, "transcript_policy_mode")
                or _is_missing_column_error(exc, "communication_level")
                or _is_missing_column_error(exc, "message_check_note")
            ):
                raise
            update_payload.pop("care_hub_idle_timeout_seconds", None)
            update_payload.pop("transcript_policy_mode", None)
            update_payload.pop("communication_level", None)
            update_payload.pop("message_check_note", None)
            (
                supabase.table("care_homes")
                .update(update_payload)
                .eq("id", care_home_id)
                .execute()
            )
        st.session_state.pop(f"care_home_profile_{care_home_id}", None)
        st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
        persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
        persisted_name = str((persisted_profile or {}).get("name") or "").strip()
        persisted_title = str((persisted_profile or {}).get("branding_banner_title") or "").strip()
        persisted_text = str((persisted_profile or {}).get("branding_banner_text") or "").strip()
        persisted_mode = normalize_operating_mode((persisted_profile or {}).get("operating_mode"))
        persisted_lifecycle_stage = normalize_lifecycle_stage(
            (persisted_profile or {}).get("lifecycle_stage")
        )
        persisted_communication_level = normalize_communication_level(
            (persisted_profile or {}).get("communication_level")
        )
        persisted_main_contact_name = str((persisted_profile or {}).get("main_contact_name") or "").strip()
        persisted_message_check_note = str((persisted_profile or {}).get("message_check_note") or "").strip()
        persisted_artwork = normalize_banner_artwork_url(
            (persisted_profile or {}).get("branding_banner_artwork_url")
        )
        persisted_transcript_policy = normalize_transcript_policy_mode(
            (persisted_profile or {}).get("transcript_policy_mode")
        )
        if persisted_mode != mode_value:
            # Fallback: retry mode update explicitly, then re-check.
            (
                supabase.table("care_homes")
                .update({"operating_mode": mode_value})
                .eq("id", care_home_id)
                .execute()
            )
            st.session_state.pop(f"care_home_profile_{care_home_id}", None)
            st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
            persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
            persisted_mode = normalize_operating_mode((persisted_profile or {}).get("operating_mode"))
            if persisted_mode != mode_value:
                return (
                    False,
                    "Mode change could not be confirmed after save. Please retry or check care_homes update permissions.",
                )
        if persisted_lifecycle_stage != lifecycle_stage_value:
            try:
                (
                    supabase.table("care_homes")
                    .update({"lifecycle_stage": lifecycle_stage_value})
                    .eq("id", care_home_id)
                    .execute()
                )
                stage_update_resp = (
                    supabase.table("care_homes")
                    .select("lifecycle_stage")
                    .eq("id", care_home_id)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                if not _is_missing_column_error(exc, "lifecycle_stage"):
                    raise
                st.session_state["_care_homes_missing_lifecycle_stage"] = True
                return (
                    False,
                    "Current situation cannot be saved because the Supabase database is missing care_homes.lifecycle_stage. Apply migration 0029_care_homes_lifecycle_stage.sql, then try again.",
                )
            st.session_state.pop(f"care_home_profile_{care_home_id}", None)
            st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
            stage_update_row = (
                stage_update_resp.data[0]
                if getattr(stage_update_resp, "data", None)
                and isinstance(stage_update_resp.data, list)
                else {}
            )
            persisted_lifecycle_stage = normalize_lifecycle_stage(
                stage_update_row.get("lifecycle_stage")
                if isinstance(stage_update_row, dict)
                else None
            )
            if persisted_lifecycle_stage == lifecycle_stage_value:
                persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
            else:
                persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
                persisted_lifecycle_stage = normalize_lifecycle_stage(
                    (persisted_profile or {}).get("lifecycle_stage")
                )
            if persisted_lifecycle_stage != lifecycle_stage_value:
                return (
                    False,
                    "Current situation change could not be confirmed after save. Please retry or check care_homes update permissions.",
                )
        if persisted_communication_level != communication_level_value:
            try:
                (
                    supabase.table("care_homes")
                    .update({"communication_level": communication_level_value})
                    .eq("id", care_home_id)
                    .execute()
                )
                level_update_resp = (
                    supabase.table("care_homes")
                    .select("communication_level")
                    .eq("id", care_home_id)
                    .limit(1)
                    .execute()
                )
            except Exception as exc:
                if _is_missing_column_error(exc, "communication_level"):
                    return (
                        False,
                        "Internal capability settings cannot be saved because the Supabase database is missing care_homes.communication_level. Apply the latest migration, then try again.",
                    )
                raise
            st.session_state.pop(f"care_home_profile_{care_home_id}", None)
            st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
            level_update_row = (
                level_update_resp.data[0]
                if getattr(level_update_resp, "data", None)
                and isinstance(level_update_resp.data, list)
                else {}
            )
            persisted_communication_level = normalize_communication_level(
                level_update_row.get("communication_level")
                if isinstance(level_update_row, dict)
                else None
            )
            if persisted_communication_level == communication_level_value:
                persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
            else:
                persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
                persisted_communication_level = normalize_communication_level(
                    (persisted_profile or {}).get("communication_level")
                )
            if persisted_communication_level != communication_level_value:
                return (
                    False,
                    "Internal capability settings could not be confirmed after save. Please retry or check care_homes update permissions.",
                )
        else:
            try:
                (
                    supabase.table("care_homes")
                    .update({"communication_level": communication_level_value})
                    .eq("id", care_home_id)
                    .execute()
                )
            except Exception as exc:
                if _is_missing_column_error(exc, "communication_level"):
                    return (
                        False,
                        "Internal capability settings cannot be saved because the Supabase database is missing care_homes.communication_level. Apply the latest migration, then try again.",
                    )
                raise
            st.session_state.pop(f"care_home_profile_{care_home_id}", None)
            st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
            persisted_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
            persisted_communication_level = normalize_communication_level(
                (persisted_profile or {}).get("communication_level")
            )
            if persisted_communication_level != communication_level_value:
                return (
                    False,
                    "Internal capability settings could not be confirmed after save. Please retry or check care_homes update permissions.",
                )
        if (
            persisted_name != name_value
            or persisted_lifecycle_stage != lifecycle_stage_value
            or persisted_communication_level != communication_level_value
            or persisted_main_contact_name != main_contact_value
            or persisted_message_check_note != message_check_note_value
            or persisted_title != title_value
            or persisted_text != text_value
            or persisted_artwork != artwork_value
            or persisted_transcript_policy != transcript_policy_value
        ):
            # Avoid false-negative save failures when immediate readback is stale or
            # a deployment is mid-migration for optional columns.
            return (
                True,
                "Settings saved. If a value does not appear immediately, refresh the page.",
            )
        return True, "Care home profile updated."
    except Exception as exc:
        return False, str(exc)


def update_active_care_home_stage_level(
    access_token: str | None,
    *,
    lifecycle_stage: int,
    communication_level: int,
) -> tuple[bool, str, dict]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id:
        return False, "No active care home is linked to this session.", {}
    if not access_token:
        return False, "Session is missing access credentials. Please sign in again.", {}
    lifecycle_stage_value = normalize_lifecycle_stage(lifecycle_stage)
    communication_level_value = normalize_communication_level(communication_level)
    if communication_level_value == 5 and lifecycle_stage_value != 4:
        return False, "Archived care-home system flag cannot be saved unless the care-home situation is selected.", {}
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error, {}
    try:
        update_resp = (
            supabase.table("care_homes")
            .update(
                {
                    "lifecycle_stage": lifecycle_stage_value,
                    "communication_level": communication_level_value,
                }
            )
            .eq("id", care_home_id)
            .execute()
        )
        updated_row_count = (
            len(update_resp.data)
            if getattr(update_resp, "data", None)
            and isinstance(update_resp.data, list)
            else None
        )
        readback_resp = (
            supabase.table("care_homes")
            .select("id, lifecycle_stage, communication_level")
            .eq("id", care_home_id)
            .limit(1)
            .execute()
        )
        row = (
            readback_resp.data[0]
            if getattr(readback_resp, "data", None)
            and isinstance(readback_resp.data, list)
            and readback_resp.data
            else {}
        )
        if not row:
            result = {
                "care_home_id": care_home_id,
                "requested_lifecycle_stage": lifecycle_stage_value,
                "requested_communication_level": communication_level_value,
                "updated_row_returned": bool(updated_row_count),
                "update_result_count": updated_row_count,
                "readback_lifecycle_stage": None,
                "readback_communication_level": None,
            }
            return (
                False,
                "Supabase update ran, but the setup row could not be read back.",
                result,
            )
        readback_stage = normalize_lifecycle_stage(row.get("lifecycle_stage"))
        readback_level = normalize_communication_level(row.get("communication_level"))
        result = {
            "care_home_id": care_home_id,
            "requested_lifecycle_stage": lifecycle_stage_value,
            "requested_communication_level": communication_level_value,
            "updated_row_returned": bool(updated_row_count),
            "update_result_count": updated_row_count,
            "readback_lifecycle_stage": readback_stage,
            "readback_communication_level": readback_level,
        }
        st.session_state.pop(f"care_home_profile_{care_home_id}", None)
        st.session_state.pop(f"care_home_profile_{care_home_id}_ts", None)
        if (
            readback_stage == lifecycle_stage_value
            and readback_level == communication_level_value
        ):
            return True, "Situation saved.", result
        return (
            False,
            "Current situation update was sent, but Supabase readback did not match.",
            result,
        )
    except Exception as exc:
        return False, str(exc), {}


def render_care_home_identity_banner(access_token: str | None) -> None:
    if st.session_state.get("_care_home_banner_rendered_in_header"):
        return
    care_home_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    care_home_name = str(care_home_profile.get("name") or "").strip()
    operating_mode = normalize_operating_mode(care_home_profile.get("operating_mode"))
    lifecycle_stage = normalize_lifecycle_stage(care_home_profile.get("lifecycle_stage"))
    home_coordination_stage = lifecycle_stage in {1, 2, 3}
    workspace_labels = get_workspace_labels_for_lifecycle_stage(
        lifecycle_stage,
        setup_name=care_home_name,
    )
    workspace_type_label = str(workspace_labels.get("workspace_type_label") or "Care Home system")
    if care_home_name:
        display_name = (
            _family_display_name_without_legacy_circle(care_home_name)
            if operating_mode == OPERATING_MODE_PERSONAL_USE or home_coordination_stage
            else care_home_name
        )
        safe_name = html.escape(display_name)
        if operating_mode == OPERATING_MODE_PERSONAL_USE or home_coordination_stage:
            person_display = str(st.session_state.get("circle_person_display_name") or "").strip()
            family_title = _family_title_from_person_display_name(person_display)
            safe_family_title = html.escape(family_title) if family_title else safe_name
            lines = [f"<strong>{safe_family_title}</strong>"]
            st.markdown(
                (
                    '<div style="margin:6px 0 12px 0;padding:8px 10px;'
                    'border:1px solid rgba(31,31,31,0.12);border-radius:10px;'
                    'background:rgba(153,255,255,0.18);font-size:0.92rem;">'
                    + "".join(lines)
                    + "</div>"
                ),
                unsafe_allow_html=True,
            )
        else:
            identity_label = str(workspace_labels.get("organisation_label") or "Care home")
            st.markdown(
                (
                    '<div style="margin:6px 0 12px 0;padding:8px 10px;'
                    'border:1px solid rgba(31,31,31,0.12);border-radius:10px;'
                    'background:rgba(153,255,255,0.18);font-size:0.92rem;">'
                    f"<strong>{identity_label}:</strong> {safe_name}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
    else:
        st.caption("You are signed in.")
    if get_app_variant() in {VARIANT_OFFICE, VARIANT_MOBILE, VARIANT_FAMILY}:
        mode_text = workspace_type_label
        st.caption(f"Mode: {mode_text}")
        message_check_note = str(care_home_profile.get("message_check_note") or "").strip()
        if message_check_note:
            st.caption(f"Message check note: {message_check_note}")
    if not bool(st.session_state.get("_care_home_custom_banner_rendered")):
        rendered = render_active_care_home_custom_banner(care_home_profile)
        st.session_state["_care_home_custom_banner_rendered"] = bool(rendered)


def render_active_care_home_name_caption() -> None:
    st.session_state["_care_home_banner_rendered_in_header"] = False
    st.session_state["_care_home_custom_banner_rendered"] = False
    app_variant = get_app_variant()
    if app_variant not in {VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}:
        return
    if not st.session_state.get("auth_uid"):
        return
    access_token = str(st.session_state.get("access_token") or "").strip()
    if not access_token:
        return
    care_home_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    care_home_name = str(care_home_profile.get("name") or "").strip()
    operating_mode = normalize_operating_mode(care_home_profile.get("operating_mode"))
    lifecycle_stage = normalize_lifecycle_stage(care_home_profile.get("lifecycle_stage"))
    home_coordination_stage = lifecycle_stage in {1, 2, 3}
    workspace_labels = get_workspace_labels_for_lifecycle_stage(
        lifecycle_stage,
        setup_name=care_home_name,
    )
    if care_home_name:
        if operating_mode == OPERATING_MODE_PERSONAL_USE or home_coordination_stage:
            person_display = str(st.session_state.get("circle_person_display_name") or "").strip()
            display_name = _family_display_name_without_legacy_circle(care_home_name)
            family_title = _family_title_from_person_display_name(person_display)
            safe_care_home_name = html.escape(family_title or display_name)
            lines = [f"<strong>{safe_care_home_name}</strong>"]
            st.markdown(
                '<div class="vm-care-home-banner">' + "".join(lines) + "</div>",
                unsafe_allow_html=True,
            )
        else:
            identity_label = str(workspace_labels.get("organisation_label") or "Care home")
            st.markdown(
                (
                    '<div class="vm-care-home-banner">'
                    f"<strong>{identity_label}:</strong> {care_home_name}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        st.session_state["_care_home_banner_rendered_in_header"] = True
    rendered = render_active_care_home_custom_banner(care_home_profile)
    st.session_state["_care_home_custom_banner_rendered"] = bool(rendered)
    message_check_note = str(care_home_profile.get("message_check_note") or "").strip()
    if message_check_note:
        st.caption(f"Message check note: {message_check_note}")


def render_active_care_home_custom_banner(care_home_profile: dict) -> bool:
    if not isinstance(care_home_profile, dict):
        return False
    banner_title = str(care_home_profile.get("branding_banner_title") or "").strip()
    banner_text = str(care_home_profile.get("branding_banner_text") or "").strip()
    banner_artwork_url = normalize_banner_artwork_url(
        care_home_profile.get("branding_banner_artwork_url")
    )
    care_home_name = str(care_home_profile.get("name") or "").strip()
    # Avoid a duplicate single-line custom banner that repeats the identity banner title.
    if (
        banner_title
        and not banner_text
        and not banner_artwork_url
        and care_home_name
        and banner_title.strip().lower() == care_home_name.strip().lower()
    ):
        return False
    if not banner_title and not banner_text and not banner_artwork_url:
        return False
    escaped_title = html.escape(banner_title)
    escaped_text = html.escape(banner_text)
    has_copy = bool(escaped_title or escaped_text)
    if has_copy:
        st.markdown('<div class="vm-care-home-custom-banner">', unsafe_allow_html=True)
        if escaped_title:
            st.markdown(
                f'<div class="vm-care-home-custom-banner-title">{escaped_title}</div>',
                unsafe_allow_html=True,
            )
        if escaped_text:
            st.markdown(
                f'<div class="vm-care-home-custom-banner-text">{escaped_text}</div>',
                unsafe_allow_html=True,
            )
    # Artwork is intentionally not rendered during the familyupdates.care transition.
    # The public/system model now lives in Markdown, not banner images.
    if has_copy:
        st.markdown("</div>", unsafe_allow_html=True)
    return True


def get_resident_full_name(resident: dict, *, operating_mode: object | None = None) -> str:
    preferred_name = str(resident.get("preferred_name") or "").strip()
    surname = str(resident.get("surname") or "").strip()
    full_name = " ".join(part for part in (preferred_name, surname) if part).strip()
    fallback_label = subject_label(operating_mode or OPERATING_MODE_CARE_ORGANISATION, title=True)
    return full_name or fallback_label


def format_resident_identity_label(
    resident: dict,
    *,
    operating_mode: object | None = None,
    include_room: bool = True,
    include_care_home: bool = True,
    separator: str = " | ",
) -> str:
    mode_value = normalize_operating_mode(operating_mode or OPERATING_MODE_CARE_ORGANISATION)
    parts = [get_resident_full_name(resident, operating_mode=mode_value)]
    if include_room and room_label(mode_value):
        room = str(resident.get("room") or "").strip()
        if room:
            parts.append(f"{room_label(mode_value, title=True)} {room}")
    if include_care_home:
        care_home_name = str(resident.get("care_home") or "").strip()
        if care_home_name:
            parts.append(care_home_name)
    return separator.join(parts)


def fetch_family_users_for_resident(
    resident_id: str, access_token: str
) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    try:
        access_table = _resident_access_table_name(supabase)
        family_col = _resident_access_family_user_column(supabase)
        family_rel = _family_user_relation_name(supabase)
        contact_resp = (
            supabase.table(access_table)
            .select(
                f"{family_col}, {family_rel}(id, display_name, relationship, auth_user_id, email)"
            )
            .eq("resident_id", resident_id)
            .eq("active", True)
            .execute()
        )
        contacts = []
        for row in contact_resp.data or []:
            contact = row.get(family_rel) or {}
            if not contact:
                continue
            contacts.append(
                {
                    "id": contact.get("id"),
                    "full_name": contact.get("display_name", "Family Member"),
                    "relationship": contact.get("relationship") or "",
                    "auth_user_id": contact.get("auth_user_id"),
                    "email": contact.get("email") or "",
                }
            )
        return contacts
    except Exception:
        return []


def family_contact_display_name(contact: dict | None) -> str:
    contact = contact or {}
    name = str(contact.get("full_name") or contact.get("display_name") or "Family Member").strip()
    relationship = str(contact.get("relationship") or "").strip()
    if relationship:
        return f"{name} ({relationship})"
    return name or "Family Member"


def find_family_contact_by_id(contacts: list[dict], family_user_id: str | None) -> dict | None:
    target_id = str(family_user_id or "").strip()
    if not target_id:
        return None
    for contact in contacts or []:
        if str((contact or {}).get("id") or "").strip() == target_id:
            return contact
    return None


def normalize_office_practical_target_type(value: object) -> str:
    target_type = str(value or "").strip()
    if target_type in {"selected_family", OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY}:
        return OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY
    if target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
        return OFFICE_PRACTICAL_TARGET_MOBILE
    return OFFICE_PRACTICAL_TARGET_ALL_FAMILY


def office_practical_target_label(message: dict | None, contacts: list[dict] | None = None) -> str:
    message = message or {}
    target_type = normalize_office_practical_target_type(message.get("target_type"))
    if target_type == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY:
        contact = find_family_contact_by_id(
            contacts or [],
            str(message.get("target_family_user_id") or "").strip(),
        )
        if contact:
            return f"{family_contact_display_name(contact)} as intended responder"
        return "one named Family Member as intended responder"
    if target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
        return "Mobile Support / carer"
    return "all Family Members"


def _get_contact_auth_user_id_via_email(email: str) -> str:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return ""
    cache_key = "auth_uid_by_email_cache"
    cache = st.session_state.get(cache_key)
    if not isinstance(cache, dict):
        cache = {}
    cached = str(cache.get(normalized_email) or "").strip()
    if cached:
        return cached
    admin_client, admin_error = get_admin_client()
    if admin_error:
        return ""
    resolved = _resolve_auth_user_id_by_email(admin_client, normalized_email).strip()
    if resolved:
        cache[normalized_email] = resolved
        st.session_state[cache_key] = cache
    return resolved


def _message_recorded_at_sort_key(message: dict | None) -> tuple[int, str]:
    recorded_at = str((message or {}).get("recorded_at") or "").strip()
    if not recorded_at:
        return (0, "")
    try:
        dt_mod = __import__("datetime")
        parsed = dt_mod.datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_mod.timezone.utc)
        return (1, parsed.astimezone(dt_mod.timezone.utc).isoformat())
    except Exception:
        return (1, recorded_at)


def _prefer_newer_message(first: dict | None, second: dict | None) -> dict | None:
    if first and not second:
        return first
    if second and not first:
        return second
    if not first and not second:
        return None
    return first if _message_recorded_at_sort_key(first) >= _message_recorded_at_sort_key(second) else second


def fetch_latest_message_for_contact_with_mapping_repair(
    resident_id: str,
    access_token: str,
    contact: dict,
    *,
    channel: str = "resident_family",
    include_audio: bool = True,
) -> dict | None:
    contact_id = str(contact.get("id") or "").strip()
    contact_user_id = str(contact.get("auth_user_id") or "").strip()
    latest_by_user: dict | None = None
    latest_by_contact_id: dict | None = None
    if contact_user_id:
        latest_by_user = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            contact_user_id=contact_user_id,
            channel=channel,
            include_audio=include_audio,
        )
    if contact_id:
        latest_by_contact_id = fetch_latest_message(
            resident_id,
            "to_resident",
            access_token,
            family_id=contact_id,
            channel=channel,
            include_audio=include_audio,
        )
    latest = _prefer_newer_message(latest_by_user, latest_by_contact_id)
    if latest:
        return latest

    contact_email = str(contact.get("email") or "").strip().lower()
    resolved_user_id = ""
    if contact_email:
        resolved_user_id = _get_contact_auth_user_id_via_email(contact_email)
    if not resolved_user_id:
        return None

    if resolved_user_id != contact_user_id:
        contact["auth_user_id"] = resolved_user_id
        if contact_id:
            supabase, error = get_authed_supabase(access_token)
            if not error:
                try:
                    family_table = _family_user_table_name(supabase)
                    supabase.table(family_table).update({"auth_user_id": resolved_user_id}).eq(
                        "id", contact_id
                    ).execute()
                except Exception:
                    pass

    latest = fetch_latest_message(
        resident_id,
        "to_resident",
        access_token,
        contact_user_id=resolved_user_id,
        channel=channel,
        include_audio=include_audio,
    )
    return _prefer_newer_message(latest, latest_by_contact_id)


def fetch_latest_message(
    resident_id: str,
    direction: str,
    access_token: str,
    contact_user_id: str | None = None,
    contact_user_id_is_null: bool = False,
    family_id: str | None = None,
    channel: str = "resident_family",
    include_audio: bool = False,
) -> dict | None:
    cache_key = (
        "fetch_latest_message",
        str(st.session_state.get("auth_uid") or ""),
        resident_id,
        direction,
        str(contact_user_id or ""),
        bool(contact_user_id_is_null),
        str(family_id or ""),
        channel,
        bool(include_audio),
    )
    cached = _get_cached_message_query_result(cache_key)
    if cached is not None:
        return cached
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        select_fields = _message_select_fields(
            include_audio=include_audio,
            include_optional_storage_columns=True,
        )
        query = (
            supabase.table("messages")
            .select(select_fields)
            .eq("resident_id", resident_id)
            .eq("direction", direction)
            .eq("channel", channel)
            .order("recorded_at", desc=True)
            .limit(1)
        )
        if contact_user_id is not None:
            query = query.eq("contact_user_id", contact_user_id)
        elif contact_user_id_is_null:
            query = query.is_("contact_user_id", "null")
        if family_id is not None:
            query = query.eq("family_id", family_id)
        try:
            resp = query.execute()
        except Exception as exc:
            missing_audio_columns, missing_transcript_columns = _message_missing_optional_columns(exc)
            missing_text_columns = _message_missing_text_columns(exc)
            if (include_audio and (missing_audio_columns or missing_transcript_columns)) or missing_text_columns:
                if missing_transcript_columns:
                    st.session_state["_messages_missing_transcript_columns"] = True
                fallback_query = (
                    supabase.table("messages")
                    .select(
                        _message_select_fields(
                            include_audio=include_audio,
                            include_optional_storage_columns=not missing_audio_columns,
                            include_optional_transcript_columns=not missing_transcript_columns,
                            include_optional_text_columns=not missing_text_columns,
                        )
                    )
                    .eq("resident_id", resident_id)
                    .eq("direction", direction)
                    .eq("channel", channel)
                    .order("recorded_at", desc=True)
                    .limit(1)
                )
                if contact_user_id is not None:
                    fallback_query = fallback_query.eq("contact_user_id", contact_user_id)
                elif contact_user_id_is_null:
                    fallback_query = fallback_query.is_("contact_user_id", "null")
                if family_id is not None:
                    fallback_query = fallback_query.eq("family_id", family_id)
                resp = fallback_query.execute()
            else:
                raise
        latest = resp.data[0] if resp.data else None
        if APP_DEBUG and direction == "from_resident":
            if latest:
                print(
                    "Loading Resident->Family message:",
                    latest.get("id"),
                    latest.get("recorded_at"),
                    latest.get("contact_user_id"),
                )
            else:
                print(
                    "Loading Resident->Family message: none",
                    resident_id,
                    contact_user_id,
                )
        _set_cached_message_query_result(cache_key, latest)
        return latest
    except Exception:
        return None


def fetch_latest_messages_for_contact_user_ids(
    resident_id: str,
    access_token: str,
    contact_user_ids: list[str],
    *,
    channel: str = "resident_family",
    include_audio: bool = False,
) -> dict[str, dict]:
    if not resident_id or not contact_user_ids:
        return {}
    unique_ids_for_cache: list[str] = []
    seen_for_cache: set[str] = set()
    for raw_id in contact_user_ids:
        user_id = str(raw_id or "").strip()
        if not user_id or user_id in seen_for_cache:
            continue
        seen_for_cache.add(user_id)
        unique_ids_for_cache.append(user_id)
    cache_key = (
        "fetch_latest_messages_for_contact_user_ids",
        str(st.session_state.get("auth_uid") or ""),
        resident_id,
        channel,
        bool(include_audio),
        tuple(sorted(unique_ids_for_cache)),
    )
    cached = _get_cached_message_query_result(cache_key)
    if isinstance(cached, dict):
        return cached
    supabase, error = get_authed_supabase(access_token)
    if error:
        return {}
    unique_ids: list[str] = []
    seen_ids: set[str] = set()
    for raw_id in contact_user_ids:
        user_id = str(raw_id or "").strip()
        if not user_id or user_id in seen_ids:
            continue
        seen_ids.add(user_id)
        unique_ids.append(user_id)
    if not unique_ids:
        return {}
    try:
        select_fields = _message_select_fields(
            include_audio=include_audio,
            include_optional_storage_columns=True,
        )
        query = (
            supabase.table("messages")
            .select(select_fields)
            .eq("resident_id", resident_id)
            .eq("direction", "to_resident")
            .eq("channel", channel)
            .in_("contact_user_id", unique_ids)
            .order("recorded_at", desc=True)
        )
        try:
            resp = query.execute()
        except Exception as exc:
            missing_audio_columns, missing_transcript_columns = _message_missing_optional_columns(exc)
            missing_text_columns = _message_missing_text_columns(exc)
            if (include_audio and (missing_audio_columns or missing_transcript_columns)) or missing_text_columns:
                if missing_transcript_columns:
                    st.session_state["_messages_missing_transcript_columns"] = True
                resp = (
                    supabase.table("messages")
                    .select(
                        _message_select_fields(
                            include_audio=include_audio,
                            include_optional_storage_columns=not missing_audio_columns,
                            include_optional_transcript_columns=not missing_transcript_columns,
                            include_optional_text_columns=not missing_text_columns,
                        )
                    )
                    .eq("resident_id", resident_id)
                    .eq("direction", "to_resident")
                    .eq("channel", channel)
                    .in_("contact_user_id", unique_ids)
                    .order("recorded_at", desc=True)
                    .execute()
                )
            else:
                raise
        latest_by_contact: dict[str, dict] = {}
        for row in resp.data or []:
            contact_user_id = str(row.get("contact_user_id") or "").strip()
            if not contact_user_id or contact_user_id in latest_by_contact:
                continue
            latest_by_contact[contact_user_id] = row
        _set_cached_message_query_result(cache_key, latest_by_contact)
        return latest_by_contact
    except Exception:
        return {}


def get_family_user_for_session(access_token: str | None) -> dict | None:
    auth_uid = str(st.session_state.get("auth_uid") or "").strip()
    if not auth_uid:
        return None
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        family_table = _family_user_table_name(supabase)
        resp = (
            supabase.table(family_table)
            .select("id, care_home_id, display_name")
            .eq("auth_user_id", auth_uid)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def _filter_practical_messages_for_family_user(
    rows: list[dict],
    family_user_id: str | None,
) -> list[dict]:
    if not family_user_id:
        return rows
    current_family_user_id = str(family_user_id or "").strip()
    filtered_rows = []
    for row in rows or []:
        target_type = normalize_office_practical_target_type(row.get("target_type"))
        target_family_user_id = str(row.get("target_family_user_id") or "").strip()
        if target_type == OFFICE_PRACTICAL_TARGET_ALL_FAMILY:
            filtered_rows.append(row)
        elif target_type == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY:
            filtered_rows.append(row)
        elif target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
            continue
    return filtered_rows


def fetch_latest_open_office_practical_message(
    resident_id: str, access_token: str | None, family_user_id: str | None = None
) -> dict | None:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        resp = (
            supabase.table("office_practical_messages")
            .select(
                "id, care_home_id, resident_id, title, body, allow_note, response_enabled, "
                "status, created_at, context_type, requested_date, requested_time_window, "
                "target_type, target_family_user_id, mobile_response_choice, mobile_response_note, "
                "mobile_response_option_ids, mobile_response_status, mobile_response_updated_at"
            )
            .eq("resident_id", resident_id)
            .eq("status", "open")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        rows = _filter_practical_messages_for_family_user(resp.data or [], family_user_id)
        return rows[0] if rows else None
    except Exception:
        try:
            legacy_resp = (
                supabase.table("office_practical_messages")
                .select("id, care_home_id, resident_id, title, body, allow_note, response_enabled, status, created_at")
                .eq("resident_id", resident_id)
                .eq("status", "open")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not legacy_resp.data:
                return None
            row = legacy_resp.data[0]
            row.setdefault("context_type", OFFICE_PRACTICAL_CONTEXT_GENERAL)
            row.setdefault("requested_date", None)
            row.setdefault("requested_time_window", None)
            row.setdefault("target_type", OFFICE_PRACTICAL_TARGET_ALL_FAMILY)
            row.setdefault("target_family_user_id", None)
            row.setdefault("mobile_response_choice", None)
            row.setdefault("mobile_response_note", "")
            row.setdefault("mobile_response_option_ids", [])
            row.setdefault("mobile_response_status", None)
            row.setdefault("mobile_response_updated_at", None)
            return row
        except Exception:
            return None


def fetch_latest_open_mobile_practical_message(
    resident_id: str, access_token: str | None
) -> dict | None:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        resp = (
            supabase.table("office_practical_messages")
            .select(
                "id, care_home_id, resident_id, title, body, allow_note, response_enabled, "
                "status, created_at, context_type, requested_date, requested_time_window, "
                "target_type, target_family_user_id, mobile_response_choice, mobile_response_note, "
                "mobile_response_option_ids, mobile_response_status, mobile_response_updated_at"
            )
            .eq("resident_id", resident_id)
            .eq("status", "open")
            .eq("target_type", OFFICE_PRACTICAL_TARGET_MOBILE)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def fetch_mobile_practical_response(
    message_id: str,
    access_token: str | None,
) -> dict | None:
    if not message_id:
        return None
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    try:
        resp = (
            supabase.table("office_practical_mobile_responses")
            .select("id, primary_choice, note, selected_option_ids, response_status")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        return None


def fetch_office_practical_message_options(
    message_id: str, access_token: str | None
) -> list[dict]:
    supabase, error = get_authed_supabase(access_token)
    if error or not message_id:
        return []
    try:
        resp = (
            supabase.table("office_practical_message_options")
            .select("id, option_label, sort_order")
            .eq("message_id", message_id)
            .order("sort_order")
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def fetch_family_practical_response(
    message_id: str,
    family_user_id: str,
    access_token: str | None,
) -> dict | None:
    if not message_id or not family_user_id:
        return None
    supabase, error = get_authed_supabase(access_token)
    if error:
        return None
    family_col = _office_practical_family_user_column(supabase)
    try:
        try:
            response_resp = (
                supabase.table("office_practical_responses")
                .select("id, primary_choice, note, response_status, planned_visit_time, share_with_family")
                .eq("message_id", message_id)
                .eq(family_col, family_user_id)
                .limit(1)
                .execute()
            )
        except Exception:
            response_resp = (
                supabase.table("office_practical_responses")
                .select("id, primary_choice, note, response_status")
                .eq("message_id", message_id)
                .eq(family_col, family_user_id)
                .limit(1)
                .execute()
            )
        if not response_resp.data:
            return None
        response_row = response_resp.data[0]
        response_id = str(response_row.get("id") or "").strip()
        selected_option_ids: list[str] = []
        if response_id:
            checks_resp = (
                supabase.table("office_practical_response_checks")
                .select("option_id")
                .eq("response_id", response_id)
                .execute()
            )
            selected_option_ids = [
                str(row.get("option_id") or "").strip()
                for row in (checks_resp.data or [])
                if str(row.get("option_id") or "").strip()
            ]
        return {
            "id": response_id,
            "primary_choice": response_row.get("primary_choice"),
            "note": response_row.get("note") or "",
            "response_status": response_row.get("response_status") or "submitted",
            "planned_visit_time": response_row.get("planned_visit_time") or "",
            "share_with_family": bool(response_row.get("share_with_family", False)),
            "selected_option_ids": selected_option_ids,
        }
    except Exception:
        return None


def fetch_shared_family_practical_responses(
    message_id: str,
    current_family_user_id: str,
    access_token: str | None,
) -> list[dict]:
    if not message_id:
        return []
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    family_col = _office_practical_family_user_column(supabase)
    family_rel = _family_user_relation_name(supabase)
    try:
        try:
            resp = (
                supabase.table("office_practical_responses")
                .select(f"{family_col}, primary_choice, planned_visit_time, note, {family_rel}(display_name)")
                .eq("message_id", message_id)
                .eq("share_with_family", True)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception:
            return []
        rows = []
        current_id = str(current_family_user_id or "").strip()
        for row in resp.data or []:
            family_user_id = str(row.get(family_col) or "").strip()
            if current_id and family_user_id == current_id:
                continue
            family_details = row.get(family_rel) or {}
            rows.append(
                {
                    "contact_name": str(family_details.get("display_name") or "Family Member"),
                    "primary_choice": str(row.get("primary_choice") or "").strip().lower(),
                    "planned_visit_time": str(row.get("planned_visit_time") or "").strip(),
                    "note": str(row.get("note") or "").strip(),
                }
            )
        return rows
    except Exception:
        return []


def fetch_family_noticeboard_notes(
    resident_id: str,
    access_token: str | None,
) -> list[dict]:
    if not resident_id:
        return []
    supabase, error = get_authed_supabase(access_token)
    if error:
        return []
    family_rel = _family_user_relation_name(supabase)
    try:
        resp = (
            supabase.table("family_noticeboard_notes")
            .select(f"id, family_user_id, note_body, {family_rel}(display_name)")
            .eq("resident_id", resident_id)
            .order("updated_at", desc=True)
            .execute()
        )
        rows = []
        for row in resp.data or []:
            family_details = row.get(family_rel) or {}
            rows.append(
                {
                    "id": str(row.get("id") or "").strip(),
                    "family_user_id": str(row.get("family_user_id") or "").strip(),
                    "contact_name": str(family_details.get("display_name") or "Family Member"),
                    "note_body": str(row.get("note_body") or "").strip(),
                }
            )
        return rows
    except Exception:
        return []


def upsert_family_noticeboard_note(
    resident_id: str,
    care_home_id: str,
    family_user_id: str,
    note_body: str,
    access_token: str | None,
) -> tuple[bool, str]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    resident_id = str(resident_id or "").strip()
    care_home_id = str(care_home_id or "").strip()
    family_user_id = str(family_user_id or "").strip()
    note_value = str(note_body or "").strip()
    if not resident_id or not care_home_id or not family_user_id:
        return False, "Your Family Member mapping could not be found. Please sign in again."
    if not note_value:
        return False, "Write a short practical note first."
    if len(note_value) > 500:
        note_value = note_value[:500]
    now_iso = __import__("datetime").datetime.utcnow().isoformat()
    payload = {
        "care_home_id": care_home_id,
        "resident_id": resident_id,
        "family_user_id": family_user_id,
        "note_body": note_value,
        "updated_at": now_iso,
    }
    try:
        try:
            (
                supabase.table("family_noticeboard_notes")
                .upsert(payload, on_conflict="resident_id,family_user_id")
                .execute()
            )
        except Exception:
            existing_resp = (
                supabase.table("family_noticeboard_notes")
                .select("id")
                .eq("resident_id", resident_id)
                .eq("family_user_id", family_user_id)
                .limit(1)
                .execute()
            )
            existing_id = (
                str(existing_resp.data[0].get("id") or "").strip()
                if existing_resp.data
                else ""
            )
            if existing_id:
                (
                    supabase.table("family_noticeboard_notes")
                    .update(payload)
                    .eq("id", existing_id)
                    .execute()
                )
            else:
                payload["created_at"] = now_iso
                supabase.table("family_noticeboard_notes").insert(payload).execute()
        return True, "Noticeboard note saved."
    except Exception as exc:
        return False, str(exc)


def clear_family_noticeboard_note(
    note_id: str,
    access_token: str | None,
) -> tuple[bool, str]:
    note_id = str(note_id or "").strip()
    if not note_id:
        return False, "Noticeboard note not found."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    try:
        supabase.table("family_noticeboard_notes").delete().eq("id", note_id).execute()
        return True, "Noticeboard note cleared."
    except Exception as exc:
        return False, str(exc)


def render_family_noticeboard_notes_for_staff(
    resident_id: str,
    access_token: str | None,
    *,
    allow_clear: bool,
    key_prefix: str,
) -> None:
    noticeboard_notes = fetch_family_noticeboard_notes(resident_id, access_token)
    st.markdown("**Family noticeboard: current practical notes from Family Members**")
    st.caption(
        "Current practical notes from Family Members. No chat, no threads, and no urgent or sensitive matters."
    )
    if not noticeboard_notes:
        st.caption("No family noticeboard notes yet.")
        return
    for notice in noticeboard_notes:
        notice_id = str(notice.get("id") or "").strip()
        contact_name = str(notice.get("contact_name") or "Family Member").strip()
        note_body = str(notice.get("note_body") or "").strip()
        if not note_body:
            continue
        st.markdown(f"- {contact_name}: {note_body}")
        if allow_clear and notice_id:
            if st.button(
                f"Clear note from {contact_name}",
                key=f"{key_prefix}_noticeboard_clear_{resident_id}_{notice_id}",
                use_container_width=True,
            ):
                ok, message = clear_family_noticeboard_note(notice_id, access_token)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def upsert_family_practical_response(
    message_id: str,
    family_user_id: str,
    primary_choice: str,
    note: str,
    selected_option_ids: list[str],
    planned_visit_time: str,
    share_with_family: bool,
    access_token: str | None,
) -> tuple[bool, str]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    if primary_choice not in STRUCTURED_RESPONSE_CHOICES:
        return False, "Please choose No response, Yes, No, or Maybe."
    family_col = _office_practical_family_user_column(supabase)
    try:
        message_resp = (
            supabase.table("office_practical_messages")
            .select("id, allow_note, response_enabled, status")
            .eq("id", message_id)
            .limit(1)
            .execute()
        )
        if not message_resp.data:
            return False, "This office message is not available."
        message_row = message_resp.data[0]
        if message_row.get("status") != "open" or not bool(
            message_row.get("response_enabled", True)
        ):
            return False, "Responses are closed for this message."

        options_resp = (
            supabase.table("office_practical_message_options")
            .select("id")
            .eq("message_id", message_id)
            .execute()
        )
        allowed_option_ids = {
            str(row.get("id") or "").strip() for row in (options_resp.data or [])
        }
        clean_option_ids = []
        for option_id in selected_option_ids or []:
            candidate = str(option_id or "").strip()
            if candidate and candidate in allowed_option_ids:
                clean_option_ids.append(candidate)

        allow_note = bool(message_row.get("allow_note", True))
        note_value = (note or "").strip()
        if not allow_note:
            note_value = ""
        if len(note_value) > 500:
            note_value = note_value[:500]

        now_iso = __import__("datetime").datetime.utcnow().isoformat()
        existing_resp = (
            supabase.table("office_practical_responses")
            .select("id")
            .eq("message_id", message_id)
            .eq(family_col, family_user_id)
            .limit(1)
            .execute()
        )
        existing_response_id = (
            str(existing_resp.data[0].get("id") or "").strip()
            if existing_resp.data
            else ""
        )
        response_payload = {
            "message_id": message_id,
            family_col: family_user_id,
            "primary_choice": primary_choice,
            "note": note_value,
            "planned_visit_time": (planned_visit_time or "").strip()[:80],
            "share_with_family": bool(share_with_family),
            "response_status": "submitted",
            "updated_at": now_iso,
        }
        try:
            if existing_response_id:
                response_payload["submitted_at"] = now_iso
                _ = (
                    supabase.table("office_practical_responses")
                    .update(response_payload)
                    .eq("id", existing_response_id)
                    .execute()
                )
                response_id = existing_response_id
            else:
                response_payload["submitted_at"] = now_iso
                inserted = (
                    supabase.table("office_practical_responses")
                    .insert(response_payload)
                    .execute()
                )
                response_id = (
                    str(inserted.data[0].get("id") or "").strip()
                    if inserted.data
                    else ""
                )
        except Exception:
            legacy_payload = dict(response_payload)
            legacy_payload.pop("planned_visit_time", None)
            legacy_payload.pop("share_with_family", None)
            if existing_response_id:
                _ = (
                    supabase.table("office_practical_responses")
                    .update(legacy_payload)
                    .eq("id", existing_response_id)
                    .execute()
                )
                response_id = existing_response_id
            else:
                inserted = (
                    supabase.table("office_practical_responses")
                    .insert(legacy_payload)
                    .execute()
                )
                response_id = (
                    str(inserted.data[0].get("id") or "").strip()
                    if inserted.data
                    else ""
                )
        if not response_id:
            return False, "Could not save response."

        _ = (
            supabase.table("office_practical_response_checks")
            .delete()
            .eq("response_id", response_id)
            .execute()
        )
        if clean_option_ids:
            check_rows = [
                {"response_id": response_id, "option_id": option_id}
                for option_id in clean_option_ids
            ]
            _ = supabase.table("office_practical_response_checks").insert(check_rows).execute()
        return True, "Response received."
    except Exception as exc:
        return False, str(exc)


def upsert_mobile_practical_response(
    message_id: str,
    primary_choice: str,
    note: str,
    selected_option_ids: list[str],
    access_token: str | None,
) -> tuple[bool, str]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    if primary_choice not in STRUCTURED_RESPONSE_CHOICES:
        return False, "Please choose No response, Yes, No, or Maybe."
    try:
        message_resp = (
            supabase.table("office_practical_messages")
            .select("id, allow_note, response_enabled, status, target_type")
            .eq("id", message_id)
            .limit(1)
            .execute()
        )
        if not message_resp.data:
            return False, "This request is not available."
        message_row = message_resp.data[0]
        if normalize_office_practical_target_type(message_row.get("target_type")) != OFFICE_PRACTICAL_TARGET_MOBILE:
            return False, "This request is not for Mobile."
        if message_row.get("status") != "open" or not bool(
            message_row.get("response_enabled", True)
        ):
            return False, "Responses are closed for this request."

        options_resp = (
            supabase.table("office_practical_message_options")
            .select("id")
            .eq("message_id", message_id)
            .execute()
        )
        allowed_option_ids = {
            str(row.get("id") or "").strip() for row in (options_resp.data or [])
        }
        clean_option_ids = []
        for option_id in selected_option_ids or []:
            candidate = str(option_id or "").strip()
            if candidate and candidate in allowed_option_ids:
                clean_option_ids.append(candidate)

        note_value = (note or "").strip() if bool(message_row.get("allow_note", True)) else ""
        if len(note_value) > 500:
            note_value = note_value[:500]
        now_iso = __import__("datetime").datetime.utcnow().isoformat()
        response_payload = {
            "message_id": message_id,
            "primary_choice": primary_choice,
            "note": note_value,
            "selected_option_ids": clean_option_ids,
            "response_status": "submitted",
            "submitted_by": st.session_state.get("auth_uid"),
            "updated_at": now_iso,
        }
        existing_resp = (
            supabase.table("office_practical_mobile_responses")
            .select("id")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        existing_response_id = (
            str(existing_resp.data[0].get("id") or "").strip()
            if existing_resp.data
            else ""
        )
        if existing_response_id:
            (
                supabase.table("office_practical_mobile_responses")
                .update(response_payload)
                .eq("id", existing_response_id)
                .execute()
            )
        else:
            response_payload["submitted_at"] = now_iso
            (
                supabase.table("office_practical_mobile_responses")
                .insert(response_payload)
                .execute()
            )
        verify_resp = (
            supabase.table("office_practical_mobile_responses")
            .select("id, primary_choice")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        verified_choice = (
            str((verify_resp.data or [{}])[0].get("primary_choice") or "")
            .strip()
            .lower()
            if verify_resp.data
            else ""
        )
        if verified_choice != primary_choice:
            return (
                False,
                "Mobile response could not be saved. Check office_practical_mobile_responses permissions.",
            )
        return True, "Mobile response received."
    except Exception as exc:
        return False, str(exc)


def create_office_practical_message(
    resident_id: str,
    care_home_id: str,
    title: str,
    body: str,
    allow_note: bool,
    checkbox_option_labels: list[str],
    context_type: str,
    requested_date: str,
    requested_time_window: str,
    target_type: str,
    target_family_user_id: str | None,
    access_token: str | None,
) -> tuple[bool, str | None, str]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, None, error
    title_value = (title or "").strip()
    body_value = (body or "").strip()
    if not title_value:
        return False, None, "Enter a short title."
    if not body_value:
        return False, None, "Enter a message."
    if len(title_value) > 120:
        title_value = title_value[:120]
    if len(body_value) > 800:
        body_value = body_value[:800]
    now_iso = __import__("datetime").datetime.utcnow().isoformat()
    try:
        context_value = (
            OFFICE_PRACTICAL_CONTEXT_VISIT
            if context_type == OFFICE_PRACTICAL_CONTEXT_VISIT
            else OFFICE_PRACTICAL_CONTEXT_GENERAL
        )
        target_value = normalize_office_practical_target_type(target_type)
        target_family_value = str(target_family_user_id or "").strip()
        if target_value == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY and not target_family_value:
            return False, None, "Choose the intended Family Member responder."
        payload = {
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "title": title_value,
            "body": body_value,
            "allow_note": bool(allow_note),
            "response_enabled": True,
            "status": "open",
            "context_type": context_value,
            "requested_date": (requested_date or "").strip() or None,
            "requested_time_window": (requested_time_window or "").strip()[:80] or None,
            "target_type": target_value,
            "target_family_user_id": (
                target_family_value
                if target_value == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY
                else None
            ),
            "created_by": st.session_state.get("auth_uid"),
            "created_at": now_iso,
        }
        try:
            msg_resp = supabase.table("office_practical_messages").insert(payload).execute()
        except Exception:
            legacy_payload = dict(payload)
            legacy_payload.pop("context_type", None)
            legacy_payload.pop("requested_date", None)
            legacy_payload.pop("requested_time_window", None)
            legacy_payload.pop("target_type", None)
            legacy_payload.pop("target_family_user_id", None)
            msg_resp = supabase.table("office_practical_messages").insert(legacy_payload).execute()
        message_id = (
            str(msg_resp.data[0].get("id") or "").strip()
            if msg_resp.data
            else ""
        )
        if not message_id:
            return False, None, "Could not publish request."
        clean_labels = []
        seen = set()
        for label in checkbox_option_labels or []:
            value = str(label or "").strip()
            if not value:
                continue
            if value.casefold() in seen:
                continue
            seen.add(value.casefold())
            clean_labels.append(value[:120])
        if clean_labels:
            option_rows = [
                {
                    "message_id": message_id,
                    "option_label": option_label,
                    "sort_order": idx + 1,
                }
                for idx, option_label in enumerate(clean_labels)
            ]
            _ = supabase.table("office_practical_message_options").insert(option_rows).execute()
        return True, message_id, "Request published."
    except Exception as exc:
        return False, None, str(exc)


def create_mobile_practical_message(
    resident_id: str,
    care_home_id: str,
    title: str,
    body: str,
    allow_note: bool,
    checkbox_option_labels: list[str],
    context_type: str,
    requested_date: str,
    requested_time_window: str,
    access_token: str | None,
) -> tuple[bool, str | None, str]:
    return create_office_practical_message(
        resident_id,
        care_home_id,
        title,
        body,
        allow_note,
        checkbox_option_labels,
        context_type,
        requested_date,
        requested_time_window,
        OFFICE_PRACTICAL_TARGET_MOBILE,
        None,
        access_token,
    )


def close_office_practical_message(
    message_id: str,
    access_token: str | None,
) -> tuple[bool, str]:
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    if not message_id:
        return False, "Message not found."
    try:
        _ = (
            supabase.table("office_practical_messages")
            .update(
                {
                    "status": "closed",
                    "response_enabled": False,
                    "closed_at": __import__("datetime").datetime.utcnow().isoformat(),
                }
            )
            .eq("id", message_id)
            .execute()
        )
        return True, "Responses closed for this request."
    except Exception as exc:
        return False, str(exc)


def fetch_office_practical_response_summary(
    message_id: str,
    access_token: str | None,
) -> dict:
    summary = {
        "responses": [],
        "choice_counts": {choice: 0 for choice in STRUCTURED_RESPONSE_CHOICES},
        "option_counts": {},
        "total": 0,
    }
    if not message_id:
        return summary
    supabase, error = get_authed_supabase(access_token)
    if error:
        return summary
    try:
        family_col = _office_practical_family_user_column(supabase)
        family_rel = _family_user_relation_name(supabase)
        options = fetch_office_practical_message_options(message_id, access_token)
        option_label_by_id = {
            str(option.get("id") or "").strip(): str(option.get("option_label") or "").strip()
            for option in options
        }
        try:
            responses_resp = (
                supabase.table("office_practical_responses")
                .select(
                    f"id, {family_col}, primary_choice, note, response_status, planned_visit_time, "
                    f"share_with_family, {family_rel}(display_name)"
                )
                .eq("message_id", message_id)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception:
            responses_resp = (
                supabase.table("office_practical_responses")
                .select(f"id, {family_col}, primary_choice, note, response_status, {family_rel}(display_name)")
                .eq("message_id", message_id)
                .order("updated_at", desc=True)
                .execute()
            )
        response_rows = responses_resp.data or []
        response_ids = [
            str(row.get("id") or "").strip()
            for row in response_rows
            if str(row.get("id") or "").strip()
        ]
        checks_by_response_id: dict[str, list[str]] = {}
        if response_ids:
            checks_resp = (
                supabase.table("office_practical_response_checks")
                .select("response_id, option_id")
                .in_("response_id", response_ids)
                .execute()
            )
            for row in checks_resp.data or []:
                response_id = str(row.get("response_id") or "").strip()
                option_id = str(row.get("option_id") or "").strip()
                option_label = option_label_by_id.get(option_id, "")
                if not response_id or not option_label:
                    continue
                checks_by_response_id.setdefault(response_id, []).append(option_label)
                summary["option_counts"][option_label] = (
                    int(summary["option_counts"].get(option_label, 0)) + 1
                )

        for row in response_rows:
            choice = str(row.get("primary_choice") or "").strip().lower()
            if choice in summary["choice_counts"]:
                summary["choice_counts"][choice] += 1
            response_id = str(row.get("id") or "").strip()
            family_details = row.get(family_rel) or {}
            summary["responses"].append(
                {
                    "contact_name": str(family_details.get("display_name") or "Family Member"),
                    "primary_choice": choice,
                    "note": str(row.get("note") or "").strip(),
                    "planned_visit_time": str(row.get("planned_visit_time") or "").strip(),
                    "share_with_family": bool(row.get("share_with_family", False)),
                    "selected_labels": checks_by_response_id.get(response_id, []),
                }
            )
        summary["total"] = len(summary["responses"])
        return summary
    except Exception:
        return summary


def decode_audio_payload(message: dict, access_token: str | None = None) -> bytes | None:
    if not message:
        return None
    audio_source = str(message.get("audio_source") or "").strip().lower()
    object_path = str(message.get("audio_object_path") or "").strip()
    if object_path and (audio_source == "storage" or not message.get("audio_storage_path")):
        downloaded = _download_audio_from_storage(
            object_path,
            access_token=access_token or st.session_state.get("access_token"),
        )
        if downloaded:
            return downloaded
    payload = str(message.get("audio_storage_path") or "").strip()
    if not payload:
        return None
    if not _looks_like_base64_payload(payload):
        downloaded = _download_audio_from_storage(
            payload,
            access_token=access_token or st.session_state.get("access_token"),
        )
        if downloaded:
            return downloaded
        relaxed_decoded = _try_decode_base64_audio(payload)
        if relaxed_decoded:
            return relaxed_decoded
        return None
    try:
        return base64.b64decode(payload)
    except Exception:
        return _try_decode_base64_audio(payload)


def render_transcript_assist(
    message: dict | None,
    *,
    policy_mode: str = "assist",
    care_home_id: str | None = None,
    resident_id: str | None = None,
) -> bool:
    def _fetch_transcript_fields_for_message(message_id: str) -> tuple[str, str]:
        normalized_id = str(message_id or "").strip()
        if not normalized_id:
            return "", ""
        access_token = str(st.session_state.get("access_token") or "").strip()
        supabase, error = get_authed_supabase(access_token)
        if error or supabase is None:
            return "", ""
        try:
            response = (
                supabase.table("messages")
                .select("transcript_text, transcript_status")
                .eq("id", normalized_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if _is_missing_column_error(exc, "transcript_text") or _is_missing_column_error(
                exc, "transcript_status"
            ):
                st.session_state["_messages_missing_transcript_columns"] = True
            return "", ""
        row = response.data[0] if response.data else {}
        if not isinstance(row, dict):
            return "", ""
        text_value = str(row.get("transcript_text") or "").strip()
        status_value = str(row.get("transcript_status") or "").strip().lower()
        return text_value, status_value

    def _persist_transcript_fields(message_id: str, transcript_fields: dict) -> None:
        normalized_id = str(message_id or "").strip()
        if not normalized_id:
            return
        access_token = str(st.session_state.get("access_token") or "").strip()
        supabase, error = get_authed_supabase(access_token)
        if error or supabase is None:
            return
        update_payload = {
            "transcript_text": transcript_fields.get("transcript_text"),
            "transcript_status": transcript_fields.get("transcript_status"),
            "transcript_model": transcript_fields.get("transcript_model"),
            "transcript_generated_at": transcript_fields.get("transcript_generated_at"),
        }
        try:
            _ = (
                supabase.table("messages")
                .update(update_payload)
                .eq("id", normalized_id)
                .execute()
            )
        except Exception as exc:
            if (
                _is_missing_column_error(exc, "transcript_text")
                or _is_missing_column_error(exc, "transcript_status")
                or _is_missing_column_error(exc, "transcript_model")
                or _is_missing_column_error(exc, "transcript_generated_at")
            ):
                st.session_state["_messages_missing_transcript_columns"] = True

    def _generate_transcript_for_message(message_obj: dict) -> tuple[str, str, str]:
        if not isinstance(message_obj, dict):
            return "", "failed", "Message is unavailable."
        audio_bytes = decode_audio_payload(message_obj, access_token=st.session_state.get("access_token"))
        if not audio_bytes:
            return "", "failed", "Audio is unavailable for transcript generation."
        audio_mime_type = str(message_obj.get("audio_mime_type") or "").strip() or "audio/wav"
        transcript_fields, transcript_error = build_transcript_fields(
            audio_bytes,
            audio_mime_type,
            requested=True,
        )
        status_value = str(transcript_fields.get("transcript_status") or "").strip().lower()
        text_value = str(transcript_fields.get("transcript_text") or "").strip()
        message_id = str(message_obj.get("id") or "").strip()
        if message_id:
            _persist_transcript_fields(message_id, transcript_fields)
        if status_value == "ready" and text_value:
            return text_value, status_value, ""
        return "", status_value or "failed", transcript_error or "Transcript could not be generated."

    try:
        mode = normalize_transcript_policy_mode(policy_mode)
        if not isinstance(message, dict):
            return True
        status = str(message.get("transcript_status") or "").strip().lower()
        transcript_text = str(message.get("transcript_text") or "").strip()
        message_id = str(message.get("id") or "").strip()
        if message_id and (not transcript_text or not status):
            fetched_text, fetched_status = _fetch_transcript_fields_for_message(message_id)
            if fetched_text and not transcript_text:
                transcript_text = fetched_text
            if fetched_status and not status:
                status = fetched_status
        message_key = message_id or (
            f"{str(message.get('direction') or '').strip()}::"
            f"{str(message.get('channel') or '').strip()}::"
            f"{str(message.get('recorded_at') or '').strip()}"
        )
        toggle_key = f"transcript_toggle::{resident_id or ''}::{message_key}"
        transcript_visible = bool(st.session_state.get(toggle_key, False))

        if transcript_text and status == "ready":
            toggle_label = "Hide transcript" if transcript_visible else "View transcript"
        elif status == "failed":
            toggle_label = "Retry transcript"
        else:
            toggle_label = "View transcript"

        if st.button(
            toggle_label,
            key=f"transcript_toggle_btn::{resident_id or ''}::{message_key}",
        ):
            if transcript_text and status == "ready":
                st.session_state[toggle_key] = not transcript_visible
                st.rerun()
            else:
                with st.spinner("Generating transcript..."):
                    generated_text, generated_status, generated_error = _generate_transcript_for_message(message)
                if generated_text and generated_status == "ready":
                    transcript_text = generated_text
                    status = "ready"
                    st.session_state[toggle_key] = True
                    st.rerun()
                else:
                    status = generated_status or "failed"
                    st.warning(generated_error or "Transcript could not be generated.")

        if transcript_text:
            if transcript_visible:
                st.markdown(transcript_text)
                st.caption("Transcript may contain errors. Voice remains the source of truth.")
            if mode != "precheck":
                return True
            ack_key = f"transcript_precheck_ack::{resident_id or ''}::{message_key}"
            reviewed = bool(st.session_state.get(ack_key))
            if st.button(
                "Mark transcript reviewed",
                key=f"transcript_precheck_btn::{resident_id or ''}::{message_key}",
                use_container_width=True,
            ):
                st.session_state[ack_key] = True
                reviewed = True
                if message_id:
                    log_audit_event(
                        "transcript_viewed_preplay",
                        "care_hub",
                        care_home_id,
                        target_id=message_id,
                        resident_id=resident_id,
                    )
            if not reviewed:
                st.warning("Transcript review is required before playback (policy mode: precheck).")
            return True
        if status == "failed":
            st.caption("Transcript is not available for this message.")
        elif status == "not_requested":
            st.caption("Transcript has not been requested for this message.")
        if mode == "precheck":
            st.caption("Transcript is unavailable. Playback remains available.")
        return True
    except Exception as exc:
        # Streamlit control-flow exceptions (for rerun/stop) must propagate.
        if exc.__class__.__name__ in {"RerunException", "StopException"}:
            raise
        if APP_DEBUG:
            print(f"[transcript-assist] suppressed error: {exc}", flush=True)
        st.caption("Transcript assist is temporarily unavailable. Playback remains available.")
        return True


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


def resolve_asset_file(filename: str) -> Path | None:
    base_dir = Path(__file__).resolve().parent
    name = str(filename or "").strip()
    if not name:
        return None
    candidates = [
        base_dir / "assets" / name,
        base_dir / "site" / "assets" / name,
        Path("assets") / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


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
    st.markdown(
        """
<style>
  .vm-logo-row {{
    display: flex;
    align-items: center;
    min-height: 58px;
  }}
  .vm-logo-row .vm-logo-text {{
    font-size: 1.72rem;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: 0;
    white-space: nowrap;
    color: #1f2937;
  }}
  .vm-logo-row .vm-logo-text span {{
    color: #6b7280;
    font-weight: 700;
  }}
  @media (max-width: 768px) {{
    .vm-logo-row .vm-logo-text {{
      font-size: 0.96rem;
    }}
  }}
</style>
<div class="vm-logo-row">
  <span class="vm-logo-text">familyupdates<span>.care</span></span>
</div>
""",
        unsafe_allow_html=True,
    )


def get_logo_data_uri() -> str:
    return ""


def render_route_transition_loader(duration_ms: int = 700) -> None:
    logo_html = '<div class="vm-wait-wordmark">familyupdates<span>.care</span></div>'
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
  .vm-wait-wordmark {{
    color: #1f2937;
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: 0;
    animation: vm-logo-fade 2.4s ease-in-out infinite;
  }}
  .vm-wait-wordmark span {{
    color: #6b7280;
    font-weight: 700;
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


def render_life_file_guide() -> None:
    render_page_header("Life File Guide", show_variant_subheading=False)
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    back_route = (
        get_home_route(runtime_variant)
        if runtime_variant in {VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}
        else PUBLIC_HOME_ROUTE
    )
    render_route_link("Back", back_route, key="life_file_guide_back")
    access_token = st.session_state.get("access_token")
    if access_token:
        lifecycle_stage = get_lifecycle_stage(access_token)
        lifecycle_policy = get_lifecycle_policy(
            lifecycle_stage,
            get_operating_mode(access_token),
            get_communication_level(access_token),
        )
        render_stage_level_status(
            lifecycle_policy,
            context="Preparation sits outside the app.",
        )
    st.markdown(
        "Use this guide to organise important information outside the app. "
        "Paper, computer files, and phone notes are all fine."
    )
    st.markdown(
        "This is preparation before family coordination becomes difficult. "
        "A simple external filing system helps the person stay independent for longer, "
        "reduces family friction, and avoids important information being sorted out in a rush."
    )
    st.markdown(
        "The important point is that information is organised in the person's own external system, "
        "accessible to the right person when needed, and separated so private information is not shared by accident."
    )
    st.caption(
        "familyupdates.care does not store these records. Keep private information separate from "
        "practical information that a carer, helper, or family member may need."
    )
    st.caption(
        "Do not put medical records, financial records, legal documents, passwords, care logs, "
        "or private long-form notes into familyupdates.care."
    )
    for section_id, title, list_heading, items in LIFE_FILE_GUIDE_SECTIONS:
        with st.expander(title, expanded=(section_id == "prep")):
            st.markdown(f"**{list_heading}:**")
            for item in items:
                st.markdown(f"- {item}")
    st.markdown("### Naming files")
    st.markdown(
        "Use plain names that can be found quickly on a computer or phone. For example: "
        "`Margaret Hill - Life Log`, `Margaret Hill - Contacts`, "
        "`Margaret Hill - Admin and Key Documents`, `Margaret Hill - Private Finance`, "
        "`Margaret Hill - Private Health Notes`, and `Margaret Hill - Carer and Housekeeping Notes`."
    )
    st.markdown("### Sharing")
    st.markdown(
        "Share only what is needed. A carer may need practical housekeeping notes. They should not "
        "normally need private finance, private health, or key document information."
    )


def render_header_menu(menu_key: str) -> None:
    current_route = st.session_state.get("current_page") or get_route()
    app_variant = resolve_runtime_variant(route_hint=current_route)
    if app_variant == VARIANT_PUBLIC and st.session_state.get("auth_uid"):
        active_role = str(st.session_state.get("active_role") or "").strip().lower()
        if active_role == "care_hub":
            app_variant = (
                VARIANT_OFFICE
                if bool(st.session_state.get("office_login_explicit"))
                else VARIANT_MOBILE
            )
        elif active_role == "family":
            app_variant = VARIANT_FAMILY
    prev_route = st.session_state.get("prev_page") or "/"
    show_back_only = current_route.startswith("/how-it-works/") and prev_route in ("/", "", None)
    with st.popover("\u2630"):
        # Prevent first action from clipping at the popover edge on small screens.
        st.markdown('<div style="height:0.9rem"></div>', unsafe_allow_html=True)
        if app_variant == VARIANT_OFFICE:
            is_authed = bool(st.session_state.get("auth_uid"))
            if not is_authed:
                if st.button("Complaints & Concerns", key=f"{menu_key}_office_complaints_public"):
                    set_public_document_route("/public/complaints-and-concerns")
                    return
                if st.button("Go to login", key=f"{menu_key}_office_login"):
                    set_route(get_login_route(app_variant))
                    return
                if st.button("Privacy Notice", key=f"{menu_key}_office_privacy_public"):
                    set_public_document_route("/public/privacy-notice")
                    return
                return
        if app_variant not in (VARIANT_OFFICE, VARIANT_FAMILY, VARIANT_MOBILE) and prev_route and prev_route != current_route:
            render_route_link("Back", prev_route, key=f"{menu_key}_back_link")
            return
        if show_back_only and app_variant not in (VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE):
            return
        if app_variant == VARIANT_OFFICE:
            access_token = st.session_state.get("access_token")
            at_home_lifecycle_stage = is_current_at_home_lifecycle_stage(access_token)
            office_label = get_at_home_voicemail_label(access_token)
            st.markdown(f"**{office_label}**")
            clicked_action = None
            inbox_label = "Back to Family Office messages"
            if st.button(inbox_label, key=f"{menu_key}_inbox"):
                clicked_action = ("route", get_home_route(app_variant))
            if st.button("How it works", key=f"{menu_key}_office_how_it_works"):
                clicked_action = ("route", "/care-hub-office/how-it-works")
            if st.button("1. Setup person/system", key=f"{menu_key}_setup_family_system"):
                clicked_action = ("route", "/care-hub/setup-family-system")
            if st.button("2. Register/invite Family Member", key=f"{menu_key}_register_family"):
                clicked_action = ("route", "/care-hub/register-family")
            if st.button("Operational variables", key=f"{menu_key}_operational_variables"):
                clicked_action = ("route", "/care-hub/operational-variables")
            if st.button("Account & Security", key=f"{menu_key}_security"):
                clicked_action = ("route", "/care-hub/security")

            st.markdown("- Daily Use -")
            handbook_label = "How it works" if at_home_lifecycle_stage else "Care Home handbook"
            if st.button(handbook_label, key=f"{menu_key}_office_doc_handbook"):
                clicked_action = (
                    ("route", "/public/how-it-works")
                    if at_home_lifecycle_stage
                    else ("doc", "docs/office/05_care_home_guide.md")
                )
            if not at_home_lifecycle_stage and st.button(
                "Handover checklist", key=f"{menu_key}_office_doc_handover"
            ):
                clicked_action = ("doc", "docs/office/care_home_handover_checklist.md")
            if st.button("Life File Guide", key=f"{menu_key}_office_life_file_guide"):
                clicked_action = ("route", LIFE_FILE_GUIDE_ROUTE)
            qa_label = "Family Office Q&A" if at_home_lifecycle_stage else "Office Q&A"
            if st.button(qa_label, key=f"{menu_key}_office_doc_qa"):
                clicked_action = ("route", "/care-hub/office/qa")

            st.markdown("- Boundaries -" if at_home_lifecycle_stage else "- Governance -")
            if st.button("Documents", key=f"{menu_key}_office_service_overview"):
                clicked_action = ("route", "/docs")
            responsibilities_label = (
                "At-home responsibilities" if at_home_lifecycle_stage else "Care home responsibilities"
            )
            if st.button(responsibilities_label, key=f"{menu_key}_office_doc_responsibilities"):
                clicked_action = ("doc", "docs/office/04_care_home_responsibilities.md")
            if st.button("Safeguarding & consent", key=f"{menu_key}_office_doc_safeguarding"):
                clicked_action = ("doc", "docs/office/09_safeguarding_consent.md")
            if st.button("Privacy notice", key=f"{menu_key}_office_privacy"):
                clicked_action = ("public_doc", "/public/privacy-notice")

            st.markdown("- Formal -")
            if st.button("Complaints & concerns", key=f"{menu_key}_office_complaints"):
                clicked_action = ("public_doc", "/public/complaints-and-concerns")
            if not at_home_lifecycle_stage and st.button(
                "Contracts & templates", key=f"{menu_key}_contracts"
            ):
                clicked_action = ("route", "/contracts")
            st.markdown("---")
            if st.button("Log out (return to login)", key=f"{menu_key}_office_sign_out"):
                clicked_action = ("sign_out", "care_hub")
            if clicked_action:
                action_type, payload = clicked_action
                if action_type == "route":
                    set_route(payload)
                elif action_type == "public_doc":
                    set_public_document_route(payload)
                elif action_type == "doc":
                    access_token = st.session_state.get("access_token")
                    st.session_state["docs_active"] = resolve_mode_doc_path(
                        str(payload or ""),
                        access_token=access_token,
                    )
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
            if st.button("Hub selection", key=f"{menu_key}_public_docs"):
                set_route("/pr-home")
                return
        if app_variant == VARIANT_MOBILE:
            is_authed = bool(st.session_state.get("auth_uid"))
            back_target = get_home_route(app_variant) if is_authed else get_login_route(app_variant)
            if prev_route and prev_route != current_route:
                back_target = prev_route
            if normalize_route(back_target) == normalize_route(current_route):
                render_public_landing_link(
                    "Back to hub selection",
                    key=f"{menu_key}_mobile_back_public_link",
                )
            else:
                render_route_link("Back", back_target, key=f"{menu_key}_mobile_back_link")
            if st.button("Hub selection", key=f"{menu_key}_mobile_public_docs"):
                set_route("/pr-home")
                return
            if st.button("How it works", key=f"{menu_key}_mobile_how_it_works"):
                set_route("/care-hub-mobile/how-it-works")
                return
            if st.button("Mobile Q&A", key=f"{menu_key}_mobile_qa"):
                set_route("/care-hub/mobile/qa")
                return
            if st.button("Life File Guide", key=f"{menu_key}_mobile_life_file_guide"):
                set_route(LIFE_FILE_GUIDE_ROUTE)
                return
            if st.button(
                "Safeguarding and Consent",
                key=f"{menu_key}_mobile_safeguarding",
            ):
                set_public_document_route("/public/safeguarding-and-consent")
                return
            if st.button("Privacy Notice", key=f"{menu_key}_mobile_privacy"):
                set_public_document_route("/public/privacy-notice")
                return
            if st.button(
                "Complaints & Concerns",
                key=f"{menu_key}_mobile_complaints",
            ):
                set_public_document_route("/public/complaints-and-concerns")
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
            render_public_landing_link(
                "Back to hub selection",
                key=f"{menu_key}_family_back_public_link",
            )
            render_route_link(
                "How it works",
                get_how_it_works_route(app_variant),
                key=f"{menu_key}_family_how_link",
            )
            render_route_link("Family Q&A", "/family/qa", key=f"{menu_key}_family_qa_link")
            render_route_link(
                "Life File Guide",
                LIFE_FILE_GUIDE_ROUTE,
                key=f"{menu_key}_family_life_file_guide_link",
            )
            render_route_link(
                "Family Terms of Use",
                "/family/terms-use",
                key=f"{menu_key}_family_terms_link",
            )
            render_route_link(
                (
                    "Contact the Family Organiser"
                    if is_current_at_home_lifecycle_stage(st.session_state.get("access_token"))
                    else "Contact the care home"
                ),
                "/family/contact",
                key=f"{menu_key}_family_contact_link",
            )
            render_route_link(
                "Family Hub login",
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
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant == VARIANT_FAMILY and not is_family_authenticated():
        show_menu = False
    if runtime_variant == VARIANT_MOBILE and not is_care_authenticated():
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
  .vm-care-home-banner {{
    margin: -2px 0 10px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(31,31,31,0.2);
    background: rgba(153, 255, 255, 0.2);
    font-size: 0.95rem;
    line-height: 1.35;
  }}
  .vm-care-home-custom-banner {{
    margin: 0 0 12px;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid rgba(31,31,31,0.18);
    background: rgba(255, 255, 255, 0.9);
  }}
  .vm-care-home-custom-banner-title {{
    font-size: 1rem;
    font-weight: 700;
    margin: 0 0 4px;
  }}
  .vm-care-home-custom-banner-text {{
    font-size: 0.92rem;
    line-height: 1.4;
    margin: 0 0 8px;
    color: rgba(31,31,31,0.86);
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
    .vm-care-home-banner {{
      margin: -1px 0 8px;
      padding: 7px 9px;
      font-size: 0.9rem;
    }}
    .vm-care-home-custom-banner {{
      margin: 0 0 10px;
      padding: 9px;
    }}
    .vm-care-home-custom-banner-title {{
      font-size: 0.95rem;
    }}
    .vm-care-home-custom-banner-text {{
      font-size: 0.88rem;
      margin: 0 0 7px;
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
    render_active_care_home_name_caption()


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
        '<div class="front-page-info-box">familyupdates.care - for non-urgent updates, specific messages, practical requests, and noticeboard notes.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">One current item is kept in each channel, with no threads.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">Not a live service. Urgent and private matters stay outside the app.</div>',
        unsafe_allow_html=True,
    )


def render_how_it_works_general() -> None:
    st.markdown(
        "Each channel keeps only the latest message, with no threads.  \n"
        "Each new message replaces the previous message in that channel.\n\n"
        "Messages are not private within the care home.  \n"
        "Care staff and office staff may read messages where required.  \n"
        "Security is in place to prevent access by members of the public."
    )


def render_how_it_works_button(button_key: str) -> None:
    if st.button("How it works", key=button_key):
        current_variant = resolve_runtime_variant(route_hint=get_route())
        set_route(get_how_it_works_route(current_variant))


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
                        set_route(PUBLIC_HOME_ROUTE)
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


def submit_public_feedback(
    *,
    audience: str,
    ease_score: int,
    calm_score: int,
    recommend_score: int,
    comment: str,
) -> tuple[bool, str]:
    valid_audiences = {"family", "resident_supported", "carer"}
    if audience not in valid_audiences:
        return False, "Please choose who is giving feedback."
    for score in (ease_score, calm_score, recommend_score):
        if int(score) < 1 or int(score) > 5:
            return False, "Please complete all three questions."
    comment_value = str(comment or "").strip()
    if len(comment_value) > 500:
        return False, "Optional comment must be 500 characters or fewer."
    supabase, error = get_supabase_client()
    if error:
        return False, error
    payload = {
        "audience": audience,
        "q1_score": int(ease_score),
        "q2_score": int(calm_score),
        "q3_score": int(recommend_score),
        "comment": comment_value or None,
    }
    try:
        supabase.table("feedback_submissions").insert(payload).execute()
    except Exception as exc:
        return False, str(exc)
    return True, "Thank you. Your anonymous feedback has been saved."


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
            /* Remove extra top padding that can create a "second bar" look */
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
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 0;
                color: #1f2937;
            }
            .public-header-title span {
                color: #6b7280;
                font-weight: 700;
            }
            @media (max-width: 768px) {
                .public-header-title {
                    font-size: 1.08rem;
                    white-space: nowrap;
                }
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
            .public-app-buttons {
                margin-top: 6px;
            }
            .pr-app-btn {
                display: block;
                width: 100%;
                text-align: center;
                text-decoration: none;
                color: #1F2937;
                font-weight: 700;
                border-radius: 12px;
                padding: 14px 12px;
                border: 2px solid rgba(31, 41, 55, 0.14);
                transition: background-color 0.2s ease, transform 0.08s ease;
                box-sizing: border-box;
                margin-bottom: 8px;
            }
            .pr-app-btn:hover {
                transform: translateY(-1px);
            }
            .pr-app-btn:active {
                transform: translateY(0);
            }
            .pr-app-btn.family {
                background: #CFE3D4;
            }
            .pr-app-btn.family:hover {
                background: #B8D2C3;
            }
            .pr-app-btn.mobile {
                background: #F6D6DF;
            }
            .pr-app-btn.mobile:hover {
                background: #EABFCC;
            }
            .pr-app-btn.office {
                background: #CDEEEE;
            }
            .pr-app-btn.office:hover {
                background: #B3DEDE;
            }
            .pr-app-btn.disabled {
                opacity: 0.65;
                cursor: not-allowed;
                pointer-events: none;
            }
            .pr-recording-card {
                border-radius: 12px;
                border: 2px solid #D8E6EC;
                background: #FBFDFF;
                padding: 12px;
                margin-top: 8px;
            }
            .pr-recording-card h3 {
                margin: 0 0 6px;
                font-size: 1rem;
            }
            .pr-recording-card p {
                margin: 0 0 10px;
                color: #4B5563;
                font-size: 0.96rem;
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
        header_html = (
            '<div class="public-header">'
            '<div class="public-header-title">familyupdates<span>.care</span></div>'
            "</div>"
        )
        st.markdown(header_html, unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## Familiar voices")
        st.markdown(
            "A structured, non-urgent family communication system around care."
        )
        st.markdown(
            """
familyupdates.care separates emergency communication from everyday communication.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent communication only.
"""
        )
        st.markdown(
            "The app provides one current update to family, one current specific organiser message, "
            "one current practical request, and noticeboard-style information. The Family Organiser has full access to the family tools; "
            "Family Members and carers can use their own enabled channels directly. One current item replaces the last, "
            "with no threads, no message build-up, and no pressure to reply instantly."
        )
        st.markdown(
            "Families use the app for everyday communication. Carers may use the app directly where enabled, or text the Family Organiser. "
            "The Family Organiser may choose to tell the family when and how frequently they will check messages."
        )
        st.markdown(
            "Emergencies follow the family's agreed emergency protocol, usually phoning a named person on their mobile. "
            "The exact protocol and how those contact details are shared are decided by the family outside the app. Otherwise, all messages are treated as non-urgent."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## A simple way to explore the idea")
        st.markdown(
            "familyupdates.care can be introduced through a simple one-to-one walkthrough."
        )
        st.markdown(
            "The session uses a simple example family update, practical request, and noticeboard note, introducing the idea in a natural way."
        )
        st.markdown(
            "There is no obligation to adopt anything, simply an opportunity to see how this might help communication for you."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## Feedback welcome")
        st.markdown(
            "We welcome feedback from Family Organisers, Family Members, carers, and helpers to help improve this service."
        )
        st.caption("Anonymous only. Please do not include names, emails, phone numbers, or medical details.")
        with st.form("public_feedback_form", clear_on_submit=True):
            audience_choice = st.selectbox(
                "Who are you?",
                options=[
                    ("family_organiser", "Family Organiser"),
                    ("family_member", "Family Member"),
                    ("carer", "Carer"),
                    ("helper", "Helper"),
                ],
                format_func=lambda item: item[1],
                key="public_feedback_audience",
            )
            ease_score = st.radio(
                "1. How easy was familyupdates.care to use today?",
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                key="public_feedback_q1",
            )
            calm_score = st.radio(
                "2. Did it help you feel more connected in a calm way?",
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                key="public_feedback_q2",
            )
            recommend_score = st.radio(
                "3. Would you recommend this for family coordination?",
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                key="public_feedback_q3",
            )
            free_text = st.text_area(
                "Optional suggestion",
                max_chars=500,
                key="public_feedback_comment",
                placeholder="Share an idea (without names, emails, phone numbers, or medical details).",
            )
            feedback_submit = st.form_submit_button("Send anonymous feedback")
        if feedback_submit:
            saved, message = submit_public_feedback(
                audience=audience_choice[0],
                ease_score=int(ease_score),
                calm_score=int(calm_score),
                recommend_score=int(recommend_score),
                comment=free_text,
            )
            if saved:
                st.success(message)
            else:
                st.error(message)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section public-app-buttons">', unsafe_allow_html=True)
        st.markdown("<h2>Choose your app</h2>", unsafe_allow_html=True)
        app_cols = st.columns(3, gap="small")
        app_entries = [
            (
                VARIANT_OFFICE,
                "Family Office",
                "For the Family Organiser to coordinate updates, requests, family access, and boundaries.",
            ),
            (
                VARIANT_FAMILY,
                "Family Hub",
                "For non-urgent family updates, practical requests, structured replies, and noticeboard notes.",
            ),
            (
                VARIANT_MOBILE,
                "Mobile",
                "For a carer, helper, supported person, or trusted family member using reduced tools.",
            ),
        ]
        for idx, (variant, label, summary) in enumerate(app_entries):
            target_url = get_public_app_url(variant)
            with app_cols[idx]:
                if target_url:
                    if hasattr(st, "link_button"):
                        st.link_button(f"Open {label} app", target_url, use_container_width=True)
                    else:
                        st.markdown(
                            f'<a href="{target_url}" target="_self">Open {label} app</a>',
                            unsafe_allow_html=True,
                        )
                st.markdown('<div class="pr-recording-card">', unsafe_allow_html=True)
                st.markdown(f"<h3>{label}</h3>", unsafe_allow_html=True)
                st.markdown(f"<p>{summary}</p>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>How it works</h2>", unsafe_allow_html=True)
        st.markdown(
            """
familyupdates.care helps structure communication when someone needs support and one family member or trusted friend has become the organiser.

It is for moments when repeated updates, questions, and practical coordination have started to overload one person.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent coordination only.
"""
        )
        st.markdown("### Communication participants")
        st.markdown("- A person or couple being supported")
        st.markdown("- Registered Family Members")
        st.markdown("- A Family Organiser who introduces the app and keeps the current information clear")
        st.markdown("- A carer, helper, supported person, or trusted family member using Mobile where relevant")
        st.markdown(
            "Each channel keeps only the latest message. A new message replaces the previous message in that channel."
        )
        render_route_link(
            "Read how familyupdates.care works",
            "/public/how-it-works",
            key="public_home_how_it_works_link",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-grid public-grid-3">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-card">
              <h3>Stop repeating updates</h3>
              <div>Send one calm update to registered Family Members. There are no replies in this update channel, and the next update replaces the previous one.</div>
            </div>
            <div class="public-card">
              <h3>Not another chat</h3>
              <div>The Family Organiser and each Family Member can keep one current specific message, without live chat, scrolling, or message threads.</div>
            </div>
            <div class="public-card pink">
              <h3>Add practical requests</h3>
              <div>Use structured questions for non-urgent practical coordination, such as visits, appointments, collecting items, or household tasks.</div>
            </div>
            <div class="public-card">
              <h3>Use Mobile from the start</h3>
              <div>Mobile is for an additional person who helps provide care support.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>Message behaviour</h2>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-steps">
              <div class="public-step">No message history</div>
              <div class="public-step">No archive</div>
              <div class="public-step">No scrolling threads</div>
              <div class="public-step">No family communication archive to maintain</div>
              <div class="public-step">This is not live messaging</div>
              <div class="public-step">Urgent and private matters stay outside the app</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>Boundaries and privacy</h2>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-roles">
              <div class="public-card">
                <h3>Family privacy boundary</h3>
                <div>Specific organiser messages are separate. Practical requests and noticeboard notes are visible to the family group.</div>
              </div>
              <div class="public-card pink">
                <h3>Family contact</h3>
                <div>Family Members still phone the person being supported in the normal way. The app is for organising family communication, not replacing personal contact.</div>
              </div>
              <div class="public-card">
                <h3>No live pressure</h3>
                <div>No notifications, no delivery/read receipts, and no typing indicators.</div>
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
              <h3>Roles and important boundaries</h3>
              <div><strong>Family Members:</strong> Family Members receive updates, respond to practical requests, and can pin one current noticeboard note.</div>
              <div><strong>Family Organiser:</strong> the organiser introduces the app and keeps a small number of non-urgent family communication channels current.</div>
              <div><strong>Person being supported:</strong> family contact by phone remains outside the app.</div>
              <div style="margin-top:8px;">This service is for non-urgent communication only. It is not for medical updates, safeguarding communication, financial decisions, legal matters, or emergencies. Use normal direct contact routes for those matters.</div>
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
    if get_app_variant() == VARIANT_PUBLIC:
        st.markdown("Communication participants")
        st.markdown(
            """
familyupdates.care helps structure communication when someone needs support and one family member or trusted friend has become the organiser.

It is used when ordinary direct family communication is no longer enough because repeated updates, questions, or practical coordination are creating communication overload.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent coordination only.
"""
        )
        st.markdown(
            "Family Organiser channels keep the latest shared update, latest specific organiser message, and latest practical request. "
            "The Family Organiser has full access to the family tools; Family Members and carers can use their own enabled channels directly. "
            "Each Family Member can keep one current noticeboard note. "
            "A new message replaces only the previous message in that channel. "
            "The general update is not a chat thread and does not take direct replies."
        )
    st.markdown("### Service overview")
    current_variant = resolve_runtime_variant(route_hint=get_route())
    if current_variant == VARIANT_MOBILE:
        render_route_link(
            "Back to Mobile",
            get_home_route(VARIANT_MOBILE),
            key="service_overview_back_mobile",
        )
    elif current_variant == VARIANT_OFFICE:
        render_route_link(
            "Back to Family Office",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="service_overview_back_office",
        )
    elif current_variant == VARIANT_FAMILY:
        family_back_route = (
            get_home_route(VARIANT_FAMILY)
            if bool(st.session_state.get("auth_uid"))
            else get_login_route(VARIANT_FAMILY)
        )
        render_route_link(
            "Back to Family Hub",
            family_back_route,
            key="service_overview_back_family",
        )
    else:
        render_public_landing_link(
            "Back to hub selection",
            key=f"service_overview_back_to_public_docs_{current_variant}",
        )
    st.markdown(
        "familyupdates.care  \n"
        "Public guides.\n\n"
        "Choose Family to continue.  \n"
        "This is not a live service."
    )

    button_cols = st.columns([1, 1, 1], gap="small")
    with button_cols[1]:
        if st.button("Open Family Hub", key="service_overview_open_family", use_container_width=True):
            set_route(FAMILY_LOGIN_ROUTE)
            st.stop()

    # Homepage buttons are handled above.

    st.markdown('<div style="margin-top:-8px;"></div>', unsafe_allow_html=True)


def get_route() -> str:
    if hasattr(st, "query_params"):
        route = st.query_params.get("route", "")
    else:
        route = st.experimental_get_query_params().get("route", [""])[0]
    if isinstance(route, list):
        route = route[0] if route else ""
    return normalize_route(route) or "/"


def _map_legacy_streamlit_page_to_route(legacy_page: str) -> str:
    raw_value = str(legacy_page or "").strip()
    if not raw_value:
        return ""
    raw_value = unquote(raw_value).strip()
    if "/" in raw_value:
        raw_value = raw_value.split("/")[-1].strip()
    if raw_value.lower().endswith(".py"):
        raw_value = raw_value[:-3]
    slug = re.sub(r"[^a-z0-9]+", "_", raw_value.lower()).strip("_")
    if slug.startswith("pages_"):
        slug = slug[len("pages_") :]
    if slug.startswith("page_"):
        slug = slug[len("page_") :]
    page_to_route = {
        "family": "/family/login",
        "care_hub_mobile": "/care-hub/mobile/login",
        "care_hub_office": "/care-hub/login",
        "pricing": "/pr-home",
        "privacy_notice": "/public/privacy-notice",
        "family_terms": "/public/family-terms-of-use",
        "safeguarding_and_consent": "/public/safeguarding-and-consent",
        "complaints": "/public/complaints-and-concerns",
    }
    mapped = page_to_route.get(slug, "")
    if not mapped:
        if "family" in slug:
            mapped = "/family/login"
        elif "mobile" in slug:
            mapped = "/care-hub/mobile/login"
        elif "office" in slug or "care_hub" in slug:
            mapped = "/care-hub/login"
        elif "privacy" in slug:
            mapped = "/public/privacy-notice"
        elif "safeguard" in slug or "consent" in slug:
            mapped = "/public/safeguarding-and-consent"
        elif "complaint" in slug:
            mapped = "/public/complaints-and-concerns"
        elif "term" in slug:
            mapped = "/public/family-terms-of-use"
        elif "price" in slug:
            mapped = "/pr-home"
    return normalize_route(mapped)


def _route_from_request_path(raw_path: str) -> str:
    path = normalize_route(raw_path) or "/"
    path_lower = path.lower()
    if path_lower.startswith("/family"):
        return FAMILY_LOGIN_ROUTE
    if path_lower.startswith("/care_hub_-_mobile") or path_lower.startswith("/care_hub_mobile"):
        return MOBILE_LOGIN_ROUTE
    if path_lower.startswith("/care_hub_-_office") or path_lower.startswith("/care_hub_office"):
        return OFFICE_LOGIN_ROUTE
    if path_lower.startswith("/mobile") or path_lower.startswith("/care-hub/mobile"):
        return MOBILE_LOGIN_ROUTE
    if path_lower.startswith("/office") or path_lower.startswith("/care-hub"):
        return OFFICE_LOGIN_ROUTE
    first = path_lower.lstrip("/").split("/", 1)[0].strip()
    mapped = _map_legacy_streamlit_page_to_route(first)
    if mapped:
        return mapped
    if path_lower.startswith("/public"):
        return "/pr-home"
    return PUBLIC_HOME_ROUTE


def _get_canonical_hosts() -> set[str]:
    canonical_hosts = {CANONICAL_PUBLIC_HOST, *CANONICAL_PUBLIC_HOST_ALIASES}
    return {value.strip(".").lower() for value in canonical_hosts if value}


def _build_seo_metadata(route: str) -> dict[str, str]:
    normalized_route = normalize_route(route) or PUBLIC_HOME_ROUTE
    route_titles: dict[str, str] = {
        "/pr-home": "familyupdates.care - Essential family coordination, separate from chat",
        "/public/how-it-works": "How familyupdates.care works",
        "/family/login": "Family Hub | familyupdates.care",
        "/care-hub/mobile/login": "Mobile | familyupdates.care",
        "/care-hub/login": "Family Office | familyupdates.care",
        "/public/privacy-notice": "Privacy Notice | familyupdates.care",
        "/public/family-terms-of-use": "Family Terms of Use | familyupdates.care",
        "/public/complaints-and-concerns": "Complaints and Concerns | familyupdates.care",
        "/public/safeguarding-and-consent": "Safeguarding and Consent | familyupdates.care",
        "/public/faq": "Family Q&A | familyupdates.care",
        "/public/qa": "Family Q&A | familyupdates.care",
        LIFE_FILE_GUIDE_ROUTE: "Life File Guide | familyupdates.care",
    }
    route_descriptions: dict[str, str] = {
        "/pr-home": "familyupdates.care helps a Family Organiser coordinate non-urgent family support without chat pressure, threads, or archives.",
        "/public/how-it-works": "How familyupdates.care works across situations, roles, updates, practical requests, and noticeboard notes.",
        "/family/login": "Family Hub access for current organiser updates, practical requests, and noticeboard notes.",
        "/care-hub/mobile/login": "Mobile access for a carer, helper, supported person, or trusted family member using reduced tools.",
        "/care-hub/login": "Family Office access for the organiser to keep one current update, family registration, practical requests, and noticeboard oversight.",
        "/public/privacy-notice": "Privacy notice for familyupdates.care, including controller/processor roles and retention boundaries.",
        "/public/family-terms-of-use": "Family Terms of Use for familyupdates.care and non-urgent message boundaries.",
        "/public/complaints-and-concerns": "How to raise platform concerns and keep family, care, safeguarding, and support boundaries clear.",
        "/public/safeguarding-and-consent": "Safeguarding and consent boundaries for familyupdates.care.",
        "/public/faq": "Frequently asked questions for Family Office, Family Hub, and Mobile.",
        "/public/qa": "Frequently asked questions for Family Office, Family Hub, and Mobile.",
        LIFE_FILE_GUIDE_ROUTE: "Guidance for external notebooks, folders, and Life Management Files.",
    }
    if normalized_route == "/public/service-overview":
        normalized_route = "/pr-home"
    title = route_titles.get(normalized_route, "familyupdates.care")
    description = route_descriptions.get(
        normalized_route,
        "familyupdates.care keeps essential family coordination separate from chat.",
    )
    return {"route": normalized_route, "title": title, "description": description}


def apply_seo_head_tags(route: str, app_variant: str) -> None:
    seo = _build_seo_metadata(route)
    canonical_route = seo["route"]
    title = seo["title"]
    description = seo["description"]
    host = _get_request_host()
    canonical_hosts = _get_canonical_hosts()
    is_canonical_host = bool(host) and host in canonical_hosts
    is_public_route = canonical_route.startswith("/public/") or canonical_route in {
        "/pr-home",
        "/family/login",
        "/service-overview",
    }
    should_index = is_canonical_host and is_public_route and app_variant in {VARIANT_PUBLIC, VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}
    robots = (
        "index,follow,max-image-preview:large,max-snippet:-1"
        if should_index
        else "noindex,nofollow,noarchive"
    )
    if canonical_route == PUBLIC_HOME_ROUTE:
        canonical_url = f"https://{CANONICAL_PUBLIC_HOST}"
    else:
        canonical_url = f"https://{CANONICAL_PUBLIC_HOST}/?{urlencode({'route': canonical_route})}"
    seo_payload = {
        "title": title,
        "description": description,
        "canonical_url": canonical_url,
        "robots": robots,
    }
    seo_payload_js = json.dumps(seo_payload)
    components.html(
        f"""
<script>
(function () {{
  try {{
    var seo = {seo_payload_js};
    var topWin = window.parent && window.parent.document ? window.parent : window;
    var doc = topWin.document || document;
    if (!doc || !doc.head) return;
    doc.title = seo.title;
    function upsertMeta(attrName, attrValue, content) {{
      if (!attrValue) return;
      var selector = 'meta[' + attrName + '=\"' + attrValue + '\"]';
      var node = doc.head.querySelector(selector);
      if (!node) {{
        node = doc.createElement('meta');
        node.setAttribute(attrName, attrValue);
        doc.head.appendChild(node);
      }}
      node.setAttribute('content', content || '');
    }}
    function upsertLink(relValue, hrefValue) {{
      var selector = 'link[rel=\"' + relValue + '\"]';
      var node = doc.head.querySelector(selector);
      if (!node) {{
        node = doc.createElement('link');
        node.setAttribute('rel', relValue);
        doc.head.appendChild(node);
      }}
      node.setAttribute('href', hrefValue || '');
    }}
    upsertMeta('name', 'description', seo.description);
    upsertMeta('name', 'robots', seo.robots);
    upsertMeta('property', 'og:site_name', 'familyupdates.care');
    upsertMeta('property', 'og:type', 'website');
    upsertMeta('property', 'og:title', seo.title);
    upsertMeta('property', 'og:description', seo.description);
    upsertMeta('property', 'og:url', seo.canonical_url);
    upsertMeta('name', 'twitter:card', 'summary');
    upsertMeta('name', 'twitter:title', seo.title);
    upsertMeta('name', 'twitter:description', seo.description);
    upsertLink('canonical', seo.canonical_url);
  }} catch (e) {{
    // SEO metadata updates are best-effort only.
  }}
}})();
</script>
""",
        height=0,
        width=0,
    )


def redirect_non_canonical_host_once() -> None:
    if not NON_CANONICAL_HOST_REDIRECT_ENABLED:
        return
    if not CANONICAL_PUBLIC_HOST:
        return
    host = _get_request_host()
    if not host:
        return
    if host in {"localhost", "127.0.0.1", "::1"}:
        return
    canonical_hosts = _get_canonical_hosts()
    if host in canonical_hosts:
        return
    if not any(host.endswith(suffix) for suffix in NON_CANONICAL_REDIRECT_HOST_SUFFIXES):
        return
    request_path = _get_request_path()
    query_map: dict[str, str] = {}
    try:
        context = getattr(st, "context", None)
        current_url = str(getattr(context, "url", "") or "").strip() if context is not None else ""
        parsed_url = urlparse(current_url) if current_url else None
        if parsed_url:
            for key, raw_value in parse_qsl(parsed_url.query, keep_blank_values=True):
                key_text = str(key or "").strip()
                if not key_text:
                    continue
                query_map[key_text] = str(raw_value or "")
    except Exception:
        query_map = {}
    route = normalize_route(query_map.get("route", "")) or ""
    if not route:
        route = _map_legacy_streamlit_page_to_route(query_map.get("page", ""))
    if not route:
        route = _route_from_request_path(request_path)
    has_auth_callback_params = any(
        bool(str(query_map.get(key, "") or "").strip())
        for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token")
    )
    # For legacy onrender links surfaced by search engines, land on the public home.
    # Keep auth callback routes intact so magic-link sign-in can complete.
    if host.endswith(".onrender.com") and not has_auth_callback_params:
        route = PUBLIC_HOME_ROUTE
    redirect_query_map: dict[str, str] = {"route": route}
    for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token"):
        value = str(query_map.get(key, "") or "").strip()
        if value:
            redirect_query_map[key] = value
    target_url = f"https://{CANONICAL_PUBLIC_HOST}/?{urlencode(redirect_query_map)}"
    target_url_js = json.dumps(target_url)
    components.html(
        f"""
<script>
(function () {{
  var target = {target_url_js};
  var appendAuthFromHash = function (targetUrl, sourceUrl) {{
    try {{
      var src = new URL(sourceUrl);
      var dst = new URL(targetUrl);
      var hash = (src.hash || "").replace(/^#/, "");
      if (!hash) return targetUrl;
      var hashParams = new URLSearchParams(hash);
      var allowed = ["access_token", "refresh_token", "token_hash", "token", "type", "code"];
      for (var i = 0; i < allowed.length; i++) {{
        var key = allowed[i];
        var value = (hashParams.get(key) || "").trim();
        if (value && !dst.searchParams.get(key)) {{
          dst.searchParams.set(key, value);
        }}
      }}
      return dst.toString();
    }} catch (e) {{
      return targetUrl;
    }}
  }};
  var currentHref = window.location.href;
  try {{
    if (window.parent && window.parent !== window) {{
      currentHref = window.parent.location.href;
    }}
  }} catch (e) {{}}
  target = appendAuthFromHash(target, currentHref);
  try {{
    if (window.parent && window.parent !== window) {{
      window.parent.location.replace(target);
      return;
    }}
  }} catch (e) {{}}
  window.location.replace(target);
}})();
</script>
""",
        height=0,
        width=0,
    )
    st.stop()


def clear_legacy_streamlit_page_param_once() -> None:
    """Strip stale Streamlit multipage query params that can trigger page-not-found notices."""
    if not hasattr(st, "query_params"):
        return
    try:
        legacy_page = str(st.query_params.get("page", "") or "").strip()
    except Exception:
        return
    if not legacy_page:
        st.session_state.pop("_legacy_page_param_cleared", None)
        return
    if bool(st.session_state.get("_legacy_page_param_cleared", False)):
        return
    mapped_route = _map_legacy_streamlit_page_to_route(legacy_page)
    if mapped_route:
        try:
            current_route = normalize_route(st.query_params.get("route", "")) or ""
        except Exception:
            current_route = ""
        if not current_route or current_route == "/":
            try:
                st.query_params["route"] = mapped_route
            except Exception:
                pass
    try:
        del st.query_params["page"]
    except Exception:
        pass
    st.session_state["_legacy_page_param_cleared"] = True
    st.rerun()


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
PUBLIC_HOME_ROUTE = "/pr-home"
LIFE_FILE_GUIDE_ROUTE = "/life-file-guide"
REMOVED_VIDEO_ROUTES = {
    "/public/help-videos",
    "/public/walkthrough-family",
    "/public/walkthrough-family-flow",
    "/public/walkthrough-mobile",
    "/public/walkthrough-mobile-flow",
    "/public/walkthrough-office",
    "/public/walkthrough-office-flow",
    "/public/walkthrough-overview",
}
FAMILY_PUBLIC_ROUTES = {
    "/family/login",
}
OFFICE_PUBLIC_ROUTES = {
    "/care-hub/login",
    "/care-hub-office/how-it-works",
    "/how-it-works/office",
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
    LIFE_FILE_GUIDE_ROUTE,
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
    LIFE_FILE_GUIDE_ROUTE,
                                }

VARIANT_CONFIG = {
    VARIANT_FAMILY: {
        "label": "Family Hub",
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
            "/public/infographic",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            LIFE_FILE_GUIDE_ROUTE,
                                                                                                            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_MOBILE: {
        "label": "Mobile",
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
            "/public/infographic",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            LIFE_FILE_GUIDE_ROUTE,
                                                                                                            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_OFFICE: {
        "label": "Family Office",
        "default_route": OFFICE_LOGIN_ROUTE,
        "how_it_works_route": "/care-hub-office/how-it-works",
        "allowed_routes": {
            OFFICE_LOGIN_ROUTE,
            OFFICE_HOME_ROUTE,
            "/care-hub/setup-family-system",
            "/care-hub/register-family",
            "/care-hub/operational-variables",
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
            "/public/infographic",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            LIFE_FILE_GUIDE_ROUTE,
                                                                                                            "/pr-home",
            "/service-overview",
        },
    },
    VARIANT_PUBLIC: {
        "label": "Public",
        "default_route": PUBLIC_HOME_ROUTE,
        "how_it_works_route": "/public/how-it-works",
        "allowed_routes": {
            "/pr-home",
            PUBLIC_HOME_ROUTE,
            "/public-docs",
            "/public/service-overview",
            "/public/how-it-works",
            "/public/infographic",
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            LIFE_FILE_GUIDE_ROUTE,
                                                                                                        },
    },
}


def get_app_variant() -> str:
    return resolve_app_variant()


def get_raw_app_variant() -> str:
    return __import__("os").getenv("APP_VARIANT", "").strip()


def _get_request_host() -> str:
    """
    Best-effort host extraction from Streamlit request context.
    Returns lowercase host without port, or empty string when unavailable.
    """
    try:
        context = getattr(st, "context", None)
        if context is None:
            return ""
        candidates = []
        headers = getattr(context, "headers", None)
        if headers:
            for key in ("x-forwarded-host", "host"):
                value = ""
                if hasattr(headers, "get"):
                    value = str(headers.get(key, "") or "").strip()
                    if not value:
                        value = str(headers.get(key.title(), "") or "").strip()
                if value:
                    candidates.append(value)
        url_value = str(getattr(context, "url", "") or "").strip()
        if url_value:
            parsed = urlparse(url_value)
            if parsed.hostname:
                candidates.append(str(parsed.hostname).strip())
        for raw_host in candidates:
            host = raw_host.split(",")[0].strip().lower()
            if host:
                if ":" in host:
                    host = host.split(":", 1)[0].strip()
                if host:
                    return host
    except Exception:
        return ""
    return ""


def _get_request_path() -> str:
    """
    Best-effort request path extraction from Streamlit request context.
    Returns normalized path (leading slash), defaulting to "/" when unavailable.
    """
    try:
        context = getattr(st, "context", None)
        if context is None:
            return "/"
        url_value = str(getattr(context, "url", "") or "").strip()
        if not url_value:
            return "/"
        parsed = urlparse(url_value)
        path = normalize_route(parsed.path or "/") or "/"
        return path
    except Exception:
        return "/"


def _recover_auth_callback_params_from_path() -> dict[str, str]:
    """
    Recover auth callback params when they are mistakenly appended to path using '&'
    instead of query params, e.g. /mobile/login&token_hash=...&type=magiclink.
    """
    recovered: dict[str, str] = {}
    try:
        context = getattr(st, "context", None)
        if context is None:
            return recovered
        url_value = str(getattr(context, "url", "") or "").strip()
        if not url_value:
            return recovered
        parsed = urlparse(url_value)
        raw_path = str(parsed.path or "")
        if "&" not in raw_path:
            return recovered
        _, suffix = raw_path.split("&", 1)
        if not suffix or "=" not in suffix:
            return recovered
        allowed_keys = {"code", "token_hash", "token", "type", "access_token", "refresh_token"}
        for key, value in parse_qsl(suffix, keep_blank_values=True):
            key = str(key or "").strip()
            value = str(value or "").strip()
            if key in allowed_keys and value:
                recovered[key] = value
    except Exception:
        return {}
    return recovered


def _recover_auth_callback_params_from_route_path(raw_path: str) -> dict[str, str]:
    recovered: dict[str, str] = {}
    path_value = str(raw_path or "").strip()
    if "&" not in path_value:
        return recovered
    try:
        _, suffix = path_value.split("&", 1)
    except ValueError:
        return recovered
    if not suffix or "=" not in suffix:
        return recovered
    allowed_keys = {"code", "token_hash", "token", "type", "access_token", "refresh_token"}
    for key, value in parse_qsl(suffix, keep_blank_values=True):
        key = str(key or "").strip()
        value = str(value or "").strip()
        if key in allowed_keys and value:
            recovered[key] = value
    return recovered


def _resolve_variant_from_request_path() -> str | None:
    """
    Resolve variant from URL path prefix.
    / -> public, /family -> family, /mobile -> mobile, /office -> office
    """
    path = _get_request_path()
    if path == "/":
        return VARIANT_PUBLIC
    first = path.lstrip("/").split("/", 1)[0].strip().lower()
    if first == "family":
        return VARIANT_FAMILY
    if first == "mobile":
        return VARIANT_MOBILE
    if first == "office":
        return VARIANT_OFFICE
    if first == "public":
        return VARIANT_PUBLIC
    return None


def _resolve_variant_from_route(route: str) -> str | None:
    """
    Resolve variant from internal app route (query-param driven).
    This is the most reliable signal in current architecture.
    """
    normalized = normalize_route(route) or "/"
    if normalized == LIFE_FILE_GUIDE_ROUTE:
        active_role = str(st.session_state.get("active_role") or "").strip().lower()
        if active_role == "family":
            return VARIANT_FAMILY
        if active_role == "care_hub":
            return VARIANT_OFFICE if bool(st.session_state.get("office_login_explicit")) else VARIANT_MOBILE
        configured_variant = get_app_variant()
        if configured_variant in {VARIANT_FAMILY, VARIANT_MOBILE, VARIANT_OFFICE}:
            return configured_variant
        return VARIANT_PUBLIC
    if normalized.startswith("/family") or normalized == "/how-it-works/family":
        return VARIANT_FAMILY
    if (
        normalized.startswith("/care-hub/mobile")
        or normalized.startswith("/care-hub-mobile")
        or normalized.startswith("/mobile")
        or normalized == "/how-it-works/mobile"
    ):
        return VARIANT_MOBILE
    if (
        normalized.startswith("/care-hub")
        or normalized.startswith("/care-hub-office")
        or normalized.startswith("/office")
        or normalized in {"/billing", "/contracts", "/docs"}
        or normalized == "/how-it-works/office"
    ):
        return VARIANT_OFFICE
    if normalized.startswith("/public") or normalized in {"/", "/service-overview", "/pr-home"}:
        return VARIANT_PUBLIC
    return None


def _parse_app_variant_by_host(raw_mapping: str) -> dict[str, str]:
    """
    Parse APP_VARIANT_BY_HOST entries formatted as:
    host1=variant1,host2=variant2
    Invalid entries are ignored to fail safely.
    """
    mapping: dict[str, str] = {}
    raw_value = str(raw_mapping or "").strip()
    if not raw_value:
        return mapping
    for part in raw_value.split(","):
        entry = part.strip()
        if not entry or "=" not in entry:
            continue
        host_raw, variant_raw = entry.split("=", 1)
        host = host_raw.strip().lower()
        variant = variant_raw.strip().lower()
        if not host or not variant:
            continue
        if ":" in host:
            host = host.split(":", 1)[0].strip()
        if variant in VARIANT_CONFIG:
            mapping[host] = variant
    return mapping


def resolve_runtime_variant(route_hint: str | None = None) -> str:
    """
    Resolve app variant by internal route first, then request path,
    then APP_VARIANT fallback.
    """
    if route_hint:
        route_variant = _resolve_variant_from_route(route_hint)
        if route_variant:
            return route_variant
    path_variant = _resolve_variant_from_request_path()
    if path_variant:
        return path_variant
    return get_app_variant()


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
    if (
        not is_authed
        and AUTH_COOKIE_PERSISTENCE_ENABLED
        and AUTH_COOKIE_SIGNING_KEY
    ):
        # When a rerun reconnects into a fresh Streamlit runtime session,
        # recover auth from the signed refresh-token cookie before redirecting.
        restore_auth_session_from_cookie()
        is_authed = bool(st.session_state.get("auth_uid"))
        is_variant_authed = (
            is_family_authenticated()
            if app_variant == VARIANT_FAMILY
            else is_care_authenticated()
        )
    if (
        not is_authed
        and st.session_state.get("access_token")
        and st.session_state.get("refresh_token")
    ):
        # Reruns can occasionally lose hydrated auth_uid/role even when tokens are valid.
        # Rehydrate once before routing to login to avoid false logout loops.
        get_mapping_status()
        is_authed = bool(st.session_state.get("auth_uid"))
        is_variant_authed = (
            is_family_authenticated()
            if app_variant == VARIANT_FAMILY
            else is_care_authenticated()
        )
    if not is_authed and st.session_state.get("refresh_token"):
        # Token hydration can occasionally fail on rerun even with a valid refresh token.
        # Try a direct refresh before forcing a login route.
        refreshed = try_refresh_session_from_state()
        if refreshed:
            get_mapping_status()
            is_authed = bool(st.session_state.get("auth_uid"))
            is_variant_authed = (
                is_family_authenticated()
                if app_variant == VARIANT_FAMILY
                else is_care_authenticated()
            )
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
    if (
        app_variant == VARIANT_MOBILE
        and is_authed
        and current_route == MOBILE_LOGIN_ROUTE
        and is_mobile_pin_verified_for_session()
    ):
        set_route(home_route)
        st.stop()
        return True
    if (
        app_variant == VARIANT_OFFICE
        and is_variant_authed
        and is_login_route_for_variant(app_variant, current_route)
        and not bool(st.session_state.get("office_login_explicit"))
    ):
        # Office should always present credential login before MFA/home routing.
        return False
    if is_variant_authed and is_login_route_for_variant(app_variant, current_route):
        if app_variant == VARIANT_MOBILE and current_route == OFFICE_LOGIN_ROUTE:
            # Mobile deployments can expose Office login route, but it must not
            # auto-redirect into Mobile home/PIN flow.
            return False
        if app_variant == VARIANT_OFFICE and is_office_mfa_required():
            set_route("/care-hub/mfa")
            st.stop()
            return True
        # Mobile must stay on login route until individual PIN gate is completed.
        # Otherwise route can bounce between login and inbox before PIN verification.
        if app_variant == VARIANT_MOBILE and not is_mobile_pin_verified_for_session():
            return False
        set_route(home_route)
        st.stop()
        return True
    return False


def get_office_home_route(is_authed: bool) -> str:
    if is_authed:
        return get_home_route(VARIANT_OFFICE)
    has_care_hub_session = bool(
        st.session_state.get("access_token")
        and st.session_state.get("refresh_token")
        and st.session_state.get("active_role") == "care_hub"
    )
    if has_care_hub_session:
        if not current_user_can_access_office():
            return get_login_route(VARIANT_MOBILE)
        st.session_state["office_login_explicit"] = True
        return get_home_route(VARIANT_OFFICE)
    return get_login_route(VARIANT_OFFICE)


def validate_supabase_config_for_variant(app_variant: str) -> None:
    if is_dev_auth_bypass_active():
        return
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
        'NEXT_PUBLIC_SUPABASE_URL="..."\n'
        'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY="..."\n\n'
        "Only the publishable key is supported in frontend/runtime app config."
    )
    st.stop()


def get_public_app_url(variant: str) -> str:
    if variant == VARIANT_FAMILY:
        return os.getenv("FAMILY_APP_URL", "").strip() or "/?route=%2Ffamily%2Flogin"
    if variant == VARIANT_MOBILE:
        return os.getenv("CARE_MOBILE_APP_URL", "").strip() or "/?route=%2Fcare-hub%2Fmobile%2Flogin"
    if variant == VARIANT_OFFICE:
        return os.getenv("CARE_OFFICE_APP_URL", "").strip() or "/?route=%2Fcare-hub%2Flogin"
    return ""


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
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant == VARIANT_MOBILE:
        return "Mobile"
    if runtime_variant == VARIANT_OFFICE:
        return get_at_home_voicemail_label(st.session_state.get("access_token"))
    app_variant = get_app_variant()
    if app_variant == VARIANT_MOBILE:
        return "Mobile"
    if app_variant == VARIANT_OFFICE:
        return get_at_home_voicemail_label(st.session_state.get("access_token"))
    return "Family system"


def get_channel_label_and_icon(channel_role: str) -> tuple[str, str]:
    role = (channel_role or "").strip().lower()
    if role == "family":
        return "Family", ""
    if role == "care_hub":
        return "Care Home system", ""
    if role == "resident":
        return "Resident", ""
    return "System", ""


def render_message_direction_header(
    from_channel_role: str,
    to_channel_role: str,
    recorded_by: str | None = None,
    *,
    show_chips: bool = False,
    use_from_to_heading: bool = False,
) -> None:
    from_label, from_icon = get_channel_label_and_icon(from_channel_role)
    to_label, to_icon = get_channel_label_and_icon(to_channel_role)
    from_prefix = f"{from_icon} " if from_icon else ""
    to_prefix = f"{to_icon} " if to_icon else ""
    heading_text = (
        f"From: {from_prefix}{from_label} &rarr; To: {to_prefix}{to_label}"
        if use_from_to_heading
        else f"{from_prefix}{from_label} &rarr; {to_prefix}{to_label}"
    )
    st.markdown(
        f'<div class="vm-section-title">{heading_text}</div>',
        unsafe_allow_html=True,
    )
    _ = show_chips
    if recorded_by:
        st.caption(f"Recorded by: {recorded_by}")


def format_soft_message_period_label(recorded_at_value: str | None) -> str | None:
    if not recorded_at_value:
        return None
    try:
        dt_mod = __import__("datetime")
        parsed = dt_mod.datetime.fromisoformat(str(recorded_at_value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_mod.timezone.utc)
        local_dt = parsed.astimezone()
        return f"Date: {local_dt.strftime('%d %b %Y')}"
    except Exception:
        return None


def format_office_sent_label(now_dt: object | None = None) -> str:
    _ = now_dt
    return "Message sent \u2014 today"


def render_audio_safe(
    audio_payload: bytes | str | None,
    *,
    audio_format: str | None = None,
    unavailable_message: str = "Audio preview is temporarily unavailable.",
) -> bool:
    if audio_payload is None:
        return False
    try:
        if audio_format:
            st.audio(audio_payload, format=audio_format)
        else:
            st.audio(audio_payload)
        return True
    except Exception as exc:
        if APP_DEBUG:
            print(f"[audio-safe] suppressed audio render error: {exc}", flush=True)
        st.caption(unavailable_message)
        return False


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
        "Family Hub login",
        brand_title="familyupdates.care",
        show_variant_subheading=False,
        show_menu=False,
    )
    timeout_notice = str(st.session_state.pop("session_timeout_notice", "") or "").strip()
    if timeout_notice:
        st.warning(timeout_notice)
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
        "Not a live service. Urgent and private matters stay outside the app.",
        "For security, Family sessions sign out after 30 minutes of inactivity.",
        "If you are signed out, request a new secure email link.",
        "Use Family Hub for current updates, practical requests, structured replies, and noticeboard notes.",
        "familyupdates.care is for non-urgent communication only. Families still need a separate urgent/emergency protocol, usually phoning a named person on their mobile. The exact protocol and how those contact details are shared are decided by the family outside the app.",
    ]
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)

    st.markdown("### Login")
    email = st.text_input("Email", key="family_login_email")
    st.caption(
        "Sign in with your invited email and a secure link. No password required. Sign out when finished on shared devices."
    )
    normalized_email = email.strip().lower()
    st.markdown('<div id="vm-login-actions"></div>', unsafe_allow_html=True)
    action_cols = st.columns(2, gap="small")
    with action_cols[0]:
        submit_login = st.button("Send secure sign-in link", key="family_login_submit")
    with action_cols[1]:
        resend_pressed = st.button("Resend sign-in link", key="family_login_resend")
    st.caption("New Family Members must be registered/invited from Office before Family login will work.")
    sign_out_pressed = False
    if st.session_state.get("auth_uid"):
        if st.button("Sign out", key="family_login_sign_out"):
            sign_out_pressed = True
    if submit_login:
        ok, message = send_magic_link_email(
            normalized_email, app_variant=VARIANT_FAMILY, should_create_user=False
        )
        if ok:
            st.success(message)
        else:
            st.error(message)
            st.info("If you are new, ask the Family Organiser or Office user to register/invite you first.")

    if sign_out_pressed:
        sign_out_user("family")
    if resend_pressed:
        ok, message = send_magic_link_email(
            normalized_email, app_variant=VARIANT_FAMILY, should_create_user=False
        )
        if ok:
            st.success(message)
        else:
            st.error(message)
            st.info("If you are new, ask the Family Organiser or Office user to register/invite you first.")

    for box in login_info_boxes:
        st.markdown(f'<div class="family-login-box">{box}</div>', unsafe_allow_html=True)
    render_public_landing_link("Back to hub selection", key="family_login_back_public")

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
            st.error("This browser is signed in to Mobile or Family Office.")
            st.info("Sign out before using Family Hub in this browser.")
            if st.button("Sign out", key="family_login_wrong_logout"):
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
    border: 5px solid #1f6f8b;
    border-radius: 18px;
    padding: 14px;
    margin: 14px 0;
    background: #eefbff;
  }}
  .vm-section-title {{
    font-weight: 700;
    margin: 8px 0 4px;
  }}
  .vm-muted-line {{
    color: rgba(31,31,31,0.72);
    font-size: 0.92rem;
    font-weight: 650;
    padding: 8px 10px;
    border-radius: 12px;
    background: rgba(31,31,31,0.05);
    border: 2px dashed rgba(31,31,31,0.18);
    margin: 6px 0 10px;
  }}
  .vm-direction-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 2px 0 8px;
  }}
  .vm-direction-chip {{
    border: 1px solid rgba(31,31,31,0.16);
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.8rem;
    line-height: 1.4;
    background: rgba(255,255,255,0.6);
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 2px solid rgba(31,31,31,0.18) !important;
    border-radius: 20px !important;
    background: #ffffff !important;
    margin: 12px 0 18px !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    border-radius: 16px !important;
    border: 0 !important;
    background: transparent !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-flow-title.resident) {{
    border-color: #0077b6 !important;
    background: #f6fcff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.resident) {{
    border-color: #0077b6 !important;
    background: #f6fcff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.resident) > div {{
    border-color: #0077b6 !important;
    box-shadow: inset 8px 0 0 #0077b6 !important;
    background: #e8f7ff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-flow-title.inbound) {{
    border-color: #d9dee3 !important;
    background: #f7f0ff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.inbound) {{
    border-color: #d9dee3 !important;
    background: #f7f0ff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.inbound) > div {{
    border-color: #d9dee3 !important;
    box-shadow: inset 8px 0 0 #f8f2ff !important;
    background: #f8f2ff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-flow-title.office) {{
    border-color: #d9dee3 !important;
    background: #f0ffff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.office) {{
    border-color: #d9dee3 !important;
    background: #f0ffff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.office) > div {{
    border-color: #d9dee3 !important;
    box-shadow: inset 8px 0 0 #f4ffff !important;
    background: #f4ffff !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-flow-title.practical) {{
    border-color: #d9dee3 !important;
    background: #fff7f3 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.practical) {{
    border-color: #d9dee3 !important;
    background: #fff7f3 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.practical) > div {{
    border-color: #d9dee3 !important;
    box-shadow: inset 8px 0 0 #fff8f5 !important;
    background: #fff8f5 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-flow-title.outbound) {{
    border-color: #d9dee3 !important;
    background: #ffffe6 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.outbound) {{
    border-color: #d9dee3 !important;
    background: #ffffe6 !important;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.family-channel-marker.outbound) > div {{
    border-color: #d9dee3 !important;
    box-shadow: inset 8px 0 0 #ffffe8 !important;
    background: #ffffe8 !important;
  }}
  .family-channel-marker {{
    display: none;
  }}
  div[data-testid="stButton"] button {{
    border-radius: 14px !important;
    border: 3px solid #1f2937 !important;
    font-weight: 800 !important;
  }}
  div[class*="st-key-family-channel"] div[data-testid="InputInstructions"] {{
    display: none !important;
  }}
  div[class*="st-key-family-channel-office"] {{
    background: #f4ffff !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-family-channel-office-message"] {{
    background: #ffffe8 !important;
    border: 6px solid #d9dee3 !important;
  }}
  div[class*="st-key-family-channel-office-message"] > div {{
    background: #ffffe8 !important;
  }}
  div[class*="st-key-family-channel-practical"] {{
    background: #fff8f5 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-family-channel-noticeboard"] {{
    background: #f4faf3 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-family-channel-inbound"] {{
    background: #f8f2ff !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header("Family Hub")
    render_dev_stage_level_status(st.session_state.get("access_token"))
    render_how_it_works_button("family_send_how_it_works")
    family_display_name = st.session_state.get("family_display_name", "Family member")
    st.markdown(f"**Hello {family_display_name}**")

    access_token = st.session_state.get("access_token")
    transcript_policy_mode = get_transcript_policy_mode(access_token)
    operating_mode = get_operating_mode(access_token)
    lifecycle_stage = get_lifecycle_stage(access_token)
    lifecycle_stage_number = normalize_lifecycle_stage(lifecycle_stage)
    communication_level = get_communication_level(access_token)
    lifecycle_policy = get_lifecycle_policy(lifecycle_stage, operating_mode, communication_level)
    lifecycle_stage_label = str(lifecycle_policy.get("lifecycle_stage_label") or "")
    at_home_lifecycle_stage = lifecycle_stage_number in {1, 2, 3}
    shared_coordination_stage = lifecycle_stage_number in {1, 2, 3}
    workspace_labels = get_workspace_labels_for_lifecycle_stage(lifecycle_stage_number)
    family_messaging_enabled = bool(lifecycle_policy.get("enable_family_messaging"))
    requests_enabled = bool(lifecycle_policy.get("enable_requests"))
    office_channel_enabled = bool(lifecycle_policy.get("enable_office_channel"))
    family_led_mode = operating_mode == OPERATING_MODE_PERSONAL_USE
    voice_messaging_enabled = family_messaging_enabled and not (
        family_led_mode or at_home_lifecycle_stage
    )
    subject_singular = str(workspace_labels.get("subject_singular") or "person")
    subject_singular_title = str(workspace_labels.get("subject_singular_title") or "Person")
    subject_plural = str(workspace_labels.get("subject_plural") or "people")
    personal_mode_ok, personal_mode_failures = validate_personal_mode_runtime(operating_mode)
    if family_led_mode and not personal_mode_ok:
        st.error(
            "Personal mode copy guard failed. Please ask Office to check Operational Variables."
        )
        st.caption("Guard details: " + "; ".join(personal_mode_failures))
        return
    main_contact_name = get_main_contact_name(access_token)
    care_home_name = fetch_active_care_home_name(access_token)
    family_user_record = get_family_user_for_session(access_token)
    family_user_id = str((family_user_record or {}).get("id") or "").strip()
    residents = fetch_family_residents(
        st.session_state.get("auth_uid", ""), access_token
    )
    if family_led_mode or at_home_lifecycle_stage:
        person_display_name = _resolve_person_display_name_from_residents(
            residents,
            selected_resident_id=str(st.session_state.get("family_selected_resident_id") or "").strip(),
        )
        if person_display_name:
            st.session_state["circle_person_display_name"] = person_display_name
        else:
            st.session_state.pop("circle_person_display_name", None)
    render_care_home_identity_banner(access_token)
    if not (family_messaging_enabled or office_channel_enabled or requests_enabled):
        st.info("Communication is inactive for the current situation.")

    if not residents:
        st.info(f"No {subject_plural} are currently linked to your Family Member account.")
        return

    resident_access_names = [
        f"{resident['preferred_name']} {resident['surname']}" for resident in residents
    ]
    if len(resident_access_names) > 1:
        st.caption(f"{subject_plural.title()} you can access: " + ", ".join(resident_access_names))
        resident_option_ids = [resident["id"] for resident in residents]
        resident_label_by_id = {
            resident["id"]: f"{resident['preferred_name']} {resident['surname']}"
            for resident in residents
        }
        selected_resident_id = st.selectbox(
            f"Select {subject_singular}",
            resident_option_ids,
            format_func=lambda resident_id: resident_label_by_id.get(resident_id, subject_singular_title),
            key="family_selected_resident_id",
        )
        residents = [
            resident for resident in residents if resident["id"] == selected_resident_id
        ]

    st.markdown(
        """
<style>
.family-flow-title {
  width: 100%;
  border-radius: 10px;
  padding: 4px 0 6px 0;
  margin: 0 0 8px 0;
  font-weight: 750;
  font-size: 1rem;
  line-height: 1.35;
  border: 0;
  box-shadow: none;
  background: transparent !important;
}
.family-flow-title.resident {
  border-color: #0077b6;
  color: #053047;
}
.family-flow-title.inbound {
  border-color: #7b2cbf;
  color: #35105d;
}
.family-flow-title.office {
  border-color: #008c8c;
  color: #004f4f;
}
.family-flow-title.practical {
  border-color: #c95f35;
  color: #5b2410;
}
.family-flow-title.outbound {
  border-color: #b59b00;
  color: #4f4300;
}
.family-channel-note {
  color: rgba(31,31,31,0.78);
  font-size: 0.94rem;
  font-weight: 550;
  margin: 0 0 12px 0;
  padding: 9px 11px;
  line-height: 1.35;
  border-radius: 14px;
  border: 3px solid rgba(31,31,31,0.16);
  background: #ffffff;
}
.family-flow-box {
  border-radius: 18px;
  padding: 12px 12px 4px 12px;
  margin: 0 0 12px 0;
  border: 5px solid;
}
.family-flow-box.outbound {
  background: #ffffe8;
  border-color: #b59b00;
}
</style>
""",
        unsafe_allow_html=True,
    )

    def render_family_flow_title(text: str, tone: str) -> None:
        safe_text = html.escape(text)
        safe_tone = html.escape(tone)
        st.markdown(
            f"<div class='family-flow-title {safe_tone}'>{safe_text}</div>",
            unsafe_allow_html=True,
        )

    def render_family_channel_marker(tone: str) -> None:
        safe_tone = html.escape(tone)
        st.markdown(
            f"<div class='family-channel-marker {safe_tone}'></div>",
            unsafe_allow_html=True,
        )

    def render_family_channel_note(text: str) -> None:
        safe_text = html.escape(text)
        st.markdown(
            f"<div class='family-channel-note'>{safe_text}</div>",
            unsafe_allow_html=True,
        )

    send_state = st.session_state.setdefault("family_send_state", {})
    has_pending_recording = any(
        bool((entry or {}).get("recording_bytes"))
        for entry in send_state.values()
        if isinstance(entry, dict)
    )
    trigger_live_message_refresh(
        "family_live_refresh",
        disabled=has_pending_recording or not is_variant_live_refresh_enabled(VARIANT_FAMILY),
    )
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
                {
                    "recording_bytes": None,
                    "preview_confirmed": False,
                    "last_message": None,
                    "recording_fingerprint": None,
                },
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
                "recording_fingerprint": None,
            },
        )
        full_name = get_resident_full_name(resident, operating_mode=operating_mode)
        person_first_name = full_name.split()[0] if full_name.split() else full_name
        room_caption = (
            f"{str(workspace_labels.get('room_label') or 'Room').title()} {resident['room']}"
            if resident.get("room") and bool(workspace_labels.get("show_room"))
            else ""
        )
        family_display_name = str(st.session_state.get("family_display_name") or "Family member").strip()

        if not (family_led_mode or at_home_lifecycle_stage):
            with st.container(border=True):
                render_family_channel_marker("resident")
                render_family_flow_title(
                    f"{subject_singular_title} ({full_name})",
                    "resident",
                )
                st.markdown(f"**{full_name}**")
                if care_home_name:
                    if bool(workspace_labels.get("show_room")):
                        st.markdown(
                            f"{workspace_labels.get('organisation_label')}: {care_home_name}"
                        )
                if room_caption:
                    st.markdown(room_caption)

        if not (voice_messaging_enabled or office_channel_enabled or requests_enabled):
            st.caption("Family communication is inactive in this situation.")
            continue

        if voice_messaging_enabled:
            with st.container(border=True, key=f"family-channel-inbound-group-{resident_id}"):
                render_family_channel_marker("inbound")
                render_family_flow_title(
                    (
                        f"Latest message from {full_name} to family group"
                        if at_home_lifecycle_stage
                        else f"Latest message from {subject_singular} ({full_name}) to family group"
                    ),
                    "inbound",
                )
                render_family_channel_note(
                    "Everyone linked can see this channel."
                )
                latest = fetch_latest_message(
                    resident_id,
                    "from_resident",
                    access_token,
                    contact_user_id_is_null=True,
                    family_id=resident.get("family_id") or resident_id,
                    channel="resident_family",
                    include_audio=True,
                )
                audio_bytes = decode_audio_payload(latest, access_token=access_token)
                if render_text_update_message(latest):
                    pass
                elif audio_bytes:
                    st.audio(audio_bytes, format=latest.get("audio_mime_type") or "audio/wav")
                    resident_sent_label = format_soft_message_period_label(latest.get("recorded_at"))
                    if resident_sent_label:
                        st.caption(resident_sent_label)
                else:
                    st.markdown(
                        '<div class="vm-muted-line">No new messages.</div>',
                        unsafe_allow_html=True,
                    )
                if latest and not is_text_update_message(latest):
                    render_transcript_assist(
                        latest,
                        policy_mode=transcript_policy_mode,
                        care_home_id=resident.get("care_home_id"),
                        resident_id=resident_id,
                    )
            with st.container(border=True, key=f"family-channel-inbound-direct-{resident_id}"):
                render_family_channel_marker("inbound")
                render_family_flow_title(
                    (
                        f"Latest message from {full_name} to you"
                        if at_home_lifecycle_stage
                        else f"Latest message from {subject_singular} ({full_name}) to you"
                    ),
                    "inbound",
                )
                render_family_channel_note(
                    f"Direct current message from {full_name} to you. Other Family Members do not see this channel."
                )
                latest_direct = fetch_latest_message(
                    resident_id,
                    "from_resident",
                    access_token,
                    contact_user_id=st.session_state.get("auth_uid"),
                    channel="resident_family",
                    include_audio=True,
                )
                direct_audio_bytes = decode_audio_payload(latest_direct, access_token=access_token)
                if render_text_update_message(latest_direct):
                    pass
                elif direct_audio_bytes:
                    st.audio(
                        direct_audio_bytes,
                        format=latest_direct.get("audio_mime_type") or "audio/wav",
                    )
                    direct_sent_label = format_soft_message_period_label(
                        latest_direct.get("recorded_at")
                    )
                    if direct_sent_label:
                        st.caption(direct_sent_label)
                else:
                    st.markdown(
                        '<div class="vm-muted-line">No direct message.</div>',
                        unsafe_allow_html=True,
                    )
                if latest_direct and not is_text_update_message(latest_direct):
                    render_transcript_assist(
                        latest_direct,
                        policy_mode=transcript_policy_mode,
                        care_home_id=resident.get("care_home_id"),
                        resident_id=resident_id,
                    )

        outbound_section_slot = st.container()

        if office_channel_enabled:
            with st.container(border=True, key=f"family-channel-office-update-{resident_id}"):
                render_family_channel_marker("office")
                office_update_title = (
                    "Shared update to Family"
                    if shared_coordination_stage
                    else (
                        "Update to Family"
                        if at_home_lifecycle_stage
                        else "Care Home update to Family (Office informational message)"
                    )
                )
                if family_led_mode:
                    if main_contact_name:
                        office_update_title = (
                            f"Update from Family Organiser {main_contact_name} "
                            "to the family group"
                        )
                    else:
                        office_update_title = "Update from Family Organiser to the family group"
                render_family_flow_title(
                    office_update_title,
                    "office",
                )
                latest_office_update = fetch_latest_message(
                    resident_id,
                    "office_to_family",
                    access_token,
                    family_id=resident.get("family_id") or resident_id,
                    channel="office_family",
                    include_audio=False,
                )
                if render_text_update_message(latest_office_update):
                    pass
                elif latest_office_update:
                    st.markdown(
                        '<div class="vm-muted-line">No current text update yet.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="vm-muted-line">No current text update yet.</div>',
                        unsafe_allow_html=True,
                    )

        if office_channel_enabled and (family_led_mode or at_home_lifecycle_stage):
            with st.container(border=True, key=f"family-channel-office-message-{resident_id}"):
                render_family_channel_marker("outbound")
                render_family_flow_title(
                    f"Your message to Family Organiser ({family_display_name})",
                    "outbound",
                )
                render_family_channel_note(
                    "When you send your current message, it replaces your previous one. "
                    "When the Family Organiser sends a new message, it replaces their previous one. "
                    "So you both see current messages only. This is non-urgent and not live."
                )
                latest_organiser_message = fetch_latest_message(
                    resident_id,
                    "from_resident",
                    access_token,
                    contact_user_id=st.session_state.get("auth_uid"),
                    channel="resident_family",
                    include_audio=False,
                )
                st.markdown("**Current message from Family Organiser**")
                if not render_text_update_message(latest_organiser_message):
                    st.markdown(
                        '<div class="vm-muted-line">No current organiser message.</div>',
                        unsafe_allow_html=True,
                    )
                latest_family_message = fetch_latest_message(
                    resident_id,
                    "to_resident",
                    access_token,
                    contact_user_id=st.session_state.get("auth_uid"),
                    channel="resident_family",
                    include_audio=False,
                )
                st.markdown("**Your current message to Family Organiser**")
                if not render_text_update_message(latest_family_message):
                    st.markdown(
                        '<div class="vm-muted-line">No current message from you.</div>',
                        unsafe_allow_html=True,
                    )
                text_nonce = int(state.get("family_organiser_text_nonce", 0))
                with st.form(
                    f"family_to_organiser_form_{resident_id}_{text_nonce}",
                    clear_on_submit=False,
                ):
                    family_to_organiser_body = st.text_area(
                        f"Type your message to Family Organiser ({family_display_name}) here:",
                        key=f"family_to_organiser_text_{resident_id}_{text_nonce}",
                        height=100,
                        max_chars=1000,
                    )
                    family_to_organiser_submitted = st.form_submit_button(
                        "Click to send and replace your message",
                        use_container_width=True,
                    )
                family_to_organiser_can_send = bool(str(family_to_organiser_body or "").strip())
                if family_to_organiser_submitted:
                    if not family_to_organiser_can_send:
                        st.info("Please write the current message first.")
                    else:
                        supabase, error = get_authed_supabase(access_token)
                        if error:
                            st.error(error)
                        else:
                            now_iso = __import__("datetime").datetime.utcnow().isoformat()
                            payload = {
                                "resident_id": resident_id,
                                "contact_user_id": st.session_state.get("auth_uid"),
                                "family_id": resident.get("family_id") or resident_id,
                                "channel": "resident_family",
                                "direction": "to_resident",
                                "audio_storage_path": "",
                                "audio_mime_type": "text/plain",
                                "audio_bytes": 0,
                                "message_kind": "text",
                                "text_title": None,
                                "text_body": str(family_to_organiser_body or "").strip(),
                                "recorded_at": now_iso,
                            }
                            resp, upsert_error = upsert_latest_message_with_fallback(
                                supabase,
                                payload,
                                "resident_id,contact_user_id,direction,channel",
                                {
                                    "resident_id": resident_id,
                                    "contact_user_id": st.session_state.get("auth_uid"),
                                    "channel": "resident_family",
                                    "direction": "to_resident",
                                },
                            )
                            if upsert_error:
                                st.error(upsert_error)
                            else:
                                message_id = (
                                    (
                                        resp.data[0].get("id")
                                        if hasattr(resp, "data")
                                        and isinstance(resp.data, list)
                                        and resp.data
                                        else None
                                    )
                                    if resp is not None
                                    else None
                                )
                                log_audit_event(
                                    "message_sent",
                                    "family",
                                    resident["care_home_id"],
                                    message_id,
                                    resident_id=resident_id,
                                )
                                bump_message_cache_epoch()
                                state["family_organiser_text_nonce"] = text_nonce + 1
                                st.success("Current message to Family Organiser replaced.")
                                st.rerun()

        if requests_enabled:
            with st.container(border=True, key=f"family-channel-practical-request-{resident_id}"):
                render_family_channel_marker("practical")
                request_sender_label = (
                    f"Family Organiser {main_contact_name}"
                    if main_contact_name
                    else "Family Organiser"
                )
                render_family_flow_title(
                    f"Practical request from {request_sender_label} to Family Members",
                    "practical",
                )
                practical_message = fetch_latest_open_office_practical_message(
                    resident_id, access_token, family_user_id=family_user_id
                )
                if practical_message:
                    practical_message_id = str(practical_message.get("id") or "").strip()
                    practical_context_type = str(
                        practical_message.get("context_type") or OFFICE_PRACTICAL_CONTEXT_GENERAL
                    ).strip()
                    practical_target_type = normalize_office_practical_target_type(
                        practical_message.get("target_type")
                    )
                    st.markdown(
                        f"**{(practical_message.get('title') or 'Request').strip()}**"
                    )
                    st.markdown(str(practical_message.get("body") or "").strip())
                    if practical_target_type == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY:
                        request_contacts = fetch_family_users_for_resident(
                            resident_id, access_token
                        )
                        st.caption(
                            f"Directed to: {office_practical_target_label(practical_message, request_contacts)}."
                        )
                    if practical_context_type == OFFICE_PRACTICAL_CONTEXT_VISIT:
                        requested_date = str(practical_message.get("requested_date") or "").strip()
                        requested_time = str(practical_message.get("requested_time_window") or "").strip()
                        if requested_date:
                            st.caption(f"Requested date: {requested_date}")
                        if requested_time:
                            st.caption(f"Requested time window: {requested_time}")
                    response_options = fetch_office_practical_message_options(
                        practical_message_id, access_token
                    )
                    existing_response = fetch_family_practical_response(
                        practical_message_id,
                        family_user_id,
                        access_token,
                    )
                    response_choice = (
                        str((existing_response or {}).get("primary_choice") or "").strip().lower()
                    )
                    choice_labels = list(STRUCTURED_RESPONSE_VALUES_BY_LABEL.keys())
                    choice_to_value = STRUCTURED_RESPONSE_VALUES_BY_LABEL
                    default_choice_label = format_structured_response_choice(response_choice)
                    default_choice_index = (
                        choice_labels.index(default_choice_label)
                        if default_choice_label in choice_labels
                        else 0
                    )
                    selected_option_ids: list[str] = []
                    existing_selected_option_ids = set(
                        (existing_response or {}).get("selected_option_ids") or []
                    )
                    primary_choice_option_labels = {
                        "yes",
                        "no",
                        "maybe",
                        "no response",
                        "no_response",
                        "not sure",
                    }
                    practical_option_labels_by_id: dict[str, str] = {}
                    practical_extra_options: list[tuple[str, str]] = []
                    for option in response_options:
                        option_id = str(option.get("id") or "").strip()
                        option_label = normalize_practical_option_label_for_mode(
                            str(option.get("option_label") or "").strip(),
                            (
                                OPERATING_MODE_PERSONAL_USE
                                if at_home_lifecycle_stage
                                else operating_mode
                            ),
                            person_first_name=person_first_name,
                        )
                        if not option_id or not option_label:
                            continue
                        practical_option_labels_by_id[option_id] = option_label
                        if option_label.strip().lower() in primary_choice_option_labels:
                            continue
                        practical_extra_options.append((option_id, option_label))
                    note_value = ""
                    planned_visit_time_value = ""
                    with st.form(
                        f"family_practical_response_form_{resident_id}_{practical_message_id}",
                        clear_on_submit=False,
                    ):
                        selected_choice_label = st.radio(
                            "Your structured response",
                            options=choice_labels,
                            index=default_choice_index,
                            horizontal=True,
                            key=f"family_practical_choice_{resident_id}_{practical_message_id}",
                        )
                        for option_id, option_label in practical_extra_options:
                            checked = st.checkbox(
                                option_label,
                                value=option_id in existing_selected_option_ids,
                                key=f"family_practical_check_{resident_id}_{practical_message_id}_{option_id}",
                            )
                            if checked:
                                selected_option_ids.append(option_id)
                        if bool(practical_message.get("allow_note", True)):
                            note_value = st.text_area(
                                "Optional short context note (not a discussion).",
                                value=str((existing_response or {}).get("note") or ""),
                                key=f"family_practical_note_{resident_id}_{practical_message_id}",
                                max_chars=500,
                            )
                        if practical_context_type == OFFICE_PRACTICAL_CONTEXT_VISIT:
                            planned_visit_time_value = st.text_input(
                                "Planned visit time (optional)",
                                value=str((existing_response or {}).get("planned_visit_time") or ""),
                                key=f"family_practical_planned_visit_time_{resident_id}_{practical_message_id}",
                                placeholder="Example: Saturday about 11am",
                            )
                        family_practical_submitted = st.form_submit_button(
                            "Send structured response",
                            use_container_width=True,
                        )
                    share_with_family_value = True
                    if family_practical_submitted:
                        if not family_user_id:
                            st.error("Your Family Member mapping could not be found. Please sign in again.")
                        else:
                            ok, message = upsert_family_practical_response(
                                practical_message_id,
                                family_user_id,
                                choice_to_value.get(selected_choice_label, "no_response"),
                                note_value,
                                selected_option_ids,
                                planned_visit_time_value,
                                share_with_family_value,
                                access_token,
                            )
                            if ok:
                                st.success("Structured response received.")
                                st.rerun()
                            else:
                                st.error(message)
                    existing_response = fetch_family_practical_response(
                        practical_message_id,
                        family_user_id,
                        access_token,
                    )
                    shared_responses = fetch_shared_family_practical_responses(
                        practical_message_id,
                        family_user_id,
                        access_token,
                    )
                    if existing_response:
                        own_choice = format_structured_response_choice(
                            existing_response.get("primary_choice")
                        )
                        if own_choice:
                            st.markdown("**Your current structured response**")
                            st.markdown(f"- Response: {own_choice}")
                        own_selected_labels = [
                            practical_option_labels_by_id.get(str(option_id or "").strip(), "")
                            for option_id in (existing_response.get("selected_option_ids") or [])
                        ]
                        own_selected_labels = [label for label in own_selected_labels if label]
                        for label in own_selected_labels:
                            st.markdown(f"- {label}")
                        own_note = str(existing_response.get("note") or "").strip()
                        if own_note:
                            st.markdown(f"- Note: {own_note}")
                        own_planned_visit = str(existing_response.get("planned_visit_time") or "").strip()
                        if own_planned_visit:
                            st.markdown(f"- Planned visit: {own_planned_visit}")
                    st.caption("Structured responses from other Family Members:")
                    if shared_responses:
                        for shared_response in shared_responses:
                            contact_name = str(shared_response.get("contact_name") or "Family Member")
                            choice_label = format_structured_response_choice(
                                shared_response.get("primary_choice")
                            )
                            st.markdown(f"- {contact_name}: {choice_label}")
                            shared_visit = str(shared_response.get("planned_visit_time") or "").strip()
                            if shared_visit:
                                st.caption(f"Planned visit: {shared_visit}")
                            shared_note = str(shared_response.get("note") or "").strip()
                            if shared_note:
                                st.caption(f"Note: {shared_note}")
                    else:
                        st.caption("No other structured responses yet.")
                else:
                    st.caption(f"No open requests for this {subject_singular}.")

            with st.container(border=True, key=f"family-channel-noticeboard-{resident_id}"):
                render_family_channel_marker("resident")
                render_family_flow_title(
                    "Family noticeboard: current practical notes from Family Members",
                    "resident",
                )
                noticeboard_notes = fetch_family_noticeboard_notes(resident_id, access_token)
                own_notice = next(
                    (
                        note
                        for note in noticeboard_notes
                        if str(note.get("family_user_id") or "").strip() == family_user_id
                    ),
                    None,
                )
                family_notice_body = st.text_area(
                    "Your current practical note",
                    value=str((own_notice or {}).get("note_body") or ""),
                    key=f"family_noticeboard_note_{resident_id}",
                    max_chars=500,
                    placeholder="Example: I am visiting Saturday afternoon.",
                )
                family_notice_cols = st.columns(2)
                with family_notice_cols[0]:
                    if st.button(
                        "Save noticeboard note",
                        key=f"family_noticeboard_save_{resident_id}",
                        use_container_width=True,
                    ):
                        ok, message = upsert_family_noticeboard_note(
                            resident_id,
                            str(resident.get("care_home_id") or ""),
                            family_user_id,
                            family_notice_body,
                            access_token,
                        )
                        if ok:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                with family_notice_cols[1]:
                    if own_notice and st.button(
                        "Clear my note",
                        key=f"family_noticeboard_clear_{resident_id}_{own_notice.get('id')}",
                        use_container_width=True,
                    ):
                        ok, message = clear_family_noticeboard_note(
                            str(own_notice.get("id") or ""),
                            access_token,
                        )
                        if ok:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                other_noticeboard_notes = [
                    note
                    for note in noticeboard_notes
                    if str(note.get("family_user_id") or "").strip() != family_user_id
                ]
                st.caption("Current notes from other Family Members:")
                if other_noticeboard_notes:
                    for notice in other_noticeboard_notes:
                        contact_name = str(notice.get("contact_name") or "Family Member").strip()
                        note_body = str(notice.get("note_body") or "").strip()
                        if note_body:
                            st.markdown(f"- {contact_name}: {note_body}")
                else:
                    st.caption("No other noticeboard notes yet.")

        if not voice_messaging_enabled:
            continue

        with outbound_section_slot.container(border=True):
            render_family_channel_marker("outbound")
            render_family_flow_title(
                f"Latest message from you ({family_display_name}) to the person being supported ({full_name})",
                "outbound",
            )
            render_family_channel_note(
                f"Your current voice message to {full_name}."
            )
            latest_sent = fetch_latest_message(
                resident_id,
                "to_resident",
                access_token,
                contact_user_id=st.session_state.get("auth_uid"),
                channel="resident_family",
                include_audio=True,
            )
            if not latest_sent:
                latest_sent = fetch_latest_message(
                    resident_id,
                    "to_resident",
                    access_token,
                    channel="resident_family",
                    include_audio=True,
                )
            latest_sent_audio = decode_audio_payload(latest_sent, access_token=access_token)
            last_message = state.get("last_message") or {}
            last_message_audio = last_message.get("audio_preview")
            if isinstance(last_message_audio, memoryview):
                last_message_audio = last_message_audio.tobytes()
            if not isinstance(last_message_audio, (bytes, bytearray)):
                last_message_audio = None
            last_message_audio_mime = (
                str(last_message.get("audio_mime_type") or "").strip() or "audio/wav"
            )
            last_message_transcript_text = str(last_message.get("transcript_text") or "").strip()
            last_message_transcript_status = str(last_message.get("transcript_status") or "").strip().lower()
            fallback_last_message_for_transcript = None
            if last_message_audio:
                fallback_last_message_for_transcript = {
                    "id": "",
                    "transcript_text": last_message_transcript_text or None,
                    "transcript_status": (
                        last_message_transcript_status
                        if last_message_transcript_status
                        else ("ready" if last_message_transcript_text else "not_requested")
                    ),
                    "audio_storage_path": base64.b64encode(bytes(last_message_audio)).decode("ascii"),
                    "audio_mime_type": last_message_audio_mime,
                }
            show_recent_send_feedback = bool(last_message and not state.get("recording_bytes"))
            if latest_sent:
                if latest_sent_audio:
                    st.audio(
                        latest_sent_audio,
                        format=latest_sent.get("audio_mime_type") or "audio/wav",
                    )
                elif last_message_audio:
                    st.audio(last_message_audio, format=last_message_audio_mime)
                    st.caption("Showing a copy of the message you just sent.")
                else:
                    st.success("Latest Family -> Resident message is saved.")
                latest_sent_at = latest_sent.get("recorded_at")
                if latest_sent_at and not show_recent_send_feedback:
                    latest_sent_label = format_soft_message_period_label(latest_sent_at)
                    if latest_sent_label:
                        st.caption(latest_sent_label)
                if not show_recent_send_feedback:
                    render_transcript_assist(
                        latest_sent,
                        policy_mode=transcript_policy_mode,
                        care_home_id=resident.get("care_home_id"),
                        resident_id=resident_id,
                    )
            if last_message and not state.get("recording_bytes"):
                sent_at = last_message.get("sent_at")
                sent_display = format_soft_message_period_label(sent_at) if sent_at else None
                if last_message_audio:
                    st.audio(last_message_audio, format=last_message_audio_mime)
                transcript_source = latest_sent or fallback_last_message_for_transcript
                if transcript_source:
                    render_transcript_assist(
                        transcript_source,
                        policy_mode=transcript_policy_mode,
                        care_home_id=resident.get("care_home_id"),
                        resident_id=resident_id,
                    )
                if sent_display:
                    st.caption(sent_display)
                if st.button(
                    "Record new message (replaces previous)",
                    key=f"family_record_new_{resident_id}",
                ):
                    state["recording_bytes"] = None
                    state["recording_mime_type"] = "audio/wav"
                    state["recording_fingerprint"] = None
                    reset_outbox_state_on_new_recording(
                        state,
                        ack_widget_key=f"family_listened_{resident_id}",
                    )
                    st.session_state.pop(f"family_upload_{resident_id}", None)
                    st.session_state.pop(f"family_audio_input_{resident_id}", None)
                    st.rerun()
                st.success("Message sent")
                continue

            native_recording_available = hasattr(st, "audio_input")
            if native_recording_available:
                recorded_from_native = st.audio_input(
                    f"Record voice message to {full_name}",
                    key=f"family_audio_input_{resident_id}",
                )
                if recorded_from_native is not None:
                    native_bytes = recorded_from_native.getvalue()
                    if native_bytes:
                        native_fp = __import__("hashlib").sha1(native_bytes).hexdigest()
                    else:
                        native_fp = None
                    if not native_bytes:
                        st.warning(
                            "That recording could not be captured correctly. Please record again."
                        )
                    elif native_fp != state.get("recording_fingerprint"):
                        reset_outbox_state_on_new_recording(
                            state,
                            ack_widget_key=f"family_listened_{resident_id}",
                        )
                        state["recording_bytes"] = native_bytes
                        state["recording_fingerprint"] = native_fp
                        state["recording_mime_type"] = (
                            getattr(recorded_from_native, "type", None) or "audio/wav"
                        )
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
                if st.button(
                    "Discard recording and try again",
                    key=f"family_discard_recording_{resident_id}",
                    use_container_width=True,
                ):
                    state["recording_bytes"] = None
                    state["recording_mime_type"] = "audio/wav"
                    state["recording_fingerprint"] = None
                    reset_outbox_state_on_new_recording(
                        state,
                        ack_widget_key=f"family_listened_{resident_id}",
                    )
                    st.session_state.pop(f"family_audio_input_{resident_id}", None)
                    st.rerun()
                state["preview_confirmed"] = st.checkbox(
                    "I have listened to this message.",
                    value=state.get("preview_confirmed", False),
                    key=f"family_listened_{resident_id}",
                )
                render_transcript_preview_controls(
                    state,
                    state.get("recording_bytes") or b"",
                    state.get("recording_mime_type") or "audio/wav",
                    policy_mode=transcript_policy_mode,
                    key_scope=f"family_preview_{resident_id}",
                )
            else:
                state["preview_confirmed"] = False
                state["transcribe_requested"] = False
                clear_transcript_preview_state(state)

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
                        now_iso = __import__("datetime").datetime.utcnow().isoformat()
                        audio_object_path, upload_error = upload_audio_to_storage(
                            audio_bytes,
                            audio_mime_type,
                            resident_id=resident_id,
                            direction="to_resident",
                        )
                        use_inline_fallback = not bool(audio_object_path)
                        if APP_DEBUG and upload_error:
                            print(f"[audio-upload] to_resident fallback to inline payload: {upload_error}")
                        payload = {
                            "resident_id": resident_id,
                            "contact_user_id": st.session_state.get("auth_uid"),
                            "family_id": resident.get("family_id") or resident_id,
                            "channel": "resident_family",
                            "direction": "to_resident",
                            "audio_storage_path": (
                                base64.b64encode(audio_bytes).decode("ascii")
                                if use_inline_fallback
                                else ""
                            ),
                            "audio_object_path": audio_object_path,
                            "audio_source": "inline" if use_inline_fallback else "storage",
                            "audio_mime_type": audio_mime_type,
                            "audio_bytes": len(audio_bytes),
                            "recorded_at": now_iso,
                        }
                        transcript_fields, transcript_error = build_transcript_fields_from_preview(
                            state,
                            audio_bytes,
                            audio_mime_type,
                            requested=bool(state.get("transcribe_requested")),
                        )
                        payload.update(transcript_fields)
                        resp, upsert_error = upsert_latest_message_with_fallback(
                            supabase,
                            payload,
                            "resident_id,contact_user_id,direction,channel",
                            {
                                "resident_id": resident_id,
                                "contact_user_id": st.session_state.get("auth_uid"),
                                "channel": "resident_family",
                                "direction": "to_resident",
                            },
                        )
                        if upsert_error:
                            st.error(upsert_error)
                        else:
                            if transcript_error and bool(state.get("transcribe_requested")):
                                st.warning(f"Message sent, but transcript failed: {transcript_error}")
                            transcript_persist_warning = consume_transcript_persist_warning()
                            if transcript_persist_warning:
                                st.warning(transcript_persist_warning)
                            message_id = (
                                (
                                    resp.data[0].get("id")
                                    if hasattr(resp, "data")
                                    and isinstance(resp.data, list)
                                    and resp.data
                                    else None
                                )
                                if resp is not None
                                else None
                            )
                            log_audit_event(
                                "message_sent",
                                "family",
                                resident["care_home_id"],
                                message_id,
                            )
                            bump_message_cache_epoch()
                            state["recording_bytes"] = None
                            state["recording_mime_type"] = "audio/wav"
                            state["preview_confirmed"] = False
                            state["transcribe_requested"] = False
                            clear_transcript_preview_state(state)
                            state["last_message"] = {
                                "sent_at": now_iso,
                                "audio_preview": bytes(audio_bytes),
                                "audio_mime_type": audio_mime_type,
                                "transcript_text": transcript_fields.get("transcript_text"),
                                "transcript_status": transcript_fields.get("transcript_status"),
                            }
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
    render_care_home_identity_banner(st.session_state.get("access_token"))
    st.write("Your message has been sent.")
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        render_route_link("Back", get_home_route(VARIANT_FAMILY), key="family_sent_back_link")
    with action_cols[1]:
        render_route_link(
            "Back to Family Hub login",
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
    access_token = st.session_state.get("access_token")
    mode_value = get_operating_mode(access_token)
    lifecycle_stage = get_lifecycle_stage(access_token)
    at_home_lifecycle_stage = normalize_lifecycle_stage(lifecycle_stage) in {1, 2, 3}
    render_page_header("Documents")

    if at_home_lifecycle_stage:
        docs = [
            {
                "title": "How it works",
                "path": "docs/public/02_how_it_works.md",
                "summary": "Current familyupdates.care guidance for family coordination.",
            },
            {
                "title": "At-home responsibilities",
                "path": "docs/office/04_care_home_responsibilities.md",
                "summary": "Responsibilities and boundaries for at-home use.",
            },
            {
                "title": "Safeguarding and consent",
                "path": "docs/office/09_safeguarding_consent.md",
                "summary": "Consent, authority, and safeguarding boundaries.",
            },
            {
                "title": "Family Office Q&A",
                "path": "docs/office/common_questions_qa.md",
                "summary": "Common questions for at-home coordination.",
            },
        ]
    else:
        docs = [
            {
                "title": "Care home responsibilities",
                "path": "docs/office/04_care_home_responsibilities.md",
                "summary": "Care home responsibilities and boundaries.",
            },
            {
                "title": "Care home guide",
                "path": "docs/office/05_care_home_guide.md",
                "summary": "Day-to-day Care Home system use (Office and Mobile).",
            },
            {
                "title": "Safeguarding and consent",
                "path": "docs/office/09_safeguarding_consent.md",
                "summary": "Consent, authority, and safeguarding guidance.",
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
    docs = [
        {
            **doc,
            "path": resolve_mode_doc_path(
                str(doc.get("path") or ""),
                operating_mode=mode_value,
                lifecycle_stage=lifecycle_stage,
            ),
        }
        for doc in docs
    ]

    if "docs_active" not in st.session_state:
        st.session_state["docs_active"] = ""

    active_path = st.session_state.get("docs_active")
    if active_path:
        active_path = resolve_mode_doc_path(
            str(active_path or ""),
            operating_mode=mode_value,
            lifecycle_stage=lifecycle_stage,
        )
        st.session_state["docs_active"] = active_path
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
        f"Back to {get_at_home_voicemail_label(access_token)}",
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
        pending_lines: list[str] = []

        def flush_pending() -> None:
            if pending_lines:
                st.markdown("\n".join(pending_lines).strip())
                pending_lines.clear()

        for line in content.splitlines():
            image_match = re.fullmatch(r"\s*!\[([^\]]*)\]\(([^)]+)\)\s*", line)
            if not image_match:
                pending_lines.append(line)
                continue
            alt_text = image_match.group(1).strip()
            image_ref = image_match.group(2).strip()
            if not image_ref:
                pending_lines.append(line)
                continue
            flush_pending()
            if re.match(r"^[a-zA-Z]+://", image_ref):
                try:
                    st.image(image_ref, caption=alt_text or None, use_container_width=True)
                except TypeError:
                    st.image(image_ref, caption=alt_text or None, use_column_width=True)
                continue
            image_path = (Path(doc_path).parent / image_ref).resolve()
            if image_path.exists():
                try:
                    st.image(str(image_path), caption=alt_text or None, use_container_width=True)
                except TypeError:
                    st.image(str(image_path), caption=alt_text or None, use_column_width=True)
            else:
                st.error(f"Image not found: {image_ref}")
        flush_pending()
    except OSError:
        st.error("Document not found.")


def render_document_boxes(doc_path: str, strip_first_heading: bool = True) -> None:
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
    except OSError:
        st.error("Document not found.")
        return
    # Remove only the leading logo marker; keep other top images (for example the cartoon).
    content = re.sub(r"\A\s*!\[logo\]\([^)]+\)\s*\n+", "", content, count=1, flags=re.I)
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
    def _render_markdown_image(markdown_line: str) -> bool:
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", markdown_line.strip())
        if not image_match:
            return False
        alt_text = image_match.group(1).strip()
        image_ref = image_match.group(2).strip()
        if not image_ref:
            return False
        try:
            if re.match(r"^[a-zA-Z]+://", image_ref):
                st.image(image_ref, caption=alt_text or None, use_container_width=True)
                return True
            image_path = (Path(doc_path).parent / image_ref).resolve()
            if image_path.exists():
                st.image(str(image_path), caption=alt_text or None, use_container_width=True)
                return True
        except TypeError:
            # Streamlit compatibility fallback for older versions.
            if re.match(r"^[a-zA-Z]+://", image_ref):
                st.image(image_ref, caption=alt_text or None, use_column_width=True)
                return True
            image_path = (Path(doc_path).parent / image_ref).resolve()
            if image_path.exists():
                st.image(str(image_path), caption=alt_text or None, use_column_width=True)
                return True
        st.error(f"Image not found: {image_ref}")
        return True

    def _render_box(markdown_text: str) -> None:
        raw_text = markdown_text.strip()
        if re.fullmatch(r"[-*_]{3,}", raw_text):
            return
        remaining_lines: list[str] = []
        for line in raw_text.splitlines():
            if _render_markdown_image(line):
                continue
            remaining_lines.append(line)
        raw_text = "\n".join(remaining_lines).strip()
        if not raw_text:
            return
        text = re.sub(r"^\s*[-*]\s+", "- ", raw_text, flags=re.M).strip()
        if re.fullmatch(r"[-*\s]+", text):
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
        "familyupdates_infographic.md": "familyupdates.care infographic",
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


def render_one_message_tester(prefix: str, state_key: str) -> None:
    st.caption(
        "This public tester stores messages only in this browser session. "
        "Each new message replaces the previous one from that person."
    )
    tester_state = st.session_state.setdefault(
        state_key,
        {
            "a_name": "Person A",
            "b_name": "Person B",
            "a_to_b": "I will be there at 3.",
            "b_to_a": "Great. Please bring milk.",
        },
    )
    name_cols = st.columns(2, gap="small")
    with name_cols[0]:
        tester_state["a_name"] = st.text_input(
            "First person",
            value=str(tester_state.get("a_name") or "Person A"),
            key=f"{prefix}_a_name",
        )
    with name_cols[1]:
        tester_state["b_name"] = st.text_input(
            "Second person",
            value=str(tester_state.get("b_name") or "Person B"),
            key=f"{prefix}_b_name",
        )
    a_name = str(tester_state.get("a_name") or "Person A").strip() or "Person A"
    b_name = str(tester_state.get("b_name") or "Person B").strip() or "Person B"
    message_cols = st.columns(2, gap="small")
    with message_cols[0]:
        st.markdown(f"**Latest from {a_name} to {b_name}**")
        st.info(str(tester_state.get("a_to_b") or "No current message."))
        with st.form(f"{prefix}_a_form", clear_on_submit=True):
            next_message = st.text_area(
                f"Replace {a_name}'s message",
                key=f"{prefix}_a_text",
                max_chars=220,
            )
            if st.form_submit_button("Replace message"):
                if next_message.strip():
                    tester_state["a_to_b"] = next_message.strip()
                    st.rerun()
    with message_cols[1]:
        st.markdown(f"**Latest from {b_name} to {a_name}**")
        st.info(str(tester_state.get("b_to_a") or "No current message."))
        with st.form(f"{prefix}_b_form", clear_on_submit=True):
            next_message = st.text_area(
                f"Replace {b_name}'s message",
                key=f"{prefix}_b_text",
                max_chars=220,
            )
            if st.form_submit_button("Replace message"):
                if next_message.strip():
                    tester_state["b_to_a"] = next_message.strip()
                    st.rerun()
    st.caption(
        "No thread is created. No history is shown. If you need a reply, send a request in the real app."
    )
    if st.button("Reset tester", key=f"{prefix}_reset"):
        st.session_state[state_key] = {
            "a_name": "Person A",
            "b_name": "Person B",
            "a_to_b": "I will be there at 3.",
            "b_to_a": "Great. Please bring milk.",
        }
        st.rerun()


def render_how_it_works_tester_button(prefix: str) -> None:
    st.markdown("## Try one-message communication")
    open_key = f"{prefix}_open"
    if st.button("Open one-message tester", key=f"{prefix}_button", use_container_width=True):
        st.session_state[open_key] = not bool(st.session_state.get(open_key, False))
    if st.session_state.get(open_key, False):
        render_one_message_tester(prefix, f"{prefix}_state")


def render_public_document(doc_path: str, back_route: str = PUBLIC_HOME_ROUTE) -> None:
    # Render all public documents in the boxed style for consistency.
    use_boxes = not doc_path.endswith("02_how_it_works.md")
    use_qa_search = doc_path.endswith("10_faq.md")
    is_how_it_works_doc = doc_path.endswith("02_how_it_works.md")
    app_variant = resolve_runtime_variant(route_hint=get_route())
    access_token = st.session_state.get("access_token")
    if app_variant == VARIANT_PUBLIC and st.session_state.get("auth_uid"):
        active_role = str(st.session_state.get("active_role") or "").strip().lower()
        if active_role == "care_hub":
            app_variant = (
                VARIANT_OFFICE
                if bool(st.session_state.get("office_login_explicit"))
                else VARIANT_MOBILE
            )
        elif active_role == "family":
            app_variant = VARIANT_FAMILY
        elif str(st.session_state.get("active_care_home_id") or "").strip():
            app_variant = (
                VARIANT_OFFICE
                if bool(st.session_state.get("office_login_explicit"))
                else VARIANT_MOBILE
            )
    mode_value = get_operating_mode(access_token) if access_token else OPERATING_MODE_CARE_ORGANISATION
    resolved_doc_path = resolve_mode_doc_path(
        doc_path,
        access_token=access_token,
        operating_mode=mode_value,
    )
    page_title = get_public_document_title(doc_path)
    return_route = normalize_route(st.session_state.get("public_doc_return_route") or "")
    if return_route.startswith("/public"):
        return_route = ""
    if app_variant == VARIANT_PUBLIC:
        render_page_header(page_title, show_menu=False, show_variant_subheading=False)
        render_route_link(
            "Back to familyupdates.care",
            back_route,
            key=f"public_doc_back_{re.sub(r'[^a-z0-9]+', '_', doc_path.lower())}",
        )
        if use_qa_search:
            render_qa_document(resolved_doc_path, search_key="public_faq_search")
        elif use_boxes:
            render_document_boxes(resolved_doc_path, strip_first_heading=True)
        else:
            render_document_content(resolved_doc_path)
        if is_how_it_works_doc:
            render_how_it_works_tester_button("public_how_it_works_one_message")
        return
    if app_variant == VARIANT_FAMILY:
        family_back_route = return_route or get_home_route(VARIANT_FAMILY)
        family_back_label = "Back" if return_route else "Back to Family Hub"
        render_page_header(page_title, show_variant_subheading=False)
        render_route_link(
            family_back_label,
            family_back_route,
            key="public_doc_back_family_login_link",
        )
        if use_qa_search:
            render_qa_document(resolved_doc_path, search_key="family_faq_search")
        elif use_boxes:
            render_document_boxes(resolved_doc_path, strip_first_heading=True)
        else:
            render_document_content(resolved_doc_path, include_logo=False, strip_first_heading=True)
        if is_how_it_works_doc:
            render_how_it_works_tester_button("family_how_it_works_one_message")
        return
    if app_variant == VARIANT_OFFICE:
        is_authed = bool(st.session_state.get("auth_uid"))
        office_home_route = return_route or get_office_home_route(is_authed)
        office_back_label = "Back" if return_route else "Back to dashboard"
        render_page_header(page_title, show_variant_subheading=False)
        render_route_link(
            office_back_label,
            office_home_route,
            key="public_doc_back_office_dashboard_link",
        )
        if use_qa_search:
            render_qa_document(resolved_doc_path, search_key="office_faq_search")
        elif use_boxes:
            render_document_boxes(resolved_doc_path, strip_first_heading=True)
        else:
            render_document_content(resolved_doc_path, include_logo=False)
        if is_how_it_works_doc:
            render_how_it_works_tester_button("office_how_it_works_one_message")
        render_route_link(
            office_back_label,
            office_home_route,
            key="public_doc_back_office_dashboard_bottom_link",
        )
        return
    if app_variant == VARIANT_MOBILE:
        mobile_back_route = return_route or get_home_route(app_variant)
        render_page_header(page_title)
        render_route_link(
            "Back",
            mobile_back_route,
            key="public_doc_back_mobile_link",
        )
        if use_qa_search:
            render_qa_document(resolved_doc_path, search_key="mobile_faq_search")
        elif use_boxes:
            render_document_boxes(resolved_doc_path, strip_first_heading=True)
        else:
            render_document_content(resolved_doc_path)
        if is_how_it_works_doc:
            render_how_it_works_tester_button("mobile_how_it_works_one_message")
        return
    render_page_header(page_title, show_menu=False, show_variant_subheading=False)
    if use_qa_search:
        render_qa_document(resolved_doc_path, search_key="fallback_faq_search")
    elif use_boxes:
        render_document_boxes(resolved_doc_path, strip_first_heading=True)
    else:
        render_document_content(resolved_doc_path)
    if is_how_it_works_doc:
        render_how_it_works_tester_button("fallback_how_it_works_one_message")
    render_public_landing_button("Back to hub selection")


def render_public_infographic() -> None:
    render_public_document("docs/public/familyupdates_infographic.md", back_route="/public/how-it-works")


def render_public_docs() -> None:
    app_variant = resolve_runtime_variant(route_hint=get_route())

    render_page_header("Public Documents")
    if app_variant == VARIANT_FAMILY:
        if st.button(
            "Back to Family Hub login",
            key="public_docs_back_family_login_link",
            use_container_width=True,
        ):
            st.session_state["force_family_login"] = True
            set_route(get_login_route(VARIANT_FAMILY))
    if app_variant == VARIANT_OFFICE:
        render_route_link(
            "Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="public_docs_back_office_dashboard_link",
        )
    st.write("Select a public document to view.")

    public_docs = []
    public_docs.extend(
        [
            ("Public Q&A", "/public/qa"),
            ("Privacy notice", "/public/privacy-notice"),
            ("Family terms of use", "/public/family-terms-of-use"),
            ("Complaints and concerns", "/public/complaints-and-concerns"),
            ("Safeguarding and consent", "/public/safeguarding-and-consent"),
        ]
    )

    for idx, (label, route) in enumerate(public_docs):
        if st.button(label, key=f"public_docs_open_{idx}", use_container_width=True):
            set_route(route)

    if app_variant == VARIANT_OFFICE:
        is_authed = bool(st.session_state.get("auth_uid"))
        render_route_link(
            "Back to Family Office",
            get_office_home_route(is_authed),
            key="public_docs_back_office_link",
        )
    elif app_variant == VARIANT_MOBILE:
        render_route_link(
            "Back to Mobile",
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


def render_familyupdates_infographic_image() -> None:
    image_path = Path(__file__).resolve().parent / "assets" / "infographic-v5.png"
    if not image_path.exists():
        return
    try:
        st.image(str(image_path), use_container_width=True)
    except TypeError:
        st.image(str(image_path), use_column_width=True)


def render_pr_homepage() -> None:
    st.markdown(
        """
        <style>
        .vm-home-shell {
            max-width: 980px;
            margin: 0 auto;
            padding: 18px 14px 24px;
        }
        .vm-home-card {
            background: #ffffff;
            border: 1px solid rgba(31, 31, 31, 0.12);
            border-radius: 14px;
            padding: 14px;
        }
        .vm-home-brand {
            margin: 0 0 8px 0;
            font-size: 1.55rem;
            font-weight: 800;
            color: #1f1f1f;
            line-height: 1.2;
            letter-spacing: 0;
            white-space: nowrap;
        }
        .vm-home-brand span {
            color: #6b7280;
            font-weight: 700;
        }
        .vm-home-caption {
            margin: 8px 0 0 0;
            color: #4b5563;
            font-size: 0.93rem;
        }
        @media (max-width: 390px) {
            .vm-home-brand {
                font-size: 1.08rem;
            }
        }
        @media (max-width: 360px) {
            .vm-home-brand {
                font-size: 0.98rem;
            }
        }
        .vm-home-infographic {
            margin: 14px 0 12px;
            border: 6px solid #d9dee3;
            border-radius: 18px;
            overflow: hidden;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="vm-home-shell">', unsafe_allow_html=True)
    st.markdown('<div class="vm-home-card">', unsafe_allow_html=True)
    st.markdown(
        '<h1 class="vm-home-brand">familyupdates<span>.care</span></h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "familyupdates.care keeps essential family coordination separate from chat.",
    )
    st.markdown('<div class="vm-home-infographic">', unsafe_allow_html=True)
    render_familyupdates_infographic_image()
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("How it works", key="pr_entry_how_it_works", use_container_width=True):
        set_route("/public/how-it-works")
        st.stop()

    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        if st.button("Family Office", key="pr_entry_office", use_container_width=True):
            set_route(OFFICE_LOGIN_ROUTE)
            st.stop()
    with action_cols[1]:
        if st.button("Family Hub", key="pr_entry_family", use_container_width=True):
            set_route(FAMILY_LOGIN_ROUTE)
            st.stop()
    with action_cols[2]:
        if st.button("Mobile", key="pr_entry_mobile", use_container_width=True):
            set_route(MOBILE_LOGIN_ROUTE)
            st.stop()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_care_hub_banner_settings() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant("Operational variables are only available in Family Office.")
        return
    save_notice_state_key = "office_operational_save_notice"
    render_page_header("Operational Variables")
    access_token = st.session_state.get("access_token")
    mode_value = get_operating_mode(access_token)
    lifecycle_stage = get_lifecycle_stage(access_token)
    lifecycle_stage_number = normalize_lifecycle_stage(lifecycle_stage)
    at_home_lifecycle_stage = lifecycle_stage_number in {1, 2, 3}
    current_workspace_labels = get_workspace_labels_for_lifecycle_stage(lifecycle_stage_number)
    current_workspace_type_label = str(
        current_workspace_labels.get("workspace_type_label") or "Care Home system"
    )
    current_office_label = str(current_workspace_labels.get("office_label") or "Care Home Office")
    current_mobile_label = str(current_workspace_labels.get("mobile_label") or "Care Home Mobile")
    subject_singular = str(current_workspace_labels.get("subject_singular") or "resident")
    subject_singular_title = str(
        current_workspace_labels.get("subject_singular_title") or "Resident"
    )
    subject_plural_title = str(
        current_workspace_labels.get("subject_plural_title") or "Residents"
    )
    render_care_home_identity_banner(access_token)
    current_communication_level = get_communication_level(access_token)
    current_policy = get_lifecycle_policy(
        lifecycle_stage,
        mode_value,
        current_communication_level,
    )
    render_stage_level_status(current_policy)
    save_notice = str(st.session_state.pop(save_notice_state_key, "") or "").strip()
    if save_notice:
        st.success(save_notice)
    st.markdown("### Operational setup variables")
    st.markdown(
        "- Current situation\n"
        "- Setup name\n"
        "- Person 1 / Person 2 names for at-home setup\n"
        "- Main supporter / organiser\n"
        f"- Idle sign-out time for {current_workspace_type_label} sessions"
    )
    st.caption(
        "Review and confirm these settings during setup so day-to-day use is consistent from launch."
    )
    st.markdown("### Family Office checks")
    st.markdown("**Daily**")
    st.checkbox("Login", key="office_checks_daily_login")
    st.checkbox("Send & playback test message", key="office_checks_daily_send_playback")
    st.markdown("**When asked**")
    st.checkbox(
        "After app update: send & play test message",
        key="office_checks_after_update_send_playback",
    )
    st.markdown("**If needed**")
    st.checkbox("Reset message list", key="office_checks_if_needed_reset_message_list")
    st.caption(
        "Reset message list rebuilds queue tracking (played/unread state and pointer). "
        "It does not delete messages."
    )
    reset_tool_residents = fetch_care_home_residents(access_token or "")
    reset_tool_resident_by_id: dict[str, dict] = {}
    reset_tool_resident_ids: list[str] = []
    reset_tool_resident_label_by_id: dict[str, str] = {}
    for resident in reset_tool_residents:
        resident_id = str(resident.get("id") or "").strip()
        if not resident_id:
            continue
        reset_tool_resident_by_id[resident_id] = resident
        reset_tool_resident_ids.append(resident_id)
        reset_tool_resident_label_by_id[resident_id] = format_resident_identity_label(
            resident,
            operating_mode=mode_value,
            include_room=bool(current_workspace_labels.get("show_room")),
            include_care_home=False,
            separator=" | ",
        )
    if reset_tool_resident_ids:
        selected_reset_resident_id = st.selectbox(
            f"{subject_singular_title} for message list reset",
            options=reset_tool_resident_ids,
            format_func=lambda value: reset_tool_resident_label_by_id.get(value, subject_singular_title),
            key="office_queue_reset_selected_resident_id",
        )
        confirm_queue_reset = st.checkbox(
            f"I confirm I want to reset queue tracking for this {subject_singular}.",
            key="office_queue_reset_confirm",
        )
        if st.button(
            f"Reset selected {subject_singular} message list",
            key="office_queue_reset_button",
            use_container_width=True,
        ):
            if not confirm_queue_reset:
                st.error("Please confirm before resetting the message list.")
            else:
                selected_reset_resident = reset_tool_resident_by_id.get(selected_reset_resident_id) or {}
                selected_reset_care_home_id = str(
                    selected_reset_resident.get("care_home_id")
                    or st.session_state.get("active_care_home_id")
                    or ""
                ).strip()
                if not selected_reset_resident_id or not selected_reset_care_home_id:
                    st.error("Could not determine person/group context for reset.")
                else:
                    cleared = clear_resident_contact_playback_state(
                        selected_reset_resident_id,
                        selected_reset_care_home_id,
                        access_token,
                    )
                    set_resident_playback_pointer(
                        selected_reset_resident_id,
                        selected_reset_care_home_id,
                        None,
                        access_token,
                    )
                    st.session_state.pop(
                        f"care_mobile_pointer_{selected_reset_resident_id}",
                        None,
                    )
                    st.session_state.pop(
                        f"care_mobile_played_cache_{selected_reset_resident_id}",
                        None,
                    )
                    st.session_state.pop(
                        f"care_mobile_last_played_{selected_reset_resident_id}",
                        None,
                    )
                    if cleared:
                        st.success(f"Selected {subject_singular} message list reset.")
                    else:
                        st.warning(
                            "Reset request completed with no DB rows changed for played/unread state."
                        )
                    st.rerun()
    else:
        st.caption(f"No {subject_plural_title.lower()} available for message list reset.")
    st.markdown("**Issues**")
    st.checkbox("Log / escalate incidents", key="office_checks_issues_log_escalate")
    st.markdown("### Operational settings")
    st.caption(
        f"Choose how long the active {current_workspace_type_label} can stay idle before it signs out. "
        f"This applies to {current_office_label} and {current_mobile_label}."
    )
    st.caption(
        "Current situation controls the family-side wording. It does not assign fixed roles to people."
    )
    if st.session_state.get("_care_homes_missing_lifecycle_stage"):
        st.warning(
            "Current situation changes cannot be saved until migration "
            "0029_care_homes_lifecycle_stage.sql is applied in Supabase."
        )

    care_home_profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    if not isinstance(care_home_profile, dict) or not str(care_home_profile.get("name") or "").strip():
        st.error(
            "Could not load the current setup settings. Save is disabled to avoid overwriting existing banner values."
        )
        st.info("Refresh the page and try again. If this persists, check that recent database migrations are applied.")
        return
    timeout_options = list(CARE_HUB_IDLE_TIMEOUT_OPTIONS_SECONDS)
    timeout_labels = {
        60 * 30: "30 minutes",
        60 * 60: "60 minutes",
        60 * 90: "90 minutes",
        60 * 120: "120 minutes",
    }
    current_timeout = normalize_care_hub_idle_timeout_seconds(
        care_home_profile.get("care_hub_idle_timeout_seconds")
    )
    current_transcript_policy = normalize_transcript_policy_mode(
        care_home_profile.get("transcript_policy_mode")
    )
    timeout_index = timeout_options.index(current_timeout)
    transcript_policy_options = list(TRANSCRIPT_POLICY_MODES)
    transcript_policy_labels = {
        "off": "Off (no transcript assist)",
        "assist": "Assist (optional transcript assist)",
        "precheck": "Precheck (review transcript before playback)",
    }
    transcript_policy_index = transcript_policy_options.index(current_transcript_policy)
    current_operating_mode = normalize_operating_mode(
        care_home_profile.get("operating_mode")
    )
    current_lifecycle_stage = normalize_lifecycle_stage(
        care_home_profile.get("lifecycle_stage")
    )
    current_communication_level = DEFAULT_COMMUNICATION_LEVEL
    active_care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    with st.expander("Technical diagnostics", expanded=False):
        st.markdown(f"- Active care home id: `{active_care_home_id or 'missing'}`")
        st.markdown(f"- Profile mode (raw): `{str(care_home_profile.get('operating_mode') or '') or 'missing'}`")
        st.markdown(f"- Profile mode (normalized): `{current_operating_mode}`")
        st.markdown(f"- Runtime mode (resolved): `{mode_value}`")
        st.markdown(f"- Profile situation value: `{current_lifecycle_stage}`")
        stage_policy = get_lifecycle_policy(
            current_lifecycle_stage,
            current_operating_mode,
            current_communication_level,
        )
        st.markdown(f"- Situation label: `{stage_policy.get('lifecycle_stage_label', '')}`")
        st.markdown(
            "- Lifecycle policy snapshot: "
            f"`requests={bool(stage_policy.get('enable_requests'))}`, "
            f"`family_messaging={bool(stage_policy.get('enable_family_messaging'))}`, "
            f"`mobile={bool(stage_policy.get('enable_mobile_channel'))}`, "
            f"`second_office={bool(stage_policy.get('enable_second_office'))}`"
        )
        if bool(stage_policy.get("enable_second_office")):
            st.caption("Second office is an archived care-home planning flag. Separate care-home office screens are not implemented yet.")
        if current_operating_mode != mode_value:
            st.warning("Profile mode and runtime mode differ. Refresh and check save/update permissions.")
        if mode_value == OPERATING_MODE_PERSONAL_USE:
            st.markdown("- Personal mode checks: subject=`person`, plural=`people`, room field hidden.")
    controls_profile_key = "office_operational_controls_profile_id"
    controls_nonce_key = "office_operational_controls_nonce"
    if st.session_state.get(controls_profile_key) != active_care_home_id:
        st.session_state[controls_profile_key] = active_care_home_id
        st.session_state[controls_nonce_key] = int(st.session_state.get(controls_nonce_key, 0)) + 1
    controls_nonce = int(st.session_state.get(controls_nonce_key, 0) or 0)
    lifecycle_widget_key = f"office_lifecycle_stage_page_{active_care_home_id}_{controls_nonce}"
    lifecycle_stage_options = [1, 4]
    lifecycle_stage_labels = {
        stage: get_lifecycle_stage_label(stage) for stage in lifecycle_stage_options
    }
    with st.form(f"office_stage_level_form_{active_care_home_id}_{controls_nonce}"):
        selected_lifecycle_stage = st.selectbox(
            "Current situation",
            options=lifecycle_stage_options,
            index=(
                lifecycle_stage_options.index(current_lifecycle_stage)
                if current_lifecycle_stage in lifecycle_stage_options
                else lifecycle_stage_options.index(1)
            ),
            format_func=lambda value: lifecycle_stage_labels.get(value, "At home"),
            key=lifecycle_widget_key,
            help="Controls which tools are available for this setup.",
        )
        selected_lifecycle_note = get_lifecycle_stage_setup_note(selected_lifecycle_stage)
        if selected_lifecycle_note:
            st.caption(selected_lifecycle_note)
        save_stage_level = st.form_submit_button(
            "Save situation",
            use_container_width=True,
        )
    stage_level_notice = str(
        st.session_state.pop("office_stage_level_save_notice", "") or ""
    ).strip()
    if stage_level_notice:
        st.success(stage_level_notice)
    selected_at_home_stage = normalize_lifecycle_stage(selected_lifecycle_stage) in {1, 2, 3}
    selected_operating_mode = get_operating_mode_for_lifecycle_stage(
        selected_lifecycle_stage,
        current_operating_mode,
    )
    if save_stage_level:
        requested_lifecycle_stage = normalize_lifecycle_stage(selected_lifecycle_stage)
        requested_communication_level = DEFAULT_COMMUNICATION_LEVEL
        if requested_communication_level == 5 and requested_lifecycle_stage != 4:
            st.error("Archived care-home system flag cannot be saved unless the care-home situation is selected.")
        else:
            saved, message, readback = update_active_care_home_stage_level(
                access_token,
                lifecycle_stage=requested_lifecycle_stage,
                communication_level=requested_communication_level,
            )
            st.session_state["office_stage_level_last_readback"] = readback
            if saved:
                st.session_state.pop(f"care_home_profile_{active_care_home_id}", None)
                st.session_state.pop(f"care_home_profile_{active_care_home_id}_ts", None)
                st.session_state[controls_nonce_key] = controls_nonce + 1
                st.session_state["office_stage_level_save_notice"] = message
                st.session_state[save_notice_state_key] = message
                st.rerun()
            else:
                st.error(message)
                if readback:
                    st.json(readback)
    st.caption("Use this button to change the situation. The form below saves names, banner, and session settings.")
    selected_workspace_labels = get_workspace_labels_for_lifecycle_stage(
        selected_lifecycle_stage,
        setup_name=str(care_home_profile.get("name") or ""),
    )
    selected_workspace_type_label = str(
        selected_workspace_labels.get("workspace_type_label") or "Care Home system"
    )
    setup_context_label = str(
        selected_workspace_labels.get("setup_context_label") or "care home"
    )
    st.caption(f"Setup context: {setup_context_label}.")
    if normalize_lifecycle_stage(selected_lifecycle_stage) == 4:
        st.caption(
            "This page configures the family-side care-home situation. Use a Family Organiser workspace name, "
            "not the care home's operational system name. The care home remains responsible for its own "
            "direct care, safeguarding, and operational communication."
        )
    setup_people = fetch_care_home_residents(access_token or "")
    setup_people = [
        person
        for person in setup_people
        if str(person.get("care_home_id") or "") == active_care_home_id
    ][:2]

    with st.form("office_care_home_banner_page_form"):
        name_field_label = (
            "Care home name" if not selected_at_home_stage else "Family setup name"
        )
        care_home_name_value = st.text_input(
            name_field_label,
            value=str(care_home_profile.get("name") or ""),
            max_chars=160,
            key="office_care_home_name_page",
        )
        person_name_updates: dict[str, str] = {}
        if selected_at_home_stage:
            st.markdown("### People in this setup")
            if setup_people:
                for idx, person in enumerate(setup_people, start=1):
                    person_id = str(person.get("id") or "").strip()
                    person_label = "Person 1" if idx == 1 else "Person 2 (optional)"
                    person_name_updates[person_id] = st.text_input(
                        person_label,
                        value=get_resident_full_name(person, operating_mode=OPERATING_MODE_PERSONAL_USE),
                        max_chars=160,
                        key=f"office_setup_person_name_{person_id}",
                    )
            else:
                st.caption("No people are linked to this setup yet. Add-person setup will be added next.")
        main_contact_name_value = st.text_input(
            str(selected_workspace_labels.get("main_contact_label") or "Main contact name (optional)"),
            value=str(care_home_profile.get("main_contact_name") or ""),
            max_chars=120,
            key="office_main_contact_name_page",
        )
        message_check_note_value = st.text_area(
            "Message check note (optional)",
            value=str(care_home_profile.get("message_check_note") or ""),
            height=90,
            max_chars=500,
            key="office_message_check_note_page",
            help=(
                "Optional note for when and how frequently the Family Organiser expects to check "
                "non-urgent messages. This is not for urgent or emergency contact."
            ),
        )
        banner_title_value = st.text_input(
            "Banner heading (optional)",
            value=str(care_home_profile.get("branding_banner_title") or ""),
            max_chars=120,
            key="office_branding_banner_title_page",
        )
        banner_text_value = st.text_area(
            "Banner message (optional)",
            value=str(care_home_profile.get("branding_banner_text") or ""),
            height=120,
            max_chars=800,
            key="office_branding_banner_text_page",
        )
        banner_artwork_value = st.text_input(
            "Banner image URL (optional)",
            value=str(care_home_profile.get("branding_banner_artwork_url") or ""),
            key="office_branding_banner_artwork_url_page",
            help=(
                "Use a full https:// URL, or just an object path under MEDIA_BASE_URL "
                f"(currently {MEDIA_BASE_URL or 'unset'})."
            ),
        )
        if MEDIA_BASE_URL:
            st.caption(
                "Example banner object path: "
                f"`{CARE_HOME_BANNER_OBJECT_PATH}` -> "
                f"`{_join_media_base_url(CARE_HOME_BANNER_OBJECT_PATH)}`"
            )
        selected_idle_timeout = st.selectbox(
            "Idle sign-out time",
            options=timeout_options,
            index=timeout_index,
            format_func=lambda value: timeout_labels.get(value, f"{int(value // 60)} minutes"),
            key="office_care_hub_idle_timeout_seconds",
            help="If no activity is detected for this period, the app signs out for security.",
        )
        selected_transcript_policy = current_transcript_policy
        save_banner = st.form_submit_button("Save names, banner, and session settings")
    if save_banner:
        requested_lifecycle_stage = current_lifecycle_stage
        requested_communication_level = min(current_communication_level, 4)
        requested_at_home_stage = requested_lifecycle_stage in {1, 2, 3}
        requested_operating_mode = get_operating_mode_for_lifecycle_stage(
            requested_lifecycle_stage,
            current_operating_mode,
        )
        if requested_communication_level == 5 and requested_lifecycle_stage != 4:
            st.error("Archived care-home system flag cannot be saved unless the care-home situation is selected.")
        else:
            saved, message = update_active_care_home_branding(
                access_token,
                care_home_name=care_home_name_value,
                operating_mode=requested_operating_mode,
                lifecycle_stage=requested_lifecycle_stage,
                communication_level=requested_communication_level,
                main_contact_name=main_contact_name_value,
                message_check_note=message_check_note_value,
                banner_title=banner_title_value,
                banner_text=banner_text_value,
                banner_artwork_url=banner_artwork_value,
                care_hub_idle_timeout_seconds=int(selected_idle_timeout),
                transcript_policy_mode=selected_transcript_policy,
            )
            if saved:
                if requested_at_home_stage:
                    people_saved, people_error = update_person_display_names(
                        access_token,
                        person_name_updates,
                    )
                    if people_saved:
                        st.session_state.pop(f"care_home_profile_{active_care_home_id}", None)
                        st.session_state.pop(f"care_home_profile_{active_care_home_id}_ts", None)
                        st.session_state[controls_nonce_key] = controls_nonce + 1
                        st.session_state[save_notice_state_key] = message
                        st.rerun()
                    else:
                        st.warning(
                            "Settings saved, but person names could not be updated: "
                            + str(people_error or "Unknown error.")
                        )
                else:
                    st.session_state.pop(f"care_home_profile_{active_care_home_id}", None)
                    st.session_state.pop(f"care_home_profile_{active_care_home_id}_ts", None)
                    st.session_state[controls_nonce_key] = controls_nonce + 1
                    st.session_state[save_notice_state_key] = message
                    st.rerun()
            else:
                st.error(message)


def render_care_hub_security() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant("Security settings are only available in Family Office.")
        return
    render_page_header("Account & Security")
    access_token = st.session_state.get("access_token")
    render_care_home_identity_banner(access_token)
    auth_uid = st.session_state.get("auth_uid")
    auth_email = st.session_state.get("auth_email") or "office-user"
    record = get_care_hub_mfa_record(access_token, auth_uid)
    enabled = bool(record and record.get("enabled"))
    mfa_required = (
        os.getenv("OFFICE_MFA_REQUIRED", "1").strip().lower() in {"1", "true", "yes", "on"}
    )
    st.caption("Operational variables are managed on the dedicated Operational variables page.")
    render_route_link(
        "Open Operational variables",
        "/care-hub/operational-variables",
        key="office_security_open_operational_variables",
    )

    st.markdown("### Mobile PIN management")
    st.caption(
        "Each Mobile Support user has their own Mobile PIN. Reset clears a selected Mobile PIN; they will set a new PIN at next Mobile login."
    )
    staff_rows, staff_rows_error = fetch_care_home_staff_mobile_pin_status(access_token)
    if staff_rows_error:
        st.error(staff_rows_error)
    elif not staff_rows:
        st.info("No Mobile Support users found for this workspace.")
    else:
        current_auth_uid = str(st.session_state.get("auth_uid") or "").strip()
        selectable_staff_ids = []
        staff_label_by_id: dict[str, str] = {}
        for row in staff_rows:
            staff_auth_user_id = str(row.get("auth_user_id") or "").strip()
            if not staff_auth_user_id:
                continue
            selectable_staff_ids.append(staff_auth_user_id)
            staff_email = str(row.get("staff_email") or "").strip() or "No email"
            pin_set = bool(row.get("mobile_pin_set"))
            pin_label = "PIN set" if pin_set else "PIN not set"
            current_label = " (you)" if staff_auth_user_id == current_auth_uid else ""
            staff_label_by_id[staff_auth_user_id] = f"{staff_email} | {pin_label}{current_label}"
        if selectable_staff_ids:
            selected_staff_auth_user_id = st.selectbox(
                "Mobile Support user",
                options=selectable_staff_ids,
                format_func=lambda value: staff_label_by_id.get(value, value),
                key="office_mobile_pin_reset_target",
            )
            confirm_staff_pin_reset = st.checkbox(
                "I confirm I want to reset this Mobile PIN.",
                key="office_mobile_pin_reset_confirm",
            )
            if st.button(
                "Reset selected Mobile PIN",
                key="office_mobile_pin_reset_button",
                use_container_width=True,
            ):
                if not confirm_staff_pin_reset:
                    st.error("Please confirm before resetting the Mobile PIN.")
                else:
                    ok, reset_message = reset_care_home_staff_mobile_pin(
                        access_token, selected_staff_auth_user_id
                    )
                    if ok:
                        st.success(reset_message)
                        st.rerun()
                    else:
                        st.error(reset_message)

    st.markdown("### Two-factor authentication (TOTP)")
    if enabled:
        st.success("Two-factor authentication is enabled.")
        if mfa_required:
            st.caption("2FA is required for Family Office and cannot be disabled.")
        elif st.button("Disable 2FA", key="mfa_disable"):
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
        if mfa_required:
            st.info("2FA is required for Family Office. Set up your authenticator app now.")
        else:
            st.info("2FA is optional but recommended for Family Office.")
        if st.button("Start 2FA setup", key="mfa_start"):
            st.session_state["mfa_enroll_secret"] = pyotp.random_base32()
            st.session_state["mfa_enroll_codes"] = generate_recovery_codes()

        secret = st.session_state.get("mfa_enroll_secret")
        codes = st.session_state.get("mfa_enroll_codes")
        if secret and codes:
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=f"{auth_email} (Office)",
                issuer_name="familyupdates-office",
            )
            qr = qrcode.make(provisioning_uri)
            qr_image = qr.get_image() if hasattr(qr, "get_image") else qr
            st.image(qr_image, width=220, caption="Scan this QR code with your authenticator app.")
            st.write("If QR scanning is difficult, add account manually using this secret key:")
            st.code(secret, language=None)
            st.caption("Do not paste the secret key below. Enter the 6-digit app code only.")
            st.write("Enter the 6-digit code from your authenticator app to activate 2FA.")
            code_input = st.text_input("Authenticator code", key="mfa_enroll_code")
            if st.button("Verify and enable 2FA", key="mfa_enroll_verify"):
                if totp.verify(normalize_totp_code(code_input), valid_window=2):
                    hashes = [hash_recovery_code(code) for code in codes]
                    ok = upsert_care_hub_mfa(access_token, auth_uid, secret, hashes, True)
                    if ok:
                        st.session_state["mfa_show_codes"] = codes
                        st.session_state.pop("mfa_enroll_secret", None)
                        st.session_state.pop("mfa_enroll_codes", None)
                        st.success("2FA enabled.")
                    else:
                        st.error("Could not enable 2FA.")
                        mfa_error = st.session_state.get("mfa_last_error")
                        if mfa_error:
                            st.error(f"2FA error detail: {mfa_error}")
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
        "Back to Family Office",
        get_office_home_route(bool(st.session_state.get("auth_uid"))),
        key="mfa_back_office_link",
    )


def render_care_hub_mfa() -> None:
    render_page_header("Two-factor verification")
    access_token = st.session_state.get("access_token")
    render_care_home_identity_banner(access_token)
    auth_uid = st.session_state.get("auth_uid")
    mfa_required = (
        os.getenv("OFFICE_MFA_REQUIRED", "1").strip().lower() in {"1", "true", "yes", "on"}
    )
    if not auth_uid:
        render_access_gate(
            "Please sign in to access Family Office.",
            get_login_route(VARIANT_OFFICE),
            "care_hub",
        )
        return
    get_mapping_status()
    if not current_user_can_access_office():
        render_wrong_variant("This account has Mobile access and cannot use Family Office two-factor verification.")
        return
    record = get_care_hub_mfa_record(access_token, auth_uid)
    if not record or not record.get("enabled"):
        if not mfa_required:
            st.info("Two-factor authentication is not enabled for this account.")
            if st.button("Continue", key="mfa_not_enabled_continue"):
                set_route(get_home_route(VARIANT_OFFICE))
                st.rerun()
            return
        st.info("Two-factor authentication is required for Family Office.")
        st.write("Set up your authenticator app to continue.")
        if st.button("Start 2FA setup", key="mfa_login_start_setup"):
            st.session_state["mfa_enroll_secret"] = pyotp.random_base32()
            st.session_state["mfa_enroll_codes"] = generate_recovery_codes()

        secret = st.session_state.get("mfa_enroll_secret")
        codes = st.session_state.get("mfa_enroll_codes")
        if secret and codes:
            totp = pyotp.TOTP(secret)
            auth_email = st.session_state.get("auth_email") or "office-user"
            provisioning_uri = totp.provisioning_uri(
                name=f"{auth_email} (Office)",
                issuer_name="familyupdates-office",
            )
            qr = qrcode.make(provisioning_uri)
            qr_image = qr.get_image() if hasattr(qr, "get_image") else qr
            st.image(qr_image, width=220, caption="Scan this QR code with your authenticator app.")
            st.write("If QR scanning is difficult, add account manually using this secret key:")
            st.code(secret, language=None)
            st.caption("Do not paste the secret key below. Enter the 6-digit app code only.")
            code_input = st.text_input("Authenticator code", key="mfa_login_enroll_code")
            if st.button("Verify and enable 2FA", key="mfa_login_enroll_verify"):
                if totp.verify(normalize_totp_code(code_input), valid_window=2):
                    hashes = [hash_recovery_code(code) for code in codes]
                    ok = upsert_care_hub_mfa(access_token, auth_uid, secret, hashes, True)
                    if ok:
                        st.session_state["mfa_show_codes"] = codes
                        st.session_state["mfa_verified"] = True
                        st.session_state.pop("mfa_enroll_secret", None)
                        st.session_state.pop("mfa_enroll_codes", None)
                        st.success("2FA enabled.")
                    else:
                        st.error("Could not enable 2FA.")
                        mfa_error = st.session_state.get("mfa_last_error")
                        if mfa_error:
                            st.error(f"2FA error detail: {mfa_error}")
                else:
                    st.error("Invalid code. Please try again.")
        if st.session_state.get("mfa_show_codes"):
            st.markdown("### Recovery codes")
            st.write("Save these codes now. They will not be shown again.")
            for code in st.session_state["mfa_show_codes"]:
                st.code(code, language=None)
            if st.button("I have saved these codes", key="mfa_login_codes_saved"):
                st.session_state.pop("mfa_show_codes", None)
                set_route(get_home_route(VARIANT_OFFICE))
                st.rerun()
        if st.button("Sign out", key="mfa_setup_sign_out"):
            sign_out_user("care_hub")
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
            verified = totp.verify(normalize_totp_code(totp_code), valid_window=2)
        elif recovery_code:
            hashed = hash_recovery_code(recovery_code)
            if hashed in recovery_hashes:
                recovery_hashes = [h for h in recovery_hashes if h != hashed]
                update_care_hub_mfa_codes(access_token, auth_uid, recovery_hashes)
                verified = True
        if verified:
            st.session_state["mfa_verified"] = True
            set_route(get_home_route(VARIANT_OFFICE))
            st.rerun()
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
        {
            "title": "Data Processing Agreement (DPA) template",
            "path": "docs/contracts/data_processing_agreement_template.md",
            "summary": "UK GDPR controller/processor terms for pilot and live service.",
        },
        {
            "title": "Pilot legal and insurance readiness checklist",
            "path": "docs/contracts/pilot_legal_insurance_readiness_checklist.md",
            "summary": "Pre-go-live legal, insurance, and incident readiness checks.",
        },
        {
            "title": "Legal documents register",
            "path": "docs/contracts/registers/voice_message_legal_documents_register.md",
            "summary": "Master register of contract, DPA, and related legal records.",
        },
        {
            "title": "External services and subscriptions register",
            "path": "docs/contracts/registers/external_services_and_subscriptions_register.md",
            "summary": "Register of third-party websites/apps used by familyupdates.care.",
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
        "Back to Family Office",
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
        "Back to Family Office",
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
    app_variant = resolve_runtime_variant(route_hint=get_route())
    login_title = "Mobile" if app_variant == VARIANT_MOBILE else "Family Office"
    render_page_header(
        login_title,
        brand_title="familyupdates.care",
        show_variant_subheading=False,
        show_menu=app_variant != VARIANT_OFFICE,
    )
    timeout_notice = str(st.session_state.pop("session_timeout_notice", "") or "").strip()
    if timeout_notice:
        st.warning(timeout_notice)
    if app_variant == VARIANT_MOBILE:
        mobile_login_boxes = [
            "Mobile is the reduced-tool route for a carer, helper, supported person, or trusted family member.",
            "Mobile is for an additional person who helps provide care support.",
            "Use Mobile only for non-urgent family coordination. Urgent, medical, safeguarding, or private matters stay outside the app.",
        ]
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
        for info in mobile_login_boxes:
            st.markdown(f'<div class="care-login-box">{html.escape(info)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)
    office_requires_explicit_login = (
        app_variant == VARIANT_OFFICE
        and not bool(st.session_state.get("office_login_explicit"))
    )
    has_auth_uid = bool(st.session_state.get("auth_uid"))
    has_auth_tokens = bool(
        st.session_state.get("access_token") and st.session_state.get("refresh_token")
    )
    if not has_auth_uid and has_auth_tokens:
        # Magic-link callbacks can occasionally land with tokens set before auth_uid hydration.
        # Re-resolve mapping once so Mobile/Office login can continue without forcing a loop.
        get_mapping_status()
        has_auth_uid = bool(st.session_state.get("auth_uid"))
    if has_auth_uid and not office_requires_explicit_login:
        allow_manual_login = False
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if care_found:
            if care_record:
                st.session_state["active_role"] = "care_hub"
                st.session_state["active_care_home_id"] = care_record.get("care_home_id")
                st.session_state["care_access_level"] = normalize_care_access_level(
                    care_record.get("care_access_level")
                )
            if app_variant == VARIANT_OFFICE and not current_user_can_access_office():
                st.error("This account has Mobile access.")
                st.info("Mobile Support users cannot use Family Office setup, registration, setup variables, or Account & Security.")
                if st.button("Go to Mobile login", key="care_login_mobile_only_go_mobile"):
                    set_route(get_login_route(VARIANT_MOBILE))
                if st.button("Sign out", key="care_login_mobile_only_sign_out"):
                    sign_out_user("care_hub")
                return
            if app_variant == VARIANT_MOBILE:
                st.markdown("### Mobile PIN access")
                if render_mobile_pin_gate(st.session_state.get("access_token")):
                    set_route(get_home_route(app_variant))
            elif app_variant == VARIANT_OFFICE and is_office_mfa_required():
                set_route("/care-hub/mfa")
                st.rerun()
            else:
                set_route(get_home_route(app_variant))
        elif family_found:
            st.error("This browser is signed in to Family Hub.")
            st.info("Sign out of Family Hub before using Mobile or Family Office in this browser.")
            if st.button("Sign out of Family Hub", key="care_login_wrong_logout"):
                sign_out_user("care_hub")
        else:
            if error:
                normalized_error = str(error).strip().lower()
                transient_session_error = (
                    "resource temporarily unavailable" in normalized_error
                    or "errno 11" in normalized_error
                )
                if transient_session_error:
                    st.warning(
                        "Temporary session check issue detected. Your session is still active; please retry."
                    )
                else:
                    st.error(error)
                    st.info("Please sign in again.")
            else:
                st.error("Account not set up yet.")
        if not allow_manual_login:
            return

    if app_variant == VARIANT_MOBILE:
        email = st.text_input("Mobile user email", key="care_mobile_login_email")
        normalized_email = email.strip().lower()
        st.caption(
            "For first sign-in (or expired session), enter your Mobile Support email and request a secure link."
        )
        action_cols = st.columns(2, gap="small")
        with action_cols[0]:
            send_link_pressed = st.button(
                "Send secure link", key="care_mobile_login_send_link"
            )
        with action_cols[1]:
            resend_link_pressed = st.button(
                "Resend secure link", key="care_mobile_login_resend_link"
            )
        if send_link_pressed or resend_link_pressed:
            ok, message = send_magic_link_email(
                normalized_email,
                app_variant=VARIANT_MOBILE,
                should_create_user=False,
            )
            if ok:
                st.success(message)
            else:
                st.error(message)
        render_public_landing_link(
            "Back to hub selection",
            key=f"care_login_back_public_{app_variant}",
        )
        return

    email = st.text_input("Family Office email", key="care_login_email")
    password = st.text_input(
        "Office password", type="password", key="care_login_password"
    )
    normalized_email = email.strip().lower()
    normalized_password = password.strip()
    st.caption("Family Office uses organiser credentials. This is separate from Family Hub and Mobile PIN access.")

    st.markdown('<div id="vm-login-actions"></div>', unsafe_allow_html=True)
    show_sign_out = st.session_state.get("auth_uid")
    action_cols = st.columns(3, gap="small")
    with action_cols[0]:
        submit_login = st.button("Log in", key="care_login_submit")
    with action_cols[1]:
        forgot_pressed = st.button("Forgot password?", key="care_login_forgot")
    with action_cols[2]:
        sign_out_pressed = (
            st.button("Sign out", key="care_login_sign_out") if show_sign_out else False
        )

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
                            st.session_state["care_access_level"] = normalize_care_access_level(
                                care_record.get("care_access_level")
                            )
                        if app_variant == VARIANT_OFFICE and not current_user_can_access_office():
                            st.error("This account has Mobile access.")
                            st.info("Mobile Support users cannot use Family Office setup, registration, setup variables, or Account & Security.")
                            return
                        if app_variant == VARIANT_OFFICE:
                            st.session_state["office_login_explicit"] = True
                        log_audit_event(
                            "login_success",
                            "care_hub",
                            st.session_state.get("active_care_home_id"),
                        )
                        if is_office_mfa_required():
                            set_route("/care-hub/mfa")
                            st.rerun()
                        else:
                            set_route(get_home_route(VARIANT_OFFICE))
                    elif family_found:
                        st.error("This account is registered for Family Hub.")
                        st.info("Use a Mobile Support or Family Office account for this route.")
                    else:
                        if mapping_error:
                            st.error(mapping_error)
                            st.info("Please sign in again.")
                        else:
                            st.error("Account not set up yet.")

    if sign_out_pressed:
        sign_out_user("care_hub")
    if forgot_pressed:
        ok, message = send_password_reset_email(normalized_email, app_variant=app_variant)
        if ok:
            st.success(message)
        else:
            st.error(message)
    render_public_landing_link(
        "Back to hub selection",
        key=f"care_login_back_public_{app_variant}",
    )


def render_care_hub() -> None:
    require_care_access()
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if get_app_variant() == VARIANT_MOBILE:
        # Keep runtime behavior locked to Mobile when the app is launched as Mobile,
        # even if route history/query params drift toward Office routes.
        runtime_variant = VARIANT_MOBILE
    if runtime_variant == VARIANT_MOBILE and not is_mobile_pin_verified_for_session():
        set_route(get_login_route(VARIANT_MOBILE))
        st.stop()
    run_daily_audit_log_retention_purge()
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
  .vm-direction-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 2px 0 8px;
  }}
  .vm-direction-chip {{
    border: 1px solid rgba(31,31,31,0.16);
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.8rem;
    line-height: 1.4;
    background: rgba(255,255,255,0.6);
  }}
  .care-flow-title {{
    border-radius: 8px;
    padding: 8px 10px;
    margin: 0 0 8px 0;
    font-weight: 700;
    line-height: 1.35;
  }}
  .care-flow-title.resident {{
    background: rgba(47, 107, 79, 0.10);
    border: 1px solid rgba(47, 107, 79, 0.24);
  }}
  .care-flow-title.inbound {{
    background: #f7f0ff;
    border: 1px solid rgba(123, 44, 191, 0.32);
  }}
  .care-flow-title.office {{
    background: #f0ffff;
    border: 1px solid rgba(0, 140, 140, 0.32);
  }}
  .care-flow-title.practical {{
    background: #fff7f3;
    border: 1px solid rgba(201, 95, 53, 0.32);
  }}
  .care-flow-title.outbound {{
    background: #ffffe6;
    border: 1px solid rgba(181, 155, 0, 0.32);
  }}
  .care-channel-note {{
    color: rgba(31,31,31,0.62);
    font-size: 0.88rem;
    margin: -2px 0 10px 0;
    line-height: 1.35;
  }}
  .care-flow-box {{
    border-radius: 10px;
    padding: 10px 10px 2px 10px;
    margin: 0 0 10px 0;
  }}
  .care-flow-box.resident {{
    background: rgba(47, 107, 79, 0.05);
    border: 1px solid rgba(47, 107, 79, 0.22);
  }}
  .care-flow-box.inbound {{
    background: #f8f2ff;
    border: 1px solid rgba(123, 44, 191, 0.28);
  }}
  .care-flow-box.office {{
    background: #f4ffff;
    border: 1px solid rgba(0, 140, 140, 0.28);
  }}
  .care-flow-box.practical {{
    background: #fff8f5;
    border: 1px solid rgba(201, 95, 53, 0.28);
  }}
  .care-flow-box.outbound {{
    background: #ffffe8;
    border: 1px solid rgba(181, 155, 0, 0.28);
  }}
  div[class*="st-key-office-channel-family-messages"] {{
    background: #f8f2ff !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-mobile-message"] {{
    background: #f8f2ff !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-mobile-channel-office-message"] {{
    background: #ffffe8 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-family-message"] {{
    background: #ffffe8 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-family-messages"] {{
    background: #f8f2ff !important;
    border: 6px solid #d9dee3 !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-family-update"] {{
    background: #f4ffff !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-practical-request"] {{
    background: #fff8f5 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
  div[class*="st-key-office-channel-noticeboard"] {{
    background: #f4faf3 !important;
    border: 6px solid #d9dee3 !important;
    border-radius: 18px !important;
    padding: 14px 14px 8px 18px !important;
    margin: 12px 0 18px !important;
  }}
</style>
""",
        unsafe_allow_html=True,
    )
    def render_care_flow_title(text: str, tone: str) -> None:
        safe_text = html.escape(text)
        safe_tone = html.escape(tone)
        st.markdown(
            f"<div class='care-flow-title {safe_tone}'>{safe_text}</div>",
            unsafe_allow_html=True,
        )
    def render_care_channel_note(text: str) -> None:
        safe_text = html.escape(text)
        st.markdown(
            f"<div class='care-channel-note'>{safe_text}</div>",
            unsafe_allow_html=True,
        )
    access_token = st.session_state.get("access_token")
    page_title = "Mobile" if runtime_variant == VARIANT_MOBILE else get_at_home_voicemail_label(access_token)
    render_page_header(page_title)
    render_dev_stage_level_status(access_token)
    if runtime_variant == VARIANT_MOBILE:
        render_public_landing_button("Back to hub selection")
    elif runtime_variant == VARIANT_OFFICE:
        render_public_landing_button("Back to hub selection")
    if (
        runtime_variant == VARIANT_MOBILE
        and st.session_state.pop("mobile_pin_just_accepted", False)
    ):
        st.success("Mobile PIN accepted.")
    mobile_status_message = st.session_state.pop("mobile_status_message", "")
    if runtime_variant == VARIANT_MOBILE and mobile_status_message:
        st.info(mobile_status_message)
    # Top action buttons removed; navigation is handled through the header menu.
    # Action row already rendered at the top of the page.

    transcript_policy_mode = get_transcript_policy_mode(access_token)
    operating_mode = get_operating_mode(access_token)
    lifecycle_stage = get_lifecycle_stage(access_token)
    lifecycle_stage_number = normalize_lifecycle_stage(lifecycle_stage)
    communication_level = get_communication_level(access_token)
    lifecycle_policy = get_lifecycle_policy(lifecycle_stage, operating_mode, communication_level)
    lifecycle_stage_label = str(lifecycle_policy.get("lifecycle_stage_label") or "")
    at_home_lifecycle_stage = lifecycle_stage_number in {1, 2, 3}
    shared_coordination_stage = lifecycle_stage_number in {1, 2, 3}
    workspace_labels = get_workspace_labels_for_lifecycle_stage(lifecycle_stage_number)
    family_messaging_enabled = bool(lifecycle_policy.get("enable_family_messaging"))
    requests_enabled = bool(lifecycle_policy.get("enable_requests"))
    office_channel_enabled = bool(lifecycle_policy.get("enable_office_channel"))
    mobile_channel_enabled = bool(lifecycle_policy.get("enable_mobile_channel"))
    family_led_mode = operating_mode == OPERATING_MODE_PERSONAL_USE
    voice_messaging_enabled = family_messaging_enabled and not (
        family_led_mode or at_home_lifecycle_stage
    )
    main_contact_name = get_main_contact_name(access_token)
    subject_singular = str(workspace_labels.get("subject_singular") or "resident")
    subject_singular_title = str(workspace_labels.get("subject_singular_title") or "Resident")
    subject_plural = str(workspace_labels.get("subject_plural") or "residents")
    subject_plural_title = str(workspace_labels.get("subject_plural_title") or "Residents")
    personal_mode_ok, personal_mode_failures = validate_personal_mode_runtime(operating_mode)
    if family_led_mode and not personal_mode_ok:
        st.error(
            "Personal mode copy guard failed. Please open Operational Variables and confirm mode settings."
        )
        st.caption("Guard details: " + "; ".join(personal_mode_failures))
        return
    residents = fetch_care_home_residents(access_token)
    if family_led_mode or at_home_lifecycle_stage:
        person_display_name = _resolve_person_display_name_from_residents(
            residents,
            selected_resident_id=str(st.session_state.get("care_selected_resident_id") or "").strip(),
        )
        if person_display_name:
            st.session_state["circle_person_display_name"] = person_display_name
        else:
            st.session_state.pop("circle_person_display_name", None)
    render_care_home_identity_banner(access_token)
    channel_enabled_for_variant = (
        mobile_channel_enabled if runtime_variant == VARIANT_MOBILE else office_channel_enabled
    )
    if not channel_enabled_for_variant:
        st.info("This channel is inactive for the current situation.")
    elif not (voice_messaging_enabled or office_channel_enabled or requests_enabled):
        st.info("Messaging is inactive for the current situation.")
    is_care_queue_variant_screen = runtime_variant in {VARIANT_MOBILE, VARIANT_OFFICE}
    include_care_home_in_resident_labels = (
        runtime_variant == VARIANT_MOBILE and not family_led_mode and not at_home_lifecycle_stage
    )
    contacts_by_resident: dict[str, list[dict]] = {}

    show_person_search = lifecycle_stage_number == 4 and not family_led_mode
    resident_search_container = st.container(border=bool(show_person_search or family_led_mode))
    search_value = ""
    if show_person_search:
        with resident_search_container:
            if runtime_variant == VARIANT_MOBILE:
                render_care_flow_title(f"Search {subject_plural}", "resident")
            search_value = st.text_input(
                f"Search {subject_plural}",
                key="care_resident_search",
                label_visibility="collapsed",
                placeholder=f"Search {subject_plural}",
            )
    elif family_led_mode:
        with resident_search_container:
            if runtime_variant == VARIANT_MOBILE:
                render_care_flow_title(subject_plural_title, "resident")

    if show_person_search and search_value:
        search_lower = search_value.strip().lower()
        search_tokens = [token for token in search_lower.split() if token]

        def resident_matches_search(resident: dict) -> bool:
            preferred = str(resident.get("preferred_name") or "").strip().lower()
            surname = str(resident.get("surname") or "").strip().lower()
            room = str(resident.get("room") or "").strip().lower()
            care_home = str(resident.get("care_home") or "").strip().lower()
            full_name = " ".join(part for part in [preferred, surname] if part).strip()
            searchable_fields = [preferred, surname, full_name, room, care_home]
            if any(search_lower in field for field in searchable_fields if field):
                return True
            if search_tokens and full_name:
                return all(token in full_name for token in search_tokens)
            return False

        residents = [
            resident
            for resident in residents
            if resident_matches_search(resident)
        ]

    if not residents:
        if search_value:
            st.info(f"No {subject_plural} match that search.")
        return

    if is_care_queue_variant_screen:
        resident_option_ids = [resident["id"] for resident in residents]
        resident_label_by_id = {}
        for resident in residents:
            resident_label_by_id[resident["id"]] = format_resident_identity_label(
                resident,
                operating_mode=operating_mode,
                include_room=bool(workspace_labels.get("show_room")),
                include_care_home=include_care_home_in_resident_labels,
                separator=" | ",
            )
        selected_resident_label = ""
        with resident_search_container:
            if len(resident_option_ids) == 1:
                selected_resident_id = resident_option_ids[0]
                selected_resident_label = resident_label_by_id.get(
                    selected_resident_id, subject_singular_title
                )
            else:
                if family_led_mode or at_home_lifecycle_stage:
                    selected_resident_id = st.radio(
                        subject_plural_title,
                        resident_option_ids,
                        format_func=lambda resident_id: resident_label_by_id.get(
                            resident_id, subject_singular_title
                        ),
                        key="care_selected_resident_id",
                    )
                else:
                    selected_resident_id = st.selectbox(
                        f"Select {subject_singular}",
                        resident_option_ids,
                        format_func=lambda resident_id: resident_label_by_id.get(
                            resident_id, subject_singular_title
                        ),
                        key="care_selected_resident_id",
                    )
                selected_resident_label = resident_label_by_id.get(
                    selected_resident_id, subject_singular_title
                )
            if runtime_variant == VARIANT_MOBILE and not family_led_mode:
                if at_home_lifecycle_stage:
                    st.caption("Selected: " + selected_resident_label)
                else:
                    st.caption(f"{subject_singular_title} selected: " + selected_resident_label)
        residents = [
            resident for resident in residents if resident["id"] == selected_resident_id
        ]

    send_state = st.session_state.setdefault("care_send_state", {})
    has_pending_recording = any(
        bool((entry or {}).get("recording_bytes") or (entry or {}).get("office_recording_bytes"))
        for entry in send_state.values()
        if isinstance(entry, dict)
    )
    current_variant = runtime_variant
    disable_live_refresh = (
        has_pending_recording
        or current_variant == VARIANT_OFFICE
        or not is_variant_live_refresh_enabled(current_variant)
    )
    trigger_live_message_refresh("care_live_refresh", disabled=disable_live_refresh)
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
                    "recording_fingerprint": None,
                    "recording_input_nonce": 0,
                    "office_recording_bytes": None,
                    "office_recording_mime_type": "audio/wav",
                    "office_preview_confirmed": False,
                    "office_recording_fingerprint": None,
                    "office_recording_input_nonce": 0,
                    "office_last_sent_fingerprint": None,
                    "office_ignore_audio_until": 0.0,
                    "office_last_sent_label": None,
                    "office_update_category": OFFICE_UPDATE_CATEGORIES[0],
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
                "recording_fingerprint": None,
                "recording_input_nonce": 0,
                "office_recording_bytes": None,
                "office_recording_mime_type": "audio/wav",
                "office_preview_confirmed": False,
                "office_recording_fingerprint": None,
                "office_recording_input_nonce": 0,
                "office_last_sent_fingerprint": None,
                "office_ignore_audio_until": 0.0,
                "office_last_sent_label": None,
                "office_update_category": OFFICE_UPDATE_CATEGORIES[0],
            },
        )
        full_name = get_resident_full_name(resident, operating_mode=operating_mode)
        person_first_name = full_name.split()[0] if full_name.split() else full_name
        if runtime_variant not in {VARIANT_MOBILE, VARIANT_OFFICE}:
            with st.container(border=True):
                if family_led_mode or at_home_lifecycle_stage:
                    render_care_flow_title(full_name, "resident")
                else:
                    render_care_flow_title(f"{subject_singular_title} ({full_name})", "resident")
                if not family_led_mode and not at_home_lifecycle_stage:
                    st.markdown(f"**{full_name}**")
                care_home_name = str(resident.get("care_home") or "").strip()
                if care_home_name:
                    if bool(workspace_labels.get("show_room")):
                        st.markdown(f"{workspace_labels.get('organisation_label')}: {care_home_name}")
                room_value = str(resident.get("room") or "").strip()
                if room_value and bool(workspace_labels.get("show_room")):
                    st.markdown(f"{workspace_labels.get('room_label')} {room_value}")

        channel_enabled_for_current_variant = (
            mobile_channel_enabled if runtime_variant == VARIANT_MOBILE else office_channel_enabled
        )
        communication_enabled = channel_enabled_for_current_variant and (
            office_channel_enabled or voice_messaging_enabled or requests_enabled
        )
        if not communication_enabled:
            if not channel_enabled_for_current_variant:
                channel_name = "Mobile Channel" if runtime_variant == VARIANT_MOBILE else "Office Channel"
                st.caption(f"{channel_name} is inactive in this situation.")
            continue

        contacts = contacts_by_resident.get(resident_id)
        if contacts is None:
            contacts = fetch_family_users_for_resident(resident_id, access_token)
            contacts_by_resident[resident_id] = contacts
        if not contacts:
            if runtime_variant == VARIANT_OFFICE:
                no_contacts_subject = full_name if at_home_lifecycle_stage else f"this {subject_singular}"
                st.warning(
                    f"No Family Members are linked to {no_contacts_subject} yet. "
                    f"Register a contact in {workspace_labels.get('office_label')} before sending messages."
                )
                if st.button(
                    "Register/invite Family Member now",
                    key=f"care_register_family_cta_{resident_id}",
                    use_container_width=True,
                ):
                    set_route("/care-hub/register-family")
                    st.rerun()
            else:
                no_contacts_subject = full_name if at_home_lifecycle_stage else f"this {subject_singular}"
                st.warning(
                    f"No Family Members are linked to {no_contacts_subject} yet. "
                    "Ask Office staff to register a contact."
                )
            continue
        is_mobile_variant = runtime_variant == VARIANT_MOBILE
        is_office_variant = runtime_variant == VARIANT_OFFICE
        is_queue_playback_variant = is_mobile_variant
        send_guard_scope = f"care_send_{resident_id}"
        manual_selection_key = f"care_manual_selected_{resident_id}"
        manual_selected_active = bool(st.session_state.get(manual_selection_key, False))
        queue_unread_count = 0
        queue_next_contact = None
        queue_unread_contacts: list[dict] = []
        if voice_messaging_enabled and contacts and (is_mobile_variant or is_office_variant):
            (
                queue_unread_count,
                queue_next_contact,
                queue_unread_contacts,
            ) = get_family_queue_status_for_resident(
                resident_id,
                resident["care_home_id"],
                contacts,
                access_token,
            )
        selected_contact = None
        latest = None
        queue_mode_label = ""
        if not contacts:
            st.markdown(
                '<div class="vm-muted-line">No linked family contacts.</div>',
                unsafe_allow_html=True,
            )
            state["selected_contact_id"] = None
            state["selected_contact_user_id"] = None
        elif is_queue_playback_variant:
            mobile_play_requested_key = f"care_mobile_play_requested_{resident_id}"
            keep_current_after_start = bool(st.session_state.get(mobile_play_requested_key, False))
            current_user_id = str(state.get("selected_contact_user_id") or "").strip()
            current_contact_id = str(state.get("selected_contact_id") or "").strip()
            manual_selected = manual_selected_active
            if manual_selected and (current_user_id or current_contact_id):
                selected_contact = None
                if current_user_id:
                    selected_contact = next(
                        (
                            c
                            for c in contacts
                            if str(c.get("auth_user_id") or "").strip() == current_user_id
                        ),
                        None,
                    )
                if selected_contact is None and current_contact_id:
                    selected_contact = next(
                        (
                            c
                            for c in contacts
                            if str(c.get("id") or "").strip() == current_contact_id
                        ),
                        None,
                    )
                if selected_contact:
                    latest = fetch_latest_message_for_contact_with_mapping_repair(
                        resident_id,
                        access_token,
                        selected_contact,
                        channel="resident_family",
                        include_audio=True,
                    )
                    queue_mode_label = "Manual selection"
                else:
                    st.session_state[manual_selection_key] = False
                    manual_selected_active = False
            if selected_contact is None and keep_current_after_start and (current_user_id or current_contact_id):
                selected_contact = next(
                    (
                        c
                        for c in contacts
                        if (
                            (current_user_id and str(c.get("auth_user_id") or "").strip() == current_user_id)
                            or (current_contact_id and str(c.get("id") or "").strip() == current_contact_id)
                        )
                    ),
                    None,
                )
                if selected_contact:
                    queue_mode_label = "Session order"

            if selected_contact is None:
                if queue_next_contact is not None:
                    selected_contact = queue_next_contact
                    queue_mode_label = (
                        "Unplayed first (round 0)" if queue_unread_count > 0 else "Session order"
                    )
                else:
                    contacts_sorted = sort_contacts_for_playback(contacts)
                    selected_contact = contacts_sorted[0] if contacts_sorted else None
                    if selected_contact:
                        queue_mode_label = "Session order"

            if selected_contact is not None and latest is None:
                latest = fetch_latest_message_for_contact_with_mapping_repair(
                    resident_id,
                    access_token,
                    selected_contact,
                    channel="resident_family",
                    include_audio=True,
                )
                if latest is None and not queue_mode_label:
                    queue_mode_label = "No family messages available."
            state["selected_contact_id"] = (selected_contact or {}).get("id")
            state["selected_contact_user_id"] = (selected_contact or {}).get("auth_user_id")
        elif is_office_variant:
            if selected_contact is None:
                # Respect explicit manual selection first; otherwise default to queue-next.
                if state.get("selected_contact_id"):
                    selected_contact = next(
                        (c for c in contacts if c.get("id") == state.get("selected_contact_id")),
                        None,
                    )
                if selected_contact is None:
                    selected_contact = queue_next_contact
                if selected_contact is None and queue_unread_contacts:
                    selected_contact = queue_unread_contacts[0]
                if selected_contact is None:
                    sorted_contacts = sort_contacts_for_playback(contacts)
                    selected_contact = sorted_contacts[0] if sorted_contacts else None
                if selected_contact:
                    state["selected_contact_id"] = selected_contact.get("id")
                    state["selected_contact_user_id"] = selected_contact.get("auth_user_id")
                    latest = fetch_latest_message_for_contact_with_mapping_repair(
                        resident_id,
                        access_token,
                        selected_contact,
                        channel="resident_family",
                        include_audio=True,
                    )
        else:
            contacts_sorted = sort_contacts_for_playback(contacts)
            contact_search = st.text_input(
                "Search family contacts",
                key=f"care_contact_search_{resident_id}",
                placeholder="Type a name or relationship",
            )
            search_term = (contact_search or "").strip().casefold()
            filtered_contacts = [
                contact
                for contact in contacts_sorted
                if (
                    not search_term
                    or search_term in str(contact.get("full_name") or "").casefold()
                    or search_term in str(contact.get("relationship") or "").casefold()
                )
            ]
            if not filtered_contacts:
                st.info("No matching family contacts. Showing all contacts.")
                filtered_contacts = contacts_sorted

            st.caption(
                f"Matching contacts: {len(filtered_contacts)}"
            )
            preview_limit = 6
            for preview_contact in filtered_contacts[:preview_limit]:
                preview_relationship = (preview_contact.get("relationship") or "").strip()
                if preview_relationship:
                    st.markdown(
                        f"- {preview_contact.get('full_name')} ({preview_relationship.title()})"
                    )
                else:
                    st.markdown(f"- {preview_contact.get('full_name')}")
            if len(filtered_contacts) > preview_limit:
                st.caption(f"Showing first {preview_limit} above. Use selector for full list.")

            contact_options: list[str] = []
            for contact in filtered_contacts:
                relationship = (contact.get("relationship") or "").strip()
                if relationship:
                    contact_options.append(f"{contact['full_name']} - {relationship.title()}")
                else:
                    contact_options.append(f"{contact['full_name']} - Family Member")

            current_selected_id = state.get("selected_contact_id")
            default_index = 0
            if current_selected_id:
                for idx, contact in enumerate(filtered_contacts):
                    if contact.get("id") == current_selected_id:
                        default_index = idx
                        break
            selected_index = st.radio(
                "Select family contact",
                options=list(range(len(filtered_contacts))),
                index=default_index if filtered_contacts else 0,
                format_func=lambda idx: contact_options[idx],
                key=f"care_recipient_{resident_id}",
            )
            selected_contact = filtered_contacts[selected_index]
            if selected_contact["id"] != state.get("selected_contact_id"):
                state["selected_contact_id"] = selected_contact["id"]
                state["selected_contact_user_id"] = selected_contact.get("auth_user_id")
                state["recording_bytes"] = None
                state["recording_mime_type"] = "audio/wav"
                state["recording_fingerprint"] = None
                reset_outbox_state_on_new_recording(
                    state,
                    ack_widget_key=f"care_listened_{resident_id}",
                    clear_care_last_sent_for_resident=resident_id,
                )

            if selected_contact is None and state.get("selected_contact_id"):
                selected_contact = next(
                    (c for c in contacts if c["id"] == state.get("selected_contact_id")),
                    None,
                )

        selected_contact_name = (
            (selected_contact or {}).get("full_name") or "family contact"
        )
        ordered_contacts_for_queue = sort_contacts_for_playback(contacts)
        queue_position_by_contact_id = {
            str(contact.get("id") or "").strip(): idx + 1
            for idx, contact in enumerate(ordered_contacts_for_queue)
            if str(contact.get("id") or "").strip()
        }
        effective_queue_next_contact = queue_next_contact
        if (
            is_mobile_variant
            and queue_mode_label in {"Session order", "Played cycle", "Unplayed first (round 0)"}
            and selected_contact is not None
        ):
            effective_queue_next_contact = selected_contact
        if effective_queue_next_contact is None and selected_contact is not None:
            effective_queue_next_contact = selected_contact
        if effective_queue_next_contact is None and contacts:
            if ordered_contacts_for_queue:
                effective_queue_next_contact = ordered_contacts_for_queue[0]
        mobile_play_requested_key = f"care_mobile_play_requested_{resident_id}"
        mobile_advance_pointer_key = f"care_mobile_advance_pointer_{resident_id}"
        family_message_panel = (
            st.container(
                border=True,
                key=(
                    f"mobile-channel-family-messages-{resident_id}"
                    if is_mobile_variant
                    else f"office-channel-family-messages-{resident_id}"
                ),
            )
            if voice_messaging_enabled and contacts and (is_mobile_variant or is_office_variant)
            else None
        )
        if voice_messaging_enabled and contacts and (is_mobile_variant or is_office_variant):
            if is_mobile_variant:
                with family_message_panel:
                    render_care_flow_title("Family messages", "inbound")
                    st.caption(f"Unplayed list ({queue_unread_count})")
                    if queue_unread_contacts:
                        for unread_contact in queue_unread_contacts:
                            unread_name = (unread_contact.get("full_name") or "family contact").strip()
                            unread_relationship = ((unread_contact.get("relationship") or "").strip())
                            unread_contact_id = str(unread_contact.get("id") or "").strip()
                            unread_position = queue_position_by_contact_id.get(unread_contact_id)
                            unread_prefix = f"{unread_position}. " if unread_position else ""
                            unread_display = (
                                f"{unread_prefix}{unread_name} ({unread_relationship.title()})"
                                if unread_relationship
                                else f"{unread_prefix}{unread_name} (Family Member)"
                            )
                            st.markdown(f"- {unread_display}")
                    else:
                        st.caption("No unplayed messages.")
                    send_guard_scope = f"care_send_{resident_id}"
                    send_guard_remaining = get_send_guard_remaining_seconds(send_guard_scope)
                    send_guard_active = send_guard_remaining > 0
                    if send_guard_active:
                        recent_sent = st.session_state.get("care_last_sent")
                        recent_sent_message = (
                            str((recent_sent or {}).get("message") or "Message sent to all Family Members.")
                            if isinstance(recent_sent, dict)
                            and str((recent_sent or {}).get("resident_id") or "").strip() == str(resident_id).strip()
                            and (time.time() - float((recent_sent or {}).get("sent_at_ts") or 0.0))
                            <= float(SEND_ACTION_GUARD_SECONDS + 2)
                            else ""
                        )
                        if recent_sent_message:
                            st.success(recent_sent_message)

            else:
                with family_message_panel:
                    if family_led_mode or at_home_lifecycle_stage:
                        render_care_flow_title(full_name, "resident")
                    else:
                        render_care_flow_title(
                            f"{subject_singular_title} ({full_name})",
                            "resident",
                        )
                    if not family_led_mode and not at_home_lifecycle_stage:
                        st.markdown(f"**{full_name}**")
                    care_home_name = str(resident.get("care_home") or "").strip()
                    if care_home_name and bool(workspace_labels.get("show_room")):
                        st.markdown(f"{workspace_labels.get('organisation_label')}: {care_home_name}")
                    room_value = str(resident.get("room") or "").strip()
                    if room_value and bool(workspace_labels.get("show_room")):
                        st.markdown(f"{workspace_labels.get('room_label')} {room_value}")
                    st.caption(f"Unplayed list ({queue_unread_count})")
                    if queue_unread_contacts:
                        for unread_contact in queue_unread_contacts:
                            unread_name = (unread_contact.get("full_name") or "family contact").strip()
                            unread_relationship = ((unread_contact.get("relationship") or "").strip())
                            unread_contact_id = str(unread_contact.get("id") or "").strip()
                            unread_position = queue_position_by_contact_id.get(unread_contact_id)
                            unread_prefix = f"{unread_position}. " if unread_position else ""
                            unread_display = (
                                f"{unread_prefix}{unread_name} ({unread_relationship.title()})"
                                if unread_relationship
                                else f"{unread_prefix}{unread_name} (Family Member)"
                            )
                            st.markdown(f"- {unread_display}")
                    else:
                        st.caption("No unplayed messages.")
                    send_guard_scope = f"care_send_{resident_id}"
                    send_guard_remaining = get_send_guard_remaining_seconds(send_guard_scope)
                    send_guard_active = send_guard_remaining > 0
                    if send_guard_active:
                        recent_sent = st.session_state.get("care_last_sent")
                        recent_sent_message = (
                            str((recent_sent or {}).get("message") or "Message sent to all Family Members.")
                            if isinstance(recent_sent, dict)
                            and str((recent_sent or {}).get("resident_id") or "").strip() == str(resident_id).strip()
                            and (time.time() - float((recent_sent or {}).get("sent_at_ts") or 0.0))
                            <= float(SEND_ACTION_GUARD_SECONDS + 2)
                            else ""
                        )
                        if recent_sent_message:
                            st.success(recent_sent_message)

                    if st.button(
                        "Play next family message",
                        key=f"care_play_next_{resident_id}",
                        disabled=send_guard_active,
                        use_container_width=True,
                    ):
                        st.session_state[manual_selection_key] = False
                        manual_selected_active = False
                        selected_contact, latest, queue_mode_selected = select_next_family_message_for_mobile(
                            resident_id,
                            resident["care_home_id"],
                            contacts,
                            access_token,
                        )
                        if selected_contact:
                            latest = fetch_latest_message_for_contact_with_mapping_repair(
                                resident_id,
                                access_token,
                                selected_contact,
                                channel="resident_family",
                                include_audio=True,
                            ) or latest
                            selected_contact_user_id = str(
                                (latest or {}).get("contact_user_id")
                                or selected_contact.get("auth_user_id")
                                or ""
                            ).strip()
                            state["selected_contact_id"] = selected_contact.get("id")
                            state["selected_contact_user_id"] = selected_contact_user_id
                            queue_mode_label = queue_mode_selected or "Session order"
                            st.session_state[mobile_play_requested_key] = True
                            st.session_state[mobile_advance_pointer_key] = False
                            listen_prefix = "care_mobile" if is_mobile_variant else "care_office"
                            st.session_state[f"{listen_prefix}_listened_confirm_{resident_id}"] = False
                        else:
                            playable_subject = full_name if at_home_lifecycle_stage else f"this {subject_singular}"
                            st.warning(
                                f"No playable family messages are available for {playable_subject}."
                            )
                            st.session_state[mobile_play_requested_key] = False
                            st.session_state[mobile_advance_pointer_key] = False
        if voice_messaging_enabled and (is_mobile_variant or is_office_variant):
            if latest is None:
                if selected_contact is not None:
                    latest = fetch_latest_message_for_contact_with_mapping_repair(
                        resident_id,
                        access_token,
                        selected_contact,
                        channel="resident_family",
                        include_audio=True,
                    )
                else:
                    latest = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=state.get("selected_contact_user_id"),
                        channel="resident_family",
                        include_audio=True,
                    )
            elif not (
                latest.get("audio_storage_path")
                or latest.get("audio_object_path")
            ):
                if selected_contact is not None:
                    latest = fetch_latest_message_for_contact_with_mapping_repair(
                        resident_id,
                        access_token,
                        selected_contact,
                        channel="resident_family",
                        include_audio=True,
                    )
                else:
                    latest = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=state.get("selected_contact_user_id"),
                        channel="resident_family",
                        include_audio=True,
                    )
            if latest is None and not manual_selected_active:
                latest = fetch_latest_message(
                    resident_id,
                    "to_resident",
                    access_token,
                    channel="resident_family",
                    include_audio=True,
                )
            latest_contact_user_id = str((latest or {}).get("contact_user_id") or "").strip()
            selected_contact_user_id = str((selected_contact or {}).get("auth_user_id") or "").strip()
            if selected_contact is not None and selected_contact_user_id:
                if latest_contact_user_id != selected_contact_user_id and latest is not None:
                    if latest_contact_user_id:
                        matched_contact = next(
                            (
                                c
                                for c in contacts
                                if str(c.get("auth_user_id") or "").strip() == latest_contact_user_id
                            ),
                            None,
                        )
                        if matched_contact is not None:
                            selected_contact = matched_contact
                            state["selected_contact_id"] = matched_contact.get("id")
                            state["selected_contact_user_id"] = matched_contact.get("auth_user_id")
            elif latest_contact_user_id:
                matched_contact = next(
                    (
                        c
                        for c in contacts
                        if str(c.get("auth_user_id") or "").strip() == latest_contact_user_id
                    ),
                    None,
                )
                if matched_contact is not None:
                    selected_contact = matched_contact
                    state["selected_contact_id"] = matched_contact.get("id")
                    state["selected_contact_user_id"] = matched_contact.get("auth_user_id")
            elif selected_contact is None:
                current_contact_id = str(state.get("selected_contact_id") or "").strip()
                if current_contact_id:
                    matched_contact = next(
                        (
                            c
                            for c in contacts
                            if str(c.get("id") or "").strip() == current_contact_id
                        ),
                        None,
                    )
                    if matched_contact is not None:
                        selected_contact = matched_contact
                        state["selected_contact_id"] = matched_contact.get("id")
                        state["selected_contact_user_id"] = matched_contact.get("auth_user_id")

            if (
                is_queue_playback_variant
                and queue_mode_label == "No family messages available."
                and selected_contact is not None
            ):
                queue_mode_label = "Session order"
            with (family_message_panel or st.container(border=True)):
                selected_contact_name_for_title = (
                    ((selected_contact or {}).get("full_name") or "").strip()
                )
                from_contact_suffix = (
                    f" (from {selected_contact_name_for_title})"
                    if selected_contact_name_for_title
                    else ""
                )
                render_care_flow_title(
                    (
                        f"Latest family message to {full_name}{from_contact_suffix}"
                        if at_home_lifecycle_stage
                        else f"Latest family message to {subject_singular} ({full_name}){from_contact_suffix}"
                    ),
                    "inbound",
                )
                mobile_play_requested = bool(st.session_state.get(mobile_play_requested_key, False))
                should_attempt_playback = (not is_mobile_variant) or mobile_play_requested or bool(latest)
                playback_source = None
                playback_source_kind = "none"
                should_show_message = should_attempt_playback
                if should_attempt_playback:
                    playback_source, playback_source_kind = resolve_audio_playback_source(
                        latest,
                        access_token=access_token,
                    )
                    if (
                        not playback_source
                        and (is_mobile_variant or is_office_variant)
                        and not manual_selected_active
                    ):
                        recovery_contact, recovery_latest, recovery_source, recovery_kind = (
                            find_next_playable_family_message_in_order(
                                resident_id,
                                contacts,
                                access_token,
                                start_after_contact_user_id=state.get("selected_contact_user_id"),
                                channel="resident_family",
                            )
                        )
                        if recovery_contact is not None and recovery_latest is not None and recovery_source:
                            selected_contact = recovery_contact
                            latest = recovery_latest
                            playback_source = recovery_source
                            playback_source_kind = recovery_kind
                            state["selected_contact_id"] = recovery_contact.get("id")
                            state["selected_contact_user_id"] = str(
                                (recovery_latest or {}).get("contact_user_id")
                                or recovery_contact.get("auth_user_id")
                                or ""
                            ).strip()
                            queue_mode_label = (
                                "Session order"
                                if is_mobile_variant or at_home_lifecycle_stage
                                else "Office review"
                            )
                playback_policy_mode = transcript_policy_mode
                if is_mobile_variant and transcript_policy_mode == "precheck":
                    playback_policy_mode = "assist"
                playback_allowed = True
                if should_attempt_playback:
                    playback_allowed = render_transcript_assist(
                        latest,
                        policy_mode=playback_policy_mode,
                        care_home_id=resident["care_home_id"],
                        resident_id=resident_id,
                    )
                has_playback_source = bool(playback_source)
                played_now = bool(has_playback_source and should_show_message and playback_allowed)
                precheck_blocking = bool(has_playback_source and should_show_message and not playback_allowed)

                if has_playback_source and should_show_message:
                    if playback_allowed:
                        try:
                            if playback_source_kind == "bytes":
                                st.audio(
                                    playback_source,
                                    format=latest.get("audio_mime_type") or "audio/wav",
                                )
                            else:
                                st.audio(playback_source)
                        except Exception as exc:
                            if APP_DEBUG:
                                print(f"[playback] suppressed audio render error: {exc}", flush=True)
                            st.caption("Message payload could not be played. Skipping to next contact.")
                            playback_source = None
                            has_playback_source = False
                            played_now = False
                        played_label = format_soft_message_period_label(latest.get("recorded_at"))
                        if played_label:
                            st.caption(played_label)
                    else:
                        st.caption("Playback locked until transcript review is complete.")
                elif should_show_message and not has_playback_source:
                    st.markdown(
                        '<div class="vm-muted-line">No new messages.</div>',
                        unsafe_allow_html=True,
                    )

                if is_mobile_variant or is_office_variant:
                    latest_message_id = str((latest or {}).get("id") or "").strip()
                    listened_prefix = "care_mobile" if is_mobile_variant else "care_office"
                    if played_now and latest_message_id:
                        latest_contact_user_id = str(
                            (latest or {}).get("contact_user_id")
                            or state.get("selected_contact_user_id")
                            or ""
                        ).strip()
                        latest_recorded_at = str((latest or {}).get("recorded_at") or "").strip()
                        listened_confirm_key = (
                            f"{listened_prefix}_listened_confirm_{resident_id}_{latest_message_id}"
                        )
                        listened_action_token = (
                            f"{latest_message_id}:{latest_contact_user_id}:{latest_recorded_at}"
                        )
                        listened_action_key = f"{listened_prefix}_listened_action_done_{resident_id}"
                        listened_now = st.checkbox(
                            (
                                f"{person_first_name} has listened - move to next message"
                                if at_home_lifecycle_stage
                                else f"The {subject_singular} has listened - move to next message"
                            ),
                            key=listened_confirm_key,
                        )
                        if (
                            listened_now
                            and st.session_state.get(listened_action_key) != listened_action_token
                        ):
                            st.session_state[listened_action_key] = listened_action_token
                            log_audit_event(
                                "message_played",
                                "care_hub",
                                resident["care_home_id"],
                                latest_message_id,
                                resident_id=resident_id,
                            )
                            if latest_contact_user_id and latest_recorded_at:
                                set_contact_last_played_recorded_at(
                                    resident_id,
                                    resident["care_home_id"],
                                    latest_contact_user_id,
                                    latest_recorded_at,
                                    access_token,
                                )
                                cache_key = f"care_mobile_played_cache_{resident_id}"
                                cache = st.session_state.get(cache_key)
                                if not isinstance(cache, dict):
                                    cache = {}
                                cache[latest_contact_user_id] = latest_recorded_at
                                st.session_state[cache_key] = cache
                                st.session_state[f"care_mobile_last_played_{resident_id}"] = {
                                    "contact_user_id": latest_contact_user_id,
                                    "recorded_at": latest_recorded_at,
                                }
                            next_contact_user_id = get_next_contact_user_id_with_message(
                                resident_id,
                                contacts,
                                access_token,
                                state.get("selected_contact_user_id"),
                            )
                            set_resident_playback_pointer(
                                resident_id,
                                resident["care_home_id"],
                                next_contact_user_id,
                                access_token,
                            )
                            st.session_state[f"care_mobile_pointer_{resident_id}"] = (
                                next_contact_user_id or ""
                            )
                            st.session_state[mobile_play_requested_key] = False
                            st.session_state[mobile_advance_pointer_key] = False
                            st.session_state[listened_confirm_key] = False
                            # Keep local play-count cache consistent immediately after confirmation.
                            cache = st.session_state.get("_message_play_count_cache")
                            if isinstance(cache, dict):
                                cache_key = (
                                    f"{resident['care_home_id'] or ''}::{resident_id or ''}::{latest_message_id}"
                                )
                                cache[cache_key] = int(cache.get(cache_key, 0) or 0) + 1
                                st.session_state["_message_play_count_cache"] = cache
                            st.rerun()
                selected_contact_name = (
                    (selected_contact or {}).get("full_name") or "family contact"
                )
                selected_contact_relationship = (
                    ((selected_contact or {}).get("relationship") or "").strip()
                )
                selected_contact_display = (
                    f"{selected_contact_name} ({selected_contact_relationship.title()})"
                    if selected_contact_relationship
                    else f"{selected_contact_name} (Family Member)"
                )
                selected_contact_id = str((selected_contact or {}).get("id") or "").strip()
                selected_contact_position = queue_position_by_contact_id.get(selected_contact_id)
                if is_queue_playback_variant and queue_mode_label:
                    st.caption(f"Queue mode: {queue_mode_label}")
        if voice_messaging_enabled:
            with st.container(border=True):
                selected_recipient_user_id = str(
                    (selected_contact or {}).get("auth_user_id")
                    or state.get("selected_contact_user_id")
                    or ""
                ).strip()
                target_options = ["Family group"]
                if selected_contact is not None:
                    target_options.append(selected_contact_display)
                target_key = f"resident_message_target_{resident_id}"
                previous_target = str(state.get("resident_message_target") or "Family group")
                target_index = target_options.index(previous_target) if previous_target in target_options else 0
                selected_message_target = st.radio(
                    "Message target",
                    options=target_options,
                    index=target_index,
                    horizontal=True,
                    key=target_key,
                )
                state["resident_message_target"] = selected_message_target
                send_to_family_group = selected_message_target == "Family group"
                target_display_name = "family group" if send_to_family_group else selected_contact_name
                target_channel_note = (
                    "Everyone linked can see this channel."
                    if send_to_family_group
                    else f"Direct current message from {full_name} to {selected_contact_name}. Only that Family Member sees this channel."
                )
                target_contact_user_id = None if send_to_family_group else selected_recipient_user_id
                target_conflict_columns = (
                    "resident_id,family_id,direction,channel"
                    if send_to_family_group
                    else "resident_id,contact_user_id,direction,channel"
                )
                target_lookup_filters = {
                    "resident_id": resident_id,
                    "channel": "resident_family",
                    "direction": "from_resident",
                }
                if send_to_family_group:
                    target_lookup_filters["family_id"] = resident.get("family_id") or resident_id
                    target_lookup_filters["contact_user_id"] = None
                else:
                    target_lookup_filters["contact_user_id"] = target_contact_user_id
                render_care_flow_title(
                    (
                        f"Latest message from {full_name} to {target_display_name}"
                        if at_home_lifecycle_stage
                        else f"Latest message from {subject_singular} ({full_name}) to {target_display_name}"
                    ),
                    "outbound",
                )
                render_care_channel_note(
                    target_channel_note
                )
                if not (is_mobile_variant or is_office_variant):
                    st.markdown(f"**Latest message from {full_name} to {target_display_name}**")
    
                latest_sent = (
                    fetch_latest_message(
                        resident_id,
                        "from_resident",
                        access_token,
                        contact_user_id=target_contact_user_id,
                        contact_user_id_is_null=send_to_family_group,
                        family_id=(resident.get("family_id") or resident_id) if send_to_family_group else None,
                        channel="resident_family",
                        include_audio=True,
                    )
                    if send_to_family_group or target_contact_user_id
                    else None
                )
                latest_sent_audio, latest_sent_audio_kind = resolve_audio_playback_source_lazy(
                    latest_sent,
                    access_token=access_token,
                )
                if latest_sent:
                    if render_text_update_message(latest_sent):
                        pass
                    elif latest_sent_audio:
                        if latest_sent_audio_kind == "bytes":
                            st.audio(
                                latest_sent_audio,
                                format=latest_sent.get("audio_mime_type") or "audio/wav",
                            )
                        else:
                            st.audio(latest_sent_audio)
                    else:
                        st.success(
                            (
                                f"Latest {full_name} -> Family message is saved."
                                if at_home_lifecycle_stage
                                else f"Latest {subject_singular_title} -> Family message is saved."
                            )
                        )
                    latest_sent_at = latest_sent.get("recorded_at")
                    if latest_sent_at and not is_text_update_message(latest_sent):
                        latest_sent_label = format_soft_message_period_label(latest_sent_at)
                        if latest_sent_label:
                            st.caption(latest_sent_label)
                    if not is_text_update_message(latest_sent):
                        render_transcript_assist(
                            latest_sent,
                            policy_mode="assist",
                            care_home_id=resident["care_home_id"],
                            resident_id=resident_id,
                        )
                if is_mobile_variant or is_office_variant:
                    text_nonce = int(state.get("resident_text_message_nonce", 0))
                    st.markdown(f"**Short text message to {target_display_name}**")
                    resident_text_body = st.text_area(
                        f"Short text message to {target_display_name}",
                        key=f"resident_short_text_{resident_id}_{text_nonce}",
                        height=90,
                        max_chars=800,
                        label_visibility="collapsed",
                    )
                    resident_text_can_send = bool(
                        str(resident_text_body or "").strip()
                        and (send_to_family_group or target_contact_user_id)
                    )
                    if st.button(
                        f"Send short message to {target_display_name}",
                        key=f"resident_short_text_send_{resident_id}_{text_nonce}",
                        disabled=not resident_text_can_send,
                        use_container_width=True,
                    ):
                        if not resident_text_can_send:
                            if not send_to_family_group and not target_contact_user_id:
                                st.info("Please select a Family Member before sending.")
                            else:
                                st.info("Please write a short message before sending.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                payload = {
                                    "resident_id": resident_id,
                                    "contact_user_id": target_contact_user_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "resident_family",
                                    "direction": "from_resident",
                                    "audio_storage_path": "",
                                    "audio_mime_type": "text/plain",
                                    "audio_bytes": 0,
                                    "message_kind": "text",
                                    "text_title": None,
                                    "text_body": str(resident_text_body or "").strip(),
                                    "recorded_at": now_iso,
                                }
                                resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    payload,
                                    target_conflict_columns,
                                    target_lookup_filters,
                                )
                                if upsert_error:
                                    if _message_missing_text_columns(Exception(upsert_error)):
                                        st.error(
                                            "Short text messages need Supabase migration 0035_messages_text_updates.sql."
                                        )
                                    else:
                                        st.error(upsert_error)
                                else:
                                    message_id = (
                                        (
                                            resp.data[0].get("id")
                                            if hasattr(resp, "data")
                                            and isinstance(resp.data, list)
                                            and resp.data
                                            else None
                                        )
                                        if resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        message_id,
                                    )
                                    bump_message_cache_epoch()
                                    state["recording_bytes"] = None
                                    state["recording_mime_type"] = "audio/wav"
                                    state["preview_confirmed"] = False
                                    state["transcribe_requested"] = False
                                    clear_transcript_preview_state(state)
                                    st.session_state["care_last_sent"] = {
                                        "resident_id": resident_id,
                                        "contact_id": None if send_to_family_group else selected_contact_id,
                                        "message": f"Short message sent to {target_display_name}.",
                                        "sent_at_ts": time.time(),
                                    }
                                    state["resident_text_message_nonce"] = text_nonce + 1
                                    activate_send_guard(send_guard_scope)
                                    st.rerun()
    
                    native_recording_available = hasattr(st, "audio_input")
                    native_recorder_error = False
                    recorded_from_native = None
                    if native_recording_available:
                        try:
                            recorded_from_native = st.audio_input(
                                f"Record voice message from {full_name} to {target_display_name}",
                                key=f"care_audio_input_{resident_id}_{state.get('recording_input_nonce', 0)}",
                            )
                        except Exception:
                            native_recorder_error = True
                            recorded_from_native = None
                    if recorded_from_native is not None:
                        native_bytes = recorded_from_native.getvalue()
                        if native_bytes:
                            native_fp = __import__("hashlib").sha1(native_bytes).hexdigest()
                        else:
                            native_fp = None
                        if not native_bytes:
                            st.warning(
                                "That recording could not be captured correctly. Please record again."
                            )
                        # Once user has confirmed preview for current recording, avoid resetting
                        # from duplicate/replayed audio_input payloads on rerun.
                        elif state.get("preview_confirmed") and state.get("recording_bytes"):
                            pass
                        elif native_fp != state.get("recording_fingerprint"):
                            reset_outbox_state_on_new_recording(
                                state,
                                ack_widget_key=f"care_listened_{resident_id}",
                                clear_care_last_sent_for_resident=resident_id,
                            )
                            state["recording_bytes"] = native_bytes
                            state["recording_fingerprint"] = native_fp
                            state["recording_mime_type"] = (
                                getattr(recorded_from_native, "type", None) or "audio/wav"
                            )
                    elif not native_recording_available or native_recorder_error:
                        if native_recorder_error:
                            st.warning(
                                "Microphone recorder could not load in this browser view. "
                                "Use the upload option below."
                            )
                        else:
                            st.warning("Native microphone recording is unavailable in this environment.")
                        uploaded_recording = st.file_uploader(
                            "Upload recorded voice message",
                            type=["wav", "mp3", "m4a", "ogg", "webm"],
                            key=f"care_upload_{resident_id}_{state.get('recording_input_nonce', 0)}",
                        )
                        if uploaded_recording is not None:
                            upload_bytes = uploaded_recording.getvalue()
                            upload_fp = (
                                __import__("hashlib").sha1(upload_bytes).hexdigest()
                                if upload_bytes
                                else None
                            )
                            if not upload_bytes:
                                st.warning("Uploaded audio file is empty. Please choose another file.")
                            elif upload_fp != state.get("recording_fingerprint"):
                                reset_outbox_state_on_new_recording(
                                    state,
                                    ack_widget_key=f"care_listened_{resident_id}",
                                    clear_care_last_sent_for_resident=resident_id,
                                )
                                state["recording_bytes"] = upload_bytes
                                state["recording_fingerprint"] = upload_fp
                                state["recording_mime_type"] = (
                                    getattr(uploaded_recording, "type", None)
                                    or "audio/wav"
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
                        render_transcript_preview_controls(
                            state,
                            state.get("recording_bytes") or b"",
                            state.get("recording_mime_type") or "audio/wav",
                            policy_mode=transcript_policy_mode,
                            key_scope=f"care_preview_{resident_id}",
                        )
                        if st.button(
                            "Reset recorder",
                            key=f"care_reset_recorder_{resident_id}",
                            use_container_width=True,
                        ):
                            state["recording_bytes"] = None
                            state["recording_mime_type"] = "audio/wav"
                            state["recording_fingerprint"] = None
                            state["recording_input_nonce"] = int(
                                state.get("recording_input_nonce", 0)
                            ) + 1
                            reset_outbox_state_on_new_recording(
                                state,
                                ack_widget_key=f"care_listened_{resident_id}",
                                clear_care_last_sent_for_resident=resident_id,
                                update_widget_state=False,
                            )
                            st.rerun()
                    else:
                        state["preview_confirmed"] = False
                        state["transcribe_requested"] = False
                        clear_transcript_preview_state(state)
    
                    sent_now = False
                    room_display = (
                        f"{workspace_labels.get('room_label')} {resident.get('room')}"
                        if resident.get("room") and bool(workspace_labels.get("show_room"))
                        else ""
                    )
                    if is_office_variant:
                        identity_suffix = (
                            f" - {room_display}" if room_display else ""
                        )
                        confirmation_line = (
                            "Sending on behalf of:<br/>"
                            f"{full_name}{identity_suffix} -> {target_display_name}"
                        )
                    else:
                        identity_parts = [full_name]
                        if room_display:
                            identity_parts.append(room_display)
                        care_home_display = ""
                        if bool(workspace_labels.get("show_room")):
                            care_home_display = (
                                str(resident.get("care_home") or "").strip()
                                or f"{workspace_labels.get('organisation_label')} not set"
                            )
                        if care_home_display:
                            identity_parts.append(care_home_display)
                        confirmation_line = (
                            "Sending on behalf of:<br/>"
                            f"{' - '.join(identity_parts)} -> {target_display_name}"
                        )
                    st.markdown(
                        f'<div class="vm-muted-line">{confirmation_line}</div>',
                        unsafe_allow_html=True,
                    )
                    last_sent = st.session_state.get("care_last_sent")
    
                    can_send = bool(
                        state.get("recording_bytes")
                        and state.get("preview_confirmed")
                        and (send_to_family_group or target_contact_user_id)
                    )
                    if st.button(
                        f"Send for {full_name}",
                        key=f"care_send_{resident_id}",
                        disabled=not can_send,
                    ):
                        if not can_send:
                            if not send_to_family_group and not target_contact_user_id:
                                st.info("Please select a Family Member before sending.")
                            else:
                                st.info("Please record and listen before sending.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                audio_bytes = state.get("recording_bytes") or b""
                                audio_mime_type = state.get("recording_mime_type") or "audio/wav"
                                now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                audio_object_path, upload_error = upload_audio_to_storage(
                                    audio_bytes,
                                    audio_mime_type,
                                    resident_id=resident_id,
                                    direction="from_resident",
                                )
                                use_inline_fallback = not bool(audio_object_path)
                                if APP_DEBUG and upload_error:
                                    print(
                                        "[audio-upload] from_resident fallback to inline payload:",
                                        upload_error,
                                    )
                                payload = {
                                    "resident_id": resident_id,
                                    "contact_user_id": target_contact_user_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "resident_family",
                                    "direction": "from_resident",
                                    "audio_storage_path": (
                                        base64.b64encode(audio_bytes).decode("ascii")
                                        if use_inline_fallback
                                        else ""
                                    ),
                                    "audio_object_path": audio_object_path,
                                    "audio_source": "inline" if use_inline_fallback else "storage",
                                    "audio_mime_type": audio_mime_type,
                                    "audio_bytes": len(audio_bytes),
                                    "message_kind": "voice",
                                    "text_title": None,
                                    "text_body": None,
                                    "recorded_at": now_iso,
                                }
                                transcript_fields, transcript_error = build_transcript_fields_from_preview(
                                    state,
                                    audio_bytes,
                                    audio_mime_type,
                                    requested=bool(state.get("transcribe_requested")),
                                )
                                payload.update(transcript_fields)
                                resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    payload,
                                    target_conflict_columns,
                                    target_lookup_filters,
                                )
                                if upsert_error:
                                    st.error(upsert_error)
                                else:
                                    if transcript_error and bool(state.get("transcribe_requested")):
                                        st.warning(f"Message sent, but transcript failed: {transcript_error}")
                                    transcript_persist_warning = consume_transcript_persist_warning()
                                    if transcript_persist_warning:
                                        st.warning(transcript_persist_warning)
                                    message_id = (
                                        (
                                            resp.data[0].get("id")
                                            if hasattr(resp, "data")
                                            and isinstance(resp.data, list)
                                            and resp.data
                                            else None
                                        )
                                        if resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        message_id,
                                    )
                                    bump_message_cache_epoch()
                                    if APP_DEBUG:
                                        print(
                                            "Saving Resident->Family message:",
                                            message_id,
                                            now_iso,
                                            target_contact_user_id or "family_group",
                                        )
                                    state["recording_bytes"] = None
                                    state["recording_mime_type"] = "audio/wav"
                                    state["preview_confirmed"] = False
                                    state["transcribe_requested"] = False
                                    clear_transcript_preview_state(state)
                                    sent_now = True
                                    st.session_state["care_last_sent"] = {
                                        "resident_id": resident_id,
                                        "contact_id": None if send_to_family_group else selected_contact_id,
                                        "message": f"Message sent to {target_display_name}.",
                                        "sent_at_ts": time.time(),
                                    }
                                    activate_send_guard(send_guard_scope)
                                    state["recording_input_nonce"] = (
                                        int(state.get("recording_input_nonce", 0)) + 1
                                    )
                                    st.rerun()
                    if sent_now:
                        st.success("Message sent.")
                    elif last_sent and last_sent.get("resident_id") == resident_id:
                        st.success(last_sent.get("message", "Message sent."))
    
        show_update_box = (
            runtime_variant == VARIANT_OFFICE
            and (shared_coordination_stage or normalize_lifecycle_stage(lifecycle_stage) == 4)
        )
        show_practical_box = requests_enabled and (
            runtime_variant == VARIANT_OFFICE
            or (runtime_variant == VARIANT_MOBILE and mobile_channel_enabled)
        )

        mobile_office_message_enabled = (
            mobile_channel_enabled
            and office_channel_enabled
            and (family_led_mode or at_home_lifecycle_stage)
            and runtime_variant in {VARIANT_MOBILE, VARIANT_OFFICE}
        )

        if mobile_office_message_enabled:
            mobile_office_container_key = (
                f"mobile-channel-office-message-{resident_id}"
                if runtime_variant == VARIANT_MOBILE
                else f"office-channel-mobile-message-{resident_id}"
            )
            with st.container(border=True, key=mobile_office_container_key):
                if runtime_variant == VARIANT_MOBILE:
                    render_care_flow_title(
                        f"Message with Family Office ({full_name})",
                        "office",
                    )
                    render_care_channel_note(
                        "When you send your current message, it replaces your previous one. "
                        "When the Family Organiser sends a new message, it replaces their previous one. "
                        "So you both see current messages only. This is non-urgent and not live."
                    )
                    latest_from_office = fetch_latest_message(
                        resident_id,
                        "office_to_mobile",
                        access_token,
                        channel="mobile_office",
                        include_audio=False,
                    )
                    latest_to_office = fetch_latest_message(
                        resident_id,
                        "mobile_to_office",
                        access_token,
                        channel="mobile_office",
                        include_audio=False,
                    )
                    st.markdown("**Current message from Family Office**")
                    if not render_text_update_message(latest_from_office):
                        st.markdown(
                            '<div class="vm-muted-line">No current message from Family Office.</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown("**Current message to Family Office**")
                    if not render_text_update_message(latest_to_office):
                        st.markdown(
                            '<div class="vm-muted-line">No current message to Family Office.</div>',
                            unsafe_allow_html=True,
                        )
                    text_nonce = int(state.get("mobile_office_text_nonce", 0))
                    mobile_to_office_body = st.text_area(
                        "Type your message to Family Office here:",
                        key=f"mobile_to_office_text_{resident_id}_{text_nonce}",
                        height=100,
                        max_chars=1000,
                    )
                    mobile_to_office_can_send = bool(str(mobile_to_office_body or "").strip())
                    if st.button(
                        "Click to send and replace your message",
                        key=f"mobile_to_office_send_{resident_id}_{text_nonce}",
                        use_container_width=True,
                    ):
                        if not mobile_to_office_can_send:
                            st.info("Please write the current message first.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                payload = {
                                    "resident_id": resident_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "mobile_office",
                                    "direction": "mobile_to_office",
                                    "audio_storage_path": "",
                                    "audio_mime_type": "text/plain",
                                    "audio_bytes": 0,
                                    "message_kind": "text",
                                    "text_title": None,
                                    "text_body": str(mobile_to_office_body or "").strip(),
                                    "recorded_at": now_iso,
                                }
                                resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    payload,
                                    "resident_id,direction,channel",
                                    {
                                        "resident_id": resident_id,
                                        "channel": "mobile_office",
                                        "direction": "mobile_to_office",
                                    },
                                )
                                if upsert_error:
                                    st.error(upsert_error)
                                else:
                                    message_id = (
                                        (
                                            resp.data[0].get("id")
                                            if hasattr(resp, "data")
                                            and isinstance(resp.data, list)
                                            and resp.data
                                            else None
                                        )
                                        if resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        message_id,
                                        resident_id=resident_id,
                                    )
                                    bump_message_cache_epoch()
                                    state["mobile_office_text_nonce"] = text_nonce + 1
                                    st.success("Current message to Family Office replaced.")
                                    st.rerun()
                else:
                    mobile_support_label = "Mobile Support / carer"
                    render_care_flow_title(
                        f"Message with {mobile_support_label} ({full_name})",
                        "office",
                    )
                    render_care_channel_note(
                        "When you send your current message, it replaces your previous one. "
                        "When Mobile Support sends a new message, it replaces their previous one. "
                        "So you both see current messages only. This is non-urgent and not live."
                    )
                    latest_from_mobile = fetch_latest_message(
                        resident_id,
                        "mobile_to_office",
                        access_token,
                        channel="mobile_office",
                        include_audio=False,
                    )
                    latest_to_mobile = fetch_latest_message(
                        resident_id,
                        "office_to_mobile",
                        access_token,
                        channel="mobile_office",
                        include_audio=False,
                    )
                    st.markdown(f"**Current message from {mobile_support_label}**")
                    if not render_text_update_message(latest_from_mobile):
                        st.markdown(
                            f'<div class="vm-muted-line">No current message from {html.escape(mobile_support_label)}.</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(f"**Current message to {mobile_support_label}**")
                    if not render_text_update_message(latest_to_mobile):
                        st.markdown(
                            f'<div class="vm-muted-line">No current message to {html.escape(mobile_support_label)}.</div>',
                            unsafe_allow_html=True,
                        )
                    text_nonce = int(state.get("office_mobile_text_nonce", 0))
                    office_to_mobile_body = st.text_area(
                        f"Type your message to {mobile_support_label} here:",
                        key=f"office_to_mobile_text_{resident_id}_{text_nonce}",
                        height=100,
                        max_chars=1000,
                    )
                    office_to_mobile_can_send = bool(str(office_to_mobile_body or "").strip())
                    if st.button(
                        "Click to send and replace your message",
                        key=f"office_to_mobile_send_{resident_id}_{text_nonce}",
                        use_container_width=True,
                    ):
                        if not office_to_mobile_can_send:
                            st.info("Please write the current message first.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                payload = {
                                    "resident_id": resident_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "mobile_office",
                                    "direction": "office_to_mobile",
                                    "audio_storage_path": "",
                                    "audio_mime_type": "text/plain",
                                    "audio_bytes": 0,
                                    "message_kind": "text",
                                    "text_title": None,
                                    "text_body": str(office_to_mobile_body or "").strip(),
                                    "recorded_at": now_iso,
                                }
                                resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    payload,
                                    "resident_id,direction,channel",
                                    {
                                        "resident_id": resident_id,
                                        "channel": "mobile_office",
                                        "direction": "office_to_mobile",
                                    },
                                )
                                if upsert_error:
                                    st.error(upsert_error)
                                else:
                                    message_id = (
                                        (
                                            resp.data[0].get("id")
                                            if hasattr(resp, "data")
                                            and isinstance(resp.data, list)
                                            and resp.data
                                            else None
                                        )
                                        if resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        message_id,
                                        resident_id=resident_id,
                                    )
                                    bump_message_cache_epoch()
                                    state["office_mobile_text_nonce"] = text_nonce + 1
                                    st.success(f"Current message to {mobile_support_label} replaced.")
                                    st.rerun()

        if (
            runtime_variant == VARIANT_OFFICE
            and office_channel_enabled
            and contacts
            and (family_led_mode or at_home_lifecycle_stage)
        ):
            with st.container(
                border=True,
                key=f"office-channel-family-message-{resident_id}",
            ):
                render_care_flow_title(
                    "Your message to a selected Family Member",
                    "office",
                )
                render_care_channel_note(
                    "When you send your current message, it replaces your previous one. "
                    "When the selected Family Member sends a new message, it replaces their previous one. "
                    "So you both see current messages only. This is non-urgent and not live."
                )
                contact_options = sort_contacts_for_playback(contacts)
                selected_specific_contact = st.selectbox(
                    "Family Member",
                    options=contact_options,
                    format_func=lambda contact: family_contact_display_name(contact),
                    key=f"office_specific_family_contact_{resident_id}",
                )
                selected_specific_contact_user_id = str(
                    (selected_specific_contact or {}).get("auth_user_id") or ""
                ).strip()
                selected_specific_contact_name = family_contact_display_name(
                    selected_specific_contact
                )
                if not selected_specific_contact_user_id:
                    st.caption("This Family Member does not yet have linked app access.")
                else:
                    latest_from_family = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=selected_specific_contact_user_id,
                        channel="resident_family",
                        include_audio=False,
                    )
                    st.markdown(f"**Current message from {selected_specific_contact_name}**")
                    if not render_text_update_message(latest_from_family):
                        st.markdown(
                            '<div class="vm-muted-line">No current message from this Family Member.</div>',
                            unsafe_allow_html=True,
                        )
                    latest_to_family = fetch_latest_message(
                        resident_id,
                        "from_resident",
                        access_token,
                        contact_user_id=selected_specific_contact_user_id,
                        channel="resident_family",
                        include_audio=False,
                    )
                    st.markdown(f"**Current message to {selected_specific_contact_name}**")
                    if not render_text_update_message(latest_to_family):
                        st.markdown(
                            '<div class="vm-muted-line">No current message to this Family Member.</div>',
                            unsafe_allow_html=True,
                        )
                    text_nonce = int(state.get("office_specific_family_text_nonce", 0))
                    office_to_family_body = st.text_area(
                        f"Type your message to {selected_specific_contact_name} here:",
                        key=f"office_specific_family_text_{resident_id}_{selected_specific_contact_user_id}_{text_nonce}",
                        height=100,
                        max_chars=1000,
                    )
                    office_to_family_can_send = bool(str(office_to_family_body or "").strip())
                    if st.button(
                        "Click to send and replace your message",
                        key=f"office_specific_family_send_{resident_id}_{selected_specific_contact_user_id}_{text_nonce}",
                        use_container_width=True,
                    ):
                        if not office_to_family_can_send:
                            st.info("Please write the current message first.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                payload = {
                                    "resident_id": resident_id,
                                    "contact_user_id": selected_specific_contact_user_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "resident_family",
                                    "direction": "from_resident",
                                    "audio_storage_path": "",
                                    "audio_mime_type": "text/plain",
                                    "audio_bytes": 0,
                                    "message_kind": "text",
                                    "text_title": None,
                                    "text_body": str(office_to_family_body or "").strip(),
                                    "recorded_at": now_iso,
                                }
                                resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    payload,
                                    "resident_id,contact_user_id,direction,channel",
                                    {
                                        "resident_id": resident_id,
                                        "contact_user_id": selected_specific_contact_user_id,
                                        "channel": "resident_family",
                                        "direction": "from_resident",
                                    },
                                )
                                if upsert_error:
                                    st.error(upsert_error)
                                else:
                                    message_id = (
                                        (
                                            resp.data[0].get("id")
                                            if hasattr(resp, "data")
                                            and isinstance(resp.data, list)
                                            and resp.data
                                            else None
                                        )
                                        if resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        message_id,
                                        resident_id=resident_id,
                                    )
                                    bump_message_cache_epoch()
                                    state["office_specific_family_text_nonce"] = text_nonce + 1
                                    st.success(
                                        f"Current message to {selected_specific_contact_name} replaced."
                                    )
                                    st.rerun()

        if show_update_box:
            with st.container(
                border=True,
                key=f"office-channel-family-update-{resident_id}",
            ):
                update_subject = full_name if at_home_lifecycle_stage else full_name
                office_update_title = (
                    f"Update from Family Organiser to the family group ({update_subject})"
                    if shared_coordination_stage
                    else f"Care Home update to all Family re: {update_subject}"
                )
                if family_led_mode:
                    if main_contact_name:
                        office_update_title = (
                            f"Update from Family Organiser {main_contact_name} "
                            f"to the family group"
                        )
                    else:
                        office_update_title = "Update from Family Organiser to the family group"
                render_care_flow_title(
                    office_update_title,
                    "office",
                )
                if family_led_mode and main_contact_name:
                    st.caption(f"Family Organiser: {main_contact_name}")
                latest_office_update = fetch_latest_message(
                    resident_id,
                    "office_to_family",
                    access_token,
                    family_id=resident.get("family_id") or resident_id,
                    channel="office_family",
                    include_audio=False,
                )
                if render_text_update_message(latest_office_update):
                    pass
                elif latest_office_update:
                    st.markdown(
                        '<div class="vm-muted-line">No current text update yet.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="vm-muted-line">No current text update yet.</div>',
                        unsafe_allow_html=True,
                    )
                office_update_phrase = (
                    "shared update" if shared_coordination_stage else "care hub update"
                )
                if family_led_mode:
                    office_update_phrase = (
                        f"update from {main_contact_name}"
                        if main_contact_name
                        else "main contact update"
                    )
                state["office_recording_bytes"] = None
                state["office_recording_mime_type"] = "audio/wav"
                state["office_preview_confirmed"] = False
                state["office_transcribe_requested"] = False
                state["office_recording_fingerprint"] = None
                clear_transcript_preview_state(state, prefix="office_")

                if show_update_box:
                    selected_office_category = st.selectbox(
                        "Update category",
                        options=list(OFFICE_UPDATE_CATEGORIES),
                        index=(
                            list(OFFICE_UPDATE_CATEGORIES).index(
                                state.get("office_update_category", OFFICE_UPDATE_CATEGORIES[0])
                            )
                            if state.get("office_update_category") in OFFICE_UPDATE_CATEGORIES
                            else 0
                        ),
                        key=f"care_office_update_category_{resident_id}",
                    )
                    state["office_update_category"] = selected_office_category
                    if shared_coordination_stage or family_led_mode:
                        st.caption(
                            "Use these categories for general reassurance only. Personal clinical or urgent matters must use your normal direct contact route."
                        )
                    else:
                        st.caption(
                            "Use these categories for general reassurance only. Personal clinical or urgent matters must use normal care-home channels."
                        )
                    text_nonce = int(state.get("office_text_update_nonce", 0))
                    text_title = st.text_input(
                        "Text update title (optional)",
                        key=f"care_office_text_update_title_{resident_id}_{text_nonce}",
                    )
                    text_body = st.text_area(
                        "Type update to family group here:",
                        key=f"care_office_text_update_body_{resident_id}_{text_nonce}",
                        height=110,
                        max_chars=1200,
                    )
                    text_can_send = bool(str(text_body or "").strip())
                    if st.button(
                        "Click to send and replace family group update",
                        key=f"care_send_office_text_update_{resident_id}_{text_nonce}",
                    ):
                        if not text_can_send:
                            st.info("Please write the text update before sending.")
                        else:
                            supabase, error = get_authed_supabase(access_token)
                            if error:
                                st.error(error)
                            else:
                                office_now_iso = __import__("datetime").datetime.utcnow().isoformat()
                                office_payload = {
                                    "resident_id": resident_id,
                                    "family_id": resident.get("family_id") or resident_id,
                                    "channel": "office_family",
                                    "direction": "office_to_family",
                                    "audio_storage_path": "",
                                    "audio_mime_type": "text/plain",
                                    "audio_bytes": 0,
                                    "message_kind": "text",
                                    "text_title": str(text_title or "").strip() or None,
                                    "text_body": str(text_body or "").strip(),
                                    "recorded_at": office_now_iso,
                                }
                                office_resp, upsert_error = upsert_latest_message_with_fallback(
                                    supabase,
                                    office_payload,
                                    "resident_id,family_id,direction,channel",
                                    {
                                        "resident_id": resident_id,
                                        "family_id": resident.get("family_id") or resident_id,
                                        "channel": "office_family",
                                        "direction": "office_to_family",
                                    },
                                )
                                if upsert_error:
                                    if _message_missing_text_columns(Exception(upsert_error)):
                                        st.error(
                                            "Text updates need Supabase migration 0035_messages_text_updates.sql."
                                        )
                                    else:
                                        st.error(upsert_error)
                                else:
                                    office_message_id = (
                                        (
                                            office_resp.data[0].get("id")
                                            if hasattr(office_resp, "data")
                                            and isinstance(office_resp.data, list)
                                            and office_resp.data
                                            else None
                                        )
                                        if office_resp is not None
                                        else None
                                    )
                                    log_audit_event(
                                        "message_sent",
                                        "care_hub",
                                        resident["care_home_id"],
                                        office_message_id,
                                    )
                                    bump_message_cache_epoch()
                                    category_label = (
                                        state.get("office_update_category")
                                        or OFFICE_UPDATE_CATEGORIES[0]
                                    )
                                    if family_led_mode:
                                        label_prefix = (
                                            f"{category_label} text update from {main_contact_name}"
                                            if main_contact_name
                                            else f"{category_label} main contact text update"
                                        )
                                    elif shared_coordination_stage:
                                        label_prefix = (
                                            f"{category_label} shared text update sent to all Family Members"
                                        )
                                    else:
                                        label_prefix = (
                                            f"{category_label} text update sent to all Family Members"
                                        )
                                    state["office_last_sent_label"] = f"{label_prefix}."
                                    state["office_text_update_nonce"] = text_nonce + 1
                                    activate_send_guard(send_guard_scope)
                                    st.rerun()
                if (
                    show_update_box
                    and state.get("office_last_sent_label")
                ):
                    st.success(state.get("office_last_sent_label"))

            if show_practical_box and runtime_variant == VARIANT_MOBILE:
                with st.container(
                    border=True,
                    key=f"mobile-channel-practical-request-{resident_id}",
                ):
                    render_care_flow_title(
                        f"Request from Office ({full_name})",
                        "practical",
                    )
                    st.markdown("**Request (structured question and fixed responses)**")
                    st.caption(
                        "Use this for non-urgent, non-essential coordination only. Use normal direct contact routes for anything urgent, sensitive, or time-critical."
                    )
                    mobile_practical = fetch_latest_open_mobile_practical_message(
                        resident_id, access_token
                    )
                    if mobile_practical:
                        mobile_practical_id = str(mobile_practical.get("id") or "").strip()
                        mobile_context_type = str(
                            mobile_practical.get("context_type")
                            or OFFICE_PRACTICAL_CONTEXT_GENERAL
                        ).strip()
                        st.markdown(f"**{str(mobile_practical.get('title') or 'Request').strip()}**")
                        st.markdown(str(mobile_practical.get("body") or "").strip())
                        if mobile_context_type == OFFICE_PRACTICAL_CONTEXT_VISIT:
                            requested_date = str(mobile_practical.get("requested_date") or "").strip()
                            requested_time = str(mobile_practical.get("requested_time_window") or "").strip()
                            if requested_date:
                                st.caption(f"Requested date: {requested_date}")
                            if requested_time:
                                st.caption(f"Requested time window: {requested_time}")
                        mobile_response_choice = str(
                            mobile_practical.get("mobile_response_choice") or ""
                        ).strip().lower()
                        existing_mobile_response = fetch_mobile_practical_response(
                            mobile_practical_id, access_token
                        )
                        if existing_mobile_response:
                            mobile_response_choice = str(
                                existing_mobile_response.get("primary_choice") or ""
                            ).strip().lower()
                        choice_labels = list(STRUCTURED_RESPONSE_VALUES_BY_LABEL.keys())
                        choice_to_value = STRUCTURED_RESPONSE_VALUES_BY_LABEL
                        default_choice_label = format_structured_response_choice(
                            mobile_response_choice
                        )
                        default_choice_index = (
                            choice_labels.index(default_choice_label)
                            if default_choice_label in choice_labels
                            else 0
                        )
                        selected_choice_label = st.radio(
                            "Mobile structured response",
                            options=choice_labels,
                            index=default_choice_index,
                            horizontal=True,
                            key=f"mobile_practical_choice_{resident_id}_{mobile_practical_id}",
                        )
                        option_rows = fetch_office_practical_message_options(
                            mobile_practical_id, access_token
                        )
                        existing_mobile_option_ids = set(
                            str(option_id or "").strip()
                            for option_id in (
                                (existing_mobile_response or {}).get("selected_option_ids")
                                or mobile_practical.get("mobile_response_option_ids")
                                or []
                            )
                            if str(option_id or "").strip()
                        )
                        selected_mobile_option_ids: list[str] = []
                        primary_choice_option_labels = {
                            "yes",
                            "no",
                            "maybe",
                            "no response",
                            "no_response",
                            "not sure",
                        }
                        for option_row in option_rows:
                            option_id = str(option_row.get("id") or "").strip()
                            option_label = normalize_practical_option_label_for_mode(
                                str(option_row.get("option_label") or "").strip(),
                                OPERATING_MODE_PERSONAL_USE
                                if at_home_lifecycle_stage
                                else operating_mode,
                                person_first_name=person_first_name,
                            )
                            if not option_id or not option_label:
                                continue
                            if option_label.strip().lower() in primary_choice_option_labels:
                                continue
                            checked = st.checkbox(
                                option_label,
                                value=option_id in existing_mobile_option_ids,
                                key=f"mobile_practical_check_{resident_id}_{mobile_practical_id}_{option_id}",
                            )
                            if checked:
                                selected_mobile_option_ids.append(option_id)
                        mobile_note_value = ""
                        if bool(mobile_practical.get("allow_note", True)):
                            mobile_note_value = st.text_area(
                                "Optional short context note (not a discussion).",
                                value=str(
                                    (existing_mobile_response or {}).get("note")
                                    or mobile_practical.get("mobile_response_note")
                                    or ""
                                ),
                                key=f"mobile_practical_note_{resident_id}_{mobile_practical_id}",
                                max_chars=500,
                            )
                        if st.button(
                            "Send Mobile structured response",
                            key=f"mobile_practical_submit_{resident_id}_{mobile_practical_id}",
                            use_container_width=True,
                        ):
                            st.session_state["mobile_status_message"] = (
                                "Saving Mobile structured response..."
                            )
                            with st.spinner("Saving Mobile structured response..."):
                                ok, mobile_message = upsert_mobile_practical_response(
                                    mobile_practical_id,
                                    choice_to_value.get(selected_choice_label, "no_response"),
                                    mobile_note_value,
                                    selected_mobile_option_ids,
                                    access_token,
                                )
                            if ok:
                                st.session_state["mobile_status_message"] = (
                                    "Mobile structured response received."
                                )
                                st.success("Mobile structured response received.")
                                st.rerun()
                            else:
                                st.session_state.pop("mobile_status_message", None)
                                st.error(mobile_message)
                        if mobile_response_choice:
                            st.caption(
                                "Current Mobile response: "
                                f"{format_structured_response_choice(mobile_response_choice)}"
                            )
                    else:
                        st.caption("No current practical request from Family Office.")

            elif show_practical_box:
                with st.container(
                    border=True,
                    key=f"office-channel-practical-request-{resident_id}",
                ):
                    request_title = (
                        f"Practical request from Family Organiser to Family Members ({full_name})"
                        if shared_coordination_stage
                        else f"Practical request to Family Members ({full_name})"
                    )
                    render_care_flow_title(
                        request_title,
                        "practical",
                    )
                    st.markdown("**Request (structured question and fixed responses)**")
                    st.caption(
                        "Use this for non-urgent coordination only (for example visits, events, reminders, attendance, or item requests)."
                    )
                    st.caption(
                        "For urgent or medical matters, use your normal direct contact route."
                        if at_home_lifecycle_stage
                        else urgent_contact_copy(operating_mode)
                    )
                    request_target_options = [
                        {
                            "id": "",
                            "target_type": OFFICE_PRACTICAL_TARGET_ALL_FAMILY,
                            "label": "All Family Members",
                        }
                    ]
                    for contact in contacts or []:
                        contact_id = str((contact or {}).get("id") or "").strip()
                        if not contact_id:
                            continue
                        request_target_options.append(
                            {
                                "id": contact_id,
                                "target_type": OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY,
                                "label": family_contact_display_name(contact),
                            }
                        )
                    if mobile_channel_enabled:
                        request_target_options.append(
                            {
                                "id": "",
                                "target_type": OFFICE_PRACTICAL_TARGET_MOBILE,
                                "label": "Mobile Support / carer",
                            }
                        )
                    selected_request_target = st.selectbox(
                        "Send request to",
                        options=request_target_options,
                        format_func=lambda option: str(option.get("label") or "Family Member"),
                        key=f"office_practical_target_{resident_id}",
                    )
                    selected_target_type = normalize_office_practical_target_type(
                        selected_request_target.get("target_type")
                    )
                    if selected_target_type == OFFICE_PRACTICAL_TARGET_DIRECTED_FAMILY:
                        st.caption(
                            "This names the intended responder. All linked Family Members can see the request and any structured responses."
                        )
                    elif selected_target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
                        st.caption(
                            "This is for Mobile Support / carer and is not shown in Family Hub."
                        )
                    practical_title = st.text_input(
                        "Request title",
                        key=f"office_practical_title_{resident_id}",
                        placeholder="Example: Weekend visits",
                    )
                    practical_body = st.text_area(
                        "Structured question",
                        key=f"office_practical_body_{resident_id}",
                        placeholder="Example: Please confirm whether you are visiting this weekend.",
                        max_chars=800,
                    )
                    practical_allow_note = st.checkbox(
                        "Allow optional short context note (not a discussion)",
                        value=True,
                        key=f"office_practical_allow_note_{resident_id}",
                    )
                    st.caption(
                        "Replies use fixed structured choices, optional tick-boxes, and an optional short context note. No chat or threads."
                    )
                    practical_is_visit = st.checkbox(
                        "This is a visit coordination message",
                        value=False,
                        key=f"office_practical_is_visit_{resident_id}",
                    )
                    practical_requested_date_iso = ""
                    practical_requested_time_window = ""
                    if practical_is_visit:
                        practical_requested_date_iso = st.text_input(
                            "Requested date (optional)",
                            key=f"office_practical_requested_date_{resident_id}",
                            placeholder="Example: 2026-04-21",
                        ).strip()
                        practical_requested_time_window = st.text_input(
                            "Requested time window (optional)",
                            key=f"office_practical_requested_time_window_{resident_id}",
                            placeholder="Example: Morning, around 11am",
                        )
                    practical_checkboxes = []
                    with st.expander("Optional structured reply choices", expanded=False):
                        practical_checkboxes = st.multiselect(
                            "Add optional tick-box choices",
                            options=[
                                normalize_practical_option_label_for_mode(
                                    option,
                                    (
                                        OPERATING_MODE_PERSONAL_USE
                                        if at_home_lifecycle_stage
                                        else operating_mode
                                    ),
                                    person_first_name=person_first_name,
                                )
                                for option in practical_checkbox_options(
                                    OPERATING_MODE_PERSONAL_USE
                                    if at_home_lifecycle_stage
                                    else operating_mode
                                )
                            ],
                            default=[],
                            key=f"office_practical_options_{resident_id}",
                        )
                    if st.button(
                        f"Publish request to {selected_request_target.get('label')}",
                        key=f"office_practical_publish_{resident_id}",
                        use_container_width=True,
                    ):
                        with st.spinner("Publishing request..."):
                            if selected_target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
                                ok, practical_message_id, practical_message = create_mobile_practical_message(
                                    resident_id,
                                    resident["care_home_id"],
                                    practical_title,
                                    practical_body,
                                    practical_allow_note,
                                    practical_checkboxes,
                                    (
                                        OFFICE_PRACTICAL_CONTEXT_VISIT
                                        if practical_is_visit
                                        else OFFICE_PRACTICAL_CONTEXT_GENERAL
                                    ),
                                    practical_requested_date_iso,
                                    practical_requested_time_window,
                                    access_token,
                                )
                            else:
                                ok, practical_message_id, practical_message = create_office_practical_message(
                                    resident_id,
                                    resident["care_home_id"],
                                    practical_title,
                                    practical_body,
                                    practical_allow_note,
                                    practical_checkboxes,
                                    (
                                        OFFICE_PRACTICAL_CONTEXT_VISIT
                                        if practical_is_visit
                                        else OFFICE_PRACTICAL_CONTEXT_GENERAL
                                    ),
                                    practical_requested_date_iso,
                                    practical_requested_time_window,
                                    selected_target_type,
                                    str(selected_request_target.get("id") or "").strip() or None,
                                    access_token,
                                )
                        if ok:
                            log_audit_event(
                                "office_practical_message_created",
                                "care_hub",
                                resident["care_home_id"],
                                practical_message_id,
                                resident_id=resident_id,
                            )
                            st.success(practical_message)
                            st.rerun()
                        else:
                            st.error(practical_message)

                    active_practical = fetch_latest_open_office_practical_message(
                        resident_id, access_token
                    )
                    if active_practical:
                        active_message_id = str(active_practical.get("id") or "").strip()
                        active_target_type = normalize_office_practical_target_type(
                            active_practical.get("target_type")
                        )
                        st.markdown("**Current open request**")
                        st.caption(
                            f"Sent to: {office_practical_target_label(active_practical, contacts)}."
                        )
                        st.markdown(f"**{str(active_practical.get('title') or '').strip()}**")
                        st.markdown(str(active_practical.get("body") or "").strip())
                        if str(active_practical.get("context_type") or "").strip() == OFFICE_PRACTICAL_CONTEXT_VISIT:
                            requested_date = str(active_practical.get("requested_date") or "").strip()
                            requested_time = str(active_practical.get("requested_time_window") or "").strip()
                            if requested_date:
                                st.caption(f"Requested date: {requested_date}")
                            if requested_time:
                                st.caption(f"Requested time window: {requested_time}")
                        option_rows = fetch_office_practical_message_options(
                            active_message_id, access_token
                        )
                        if option_rows:
                            st.caption("Enabled tick-box options:")
                            for option_row in option_rows:
                                label = normalize_practical_option_label_for_mode(
                                    str(option_row.get("option_label") or "").strip(),
                                    operating_mode,
                                    person_first_name=person_first_name,
                                )
                                if label:
                                    st.markdown(f"- {label}")
                        if active_target_type == OFFICE_PRACTICAL_TARGET_MOBILE:
                            mobile_response = fetch_mobile_practical_response(
                                active_message_id, access_token
                            )
                            mobile_choice = str(
                                (mobile_response or {}).get("primary_choice")
                                or active_practical.get("mobile_response_choice")
                                or ""
                            ).strip().lower()
                            if mobile_choice:
                                st.caption(
                                    "Mobile structured response: "
                                    f"{format_structured_response_choice(mobile_choice)}"
                                )
                                selected_mobile_ids = set(
                                    str(option_id or "").strip()
                                    for option_id in (
                                        (mobile_response or {}).get("selected_option_ids")
                                        or active_practical.get("mobile_response_option_ids")
                                        or []
                                    )
                                    if str(option_id or "").strip()
                                )
                                selected_mobile_labels = []
                                for option_row in option_rows:
                                    option_id = str(option_row.get("id") or "").strip()
                                    if option_id not in selected_mobile_ids:
                                        continue
                                    selected_mobile_labels.append(
                                        normalize_practical_option_label_for_mode(
                                            str(option_row.get("option_label") or "").strip(),
                                            operating_mode,
                                            person_first_name=person_first_name,
                                        )
                                    )
                                if selected_mobile_labels:
                                    st.caption(
                                        "Mobile selections: " + ", ".join(selected_mobile_labels)
                                    )
                                mobile_note = str(
                                    (mobile_response or {}).get("note")
                                    or active_practical.get("mobile_response_note")
                                    or ""
                                ).strip()
                                if mobile_note:
                                    st.caption(f"Mobile note: {mobile_note}")
                            else:
                                st.caption("No Mobile response yet.")
                        else:
                            summary = fetch_office_practical_response_summary(
                                active_message_id, access_token
                            )
                            st.caption(
                                "Structured responses: "
                                f"No response {summary['choice_counts'].get('no_response', 0)} | "
                                f"Yes {summary['choice_counts'].get('yes', 0)} | "
                                f"No {summary['choice_counts'].get('no', 0)} | "
                                f"Maybe {summary['choice_counts'].get('maybe', 0)} | "
                                f"Total {summary.get('total', 0)}"
                            )
                            option_counts = summary.get("option_counts") or {}
                            if option_counts:
                                st.caption("Tick-box selections:")
                                for option_label, option_count in option_counts.items():
                                    display_label = normalize_practical_option_label_for_mode(
                                        str(option_label or "").strip(),
                                        operating_mode,
                                        person_first_name=person_first_name,
                                    )
                                    st.markdown(f"- {display_label}: {option_count}")
                            responses = summary.get("responses") or []
                            if responses:
                                st.caption("Family structured responses:")
                                for response in responses:
                                    contact_name = str(response.get("contact_name") or "Family Member")
                                    choice_label = format_structured_response_choice(
                                        response.get("primary_choice")
                                    )
                                    st.markdown(f"- {contact_name}: {choice_label}")
                                    selected_labels = response.get("selected_labels") or []
                                    if selected_labels:
                                        display_selected_labels = [
                                            normalize_practical_option_label_for_mode(
                                                str(label or "").strip(),
                                                operating_mode,
                                                person_first_name=person_first_name,
                                            )
                                            for label in selected_labels
                                        ]
                                        st.caption("Selections: " + ", ".join(display_selected_labels))
                                    planned_visit = str(response.get("planned_visit_time") or "").strip()
                                    if planned_visit:
                                        st.caption(f"Planned visit: {planned_visit}")
                        if st.button(
                            "Close responses for this request",
                            key=f"office_practical_close_{resident_id}_{active_message_id}",
                            use_container_width=True,
                        ):
                            ok, close_message = close_office_practical_message(
                                active_message_id, access_token
                            )
                            if ok:
                                log_audit_event(
                                    "office_practical_message_closed",
                                    "care_hub",
                                    resident["care_home_id"],
                                    active_message_id,
                                    resident_id=resident_id,
                                )
                                st.success(close_message)
                                st.rerun()
                            else:
                                st.error(close_message)

                with st.container(
                    border=True,
                    key=f"office-channel-noticeboard-{resident_id}",
                ):
                    render_family_noticeboard_notes_for_staff(
                        resident_id,
                        access_token,
                        allow_clear=True,
                        key_prefix="office",
                    )

    # Navigation rendered at the top of the page.


def render_care_hub_register_family() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant(
            "Family Member registration is only available in Office."
        )
        return
    back_route = OFFICE_HOME_ROUTE
    render_page_header("Register/invite Family Member", show_menu=False)
    access_token = st.session_state.get("access_token")
    render_route_link(
        f"Back to {get_at_home_voicemail_label(access_token)}",
        back_route,
        key="office_register_family_back_dashboard_link",
    )
    render_care_home_identity_banner(access_token)
    st.info(
        "Use this page to add a Family Member, such as a brother, daughter, son, friend, or other approved person. "
        "Family login will not work for their email until this step has been completed."
    )
    residents = fetch_care_home_residents(access_token)
    render_office_family_registration_form(access_token, residents)


def create_supported_person(
    access_token: str | None,
    *,
    display_name: str,
    reference: str,
) -> tuple[bool, str]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id:
        return False, "No active family setup is linked to this session."
    name_value = str(display_name or "").strip()
    reference_value = str(reference or "").strip() or "Home"
    if not name_value:
        return False, "Enter the person/couple display name."
    if len(name_value) > 160:
        return False, "Display name must be 160 characters or fewer."
    if len(reference_value) > 80:
        return False, "Reference must be 80 characters or fewer."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    try:
        supabase.table("residents").insert(
            {
                "care_home_id": care_home_id,
                "preferred_display_name": name_value,
                "care_home_reference": reference_value,
                "active": True,
            }
        ).execute()
        return True, "Person added."
    except Exception as exc:
        return False, str(exc)


def invite_mobile_carer(
    *,
    email: str,
) -> tuple[bool, str]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    normalized_email = str(email or "").strip().lower()
    if not care_home_id:
        return False, "No active family setup is linked to this session."
    if not normalized_email:
        return False, "Enter the carer's email."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        return False, "Enter a valid carer email address."
    admin_client, admin_error = get_admin_client()
    if admin_error:
        return False, admin_error
    redirect_to = get_magic_link_redirect_url(VARIANT_MOBILE).strip()
    invited, auth_user_id, invite_error = invite_user(
        admin_client,
        normalized_email,
        redirect_to_override=redirect_to,
    )
    if not auth_user_id:
        auth_user_id = _resolve_auth_user_id_by_email(admin_client, normalized_email)
    if not auth_user_id:
        return False, str(invite_error or "Could not invite or resolve this carer account.")
    try:
        try:
            admin_client.table("care_home_users").upsert(
                {
                    "care_home_id": care_home_id,
                    "auth_user_id": auth_user_id,
                    "care_access_level": CARE_ACCESS_MOBILE,
                    "active": True,
                },
                on_conflict="care_home_id,auth_user_id",
            ).execute()
        except Exception as exc:
            if not _is_missing_column_error(exc, "care_access_level"):
                raise
            return (
                False,
                "The database is missing care_home_users.care_access_level. Apply migration 0039 before adding Mobile Support users.",
            )
        if invited:
            return True, "Mobile Support user invited. They will set their Mobile PIN at first Mobile login."
        return True, "Existing user linked as Mobile Support. They can use Mobile login."
    except Exception as exc:
        return False, str(exc)


def invite_office_user(
    *,
    email: str,
) -> tuple[bool, str]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    normalized_email = str(email or "").strip().lower()
    if not care_home_id:
        return False, "No active family setup is linked to this session."
    if not normalized_email:
        return False, "Enter the Office user's email."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        return False, "Enter a valid Office user email address."
    admin_client, admin_error = get_admin_client()
    if admin_error:
        return False, admin_error
    redirect_to = get_magic_link_redirect_url(VARIANT_OFFICE).strip()
    invited, auth_user_id, invite_error = invite_user(
        admin_client,
        normalized_email,
        redirect_to_override=redirect_to,
    )
    if not auth_user_id:
        auth_user_id = _resolve_auth_user_id_by_email(admin_client, normalized_email)
    if not auth_user_id:
        return False, str(invite_error or "Could not invite or resolve this Office account.")
    try:
        try:
            admin_client.table("care_home_users").upsert(
                {
                    "care_home_id": care_home_id,
                    "auth_user_id": auth_user_id,
                    "care_access_level": CARE_ACCESS_OFFICE,
                    "active": True,
                },
                on_conflict="care_home_id,auth_user_id",
            ).execute()
        except Exception as exc:
            if not _is_missing_column_error(exc, "care_access_level"):
                raise
            return (
                False,
                "The database is missing care_home_users.care_access_level. Apply migration 0039 before adding Office users.",
            )
        if invited:
            return True, "Office user invited. They will have full Office access for this family setup."
        return True, "Existing user linked with full Office access."
    except Exception as exc:
        return False, str(exc)


def render_family_system_setup() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant("Setup is only available in Office.")
        return
    if not current_user_can_access_office():
        render_wrong_variant("Mobile Support users cannot use setup.")
        return
    access_token = st.session_state.get("access_token")
    render_page_header("Setup family system", show_menu=False)
    render_route_link(
        f"Back to {get_at_home_voicemail_label(access_token)}",
        get_home_route(VARIANT_OFFICE),
        key="family_system_setup_back",
    )
    render_care_home_identity_banner(access_token)
    st.info(
        "Use this page first for the basic trial setup. After this, use Register/invite Family Member so family login will work."
    )
    st.markdown("#### Setup order")
    st.markdown(
        """
1. Add the person being supported.
2. Save the Family Organiser details.
3. Add any carer who needs Mobile access.
4. Add any trusted co-organiser who needs Office access.
5. Register/invite Family Members, such as brothers, sisters, children, or friends.
"""
    )

    st.markdown("### Person being supported")
    st.caption("Add the person or couple the family communication is about.")
    current_people = fetch_care_home_residents(access_token or "")
    if current_people:
        for person in current_people:
            st.caption("Current: " + format_resident_identity_label(
                person,
                operating_mode=get_operating_mode(access_token),
                include_room=False,
            ))
    with st.form("family_setup_add_person_form"):
        person_name = st.text_input("Person/couple display name", key="family_setup_person_name")
        person_reference = st.text_input(
            "Reference (optional)",
            value="Home",
            key="family_setup_person_reference",
        )
        add_person = st.form_submit_button("Add person")
    if add_person:
        ok, message = create_supported_person(
            access_token,
            display_name=person_name,
            reference=person_reference,
        )
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.markdown("### Family Organiser")
    profile = fetch_active_care_home_profile(access_token, force_refresh=True)
    st.caption("The Family Organiser has full access to the family tools. This does not make them the emergency contact automatically.")
    with st.form("family_setup_organiser_form"):
        organiser_name = st.text_input(
            "Family Organiser name",
            value=str(profile.get("main_contact_name") or ""),
            key="family_setup_organiser_name",
        )
        setup_name = st.text_input(
            "Family setup name",
            value=str(profile.get("name") or ""),
            key="family_setup_name",
        )
        save_organiser = st.form_submit_button("Save organiser details")
    if save_organiser:
        saved, message = update_active_care_home_branding(
            access_token,
            care_home_name=setup_name,
            operating_mode=OPERATING_MODE_PERSONAL_USE,
            lifecycle_stage=get_lifecycle_stage(access_token),
            communication_level=get_communication_level(access_token),
            main_contact_name=organiser_name,
            message_check_note=str(profile.get("message_check_note") or ""),
            banner_title=str(profile.get("branding_banner_title") or ""),
            banner_text=str(profile.get("branding_banner_text") or ""),
            banner_artwork_url=str(profile.get("branding_banner_artwork_url") or ""),
            care_hub_idle_timeout_seconds=int(profile.get("care_hub_idle_timeout_seconds") or CARE_HUB_SESSION_TIMEOUT_SECONDS),
            transcript_policy_mode=str(profile.get("transcript_policy_mode") or "assist"),
        )
        if saved:
            st.success("Family Organiser details saved.")
        else:
            st.error(message)

    st.markdown("### Mobile Support")
    st.caption("Mobile Support users can use Mobile for practical support tasks. They cannot register people, change setup variables, or open Account & Security.")
    with st.form("family_setup_mobile_carer_form"):
        carer_email = st.text_input("Mobile Support email", key="family_setup_carer_email")
        invite_carer = st.form_submit_button("Invite Mobile Support")
    if invite_carer:
        ok, message = invite_mobile_carer(email=carer_email)
        if ok:
            st.success(message)
        else:
            st.error(message)

    st.markdown("### Family Office users")
    st.caption("Family Office users have full access to the family setup, including registration, setup variables, and Account & Security. Use this only for trusted people such as a co-organiser or LPA/finance sibling.")
    with st.form("family_setup_office_user_form"):
        office_user_email = st.text_input("Family Office user email", key="family_setup_office_user_email")
        invite_office = st.form_submit_button("Invite Family Office user")
    if invite_office:
        ok, message = invite_office_user(email=office_user_email)
        if ok:
            st.success(message)
        else:
            st.error(message)

    st.markdown("### Family Members")
    st.caption("Use this for family members and friends. They cannot log in until they have been registered/invited.")
    render_route_link(
        "Register/invite Family Member",
        "/care-hub/register-family",
        key="family_setup_register_contact_link",
    )


def main() -> None:
    st.set_page_config(
        page_title="familyupdates.care - Essential family coordination, separate from chat",
        page_icon="ðŸ—£ï¸",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    redirect_non_canonical_host_once()
    raw_variant = get_raw_app_variant()
    init_state()
    clear_legacy_streamlit_page_param_once()
    pre_auth_route = get_route()
    request_path = _get_request_path()
    recovered_request_path_auth = _recover_auth_callback_params_from_route_path(request_path)
    if recovered_request_path_auth and hasattr(st, "query_params"):
        promoted_any = False
        try:
            for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token"):
                value = str(recovered_request_path_auth.get(key, "") or "").strip()
                if value and not str(st.query_params.get(key, "") or "").strip():
                    st.query_params[key] = value
                    promoted_any = True
        except Exception:
            promoted_any = False
        if promoted_any and not bool(st.session_state.get("_auth_path_promoted_once", False)):
            st.session_state["_auth_path_promoted_once"] = True
            st.rerun()
    else:
        st.session_state.pop("_auth_path_promoted_once", None)
    if pre_auth_route in ("/", ""):
        if request_path.startswith("/family"):
            pre_auth_route = FAMILY_LOGIN_ROUTE
        elif request_path.startswith("/mobile") or request_path.startswith("/care-hub/mobile"):
            pre_auth_route = MOBILE_LOGIN_ROUTE
        elif request_path.startswith("/office") or request_path.startswith("/care-hub"):
            pre_auth_route = OFFICE_LOGIN_ROUTE
        elif request_path.startswith("/public"):
            pre_auth_route = "/pr-home"
    route_variant = _resolve_variant_from_route(pre_auth_route)
    path_variant = _resolve_variant_from_request_path()
    if not raw_variant and not route_variant and not path_variant:
        st.error(
            "Configuration error: APP_VARIANT is required when request path does not map to a variant.\n\n"
            f"Allowed values: {ALLOWED_VARIANT_VALUES_TEXT}."
        )
        st.stop()
    try:
        app_variant = resolve_runtime_variant(route_hint=pre_auth_route)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    dev_bypass_applied, dev_bypass_error = _apply_dev_auth_bypass_session(app_variant)
    if DEV_AUTH_BYPASS_ENABLED and variant_requires_auth(app_variant) and not dev_bypass_applied:
        st.error("Local developer auth bypass did not start.")
        if dev_bypass_error:
            st.error(dev_bypass_error)
        st.caption(
            "Check SUPABASE_URL, SUPABASE_SECRET_KEY, and that this Supabase project has "
            "an active mapping row for this variant."
        )
        st.stop()
    if variant_requires_auth(app_variant) and AUTH_COOKIE_PERSISTENCE_ENABLED:
        if not AUTH_COOKIE_SIGNING_KEY:
            if app_variant == VARIANT_FAMILY:
                st.error("Configuration error: AUTH_COOKIE_SIGNING_KEY is required for secure session cookies.")
                st.stop()
        else:
            restore_auth_session_from_cookie()
    if pre_auth_route in {FAMILY_LOGIN_ROUTE, MOBILE_LOGIN_ROUTE, OFFICE_LOGIN_ROUTE}:
        normalize_auth_hash_fragment_on_login_routes()
    should_consume_auth_callback = False
    if hasattr(st, "query_params"):
        try:
            qp = st.query_params
            should_consume_auth_callback = any(
                bool(str(qp.get(key, "") or "").strip())
                for key in ("code", "token_hash", "token", "type", "access_token", "refresh_token")
            )
        except Exception:
            should_consume_auth_callback = False
    if should_consume_auth_callback or recovered_request_path_auth:
        consume_magic_link_callback()
    route = get_route()
    if route in ("/", "") and pre_auth_route not in ("/", ""):
        route = pre_auth_route
    st.session_state.route = route
    early_public_route_redirects = {
        "/service-overview": "/pr-home",
        "/public-docs": "/pr-home",
        "/public/service-overview": "/pr-home",
        "/public/resident-participation": "/pr-home",
        "/public/family-guide": "/public/qa",
    }
    early_public_target = early_public_route_redirects.get(route)
    if early_public_target:
        route = early_public_target
        st.session_state.route = route
        if hasattr(st, "query_params"):
            try:
                current_route_param = normalize_route(st.query_params.get("route", "")) or "/"
                if current_route_param != route:
                    st.query_params["route"] = route
            except Exception:
                pass
    default_route = normalize_route(get_default_route(app_variant)) or "/"
    if route in ("/", ""):
        target_route = FAMILY_LOGIN_ROUTE if app_variant == VARIANT_FAMILY else default_route
        route = target_route
        st.session_state.route = route
    apply_seo_head_tags(route, app_variant)
    route_allowlisted = is_route_allowed(app_variant, route)
    if APP_DEBUG:
        print(
            f"[startup] variant={app_variant} route={route} allowlisted={route_allowlisted}",
            flush=True,
        )
    guard_route_access(route, app_variant)
    # Debug startup banner disabled in UI.
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
        render_debug_panel("family_unauth", app_variant, "render_family_login + st.stop")
        render_family_login()
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
        set_route("/family/how-it-works")
    elif route == "/family/instructions":
        set_route("/family/how-it-works")
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
        render_pr_homepage()
    elif route == "/service-overview":
        set_route("/pr-home")
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
    elif route == "/care-hub/setup-family-system":
        render_family_system_setup()
    elif route == "/care-hub/instructions":
        render_care_hub_instructions()
    elif route == "/care-hub/training":
        render_care_hub_training()
    elif route == "/care-hub/care-home-banner":
        set_route("/care-hub/operational-variables")
    elif route == "/care-hub/operational-variables":
        render_care_hub_banner_settings()
    elif route == "/care-hub/security":
        render_care_hub_security()
    elif route == "/care-hub/office/qa":
        access_token = st.session_state.get("access_token")
        qa_title = (
            "Family Office Q&A"
            if is_current_at_home_lifecycle_stage(access_token)
            else "Office Q&A"
        )
        render_page_header(qa_title, show_variant_subheading=False)
        render_care_home_identity_banner(access_token)
        render_route_link(
            "Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="office_qa_back_dashboard_link",
        )
        render_qa_document(
            resolve_mode_doc_path(
                "docs/office/common_questions_qa.md",
                access_token=access_token,
            ),
            search_key="office_qa_search",
        )
    elif route == "/care-hub/mobile/qa":
        render_page_header("Mobile Q&A", show_variant_subheading=False)
        access_token = st.session_state.get("access_token")
        render_care_home_identity_banner(access_token)
        render_route_link("Back", get_home_route(VARIANT_MOBILE), key="mobile_qa_back_link")
        render_qa_document(
            resolve_mode_doc_path("docs/public/12_mobile_qa.md", access_token=access_token),
            search_key="mobile_qa_search",
        )
    elif route == "/family/qa":
        render_page_header("Family Q&A", show_variant_subheading=False)
        access_token = st.session_state.get("access_token")
        render_care_home_identity_banner(access_token)
        render_route_link("Back", get_home_route(VARIANT_FAMILY), key="family_qa_back_link")
        render_qa_document(
            resolve_mode_doc_path("docs/public/11_family_qa.md", access_token=access_token),
            search_key="family_qa_search",
        )
    elif route == LIFE_FILE_GUIDE_ROUTE:
        render_life_file_guide()
    elif route == "/docs":
        render_docs()
    elif route == "/public-docs":
        set_route("/pr-home")
    elif route == "/public/service-overview":
        set_route("/pr-home")
    elif route == "/public/how-it-works":
        render_public_document("docs/public/02_how_it_works.md", back_route="/pr-home")
    elif route == "/public/infographic":
        render_public_infographic()
    elif route == "/public/resident-participation":
        set_route("/pr-home")
    elif route == "/public/family-guide":
        set_route("/public/qa")
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
    elif route in REMOVED_VIDEO_ROUTES:
        set_route("/public/how-it-works")
    elif route == "/public-privacy":
        set_route("/public/privacy-notice")
    elif route == "/public-complaints":
        set_route("/public/complaints-and-concerns")
    elif route == "/public-safeguarding":
        set_route("/public/safeguarding-and-consent")
    elif route == "/contracts":
        render_contracts()
    elif route == "/billing":
        set_route(get_home_route(VARIANT_OFFICE))
    elif route == "/care-hub/mfa":
        render_care_hub_mfa()
    else:
        fallback_route = (
            _map_legacy_streamlit_page_to_route(route)
            or _route_from_request_path(request_path)
            or default_route
            or PUBLIC_HOME_ROUTE
        )
        fallback_route = normalize_route(fallback_route) or PUBLIC_HOME_ROUTE
        if fallback_route == route:
            fallback_route = PUBLIC_HOME_ROUTE
        set_route(fallback_route)
        st.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - runtime safety net
        st.error("Application error while rendering.")
        st.error(str(exc))
        st.exception(exc)
