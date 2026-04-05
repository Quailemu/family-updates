# voicemailcare.com UI

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
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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

FAMILY_SESSION_TIMEOUT_SECONDS = int(
    os.getenv("FAMILY_SESSION_TIMEOUT_SECONDS", str(60 * 30))
)
# Guard against accidental very-low timeout values in deployment config.
# Care Hub sessions should not expire during normal short pauses in workflow.
CARE_HUB_SESSION_TIMEOUT_SECONDS = max(
    int(os.getenv("CARE_HUB_SESSION_TIMEOUT_SECONDS", str(60 * 30))),
    60 * 30,
)
CARE_HUB_IDLE_TIMEOUT_OPTIONS_SECONDS = (60 * 30, 60 * 60, 60 * 90, 60 * 120)
APP_DEBUG = os.getenv("APP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
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
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_AUDIO_BUCKET = os.getenv("SUPABASE_AUDIO_BUCKET", "voice-messages").strip() or "voice-messages"
OFFICE_UPDATE_CATEGORIES = (
    "General reassurance",
    "Daily life",
    "Activities",
    "Meals",
)
OFFICE_PRACTICAL_CHECKBOX_OPTIONS = (
    "Yes",
    "No",
    "Not sure",
    "Pencil me in",
    "Send me a link",
    "Send me an invite",
    "Day/date/time please",
    "Please call me",
    "I will call the care home",
    "I will sort this out",
    "I will bring requested items",
    "I can attend",
    "I cannot attend",
    "I will book and take them",
    "Please arrange this and confirm to family",
    "Please share more detail",
    "I don't understand - please explain",
    "I will do this if no one else can",
    "I have seen this",
)
OFFICE_PRACTICAL_CONTEXT_GENERAL = "general"
OFFICE_PRACTICAL_CONTEXT_VISIT = "visit"
SEND_ACTION_GUARD_SECONDS = max(
    int(os.getenv("SEND_ACTION_GUARD_SECONDS", "5")),
    3,
)

ALLOWED_VARIANT_VALUES_TEXT = "public, family, mobile, office"
AUTH_COOKIE_NAME = "vm_auth_rt"
AUTH_COOKIE_MAX_AGE_SECONDS = int(os.getenv("AUTH_COOKIE_MAX_AGE_SECONDS", str(60 * 60 * 24 * 14)))
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "1").strip().lower() in {"1", "true", "yes", "on"}
AUTH_COOKIE_SIGNING_KEY = os.getenv("AUTH_COOKIE_SIGNING_KEY", "").strip()
AUTH_COOKIE_PERSISTENCE_MODE = os.getenv("AUTH_COOKIE_PERSISTENCE_ENABLED", "0").strip().lower()
if AUTH_COOKIE_PERSISTENCE_MODE in {"1", "true", "yes", "on"}:
    AUTH_COOKIE_PERSISTENCE_ENABLED = True
elif AUTH_COOKIE_PERSISTENCE_MODE in {"0", "false", "no", "off"}:
    AUTH_COOKIE_PERSISTENCE_ENABLED = False
else:
    # Security-first default for production: require explicit opt-in.
    AUTH_COOKIE_PERSISTENCE_ENABLED = False
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
            family_table = _family_user_table_name(supabase)
            family_resp = (
                supabase.table(family_table)
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


def get_public_landing_url() -> str:
    # Always route public back-links to the static marketing homepage.
    return "https://voicemailcare.com"


def redirect_to_public_landing() -> None:
    url = get_public_landing_url()
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={safe_url}">',
        unsafe_allow_html=True,
    )
    st.markdown(f"[Continue to main public page]({url})")
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


def _strip_optional_message_audio_columns(payload: dict) -> dict:
    cleaned = dict(payload or {})
    cleaned.pop("audio_object_path", None)
    cleaned.pop("audio_source", None)
    return cleaned


def _looks_like_base64_payload(value: str) -> bool:
    normalized = str(value or "").strip()
    if len(normalized) < 32:
        return False
    if len(normalized) % 4 != 0:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", normalized))


def _message_select_fields(include_audio: bool, include_optional_storage_columns: bool = True) -> str:
    fields = "id, resident_id, contact_user_id, family_id, channel, direction, recorded_at"
    if include_audio:
        audio_fields = ["audio_storage_path", "audio_mime_type", "audio_bytes"]
        if include_optional_storage_columns:
            audio_fields.extend(["audio_object_path", "audio_source"])
        fields = (
            "id, resident_id, contact_user_id, family_id, channel, direction, "
            + ", ".join(audio_fields)
            + ", recorded_at"
        )
    return fields


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


def _download_audio_from_storage(
    object_path: str, access_token: str | None = None
) -> bytes | None:
    path = str(object_path or "").strip()
    if not path:
        return None
    cache = st.session_state.get("_audio_storage_blob_cache")
    if not isinstance(cache, dict):
        cache = {}
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
            if _is_missing_column_error(exc, "audio_object_path") or _is_missing_column_error(
                exc, "audio_source"
            ):
                legacy_payload = _strip_optional_message_audio_columns(payload)
                try:
                    response = (
                        supabase.table("messages")
                        .upsert(legacy_payload, on_conflict=conflict_columns)
                        .execute()
                    )
                    st.session_state["_messages_conflict_upsert_supported"] = True
                    return response, None
                except Exception as legacy_exc:
                    return None, str(legacy_exc)
            if not _is_missing_conflict_constraint_error(exc):
                return None, str(exc)
            st.session_state["_messages_conflict_upsert_supported"] = False

    try:
        existing_query = supabase.table("messages").select("id")
        for key, value in lookup_filters.items():
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
                if _is_missing_column_error(exc, "audio_object_path") or _is_missing_column_error(
                    exc, "audio_source"
                ):
                    write_payload = _strip_optional_message_audio_columns(write_payload)
                    response = (
                        supabase.table("messages").update(write_payload).eq("id", existing_id).execute()
                    )
                else:
                    raise
        else:
            try:
                response = supabase.table("messages").insert(write_payload).execute()
            except Exception as exc:
                if _is_missing_column_error(exc, "audio_object_path") or _is_missing_column_error(
                    exc, "audio_source"
                ):
                    write_payload = _strip_optional_message_audio_columns(write_payload)
                    response = supabase.table("messages").insert(write_payload).execute()
                else:
                    raise
        return response, None
    except Exception as exc:
        return None, str(exc)

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
        return urlunparse(parsed._replace(path=normalized_path, query=normalized_query))
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
                "This email has not been invited yet. Please ask the care home to invite you.",
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
        return
    if callback_sig:
        st.session_state["_last_magiclink_callback_sig"] = callback_sig

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

    var markerKey = "vm_hash_normalized_sig_v1";
    var sig = raw.slice(0, 180);
    try {
      if (topWin.sessionStorage && topWin.sessionStorage.getItem(markerKey) === sig) return;
      if (topWin.sessionStorage) topWin.sessionStorage.setItem(markerKey, sig);
    } catch (e) {
      // Continue even if sessionStorage is unavailable.
    }

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
                        "This Mobile PIN is already used by another staff account in this care home. Choose a different PIN."
                    )
                else:
                    st.error(msg)
                return False
            mark_mobile_pin_verified()
            st.session_state["mobile_pin_just_accepted"] = True
            set_route(MOBILE_HOME_ROUTE)
            return True
        return False

    st.caption("PIN access is individual to each staff account.")
    with st.expander("Change Mobile PIN"):
        st.caption("Use this if you know your current PIN. If forgotten, ask Office to reset it.")
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
                        "This Mobile PIN is already used by another staff account in this care home. Choose a different PIN."
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
        return False, "Select a staff account first."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    try:
        supabase.rpc(
            "reset_staff_mobile_pin", {"p_staff_auth_user_id": target_user_id}
        ).execute()
        return True, "Mobile PIN reset. Staff member must set a new PIN at next Mobile login."
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
        relationship="",
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
                    "Family member linked to resident access\n"
                    f"Care home: {active_care_home_name}\n"
                    f"Registered by: {registering_staff_name}\n"
                    f"Date: {registration_date}\n"
                    f"Family email: {pending_payload.get('email', 'contact')}"
                )
                st.rerun()
            else:
                st.error(mapping_error or "Retry failed. Please try again.")

    active_care_home_name = str(
        st.session_state.get("active_care_home_name")
        or st.session_state.get("care_home_name")
        or "this care home"
    ).strip()
    if active_care_home_name.lower() == "this care home":
        resolved_care_home_name = fetch_active_care_home_name(access_token)
        if resolved_care_home_name:
            active_care_home_name = resolved_care_home_name
    registering_staff_name = str(
        st.session_state.get("auth_email")
        or st.session_state.get("auth_uid")
        or "Office staff"
    ).strip()
    registration_date = time.strftime("%d %b %Y")
    st.caption(
        f"{active_care_home_name} is registering a Family Member for this resident. "
        "The care home makes the access decision and keeps the registration record."
    )
    st.markdown("#### Registration record details")
    st.markdown(
        f"Care home: **{active_care_home_name}**  \n"
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
            include_room=True,
            include_care_home=False,
            separator=" | ",
        )
        resident_options.append(resident_id)
        resident_by_id[resident_id] = resident
        resident_label_by_id[resident_id] = label
    if not resident_options:
        st.info("No valid residents are available for family registration.")
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
        st.markdown("#### Section 1 — Family Member Details")
        first_name = st.text_input("First name", key="office_family_first_name")
        last_name = st.text_input("Last name", key="office_family_last_name")
        email = st.text_input("Email", key="office_family_email")
        st.markdown("#### Section 2 — Link to Resident")
        resident_id = st.selectbox(
            "Resident",
            resident_options,
            format_func=lambda rid: resident_label_by_id.get(rid, "Resident"),
            key="office_family_resident_select",
        )
        st.markdown("#### Section 3 — Confirmation")
        resident_access_confirmed = st.checkbox(
            f"I confirm that {active_care_home_name} has decided this person may be added "
            "as a Family Member for this resident and is solely responsible "
            "for determining, granting, and maintaining their access to the resident.",
            key="office_family_authorisation_confirm",
        )
        st.caption(
            "voicemailcare.com does not decide who may be added. The care home is responsible for that decision."
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
    if not first_value or not last_value or not normalized_email:
        st.error("First name, last name, and email are required.")
        return
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        st.error("Enter a valid email address.")
        return
    if not resident_access_confirmed:
        st.error("Please confirm care home authorisation before sending the invitation.")
        return

    resident = resident_by_id.get(resident_id)
    if not resident:
        st.error("Select a resident.")
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
    }
    mapping_ok, mapping_error = _apply_family_registration_mapping(access_token, payload)
    if mapping_ok:
        st.session_state.pop(pending_key, None)
        st.success(
            "Invitation sent\n"
            f"Care home: {active_care_home_name}\n"
            f"Registered by: {registering_staff_name}\n"
            f"Date: {registration_date}\n"
            f"Family email: {normalized_email}\n"
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
        render_route_link(
            "Back to videos",
            "/public/walkthrough-overview",
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
            set_route("/public/walkthrough-overview")
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


def render_how_it_works_diagram_and_notes() -> None:
    diagram_path = Path("assets/voice-message-flow-diagram.png")
    if diagram_path.exists():
        try:
            st.image(str(diagram_path), caption="Voicemailcare.com flow diagram", use_container_width=True)
        except TypeError:
            st.image(str(diagram_path), caption="Voicemailcare.com flow diagram", use_column_width=True)
    else:
        st.error("Flow diagram image not found: assets/voice-message-flow-diagram.png")
    st.markdown(
        "- The diagram shows the three app interfaces: Family, Care Hub – Mobile, and Care Hub – Office.\n"
        "- Each Family Member has their own individual communication channel to the resident.\n"
        "- Office practical messages collect quick structured family responses to support efficient, inclusive practical decision-making.\n"
        "- The care home reviews responses and makes the final operational decision.\n"
        "- Each channel keeps only the latest message, and a new message replaces the previous one in that channel."
    )


def render_how_it_works_video_links(
    specific_label: str,
    specific_route: str,
    key_prefix: str,
) -> None:
    st.markdown("### Watch videos")
    video_cols = st.columns(2, gap="small")
    with video_cols[0]:
        render_route_link(
            "Universal Diagram video",
            "/public/walkthrough-overview",
            key=f"{key_prefix}_video_overview_link",
        )
    with video_cols[1]:
        render_route_link(
            f"{specific_label} Record video",
            specific_route,
            key=f"{key_prefix}_video_specific_link",
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
        "voicemailcare.com — for non-urgent social voice messages between residents and Family Members.",
        "Family -> Resident uses separate per-family-member channels. Resident -> Family channel keeps the latest shared resident message for all Family Members. No threads.",
        "Family access uses secure email login links. No SMS and no phone-number login.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    render_how_it_works_video_links("Family", "/public/walkthrough-family", "how_family")
    render_how_it_works_diagram_and_notes()
    family_back_route = (
        get_home_route(VARIANT_FAMILY)
        if st.session_state.get("auth_uid")
        else get_login_route(VARIANT_FAMILY)
    )
    render_route_link("Back to Family", family_back_route, key="family_how_it_works_back_link")


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
        "voicemailcare.com — for non-urgent social voice messages between residents and Family Members.",
        "Family -> Resident uses separate per-family-member channels. Resident -> Family channel keeps the latest shared resident message for all Family Members. No threads.",
        "Care Hub – Mobile uses individual staff PIN access for day-to-day use.",
        "Secure email link is used only for first sign-in or expired-session recovery.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    render_how_it_works_video_links(
        "Care Hub – Mobile",
        "/public/walkthrough-mobile",
        "how_mobile",
    )
    render_how_it_works_diagram_and_notes()
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
        "voicemailcare.com — for non-urgent social voice messages between residents and Family Members.",
        "Family -> Resident uses separate per-family-member channels. Resident -> Family channel keeps the latest shared resident message for all Family Members. No threads.",
        "Care Hub – Office is a separate staff/admin access path.",
        "Office authentication is distinct from Family email links and Mobile staff PIN access.",
        "If Office 2FA is enabled, users complete Office verification after login.",
    ]
    for box in info_boxes:
        st.markdown(f'<div class="family-how-box">{box}</div>', unsafe_allow_html=True)
    render_how_it_works_video_links(
        "Care Hub – Office",
        "/public/walkthrough-office",
        "how_office",
    )
    render_how_it_works_diagram_and_notes()


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
        render_route_link("Back", "/family/how-it-works", key="family_doc_back_link")
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
        render_route_link("Back", "/family/how-it-works", key="family_contact_back_link")
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
            if st.button("Videos", key="care_hub_nav_service_overview", use_container_width=True):
                set_route("/public/walkthrough-overview")
        with nav_cols[2]:
            if st.button("Contracts", key="care_hub_nav_contracts", use_container_width=True):
                set_route("/contracts")
        with nav_cols[3]:
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
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
    if runtime_variant not in {VARIANT_MOBILE, VARIANT_OFFICE}:
        wrong_variant_screen(get_route(), "Care Hub pages are not available in this app.")
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
        if runtime_variant == VARIANT_OFFICE:
            st.session_state["office_login_explicit"] = True
        if runtime_variant == VARIANT_OFFICE and is_office_mfa_required():
            if get_route() != "/care-hub/mfa":
                set_route("/care-hub/mfa")
            st.stop()
        return
    if family_found:
        render_wrong_variant("Your login details are for Family.")
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
            str(c.get("full_name") or "").strip().casefold(),
            str(c.get("id") or ""),
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
        include_audio=False,
    )
    ordered_user_ids: list[str] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
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
        return ""
    return str(resp.data[0].get("last_played_recorded_at") or "").strip()


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
        include_audio=False,
    )

    queued_items: list[dict] = []
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
            continue
        if not contact_user_id:
            continue
        if str(latest.get("contact_user_id") or "").strip() != contact_user_id:
            latest = dict(latest)
            latest["contact_user_id"] = contact_user_id
        contact["auth_user_id"] = contact_user_id
        is_unread = not has_message_been_played_since_recorded(
            latest,
            resident_id=resident_id,
            care_home_id=care_home_id,
        )
        if is_unread and has_message_been_played_in_mobile_session_since_recorded(
            latest,
            resident_id=resident_id,
        ):
            is_unread = False
        queued_items.append(
            {
                "contact": contact,
                "message": latest,
                "is_unread": is_unread,
                "contact_user_id": contact_user_id,
            }
        )

    if not queued_items:
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

    min_play_count = min(0 if bool(item.get("is_unread")) else 1 for item in queued_items)
    active_round_user_ids = {
        str(item.get("contact_user_id") or "").strip()
        for item in queued_items
        if (0 if bool(item.get("is_unread")) else 1) == min_play_count
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
                        else "Played cycle"
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
        include_audio=False,
    )
    unread_count = 0
    unread_contacts: list[dict] = []
    next_contact: dict | None = None
    for contact in contacts_sorted:
        contact_user_id = str(contact.get("auth_user_id") or "").strip()
        latest = latest_by_contact.get(contact_user_id)
        if not latest:
            continue
        if next_contact is None:
            next_contact = contact
        if contact_user_id and str(latest.get("contact_user_id") or "").strip() != contact_user_id:
            latest = dict(latest)
            latest["contact_user_id"] = contact_user_id
        is_unread = not has_message_been_played_since_recorded(
            latest,
            resident_id=resident_id,
            care_home_id=care_home_id,
        )
        if is_unread:
            unread_count += 1
            unread_contacts.append(contact)
            if next_contact is None:
                next_contact = contact
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
        clear_session_state()
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


def get_care_hub_idle_timeout_seconds(access_token: str | None) -> int:
    profile = fetch_active_care_home_profile(access_token)
    timeout_value = profile.get("care_hub_idle_timeout_seconds")
    return normalize_care_hub_idle_timeout_seconds(timeout_value)


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


def fetch_active_care_home_profile(access_token: str | None) -> dict:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id or not access_token:
        return {}
    cache_key = f"care_home_profile_{care_home_id}"
    cached_profile = st.session_state.get(cache_key)
    if isinstance(cached_profile, dict) and str(cached_profile.get("name") or "").strip():
        return cached_profile
    supabase, error = get_authed_supabase(access_token)
    if error:
        return {}
    select_fields = (
        "name, branding_banner_title, branding_banner_text, "
        "branding_banner_artwork_url, care_hub_idle_timeout_seconds"
    )
    fallback_select_fields = (
        "name, branding_banner_title, branding_banner_text, branding_banner_artwork_url"
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
            if not _is_missing_column_error(exc, "care_hub_idle_timeout_seconds"):
                raise
            resp = (
                supabase.table("care_homes")
                .select(fallback_select_fields)
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
                if not _is_missing_column_error(exc, "care_hub_idle_timeout_seconds"):
                    raise
                fallback_resp = (
                    supabase.table("care_homes")
                    .select(fallback_select_fields)
                    .eq("id", care_home_id)
                    .limit(1)
                    .execute()
                )
            row = (fallback_resp.data or [{}])[0]
        profile = {
            "name": str(row.get("name") or "").strip(),
            "branding_banner_title": str(row.get("branding_banner_title") or "").strip(),
            "branding_banner_text": str(row.get("branding_banner_text") or "").strip(),
            "branding_banner_artwork_url": str(row.get("branding_banner_artwork_url") or "").strip(),
            "care_hub_idle_timeout_seconds": normalize_care_hub_idle_timeout_seconds(
                row.get("care_hub_idle_timeout_seconds")
            ),
        }
        if profile["name"]:
            st.session_state[cache_key] = profile
        return profile
    except Exception:
        return {}


def update_active_care_home_branding(
    access_token: str | None,
    *,
    care_home_name: str,
    banner_title: str,
    banner_text: str,
    banner_artwork_url: str,
    care_hub_idle_timeout_seconds: int,
) -> tuple[bool, str]:
    care_home_id = str(st.session_state.get("active_care_home_id") or "").strip()
    if not care_home_id:
        return False, "No active care home is linked to this session."
    if not access_token:
        return False, "Session is missing access credentials. Please sign in again."
    name_value = str(care_home_name or "").strip()
    title_value = str(banner_title or "").strip()
    text_value = str(banner_text or "").strip()
    artwork_value = str(banner_artwork_url or "").strip()
    timeout_value = normalize_care_hub_idle_timeout_seconds(care_hub_idle_timeout_seconds)
    if not name_value:
        return False, "Care home name is required."
    if len(name_value) > 160:
        return False, "Care home name must be 160 characters or fewer."
    if len(title_value) > 120:
        return False, "Banner title must be 120 characters or fewer."
    if len(text_value) > 800:
        return False, "Banner text must be 800 characters or fewer."
    if artwork_value and not re.match(r"^https?://", artwork_value, re.IGNORECASE):
        return False, "Artwork URL must start with http:// or https://"
    if len(artwork_value) > 1000:
        return False, "Artwork URL must be 1000 characters or fewer."
    supabase, error = get_authed_supabase(access_token)
    if error:
        return False, error
    update_payload = {
        "name": name_value,
        "branding_banner_title": title_value or None,
        "branding_banner_text": text_value or None,
        "branding_banner_artwork_url": artwork_value or None,
        "care_hub_idle_timeout_seconds": timeout_value,
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
            if not _is_missing_column_error(exc, "care_hub_idle_timeout_seconds"):
                raise
            update_payload.pop("care_hub_idle_timeout_seconds", None)
            (
                supabase.table("care_homes")
                .update(update_payload)
                .eq("id", care_home_id)
                .execute()
            )
        st.session_state.pop(f"care_home_profile_{care_home_id}", None)
        persisted_profile = fetch_active_care_home_profile(access_token)
        persisted_name = str((persisted_profile or {}).get("name") or "").strip()
        persisted_title = str((persisted_profile or {}).get("branding_banner_title") or "").strip()
        persisted_text = str((persisted_profile or {}).get("branding_banner_text") or "").strip()
        persisted_artwork = str((persisted_profile or {}).get("branding_banner_artwork_url") or "").strip()
        if (
            persisted_name != name_value
            or persisted_title != title_value
            or persisted_text != text_value
            or persisted_artwork != artwork_value
        ):
            return (
                False,
                "Settings could not be confirmed after save. Please retry or check care_homes update permissions.",
            )
        return True, "Care home profile updated."
    except Exception as exc:
        return False, str(exc)


def render_care_home_identity_banner(access_token: str | None) -> None:
    if (
        get_app_variant() in {VARIANT_MOBILE, VARIANT_OFFICE}
        and st.session_state.get("_care_home_banner_rendered_in_header")
    ):
        return
    care_home_profile = fetch_active_care_home_profile(access_token)
    care_home_name = str(care_home_profile.get("name") or "").strip()
    if care_home_name:
        safe_name = html.escape(care_home_name)
        st.markdown(
            (
                '<div style="margin:6px 0 12px 0;padding:8px 10px;'
                'border:1px solid rgba(31,31,31,0.12);border-radius:10px;'
                'background:rgba(153,255,255,0.18);font-size:0.92rem;">'
                f"<strong>Care home:</strong> {safe_name}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    else:
        st.caption("You are signed in.")
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
    care_home_profile = fetch_active_care_home_profile(access_token)
    care_home_name = str(care_home_profile.get("name") or "").strip()
    if care_home_name:
        st.markdown(
            (
                '<div class="vm-care-home-banner">'
                f"<strong>Care home:</strong> {care_home_name}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.session_state["_care_home_banner_rendered_in_header"] = True
    rendered = render_active_care_home_custom_banner(care_home_profile)
    st.session_state["_care_home_custom_banner_rendered"] = bool(rendered)


def render_active_care_home_custom_banner(care_home_profile: dict) -> bool:
    if not isinstance(care_home_profile, dict):
        return False
    banner_title = str(care_home_profile.get("branding_banner_title") or "").strip()
    banner_text = str(care_home_profile.get("branding_banner_text") or "").strip()
    banner_artwork_url = str(care_home_profile.get("branding_banner_artwork_url") or "").strip()
    if not banner_title and not banner_text and not banner_artwork_url:
        return False
    escaped_title = html.escape(banner_title)
    escaped_text = html.escape(banner_text)
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
    if banner_artwork_url:
        # Use browser-side rendering to avoid Streamlit server-side URL fetch limitations.
        safe_artwork_url = html.escape(banner_artwork_url.replace(" ", "%20"), quote=True)
        st.markdown(
            f'<img src="{safe_artwork_url}" alt="Care home custom banner artwork" '
            'style="display:block;max-width:100%;height:auto;border-radius:6px;" />',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return True


def get_resident_full_name(resident: dict) -> str:
    preferred_name = str(resident.get("preferred_name") or "").strip()
    surname = str(resident.get("surname") or "").strip()
    full_name = " ".join(part for part in (preferred_name, surname) if part).strip()
    return full_name or "Resident"


def format_resident_identity_label(
    resident: dict,
    *,
    include_room: bool = True,
    include_care_home: bool = True,
    separator: str = " | ",
) -> str:
    parts = [get_resident_full_name(resident)]
    if include_room:
        room = str(resident.get("room") or "").strip()
        if room:
            parts.append(f"Room {room}")
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


def fetch_latest_message_for_contact_with_mapping_repair(
    resident_id: str,
    access_token: str,
    contact: dict,
    *,
    channel: str = "resident_family",
    include_audio: bool = True,
) -> dict | None:
    contact_user_id = str(contact.get("auth_user_id") or "").strip()
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

    contact_email = str(contact.get("email") or "").strip().lower()
    if not contact_email:
        return None
    resolved_user_id = _get_contact_auth_user_id_via_email(contact_email)
    if not resolved_user_id:
        return None

    if resolved_user_id != contact_user_id:
        contact["auth_user_id"] = resolved_user_id
        contact_id = str(contact.get("id") or "").strip()
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

    return fetch_latest_message(
        resident_id,
        "to_resident",
        access_token,
        contact_user_id=resolved_user_id,
        channel=channel,
        include_audio=include_audio,
    )


def fetch_latest_message(
    resident_id: str,
    direction: str,
    access_token: str,
    contact_user_id: str | None = None,
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
        if family_id is not None:
            query = query.eq("family_id", family_id)
        try:
            resp = query.execute()
        except Exception as exc:
            if include_audio and (
                _is_missing_column_error(exc, "audio_object_path")
                or _is_missing_column_error(exc, "audio_source")
            ):
                fallback_query = (
                    supabase.table("messages")
                    .select(
                        _message_select_fields(
                            include_audio=include_audio,
                            include_optional_storage_columns=False,
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
                if family_id is not None:
                    fallback_query = fallback_query.eq("family_id", family_id)
                resp = fallback_query.execute()
            else:
                raise
        latest = resp.data[0] if resp.data else None
        if APP_DEBUG and direction == "from_resident":
            if latest:
                print(
                    "Loading Resident→Family message:",
                    latest.get("id"),
                    latest.get("recorded_at"),
                    latest.get("contact_user_id"),
                )
            else:
                print(
                    "Loading Resident→Family message: none",
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
            if include_audio and (
                _is_missing_column_error(exc, "audio_object_path")
                or _is_missing_column_error(exc, "audio_source")
            ):
                resp = (
                    supabase.table("messages")
                    .select(
                        _message_select_fields(
                            include_audio=include_audio,
                            include_optional_storage_columns=False,
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


def fetch_latest_open_office_practical_message(
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
                "status, created_at, context_type, requested_date, requested_time_window"
            )
            .eq("resident_id", resident_id)
            .eq("status", "open")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
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
            return row
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
    if primary_choice not in {"yes", "no", "maybe"}:
        return False, "Please choose Yes, No, or Maybe."
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
            msg_resp = supabase.table("office_practical_messages").insert(legacy_payload).execute()
        message_id = (
            str(msg_resp.data[0].get("id") or "").strip()
            if msg_resp.data
            else ""
        )
        if not message_id:
            return False, None, "Could not publish practical message."
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
        return True, message_id, "Practical message published."
    except Exception as exc:
        return False, None, str(exc)


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
        return True, "Responses closed for this practical message."
    except Exception as exc:
        return False, str(exc)


def fetch_office_practical_response_summary(
    message_id: str,
    access_token: str | None,
) -> dict:
    summary = {
        "responses": [],
        "choice_counts": {"yes": 0, "no": 0, "maybe": 0},
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
  <span class="vm-logo-text">voicemailcare.com</span>
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
    current_route = st.session_state.get("current_page") or get_route()
    app_variant = resolve_runtime_variant(route_hint=current_route)
    prev_route = st.session_state.get("prev_page") or "/"
    show_back_only = current_route.startswith("/how-it-works/") and prev_route in ("/", "", None)
    with st.popover("≡"):
        # Prevent first action from clipping at the popover edge on small screens.
        st.markdown('<div style="height:0.9rem"></div>', unsafe_allow_html=True)
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
                if st.button("Videos", key=f"{menu_key}_office_service_overview_public"):
                    set_route("/public/walkthrough-overview")
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
            if st.button("Operational variables", key=f"{menu_key}_operational_variables"):
                clicked_action = ("route", "/care-hub/operational-variables")
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
            if st.button("Handover checklist", key=f"{menu_key}_office_doc_handover"):
                clicked_action = ("doc", "docs/office/care_home_handover_checklist.md")
            if st.button("Office Q&A", key=f"{menu_key}_office_doc_qa"):
                clicked_action = ("route", "/care-hub/office/qa")

            st.markdown("— Governance —")
            if st.button("Videos", key=f"{menu_key}_office_service_overview"):
                clicked_action = ("route", "/public/walkthrough-overview")
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
            if st.button("Public info", key=f"{menu_key}_public_docs"):
                redirect_to_public_landing()
                return
        if app_variant == VARIANT_MOBILE:
            is_authed = bool(st.session_state.get("auth_uid"))
            back_target = get_home_route(app_variant) if is_authed else get_login_route(app_variant)
            if prev_route and prev_route != current_route:
                back_target = prev_route
            if normalize_route(back_target) == normalize_route(current_route):
                render_public_landing_link(
                    "Back to main public page",
                    key=f"{menu_key}_mobile_back_public_link",
                )
            else:
                render_route_link("Back", back_target, key=f"{menu_key}_mobile_back_link")
            if st.button("Public info", key=f"{menu_key}_mobile_public_docs"):
                redirect_to_public_landing()
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
            render_public_landing_link(
                "Back to main public page",
                key=f"{menu_key}_family_back_public_link",
            )
            render_route_link(
                "How it works",
                get_how_it_works_route(app_variant),
                key=f"{menu_key}_family_how_link",
            )
            render_route_link(
                "Videos",
                "/public/walkthrough-overview",
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
        '<div class="front-page-info-box">voicemailcare.com — for non-urgent social voice messages.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">One message kept at a time in each direction (between each Family Member and each resident), with no threads.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="front-page-info-box">Not a live service. Messages are played when staff are available.</div>',
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
    render_how_it_works_diagram_and_notes()


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
        logo_data = get_logo_data_uri()
        if logo_data:
            header_html = (
                f'<div class="public-header">'
                f'<img src="{logo_data}" alt="logo" style="height:84px;width:auto;display:block;" />'
                f'<div class="public-header-title">voicemailcare.com</div>'
                f"</div>"
            )
        else:
            header_html = (
                '<div class="public-header">'
                '<div class="public-header-title">voicemailcare.com</div>'
                "</div>"
            )
        st.markdown(header_html, unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## Familiar voices")
        st.markdown(
            "A simple communication tool for care homes, residents, and their families."
        )
        st.markdown(
            "Family members may each send an individual message to a resident at any time, as it is not a live service. "
            "Carers may play messages for the resident when convenient. Carers may also help residents record one reply to the family group."
        )
        st.markdown(
            "The care home may also send non-urgent or practical updates, and families may respond with structured text to simple requests."
        )
        st.markdown(
            "There is no message history, no long threads, and it is not live. "
            "It fits around normal care routines and helps keep communication manageable."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## A simple way to explore the idea")
        st.markdown(
            "Voicemail Care can be introduced through a one-to-one, activity-based session in the care home."
        )
        st.markdown(
            "The session uses printed artwork and conversation as a starting point. "
            "A short voice message can be played as part of the interaction, introducing the idea in a natural way."
        )
        st.markdown(
            "There is no obligation to adopt anything, simply an opportunity to see how this might help communication for you."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("## Feedback welcome")
        st.markdown(
            "We warmly welcome feedback from carers, residents (with support), and families to help us improve this service."
        )
        st.caption("Anonymous only. Please do not include names, emails, phone numbers, or medical details.")
        with st.form("public_feedback_form", clear_on_submit=True):
            audience_choice = st.selectbox(
                "Who are you?",
                options=[
                    ("family", "Family"),
                    ("resident_supported", "Resident (with support)"),
                    ("carer", "Carer"),
                ],
                format_func=lambda item: item[1],
                key="public_feedback_audience",
            )
            ease_score = st.radio(
                "1. How easy was voice-message.com to use today?",
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
                "3. Would you recommend this for care-home communication?",
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
        if st.button(
            "Watch Universal Diagram video",
            key="public_watch_overview",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-overview")
        app_cols = st.columns(3, gap="small")
        app_entries = [
            (
                VARIANT_FAMILY,
                "Family",
                "For families and friends to send and hear non-urgent messages.",
                "/public/walkthrough-family",
                "PUBLIC_FAMILY_RECORD_VIDEO_URL,PUBLIC_VIDEO_FAMILY_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_FAMILY_URL",
                "assets/voice-message-family-walkthrough-v1.mp4",
            ),
            (
                VARIANT_MOBILE,
                "Care Hub – Mobile",
                "For care staff to play family messages and support resident recordings.",
                "/public/walkthrough-mobile",
                "PUBLIC_MOBILE_RECORD_VIDEO_URL,PUBLIC_VIDEO_MOBILE_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_MOBILE_URL",
                "assets/voice-message-mobile-walkthrough-v1.mp4",
            ),
            (
                VARIANT_OFFICE,
                "Care Hub – Office",
                "For office oversight, one-way updates, and practical structured messages.",
                "/public/walkthrough-office",
                "PUBLIC_OFFICE_RECORD_VIDEO_URL,PUBLIC_VIDEO_OFFICE_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_OFFICE_URL",
                "assets/voice-message-office-walkthrough-v1.mp4",
            ),
        ]
        for idx, (variant, label, summary, walkthrough_route, video_env_var, local_video_path) in enumerate(app_entries):
            target_url = get_public_app_url(variant)
            if variant == VARIANT_FAMILY:
                watch_label = "Watch Family Record video"
            elif variant == VARIANT_MOBILE:
                watch_label = "Watch Care Hub – Mobile Record video"
            else:
                watch_label = "Watch Care Hub – Office Record video"
            with app_cols[idx]:
                if st.button(watch_label, key=f"public_watch_{variant}", use_container_width=True):
                    set_route(walkthrough_route)
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
        public_diagram_path = Path("assets/voice-message-flow-diagram.png")
        if public_diagram_path.exists():
            try:
                st.image(
                    str(public_diagram_path),
                    caption="Voicemailcare.com flow diagram",
                    use_container_width=True,
                )
            except TypeError:
                st.image(
                    str(public_diagram_path),
                    caption="Voicemailcare.com flow diagram",
                    use_column_width=True,
                )
        else:
            st.error("Flow diagram image not found: assets/voice-message-flow-diagram.png")
        st.markdown(
            "- The diagram shows the three app interfaces: Family, Care Hub – Mobile, and Care Hub – Office.\n"
            "- Each family member has their own individual communication channel to the resident, managed by the care home.\n"
            "- Office practical messages collect quick structured family responses to support efficient, inclusive practical decision-making.\n"
            "- The care home reviews responses and makes the final operational decision.\n"
            "- Each channel keeps only the latest message, and a new message replaces the previous one in that channel."
        )
        st.markdown("### Communication participants")
        st.markdown("- Residents")
        st.markdown("- Families")
        st.markdown("- Care Hub (Office and Mobile)")
        st.caption("Here, families means Family Members registered by the care home.")
        st.markdown(
            "Each channel keeps only the latest message. A new message replaces the previous message in that channel."
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-grid public-grid-3">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-card">
              <h3>Office -&gt; Family (one-way updates)</h3>
              <div>Care Hub – Office sends the latest general update voice message to all Family Members. No replies in this general update channel. A new update replaces the previous general update.</div>
            </div>
            <div class="public-card">
              <h3>Office practical text message (structured replies from family)</h3>
              <div>Care Hub – Office can also send the latest practical text message for a resident. Family replies are designed to be minimal: Yes/No/Maybe plus optional tick-box selections, with only a short optional note.</div>
            </div>
            <div class="public-card pink">
              <h3>Resident -&gt; Family (one message out)</h3>
              <div>Care Hub – Mobile supports the resident to record the latest message to all Family Members. A new recording replaces the previous resident message.</div>
            </div>
            <div class="public-card">
              <h3>Family -&gt; Resident (one message each)</h3>
              <div>Each Family Member channel keeps only the latest message to the resident. Mobile playback is one-at-a-time in a fair rotating order, with unplayed messages first.</div>
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
              <div class="public-step">This is not live messaging</div>
              <div class="public-step">Messages are played when staff are available and recorded when appropriate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="public-section">', unsafe_allow_html=True)
        st.markdown("<h2>Playback and privacy</h2>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="public-roles">
              <div class="public-card">
                <h3>Family privacy boundary</h3>
                <div>Family members do not hear each other's Family -&gt; Resident messages. Each Family Member channel is separate.</div>
              </div>
              <div class="public-card pink">
                <h3>Care Hub playback</h3>
                <div>Family messages are played to residents in Care Hub – Mobile and are operationally visible in Care Hub – Office.</div>
              </div>
              <div class="public-card">
                <h3>No live pressure</h3>
                <div>No notifications, no delivery/read receipts, and no typing indicators. Message date is shown without time in Family and Care Hub – Mobile views.</div>
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
              <div><strong>Family Members:</strong> Family Members send messages and listen to the resident's current shared reply.</div>
              <div><strong>Care Hub – Mobile:</strong> staff play family messages and support resident recordings.</div>
              <div><strong>Care Hub – Office:</strong> oversight plus one-way updates to family.</div>
              <div style="margin-top:8px;">This service is for social communication only. It is not for medical updates, health information, safeguarding communication, or urgent enquiries. For those matters, contact the care home directly using normal channels.</div>
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
        public_diagram_path = Path("assets/voice-message-flow-diagram.png")
        if public_diagram_path.exists():
            try:
                st.image(
                    str(public_diagram_path),
                    caption="Voicemailcare.com flow diagram",
                    use_container_width=True,
                )
            except TypeError:
                st.image(
                    str(public_diagram_path),
                    caption="Voicemailcare.com flow diagram",
                    use_column_width=True,
                )
            st.markdown("Communication participants")
            st.markdown(
                "This diagram shows how voice messages and updates are organised across channels. "
                "Each Family Member has their own individual channel for "
                "Family/Friend -> Resident messages, managed by the care home. Care Hub – Mobile plays these family messages in a "
                "fair rotating order, with unplayed messages first."
            )
            st.markdown(
                "Resident -> Family channel keeps the latest resident message shared to all Family Members. "
                "The care home can also send a one-way Office update to all Family Members. "
                "Office practical messages collect quick structured family responses, and the care home makes the final operational decision. "
                "Each Family Member channel keeps only the latest message. "
                "A new message replaces only the previous message in that channel."
            )
            st.markdown("### Start here: Service flow overview (90 seconds)")
            overview_video = resolve_public_video_source(
                "PUBLIC_VIDEO_OVERVIEW_URL",
                "assets/voice-message-flow-overview-v1.mp4",
            )
            if overview_video:
                try:
                    st.video(overview_video)
                except Exception:
                    pass
    st.markdown("### Service overview")
    current_variant = get_app_variant()
    render_public_landing_link(
        "← Back to main public page",
        key=f"service_overview_back_to_public_docs_{current_variant}",
    )
    st.markdown(
        "voicemailcare.com  \n"
        "One message in. One message out.  \n"
        "No threads. No pressure.\n\n"
        "The service supports non-urgent social voice messages between residents and Family Members.  \n"
        "The care home office may also send non-urgent general updates about daily life in the home.  \n"
        "Office updates are one-way informational messages.\n\n"
        "This is not a live service. Messages are played when staff are available, to fit around care routines.  \n"
        "The service is not intended for care updates, health information, safeguarding communication, or urgent enquiries."
    )

    button_cols = st.columns(3, gap="small")
    render_public_app_buttons(button_cols)

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
    "/public/walkthrough-family",
    "/public/walkthrough-family-flow",
    "/public/walkthrough-mobile",
    "/public/walkthrough-mobile-flow",
    "/public/walkthrough-office",
    "/public/walkthrough-office-flow",
    "/public/walkthrough-overview",
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
    "/public/walkthrough-family",
    "/public/walkthrough-family-flow",
    "/public/walkthrough-mobile",
    "/public/walkthrough-mobile-flow",
    "/public/walkthrough-office",
    "/public/walkthrough-office-flow",
    "/public/walkthrough-overview",
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
            "/public/walkthrough-family",
            "/public/walkthrough-family-flow",
            "/public/walkthrough-mobile",
            "/public/walkthrough-mobile-flow",
            "/public/walkthrough-office",
            "/public/walkthrough-office-flow",
            "/public/walkthrough-overview",
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
            "/public/walkthrough-family",
            "/public/walkthrough-family-flow",
            "/public/walkthrough-mobile",
            "/public/walkthrough-mobile-flow",
            "/public/walkthrough-office",
            "/public/walkthrough-office-flow",
            "/public/walkthrough-overview",
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
            "/public/resident-participation",
            "/public/family-guide",
            "/public/qa",
            "/public/faq",
            "/public/privacy-notice",
            "/public/family-terms-of-use",
            "/public/complaints-and-concerns",
            "/public/safeguarding-and-consent",
            "/public/walkthrough-family",
            "/public/walkthrough-family-flow",
            "/public/walkthrough-mobile",
            "/public/walkthrough-mobile-flow",
            "/public/walkthrough-office",
            "/public/walkthrough-office-flow",
            "/public/walkthrough-overview",
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
            "/public/walkthrough-family",
            "/public/walkthrough-family-flow",
            "/public/walkthrough-mobile",
            "/public/walkthrough-mobile-flow",
            "/public/walkthrough-office",
            "/public/walkthrough-office-flow",
            "/public/walkthrough-overview",
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
    if normalized.startswith("/family") or normalized == "/how-it-works/family":
        return VARIANT_FAMILY
    if (
        normalized.startswith("/care-hub/mobile")
        or normalized.startswith("/mobile")
        or normalized == "/how-it-works/mobile"
    ):
        return VARIANT_MOBILE
    if (
        normalized.startswith("/care-hub")
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
        and is_login_route_for_variant(app_variant, current_route)
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
        st.session_state["office_login_explicit"] = True
        return get_home_route(VARIANT_OFFICE)
    return get_login_route(VARIANT_OFFICE)


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


def normalize_public_video_url(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    # Allow values copied as "URL=https://..." or "PUBLIC_VIDEO_...=https://...".
    if "=" in value:
        lhs, rhs = value.split("=", 1)
        lhs = lhs.strip().lower()
        rhs = rhs.strip()
        if lhs.endswith("url") and rhs.startswith(("http://", "https://")):
            value = rhs
    # Strip accidental wrapping quotes.
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    return value


DEFAULT_PUBLIC_VIDEO_URLS: dict[str, str] = {}


def resolve_public_video_source(env_var: str, local_path: str) -> str | None:
    candidate_vars = [candidate.strip() for candidate in str(env_var).split(",") if candidate.strip()]
    for candidate in candidate_vars:
        url = normalize_public_video_url(os.getenv(candidate, ""))
        parsed = urlparse(url) if url else None
        host = ((parsed.netloc if parsed else "") or "").lower()
        if url and host.endswith("dropbox.com"):
            continue
        if url:
            return url
    for candidate in candidate_vars:
        fallback_url = normalize_public_video_url(DEFAULT_PUBLIC_VIDEO_URLS.get(candidate, ""))
        if fallback_url:
            return fallback_url
    local_file = Path(local_path)
    if local_file.exists():
        return str(local_file)
    return None


def render_public_app_buttons(cols: list) -> None:
    entries = [
        ("Family", "/public/walkthrough-family"),
        ("Care Hub – Mobile", "/public/walkthrough-mobile"),
        ("Care Hub – Office", "/public/walkthrough-office"),
    ]
    for idx, (label, route) in enumerate(entries):
        with cols[idx]:
            if st.button(label, key=f"public_walkthrough_{idx}", use_container_width=True):
                set_route(route)


def render_public_walkthrough_page(
    page_title: str,
    video_env_var: str,
    local_video_path: str,
    role_summary: list[str],
    back_route: str | None = None,
    fallback_doc_path: str | None = None,
) -> None:
    def _is_walkthrough_route(route_value: str) -> bool:
        normalized = normalize_route(route_value)
        return normalized.startswith("/public/walkthrough")

    effective_back_route = back_route
    current_route = normalize_route(get_route()) or "/"
    prev_route = normalize_route(st.session_state.get("prev_page") or "")
    back_route_memory_key = f"_walkthrough_back_route::{current_route}"
    if (
        not effective_back_route
        and prev_route
        and prev_route != current_route
        and not (_is_walkthrough_route(current_route) and _is_walkthrough_route(prev_route))
    ):
        # Preserve in-app navigation context (for example Family -> Diagram video -> Back).
        effective_back_route = prev_route
        st.session_state[back_route_memory_key] = prev_route
    if not effective_back_route:
        remembered_back_route = normalize_route(st.session_state.get(back_route_memory_key) or "")
        if (
            remembered_back_route
            and remembered_back_route != current_route
            and not (
                _is_walkthrough_route(current_route)
                and _is_walkthrough_route(remembered_back_route)
            )
        ):
            effective_back_route = remembered_back_route
    if not effective_back_route:
        app_variant = resolve_runtime_variant(route_hint=current_route)
        if app_variant == VARIANT_PUBLIC:
            effective_back_route = "/service-overview"
        elif app_variant == VARIANT_OFFICE:
            if st.session_state.get("auth_uid"):
                effective_back_route = "/docs"
            else:
                effective_back_route = "/service-overview"
        elif app_variant in {VARIANT_MOBILE, VARIANT_FAMILY}:
            effective_back_route = "/service-overview"
        else:
            effective_back_route = "/service-overview"
    # If an authenticated user opened walkthrough pages from login flow/history,
    # keep Back inside the authenticated app home rather than returning to login.
    if (
        st.session_state.get("auth_uid")
        and effective_back_route in {FAMILY_LOGIN_ROUTE, MOBILE_LOGIN_ROUTE, OFFICE_LOGIN_ROUTE}
    ):
        active_role = str(st.session_state.get("active_role") or "").strip().lower()
        if active_role == "family":
            effective_back_route = FAMILY_HOME_ROUTE
        elif active_role == "care_hub":
            if bool(st.session_state.get("office_login_explicit")):
                effective_back_route = OFFICE_HOME_ROUTE
            elif effective_back_route == OFFICE_LOGIN_ROUTE:
                effective_back_route = OFFICE_HOME_ROUTE
            else:
                effective_back_route = MOBILE_HOME_ROUTE
        else:
            base_variant = get_app_variant()
            if base_variant == VARIANT_FAMILY:
                effective_back_route = FAMILY_HOME_ROUTE
            elif base_variant == VARIANT_MOBILE:
                effective_back_route = MOBILE_HOME_ROUTE
            elif base_variant == VARIANT_OFFICE:
                effective_back_route = OFFICE_HOME_ROUTE
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
    if care_session and effective_back_route in {"/public/walkthrough-overview", "/service-overview", "/"}:
        effective_back_route = (
            OFFICE_HOME_ROUTE
            if bool(st.session_state.get("office_login_explicit"))
            else MOBILE_HOME_ROUTE
        )
    render_route_link(
        "← Back",
        effective_back_route,
        key=f"walkthrough_back_{page_title.lower().replace(' ', '_').replace('–', '-')}",
    )
    render_page_header(page_title, show_menu=False, show_variant_subheading=False)
    st.caption(
        "Note: App name updated to voicemailcare.com."
    )
    normalized_title = page_title.strip().lower()
    if normalized_title.endswith("record video"):
        st.caption("Record video — Send a voice message.")
    elif normalized_title.endswith("diagram video"):
        st.caption("Diagram video — How the system works.")
    video_source = resolve_public_video_source(video_env_var, local_video_path)
    if video_source:
        try:
            st.video(video_source)
        except Exception:
            st.warning(
                f"Video failed to load from {video_env_var}. Check the URL format and permissions."
            )
            if fallback_doc_path:
                st.caption("Showing written guide instead:")
                render_document_boxes(fallback_doc_path, strip_first_heading=True)
    else:
        st.warning(
            f"Video not found. Set {video_env_var} or add {local_video_path}."
        )
        if fallback_doc_path:
            st.caption("Showing written guide instead:")
            render_document_boxes(fallback_doc_path, strip_first_heading=True)
    st.markdown("### What this video shows")
    for line in role_summary:
        st.markdown(f"- {line}")
    st.markdown(
        "For urgent, medical, safeguarding, or emergency matters, contact the care home directly."
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


def get_channel_label_and_icon(channel_role: str) -> tuple[str, str]:
    role = (channel_role or "").strip().lower()
    if role == "family":
        return "Family", ""
    if role == "care_hub":
        return "Care Hub", ""
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


def render_slow_speech_hint() -> None:
    st.markdown(
        """
<style>
  .vm-slow-hint {
    display: flex;
    align-items: center;
    margin: 6px 0 10px 0;
  }
  .vm-slow-text {
    font-size: 0.9rem;
    color: #111;
  }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="vm-slow-hint" aria-label="Speak slowly and clearly">
  <div class="vm-slow-text">Speak slowly and clearly.</div>
</div>
""",
        unsafe_allow_html=True,
    )


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
        brand_title="voicemailcare.com",
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
        "Not a live service. Messages are played when staff are available.",
        "For security, Family sessions sign out after 30 minutes of inactivity.",
        "If you are signed out, request a new secure email link.",
        "Plan your message first. Most messages only need a few seconds.",
        "For urgent matters or safeguarding concerns, contact the care home directly.",
    ]
    for box in login_info_boxes:
        st.markdown(f'<div class="family-login-box">{box}</div>', unsafe_allow_html=True)
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
    st.caption("If this email has not been invited yet, ask the care home to invite you.")
    sign_out_pressed = False
    if st.session_state.get("auth_uid"):
        if st.button("Sign out", key="family_login_sign_out"):
            sign_out_pressed = True
    render_public_landing_link("Back to main public page", key="family_login_back_public")

    if submit_login:
        ok, message = send_magic_link_email(
            normalized_email, app_variant=VARIANT_FAMILY, should_create_user=False
        )
        if ok:
            st.success(message)
        else:
            st.error(message)
            st.info("If you are new, ask the care home to send your invitation first.")

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
            st.info("If you are new, ask the care home to send your invitation first.")

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
    care_home_name = fetch_active_care_home_name(access_token)
    family_user_record = get_family_user_for_session(access_token)
    family_user_id = str((family_user_record or {}).get("id") or "").strip()
    render_care_home_identity_banner(access_token)
    residents = fetch_family_residents(
        st.session_state.get("auth_uid", ""), access_token
    )

    if not residents:
        st.info("No residents are currently linked to your Family Member account.")
        return

    resident_access_names = [
        f"{resident['preferred_name']} {resident['surname']}" for resident in residents
    ]
    if len(resident_access_names) == 1:
        st.caption(f"Registered residents: {resident_access_names[0]}")
    else:
        st.caption("Residents you can access: " + ", ".join(resident_access_names))
        resident_option_ids = [resident["id"] for resident in residents]
        resident_label_by_id = {
            resident["id"]: f"{resident['preferred_name']} {resident['surname']}"
            for resident in residents
        }
        selected_resident_id = st.selectbox(
            "Select resident",
            resident_option_ids,
            format_func=lambda resident_id: resident_label_by_id.get(resident_id, "Resident"),
            key="family_selected_resident_id",
        )
        residents = [
            resident for resident in residents if resident["id"] == selected_resident_id
        ]

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
        full_name = f"{resident['preferred_name']} {resident['surname']}"
        room_label = f"Room {resident['room']}" if resident.get("room") else ""

        st.markdown('<div class="vm-resident-card">', unsafe_allow_html=True)
        st.markdown(f"**{full_name}**")
        if care_home_name:
            st.markdown(f"*Care home: {care_home_name}*")
        if room_label:
            st.markdown(f"*{room_label}*")

        st.markdown(f"**Latest message from {full_name} to Family Members**")
        latest = fetch_latest_message(
            resident_id,
            "from_resident",
            access_token,
            family_id=resident.get("family_id") or resident_id,
            channel="resident_family",
            include_audio=True,
        )
        audio_bytes = decode_audio_payload(latest, access_token=access_token)
        if audio_bytes:
            st.audio(audio_bytes, format=latest.get("audio_mime_type") or "audio/wav")
            resident_sent_label = format_soft_message_period_label(latest.get("recorded_at"))
            if resident_sent_label:
                st.caption(resident_sent_label)
        else:
            st.markdown(
                '<div class="vm-muted-line">No new messages.</div>',
                unsafe_allow_html=True,
            )

        st.markdown("**Care Hub update to Family (Office informational message)**")
        st.caption("Latest office update for this resident. Office updates are informational only.")
        latest_office_update = fetch_latest_message(
            resident_id,
            "office_to_family",
            access_token,
            family_id=resident.get("family_id") or resident_id,
            channel="office_family",
            include_audio=True,
        )
        latest_office_audio = decode_audio_payload(
            latest_office_update,
            access_token=access_token,
        )
        if latest_office_audio:
            st.audio(
                latest_office_audio,
                format=latest_office_update.get("audio_mime_type") or "audio/wav",
            )
            office_soft_label = format_soft_message_period_label(
                latest_office_update.get("recorded_at")
            )
            if office_soft_label:
                st.caption(office_soft_label)
        else:
            st.markdown(
                '<div class="vm-muted-line">No care hub updates.</div>',
                unsafe_allow_html=True,
            )

        practical_message = fetch_latest_open_office_practical_message(
            resident_id, access_token
        )
        if practical_message:
            practical_message_id = str(practical_message.get("id") or "").strip()
            practical_context_type = str(
                practical_message.get("context_type") or OFFICE_PRACTICAL_CONTEXT_GENERAL
            ).strip()
            st.markdown("**Office practical message**")
            st.markdown(
                f"**{(practical_message.get('title') or 'Practical update').strip()}**"
            )
            st.markdown(str(practical_message.get("body") or "").strip())
            if practical_context_type == OFFICE_PRACTICAL_CONTEXT_VISIT:
                requested_date = str(practical_message.get("requested_date") or "").strip()
                requested_time = str(practical_message.get("requested_time_window") or "").strip()
                if requested_date:
                    st.caption(f"Requested date: {requested_date}")
                if requested_time:
                    st.caption(f"Requested time window: {requested_time}")
            st.caption("For urgent or medical matters, please call the care home directly.")
            st.caption("Messages sent here are not monitored for emergencies.")
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
            choice_labels = ["Yes", "No", "Maybe"]
            choice_to_value = {"Yes": "yes", "No": "no", "Maybe": "maybe"}
            default_choice_index = (
                choice_labels.index(response_choice.title())
                if response_choice in {"yes", "no", "maybe"}
                else 0
            )
            selected_choice_label = st.radio(
                "Your response",
                options=choice_labels,
                index=default_choice_index,
                horizontal=True,
                key=f"family_practical_choice_{resident_id}_{practical_message_id}",
            )
            selected_option_ids: list[str] = []
            existing_selected_option_ids = set(
                (existing_response or {}).get("selected_option_ids") or []
            )
            for option in response_options:
                option_id = str(option.get("id") or "").strip()
                option_label = str(option.get("option_label") or "").strip()
                if not option_id or not option_label:
                    continue
                checked = st.checkbox(
                    option_label,
                    value=option_id in existing_selected_option_ids,
                    key=f"family_practical_check_{resident_id}_{practical_message_id}_{option_id}",
                )
                if checked:
                    selected_option_ids.append(option_id)
            note_value = ""
            if bool(practical_message.get("allow_note", True)):
                note_value = st.text_area(
                    "Add a short note for the office (optional).",
                    value=str((existing_response or {}).get("note") or ""),
                    key=f"family_practical_note_{resident_id}_{practical_message_id}",
                    max_chars=500,
                )
            planned_visit_time_value = ""
            if practical_context_type == OFFICE_PRACTICAL_CONTEXT_VISIT:
                planned_visit_time_value = st.text_input(
                    "Planned visit time (optional)",
                    value=str((existing_response or {}).get("planned_visit_time") or ""),
                    key=f"family_practical_planned_visit_time_{resident_id}_{practical_message_id}",
                    placeholder="Example: Saturday about 11am",
                )
            share_with_family_value = st.checkbox(
                "Share this response with all Family Members",
                value=bool((existing_response or {}).get("share_with_family", False)),
                key=f"family_practical_share_{resident_id}_{practical_message_id}",
            )
            if st.button(
                "Send response",
                key=f"family_practical_submit_{resident_id}_{practical_message_id}",
            ):
                if not family_user_id:
                    st.error("Your Family Member mapping could not be found. Please sign in again.")
                else:
                    ok, message = upsert_family_practical_response(
                        practical_message_id,
                        family_user_id,
                        choice_to_value.get(selected_choice_label, "maybe"),
                        note_value,
                        selected_option_ids,
                        planned_visit_time_value,
                        share_with_family_value,
                        access_token,
                    )
                    if ok:
                        st.success("Response received.")
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
                own_choice = str(existing_response.get("primary_choice") or "").strip().title()
                if own_choice:
                    st.caption(f"Your current response: {own_choice}")
            st.caption("Shared responses from other Family Members:")
            if shared_responses:
                for shared_response in shared_responses:
                    contact_name = str(shared_response.get("contact_name") or "Family Member")
                    choice_label = str(shared_response.get("primary_choice") or "").strip().title()
                    st.markdown(f"- {contact_name}: {choice_label}")
                    shared_visit = str(shared_response.get("planned_visit_time") or "").strip()
                    if shared_visit:
                        st.caption(f"Planned visit: {shared_visit}")
                    shared_note = str(shared_response.get("note") or "").strip()
                    if shared_note:
                        st.caption(f"Note: {shared_note}")
            else:
                st.caption("No shared responses yet.")
        else:
            st.caption("No open practical office messages for this resident.")

        st.markdown(f"**Latest message from you to {full_name}**")
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
        show_recent_send_feedback = bool(
            (state.get("last_message") or {}) and not state.get("recording_bytes")
        )
        if latest_sent and not state.get("recording_bytes"):
            if latest_sent_audio:
                st.audio(
                    latest_sent_audio,
                    format=latest_sent.get("audio_mime_type") or "audio/wav",
                )
            else:
                st.success("Latest Family → Resident message is saved.")
            latest_sent_at = latest_sent.get("recorded_at")
            if latest_sent_at and not show_recent_send_feedback:
                latest_sent_label = format_soft_message_period_label(latest_sent_at)
                if latest_sent_label:
                    st.caption(latest_sent_label)
        last_message = state.get("last_message") or {}
        if last_message and not state.get("recording_bytes"):
            sent_at = last_message.get("sent_at")
            sent_display = format_soft_message_period_label(sent_at) if sent_at else None
            st.success("Message sent")
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
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        native_recording_available = hasattr(st, "audio_input")
        if native_recording_available:
            recorded_from_native = st.audio_input(
                f"Record voice message to {full_name}",
                key=f"family_audio_input_{resident_id}",
            )
            render_slow_speech_hint()
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
                        )
                        bump_message_cache_epoch()
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
    render_care_home_identity_banner(st.session_state.get("access_token"))
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
    render_care_home_identity_banner(st.session_state.get("access_token"))
    st.markdown("### Videos")
    st.caption("Two video types: Record video and Diagram video.")
    walkthrough_cols_top = st.columns(2, gap="small")
    with walkthrough_cols_top[0]:
        if st.button(
            "Universal Diagram video",
            key="docs_walkthrough_overview",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-overview")
    with walkthrough_cols_top[1]:
        if st.button(
            "Family Diagram video",
            key="docs_walkthrough_family_flow",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-family-flow")
    walkthrough_cols_mid = st.columns(2, gap="small")
    with walkthrough_cols_mid[0]:
        if st.button(
            "Care Hub – Mobile Diagram video",
            key="docs_walkthrough_mobile_flow",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-mobile-flow")
    with walkthrough_cols_mid[1]:
        if st.button(
            "Care Hub – Office Diagram video",
            key="docs_walkthrough_office_flow",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-office-flow")
    walkthrough_cols_bottom = st.columns(1, gap="small")
    with walkthrough_cols_bottom[0]:
        if st.button(
            "Care Hub – Office Record video",
            key="docs_walkthrough_office_audio",
            use_container_width=True,
        ):
            set_route("/public/walkthrough-office")
    st.write("")

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
            "summary": "How to invite and register a Family Member.",
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


def render_public_document(doc_path: str, back_route: str = "/public/walkthrough-overview") -> None:
    # Render all public documents in the boxed style for consistency.
    use_boxes = True
    use_qa_search = doc_path.endswith("10_faq.md")
    app_variant = get_app_variant()
    if app_variant == VARIANT_PUBLIC:
        st.markdown(f"[← Back to videos](?route={back_route})")
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
        "← Back to videos",
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
        "← Back to videos",
        back_route,
        key="public_doc_back_service_overview_bottom",
    )


def render_public_docs() -> None:
    app_variant = get_app_variant()

    render_page_header("Public Documents")
    if app_variant == VARIANT_FAMILY:
        if st.button(
            "← Back to Family login",
            key="public_docs_back_family_login_link",
            use_container_width=True,
        ):
            st.session_state["force_family_login"] = True
            set_route(get_login_route(VARIANT_FAMILY))
    if app_variant == VARIANT_OFFICE:
        render_route_link(
            "← Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="public_docs_back_office_dashboard_link",
        )
    st.write("Select a public document to view.")

    if app_variant == VARIANT_FAMILY:
        public_docs = [
            ("Universal Diagram video", "/public/walkthrough-overview"),
            ("Family Diagram video", "/public/walkthrough-family-flow"),
            ("Family Record video", "/public/walkthrough-family"),
        ]
    elif app_variant == VARIANT_MOBILE:
        public_docs = [
            ("Universal Diagram video", "/public/walkthrough-overview"),
            ("Care Hub – Mobile Diagram video", "/public/walkthrough-mobile-flow"),
            ("Care Hub – Mobile Record video", "/public/walkthrough-mobile"),
        ]
    elif app_variant == VARIANT_OFFICE:
        public_docs = [
            ("Universal Diagram video", "/public/walkthrough-overview"),
            ("Family Diagram video", "/public/walkthrough-family-flow"),
            ("Care Hub – Mobile Diagram video", "/public/walkthrough-mobile-flow"),
            ("Care Hub – Office Diagram video", "/public/walkthrough-office-flow"),
            ("Care Hub – Office Record video", "/public/walkthrough-office"),
        ]
    else:
        public_docs = [
            ("Universal Diagram video", "/public/walkthrough-overview"),
            ("Family Diagram video", "/public/walkthrough-family-flow"),
            ("Care Hub – Mobile Diagram video", "/public/walkthrough-mobile-flow"),
            ("Care Hub – Office Diagram video", "/public/walkthrough-office-flow"),
            ("Family Record video", "/public/walkthrough-family"),
            ("Care Hub – Mobile Record video", "/public/walkthrough-mobile"),
            ("Care Hub – Office Record video", "/public/walkthrough-office"),
        ]
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
        st.markdown('<div class="pr-header-title">voicemailcare.com</div>', unsafe_allow_html=True)

    st.markdown('<div class="pr-hero">', unsafe_allow_html=True)
    st.markdown("<h1>One message in. One message out.</h1>", unsafe_allow_html=True)
    st.markdown(
        '<div class="pr-subheading">Non-urgent social voice messages between residents and Family Members, with optional structured Office practical replies.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="pr-calm">No threads. No pressure.</div>', unsafe_allow_html=True)
    diagram_path = Path(__file__).resolve().parent / "assets" / "voice-message-flow-diagram.png"
    if diagram_path.exists():
        st.image(
            diagram_path.read_bytes(),
            use_container_width=True,
        )
    st.markdown(
        """
<div class="pr-explain">
Each channel keeps only the latest message.<br />
A new message replaces the previous message in that channel.<br />
Office general updates are one-way; Office practical messages allow structured family replies (Yes/No/Maybe, optional tick-boxes, optional short note).<br />
For urgent, medical, safeguarding, or emergency matters, contact the care home directly.
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="pr-content">', unsafe_allow_html=True)
    info_cols = st.columns(3, gap="small")
    with info_cols[0]:
        if st.button("Learn about Family app", key="pr_info_family", use_container_width=True):
            set_route("/public/walkthrough-family")
            st.stop()
    with info_cols[1]:
        if st.button("Learn about Care Hub - Mobile", key="pr_info_mobile", use_container_width=True):
            set_route("/public/walkthrough-mobile")
            st.stop()
    with info_cols[2]:
        if st.button("Learn about Care Hub - Office", key="pr_info_office", use_container_width=True):
            set_route("/public/walkthrough-office")
            st.stop()
    st.markdown(
        "**Family app**: non-urgent social voice messages between Family Members and residents, "
        "plus structured replies to Office practical messages."
    )
    st.markdown(
        "**Care Hub - Mobile**: staff-assisted playback and resident recording support, including fair rotating "
        "playback with unplayed family messages first."
    )
    st.markdown(
        "**Care Hub - Office**: governance and oversight, one-way general family updates, and practical messages "
        "with structured family responses."
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


def render_care_hub_banner_settings() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant("Operational variables are only available in Care Hub – Office.")
        return
    save_notice_state_key = "office_operational_save_notice"
    render_page_header("Operational Variables")
    access_token = st.session_state.get("access_token")
    render_care_home_identity_banner(access_token)
    save_notice = str(st.session_state.pop(save_notice_state_key, "") or "").strip()
    if save_notice:
        st.success(save_notice)
    st.markdown("### Operational setup variables")
    st.markdown(
        "- Care home name\n"
        "- Business banner heading (optional)\n"
        "- Business banner message (optional)\n"
        "- Business banner image URL (optional)\n"
        "- Idle sign-out time for Care Hub sessions"
    )
    st.caption(
        "Review and confirm these settings during setup so day-to-day use is consistent from launch."
    )
    st.markdown("### ✅ Voice Message – Office Checks")
    st.markdown("**Daily**")
    st.checkbox("Login", key="office_checks_daily_login")
    st.checkbox("Send & playback test message", key="office_checks_daily_send_playback")
    st.markdown("**Weekly**")
    st.checkbox("Check diagram video link", key="office_checks_weekly_walkthrough")
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
            include_room=True,
            include_care_home=False,
            separator=" | ",
        )
    if reset_tool_resident_ids:
        selected_reset_resident_id = st.selectbox(
            "Resident for message list reset",
            options=reset_tool_resident_ids,
            format_func=lambda value: reset_tool_resident_label_by_id.get(value, "Resident"),
            key="office_queue_reset_selected_resident_id",
        )
        confirm_queue_reset = st.checkbox(
            "I confirm I want to reset queue tracking for this resident.",
            key="office_queue_reset_confirm",
        )
        if st.button(
            "Reset selected resident message list",
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
                    st.error("Could not determine resident/care home context for reset.")
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
                        st.success("Selected resident message list reset.")
                    else:
                        st.warning(
                            "Reset request completed with no DB rows changed for played/unread state."
                        )
                    st.rerun()
    else:
        st.caption("No residents available for message list reset.")
    st.markdown("**Issues**")
    st.checkbox("Log / escalate incidents", key="office_checks_issues_log_escalate")
    st.markdown("### Office care home banner")
    st.caption("Add your logo or your own banner design for Care Hub – Office and Family views.")
    st.markdown("### Operational settings")
    st.caption(
        "Choose how long Care Hub can stay idle before it signs out. This applies to Care Hub – Office and Care Hub – Mobile."
    )

    care_home_profile = fetch_active_care_home_profile(access_token)
    if not isinstance(care_home_profile, dict) or not str(care_home_profile.get("name") or "").strip():
        st.error(
            "Could not load the current care home settings. Save is disabled to avoid overwriting existing banner values."
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
    timeout_index = timeout_options.index(current_timeout)
    with st.form("office_care_home_banner_page_form"):
        care_home_name_value = st.text_input(
            "Care home name",
            value=str(care_home_profile.get("name") or ""),
            max_chars=160,
            key="office_care_home_name_page",
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
            help="Use a full https:// image URL for your logo or banner artwork.",
        )
        selected_idle_timeout = st.selectbox(
            "Idle sign-out time",
            options=timeout_options,
            index=timeout_index,
            format_func=lambda value: timeout_labels.get(value, f"{int(value // 60)} minutes"),
            key="office_care_hub_idle_timeout_seconds",
            help="If no activity is detected for this period, the app signs out for security.",
        )
        save_banner = st.form_submit_button("Save banner and operational settings")
    if save_banner:
        saved, message = update_active_care_home_branding(
            access_token,
            care_home_name=care_home_name_value,
            banner_title=banner_title_value,
            banner_text=banner_text_value,
            banner_artwork_url=banner_artwork_value,
            care_hub_idle_timeout_seconds=int(selected_idle_timeout),
        )
        if saved:
            st.success(message)
        else:
            st.error(message)


def render_care_hub_security() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant("Security settings are only available in Care Hub – Office.")
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

    st.markdown("### Mobile staff PIN management")
    st.caption(
        "Each staff member has their own Mobile PIN. Reset clears a selected staff PIN; they will set a new PIN at next Mobile login."
    )
    staff_rows, staff_rows_error = fetch_care_home_staff_mobile_pin_status(access_token)
    if staff_rows_error:
        st.error(staff_rows_error)
    elif not staff_rows:
        st.info("No staff accounts found for this care home.")
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
                "Staff account",
                options=selectable_staff_ids,
                format_func=lambda value: staff_label_by_id.get(value, value),
                key="office_mobile_pin_reset_target",
            )
            confirm_staff_pin_reset = st.checkbox(
                "I confirm I want to reset this staff Mobile PIN.",
                key="office_mobile_pin_reset_confirm",
            )
            if st.button(
                "Reset selected staff Mobile PIN",
                key="office_mobile_pin_reset_button",
                use_container_width=True,
            ):
                if not confirm_staff_pin_reset:
                    st.error("Please confirm before resetting the staff PIN.")
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
            st.caption("2FA is required for Care Hub - Office and cannot be disabled.")
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
            st.info("2FA is required for Care Hub - Office. Set up your authenticator app now.")
        else:
            st.info("2FA is optional but recommended for Care Hub - Office.")
        if st.button("Start 2FA setup", key="mfa_start"):
            st.session_state["mfa_enroll_secret"] = pyotp.random_base32()
            st.session_state["mfa_enroll_codes"] = generate_recovery_codes()

        secret = st.session_state.get("mfa_enroll_secret")
        codes = st.session_state.get("mfa_enroll_codes")
        if secret and codes:
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=f"{auth_email} (Office)",
                issuer_name="voicemailcare-office",
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
        "Back to Care Hub – Office",
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
            "Please sign in to access Care Hub – Office.",
            get_login_route(VARIANT_OFFICE),
            "care_hub",
        )
        return
    record = get_care_hub_mfa_record(access_token, auth_uid)
    if not record or not record.get("enabled"):
        if not mfa_required:
            st.info("Two-factor authentication is not enabled for this account.")
            if st.button("Continue", key="mfa_not_enabled_continue"):
                set_route(get_home_route(VARIANT_OFFICE))
                st.rerun()
            return
        st.info("Two-factor authentication is required for Care Hub - Office.")
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
                issuer_name="voicemailcare-office",
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
            "summary": "Register of third-party websites/apps used by voicemailcare.com.",
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
    app_variant = resolve_runtime_variant(route_hint=get_route())
    login_label = "Care Hub – Mobile" if app_variant == VARIANT_MOBILE else "Care Hub – Office"
    render_page_header(
        f"{login_label} login",
        brand_title="voicemailcare.com",
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
            "Not a live service. Messages are played when staff are available.",
            "Mobile access uses an individual staff PIN for day-to-day use.",
            "Use email secure link only for first sign-in or when session access has expired.",
        ]
        for box in mobile_login_boxes:
            st.markdown(f'<div class="care-login-box">{box}</div>', unsafe_allow_html=True)
    elif app_variant == VARIANT_OFFICE:
        st.caption("Office login is a separate staff/admin access path.")
    render_public_landing_link(
        "Back to main public page",
        key=f"care_login_back_public_{app_variant}",
    )
    st.markdown('<div class="vm-login">', unsafe_allow_html=True)
    office_requires_explicit_login = (
        app_variant == VARIANT_OFFICE
        and not bool(st.session_state.get("office_login_explicit"))
    )
    if st.session_state.get("auth_uid") and not office_requires_explicit_login:
        allow_manual_login = False
        family_found, care_found, error, family_record, care_record = get_mapping_status()
        if care_found:
            if care_record:
                st.session_state["active_role"] = "care_hub"
                st.session_state["active_care_home_id"] = care_record.get("care_home_id")
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
            st.error("Wrong app variant")
            st.info("Your login details are for Family.")
            if st.button("Log out", key="care_login_wrong_logout"):
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
        email = st.text_input("Staff email", key="care_mobile_login_email")
        normalized_email = email.strip().lower()
        st.caption(
            "For first sign-in (or expired session), enter your staff email and request a secure link."
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
        return

    email = st.text_input("Staff/admin email", key="care_login_email")
    password = st.text_input(
        "Office password", type="password", key="care_login_password"
    )
    normalized_email = email.strip().lower()
    normalized_password = password.strip()
    st.caption("Office uses staff/admin credentials. This is separate from Family and Mobile PIN access.")

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
                        st.error("Wrong app variant")
                        st.info("Your login details are for Family.")
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


def render_care_hub() -> None:
    require_care_access()
    runtime_variant = resolve_runtime_variant(route_hint=get_route())
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
</style>
""",
        unsafe_allow_html=True,
    )
    render_page_header(f"{get_care_hub_label()} voice messages")
    if runtime_variant == VARIANT_MOBILE:
        st.caption("App interface: Care Hub – Mobile")
        render_public_landing_button("Back to main public page")
    elif runtime_variant == VARIANT_OFFICE:
        render_public_landing_button("Back to main public page")
    if (
        runtime_variant == VARIANT_MOBILE
        and st.session_state.pop("mobile_pin_just_accepted", False)
    ):
        st.success("Mobile PIN accepted.")
    # Top action buttons removed; navigation is handled through the header menu.
    # Action row already rendered at the top of the page.

    access_token = st.session_state.get("access_token")
    render_care_home_identity_banner(access_token)
    residents = fetch_care_home_residents(access_token)
    is_care_queue_variant_screen = runtime_variant in {VARIANT_MOBILE, VARIANT_OFFICE}
    include_care_home_in_resident_labels = runtime_variant == VARIANT_MOBILE
    contacts_by_resident: dict[str, list[dict]] = {}

    search_value = st.text_input("Search residents", key="care_resident_search")
    if search_value:
        search_lower = search_value.strip().lower()
        residents = [
            resident
            for resident in residents
            if search_lower in resident["preferred_name"].lower()
            or search_lower in resident["surname"].lower()
            or (resident.get("room") and search_lower in resident["room"])
            or (resident.get("care_home") and search_lower in resident["care_home"].lower())
        ]

    if not residents:
        if search_value:
            st.info("No residents match that search.")
        return

    if is_care_queue_variant_screen:
        resident_option_ids = [resident["id"] for resident in residents]
        resident_label_by_id = {}
        for resident in residents:
            resident_label_by_id[resident["id"]] = format_resident_identity_label(
                resident,
                include_room=True,
                include_care_home=include_care_home_in_resident_labels,
                separator=" | ",
            )
        if len(resident_option_ids) == 1:
            selected_resident_id = resident_option_ids[0]
            st.caption(
                "Resident selected: "
                + resident_label_by_id.get(selected_resident_id, "Resident")
            )
        else:
            selected_resident_id = st.selectbox(
                "Select resident",
                resident_option_ids,
                format_func=lambda resident_id: resident_label_by_id.get(resident_id, "Resident"),
                key="care_selected_resident_id",
            )
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
        full_name = get_resident_full_name(resident)
        st.markdown('<div class="vm-resident-card">', unsafe_allow_html=True)
        st.markdown("**Resident:**")
        st.markdown(
            f"**{format_resident_identity_label(resident, include_room=True, include_care_home=include_care_home_in_resident_labels, separator=' | ')}**"
        )

        contacts = contacts_by_resident.get(resident_id)
        if contacts is None:
            contacts = fetch_family_users_for_resident(resident_id, access_token)
            contacts_by_resident[resident_id] = contacts
        if not contacts:
            if runtime_variant == VARIANT_OFFICE:
                st.warning(
                    "No Family Members are linked to this resident yet. "
                    "Register a family member in Care Hub – Office before sending messages."
                )
                if st.button(
                    "Register family member now",
                    key=f"care_register_family_cta_{resident_id}",
                    use_container_width=True,
                ):
                    set_route("/care-hub/register-family")
                    st.rerun()
            else:
                st.warning(
                    "No Family Members are linked to this resident yet. "
                    "Ask Office staff to register a family member."
                )
            st.markdown("</div>", unsafe_allow_html=True)
            continue
        is_mobile_variant = runtime_variant == VARIANT_MOBILE
        is_office_variant = runtime_variant == VARIANT_OFFICE
        is_queue_playback_variant = is_mobile_variant
        manual_selection_key = f"care_manual_selected_{resident_id}"
        queue_unread_count = 0
        queue_next_contact = None
        queue_unread_contacts: list[dict] = []
        if contacts and (is_mobile_variant or is_office_variant):
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
            st.caption(
                "Play messages follows a fixed contact order. Unplayed messages are always first."
            )
            mobile_play_requested_key = f"care_mobile_play_requested_{resident_id}"
            keep_current_after_start = bool(st.session_state.get(mobile_play_requested_key, False))
            current_user_id = str(state.get("selected_contact_user_id") or "").strip()
            manual_selected = bool(st.session_state.get(manual_selection_key, False))
            if manual_selected and current_user_id:
                selected_contact = next(
                    (
                        c
                        for c in contacts
                        if str(c.get("auth_user_id") or "").strip() == current_user_id
                    ),
                    None,
                )
                if selected_contact:
                    latest = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=current_user_id,
                        channel="resident_family",
                    )
                    queue_mode_label = "Manual selection"
                else:
                    st.session_state[manual_selection_key] = False
            queue_selected_contact, queue_latest, queue_mode_label = select_next_family_message_for_mobile(
                resident_id,
                resident["care_home_id"],
                contacts,
                access_token,
            )
            if selected_contact is None and keep_current_after_start and current_user_id:
                queue_user_id = str((queue_selected_contact or {}).get("auth_user_id") or "").strip()
                if queue_user_id and queue_user_id == current_user_id:
                    selected_contact = next(
                        (
                            c
                            for c in contacts
                            if str(c.get("auth_user_id") or "").strip() == current_user_id
                        ),
                        None,
                    )
                    if selected_contact:
                        latest = fetch_latest_message(
                            resident_id,
                            "to_resident",
                            access_token,
                            contact_user_id=current_user_id,
                            channel="resident_family",
                        )
                        queue_mode_label = "Session order"
                    else:
                        selected_contact, latest = queue_selected_contact, queue_latest
                else:
                    selected_contact, latest = queue_selected_contact, queue_latest
            elif selected_contact is None:
                selected_contact, latest = queue_selected_contact, queue_latest
            state["selected_contact_id"] = (selected_contact or {}).get("id")
            state["selected_contact_user_id"] = (selected_contact or {}).get("auth_user_id")
        elif is_office_variant:
            st.caption(
                "Office review playback follows the same fixed contact order "
                "(does not change resident queue order)."
            )
            if st.button(
                "Play next unread family message (Office review)",
                key=f"office_play_next_{resident_id}",
                use_container_width=True,
            ):
                st.session_state[manual_selection_key] = False
                selected_contact, latest, queue_mode_label = select_next_family_message_for_mobile(
                    resident_id,
                    resident["care_home_id"],
                    contacts,
                    access_token,
                )
                if selected_contact:
                    state["selected_contact_id"] = selected_contact.get("id")
                    state["selected_contact_user_id"] = selected_contact.get("auth_user_id")
                    latest = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=selected_contact.get("auth_user_id"),
                        channel="resident_family",
                        include_audio=True,
                    )
                    latest_message_id = str((latest or {}).get("id") or "").strip()
                    if latest_message_id and not has_message_been_played_since_recorded(
                        latest,
                        resident_id=resident_id,
                        care_home_id=resident["care_home_id"],
                    ):
                        latest_contact_user_id = str(
                            (latest or {}).get("contact_user_id")
                            or selected_contact.get("auth_user_id")
                            or ""
                        ).strip()
                        latest_recorded_at = str((latest or {}).get("recorded_at") or "").strip()
                        log_audit_event(
                            "message_played",
                            "care_hub",
                            resident["care_home_id"],
                            latest_message_id,
                            resident_id=resident_id,
                        )
                        set_contact_last_played_recorded_at(
                            resident_id,
                            resident["care_home_id"],
                            latest_contact_user_id,
                            latest_recorded_at,
                            access_token,
                        )
                    # Advance Office session pointer so each click moves through queue order.
                    office_next_contact_user_id = get_next_contact_user_id_with_message(
                        resident_id,
                        contacts,
                        access_token,
                        state.get("selected_contact_user_id"),
                    )
                    st.session_state[f"care_mobile_pointer_{resident_id}"] = (
                        office_next_contact_user_id or ""
                    )
                    st.rerun()
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
                    latest = fetch_latest_message(
                        resident_id,
                        "to_resident",
                        access_token,
                        contact_user_id=selected_contact.get("auth_user_id"),
                        channel="resident_family",
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
                    contact_options.append(f"{contact['full_name']} — {relationship.title()}")
                else:
                    contact_options.append(f"{contact['full_name']} — Family Member")

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
        if contacts and (is_mobile_variant or is_office_variant):
            st.caption(f"Unread family messages: {queue_unread_count}")
            if queue_next_contact:
                next_name = (queue_next_contact.get("full_name") or "family contact").strip()
                next_relationship = ((queue_next_contact.get("relationship") or "").strip())
                next_display = (
                    f"{next_name} ({next_relationship.title()})"
                    if next_relationship
                    else f"{next_name} (Family Member)"
                )
                st.caption(f"Next in queue: {next_display}")
            else:
                st.caption("Next in queue: none")
            if queue_unread_contacts:
                st.caption("Unplayed list:")
                for unread_contact in queue_unread_contacts:
                    unread_name = (unread_contact.get("full_name") or "family contact").strip()
                    unread_relationship = ((unread_contact.get("relationship") or "").strip())
                    unread_display = (
                        f"{unread_name} ({unread_relationship.title()})"
                        if unread_relationship
                        else f"{unread_name} (Family Member)"
                    )
                    st.markdown(f"- {unread_display}")
            send_guard_scope = f"care_send_{resident_id}"
            send_guard_remaining = get_send_guard_remaining_seconds(send_guard_scope)
            send_guard_active = send_guard_remaining > 0
            if send_guard_active:
                st.warning(
                    "Please wait until you see the sent confirmation before playing another message. "
                    f"({send_guard_remaining}s)"
                )

            playlist_contacts = sort_contacts_for_playback(contacts)
            if playlist_contacts:
                with st.expander("Select from family playlist"):
                    playlist_options = []
                    for playlist_contact in playlist_contacts:
                        playlist_name = (playlist_contact.get("full_name") or "family contact").strip()
                        playlist_relationship = ((playlist_contact.get("relationship") or "").strip())
                        playlist_label = (
                            f"{playlist_name} ({playlist_relationship.title()})"
                            if playlist_relationship
                            else f"{playlist_name} (Family Member)"
                        )
                        playlist_options.append((playlist_label, playlist_contact))
                    selected_playlist_label = st.selectbox(
                        "Family Member",
                        options=[label for label, _ in playlist_options],
                        key=f"care_playlist_select_{resident_id}",
                    )
                    if st.button(
                        "Play selected family message",
                        key=f"care_playlist_play_{resident_id}",
                        disabled=send_guard_active,
                        use_container_width=True,
                    ):
                        selected_contact = next(
                            (
                                contact
                                for label, contact in playlist_options
                                if label == selected_playlist_label
                            ),
                            None,
                        )
                        if selected_contact:
                            st.session_state[manual_selection_key] = True
                            state["selected_contact_id"] = selected_contact.get("id")
                            state["selected_contact_user_id"] = selected_contact.get("auth_user_id")
                            latest = fetch_latest_message(
                                resident_id,
                                "to_resident",
                                access_token,
                                contact_user_id=selected_contact.get("auth_user_id"),
                                channel="resident_family",
                                include_audio=True,
                            )
                            latest_message_id = str((latest or {}).get("id") or "").strip()
                            if latest_message_id and not has_message_been_played_since_recorded(
                                latest,
                                resident_id=resident_id,
                                care_home_id=resident["care_home_id"],
                            ):
                                latest_contact_user_id = str(
                                    (latest or {}).get("contact_user_id")
                                    or selected_contact.get("auth_user_id")
                                    or ""
                                ).strip()
                                latest_recorded_at = str((latest or {}).get("recorded_at") or "").strip()
                                log_audit_event(
                                    "message_played",
                                    "care_hub",
                                    resident["care_home_id"],
                                    latest_message_id,
                                    resident_id=resident_id,
                                )
                                set_contact_last_played_recorded_at(
                                    resident_id,
                                    resident["care_home_id"],
                                    latest_contact_user_id,
                                    latest_recorded_at,
                                    access_token,
                                )
                            if is_mobile_variant:
                                st.session_state[f"care_mobile_play_requested_{resident_id}"] = True
                            st.rerun()
        if is_mobile_variant or is_office_variant:
            mobile_play_requested_key = f"care_mobile_play_requested_{resident_id}"
            mobile_advance_pointer_key = f"care_mobile_advance_pointer_{resident_id}"
            if is_mobile_variant:
                if st.button(
                    "Play next family message",
                    key=f"care_play_next_{resident_id}",
                    disabled=send_guard_active,
                    use_container_width=True,
                ):
                    st.session_state[manual_selection_key] = False
                    selected_contact, latest, queue_mode_label = select_next_family_message_for_mobile(
                        resident_id,
                        resident["care_home_id"],
                        contacts,
                        access_token,
                    )
                    if selected_contact:
                        selected_contact_user_id = str(
                            (latest or {}).get("contact_user_id")
                            or selected_contact.get("auth_user_id")
                            or ""
                        ).strip()
                        state["selected_contact_id"] = selected_contact.get("id")
                        state["selected_contact_user_id"] = selected_contact_user_id
                        st.session_state[mobile_play_requested_key] = True
                        st.session_state[mobile_advance_pointer_key] = True
                    else:
                        st.session_state[mobile_play_requested_key] = False
                        st.session_state[mobile_advance_pointer_key] = False
                    st.rerun()

            if latest is None:
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
                latest = fetch_latest_message(
                    resident_id,
                    "to_resident",
                    access_token,
                    contact_user_id=state.get("selected_contact_user_id"),
                    channel="resident_family",
                    include_audio=True,
                )
            latest_contact_user_id = str((latest or {}).get("contact_user_id") or "").strip()
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
            if is_queue_playback_variant and queue_mode_label:
                st.caption(f"Queue mode: {queue_mode_label}")
            if is_mobile_variant:
                st.caption(f"Now playing from: {selected_contact_display}")
            else:
                st.caption(f"Office review playing: {selected_contact_display}")

            st.markdown(f"**Latest message from {selected_contact_name} to {full_name}**")
            audio_bytes = decode_audio_payload(latest, access_token=access_token)
            should_show_message = True
            if is_mobile_variant:
                should_show_message = bool(st.session_state.get(mobile_play_requested_key, False))
                if not should_show_message:
                    st.caption("Press 'Play next family message' to start playback.")

            if audio_bytes and should_show_message:
                st.audio(audio_bytes, format=latest.get("audio_mime_type") or "audio/wav")
                played_label = format_soft_message_period_label(latest.get("recorded_at"))
                if played_label:
                    st.caption(played_label)
                if is_mobile_variant:
                    st.caption("Press 'Play next family message' for the next contact.")
                else:
                    st.caption("Use Office review controls or playlist selection to continue.")
            elif not audio_bytes:
                st.markdown(
                    '<div class="vm-muted-line">No new messages.</div>',
                    unsafe_allow_html=True,
                )
                if is_mobile_variant and bool(
                    st.session_state.get(mobile_advance_pointer_key, False)
                ):
                    st.caption("Message payload could not be played. Skipping to next contact.")

            if is_mobile_variant:
                latest_message_id = str((latest or {}).get("id") or "").strip()
                advance_pointer_now = bool(st.session_state.get(mobile_advance_pointer_key, False))
                if advance_pointer_now:
                    if latest_message_id and not has_message_been_played_since_recorded(
                        latest,
                        resident_id=resident_id,
                        care_home_id=resident["care_home_id"],
                    ):
                        log_audit_event(
                            "message_played",
                            "care_hub",
                            resident["care_home_id"],
                            latest_message_id,
                            resident_id=resident_id,
                        )
                    latest_contact_user_id = str(
                        (latest or {}).get("contact_user_id")
                        or state.get("selected_contact_user_id")
                        or ""
                    ).strip()
                    latest_recorded_at = str((latest or {}).get("recorded_at") or "").strip()
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
                    if APP_DEBUG:
                        st.caption(
                            "Queue debug: "
                            f"current={state.get('selected_contact_user_id')} "
                            f"played_message={latest_message_id} "
                            f"next={next_contact_user_id or 'none'}"
                        )
                if advance_pointer_now:
                    st.session_state[mobile_advance_pointer_key] = False

        if is_mobile_variant or is_office_variant:
            st.markdown(f"**Latest message from {full_name} to all Family Members**")
        else:
            st.markdown(f"**Latest message from {full_name} to {selected_contact_name}**")

        latest_sent = fetch_latest_message(
            resident_id,
            "from_resident",
            access_token,
            family_id=resident.get("family_id") or resident_id,
            channel="resident_family",
            include_audio=True,
        )
        latest_sent_audio = None
        latest_sent_audio = decode_audio_payload(latest_sent, access_token=access_token)
        if latest_sent and not state.get("recording_bytes"):
            if latest_sent_audio:
                st.audio(
                    latest_sent_audio,
                    format=latest_sent.get("audio_mime_type") or "audio/wav",
                )
            else:
                st.success("Latest Resident → Family message is saved.")
            latest_sent_at = latest_sent.get("recorded_at")
            if latest_sent_at:
                latest_sent_label = format_soft_message_period_label(latest_sent_at)
                if latest_sent_label:
                    st.caption(latest_sent_label)
        if is_mobile_variant or is_office_variant:
            if hasattr(st, "audio_input"):
                recorded_from_native = st.audio_input(
                    f"Record voice message from {full_name} to all Family Members",
                    key=f"care_audio_input_{resident_id}_{state.get('recording_input_nonce', 0)}",
                )
                render_slow_speech_hint()
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

            sent_now = False
            room_display = f"Room {resident.get('room')}" if resident.get("room") else "Room not set"
            if is_office_variant:
                confirmation_line = (
                    "Sending on behalf of:<br/>"
                    f"{full_name} — {room_display} \u2192 all Family Members"
                )
            else:
                care_home_display = (
                    str(resident.get("care_home") or "").strip() or "Care home not set"
                )
                confirmation_line = (
                    "Sending on behalf of:<br/>"
                    f"{full_name} — {room_display} — {care_home_display} \u2192 all Family Members"
                )
            st.markdown(
                f'<div class="vm-muted-line">{confirmation_line}</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                "After pressing Send, wait for the sent confirmation before playing another message."
            )
            last_sent = st.session_state.get("care_last_sent")
            if sent_now:
                st.success("Message sent.")
            elif last_sent and last_sent.get("resident_id") == resident_id:
                st.success(last_sent.get("message", "Message sent."))

            can_send = bool(
                state.get("recording_bytes")
                and state.get("preview_confirmed")
            )
            if st.button(
                f"Send for {full_name}",
                key=f"care_send_{resident_id}",
                disabled=not can_send,
            ):
                if not can_send:
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
                            "contact_user_id": None,
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
                            "recorded_at": now_iso,
                        }
                        resp, upsert_error = upsert_latest_message_with_fallback(
                            supabase,
                            payload,
                            "resident_id,family_id,direction,channel",
                            {
                                "resident_id": resident_id,
                                "family_id": resident.get("family_id") or resident_id,
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
                            )
                            bump_message_cache_epoch()
                            if APP_DEBUG:
                                print(
                                    "Saving Resident→Family message:",
                                    message_id,
                                    now_iso,
                                    "broadcast",
                                )
                            state["recording_bytes"] = None
                            state["recording_mime_type"] = "audio/wav"
                            state["preview_confirmed"] = False
                            sent_now = True
                            st.session_state["care_last_sent"] = {
                                "resident_id": resident_id,
                                "contact_id": None,
                                "message": "Message sent to all Family Members.",
                            }
                            activate_send_guard(send_guard_scope)
                            state["recording_input_nonce"] = (
                                int(state.get("recording_input_nonce", 0)) + 1
                            )
                            st.rerun()

        if runtime_variant in {VARIANT_OFFICE, VARIANT_MOBILE}:
            st.markdown("**Care Hub ↔ Family**")
            st.caption("Office update to Family")
            latest_office_update = fetch_latest_message(
                resident_id,
                "office_to_family",
                access_token,
                family_id=resident.get("family_id") or resident_id,
                channel="office_family",
                include_audio=True,
            )
            latest_office_audio = decode_audio_payload(
                latest_office_update,
                access_token=access_token,
            )
            if latest_office_audio:
                st.audio(
                    latest_office_audio,
                    format=latest_office_update.get("audio_mime_type") or "audio/wav",
                )
                if runtime_variant == VARIANT_MOBILE:
                    soft_label = format_soft_message_period_label(
                        latest_office_update.get("recorded_at")
                    )
                    if soft_label:
                        st.caption(soft_label)
            else:
                st.markdown(
                    '<div class="vm-muted-line">No care hub updates.</div>',
                    unsafe_allow_html=True,
                )

            if runtime_variant == VARIANT_OFFICE and hasattr(st, "audio_input"):
                recorded_office = st.audio_input(
                    "Record care hub update",
                    key=f"care_office_audio_input_{resident_id}_{state.get('office_recording_input_nonce', 0)}",
                )
                render_slow_speech_hint()
                if recorded_office is not None:
                    office_bytes = recorded_office.getvalue()
                    office_fp = (
                        __import__("hashlib").sha1(office_bytes).hexdigest()
                        if office_bytes
                        else None
                    )
                    if not office_bytes:
                        st.warning(
                            "That care hub update recording could not be captured correctly. Please record again."
                        )
                    now_ts = time.time()
                    # Prevent stale recorder replay after a send from re-populating the form.
                    if (
                        now_ts < float(state.get("office_ignore_audio_until") or 0.0)
                        and not state.get("office_recording_bytes")
                    ):
                        pass
                    elif (
                        office_bytes
                        and office_fp
                        and office_fp == state.get("office_last_sent_fingerprint")
                        and not state.get("office_recording_bytes")
                    ):
                        pass
                    # Once user has confirmed preview for current recording, avoid resetting
                    # from duplicate/replayed audio_input payloads.
                    elif state.get("office_preview_confirmed") and state.get("office_recording_bytes"):
                        pass
                    elif office_bytes and office_fp != state.get("office_recording_fingerprint"):
                        state["office_recording_bytes"] = office_bytes
                        state["office_recording_fingerprint"] = office_fp
                        state["office_recording_mime_type"] = (
                            getattr(recorded_office, "type", None) or "audio/wav"
                        )
                        state["office_preview_confirmed"] = False
                        state["office_last_sent_label"] = None
                        state["office_last_sent_fingerprint"] = None
                        st.session_state[f"care_office_listened_{resident_id}"] = False
            elif runtime_variant == VARIANT_OFFICE:
                st.warning("Native microphone recording is unavailable in this environment.")

            if runtime_variant == VARIANT_OFFICE and state.get("office_recording_bytes"):
                st.caption("Captured care hub update preview:")
                st.audio(
                    state["office_recording_bytes"],
                    format=state.get("office_recording_mime_type") or "audio/wav",
                )
                state["office_preview_confirmed"] = st.checkbox(
                    "I have listened to this care hub update.",
                    value=state.get("office_preview_confirmed", False),
                    key=f"care_office_listened_{resident_id}",
                )
                if st.button(
                    "Reset care hub recorder",
                    key=f"care_office_reset_recorder_{resident_id}",
                    use_container_width=True,
                ):
                    state["office_recording_bytes"] = None
                    state["office_recording_mime_type"] = "audio/wav"
                    state["office_recording_fingerprint"] = None
                    state["office_preview_confirmed"] = False
                    state["office_last_sent_label"] = None
                    state["office_last_sent_fingerprint"] = None
                    state["office_recording_input_nonce"] = int(
                        state.get("office_recording_input_nonce", 0)
                    ) + 1
                    st.rerun()
            elif runtime_variant == VARIANT_OFFICE:
                state["office_preview_confirmed"] = False

            if (
                runtime_variant == VARIANT_OFFICE
                and state.get("office_last_sent_label")
                and not state.get("office_recording_bytes")
            ):
                st.success(state.get("office_last_sent_label"))

            if runtime_variant == VARIANT_OFFICE:
                st.markdown("**Office update**")
                st.caption(
                    "This update will be sent to all Family Members for this resident and will appear in Care Hub Mobile."
                )
                st.caption(
                    "Office updates are non-urgent, one-way updates from the care team (no replies). For any queries, please contact the care home directly."
                )
                st.caption(
                    "After pressing Send, wait for the sent confirmation before playing another message."
                )
                selected_office_category = st.selectbox(
                    "Office update category (non-urgent)",
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
                st.caption(
                    "Use these categories for general reassurance only. Personal clinical or urgent matters must use normal care-home channels."
                )

            office_can_send = bool(
                state.get("office_recording_bytes") and state.get("office_preview_confirmed")
            )
            if runtime_variant == VARIANT_OFFICE and st.button(
                f"Send care hub update for {full_name}",
                key=f"care_send_office_update_{resident_id}",
                disabled=not office_can_send,
            ):
                if not office_can_send:
                    st.info("Please record and listen before sending the care hub update.")
                else:
                    supabase, error = get_authed_supabase(access_token)
                    if error:
                        st.error(error)
                    else:
                        office_audio_bytes = state.get("office_recording_bytes") or b""
                        office_audio_mime = state.get("office_recording_mime_type") or "audio/wav"
                        office_now_iso = __import__("datetime").datetime.utcnow().isoformat()
                        office_audio_object_path, office_upload_error = upload_audio_to_storage(
                            office_audio_bytes,
                            office_audio_mime,
                            resident_id=resident_id,
                            direction="office_to_family",
                        )
                        office_inline_fallback = not bool(office_audio_object_path)
                        if APP_DEBUG and office_upload_error:
                            print(
                                "[audio-upload] office_to_family fallback to inline payload:",
                                office_upload_error,
                            )
                        office_payload = {
                            "resident_id": resident_id,
                            "family_id": resident.get("family_id") or resident_id,
                            "channel": "office_family",
                            "direction": "office_to_family",
                            "audio_storage_path": (
                                base64.b64encode(office_audio_bytes).decode("ascii")
                                if office_inline_fallback
                                else ""
                            ),
                            "audio_object_path": office_audio_object_path,
                            "audio_source": "inline" if office_inline_fallback else "storage",
                            "audio_mime_type": office_audio_mime,
                            "audio_bytes": len(office_audio_bytes),
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
                            state["office_recording_bytes"] = None
                            state["office_recording_mime_type"] = "audio/wav"
                            state["office_preview_confirmed"] = False
                            sent_office_fp = state.get("office_recording_fingerprint")
                            state["office_recording_fingerprint"] = None
                            state["office_recording_input_nonce"] = (
                                int(state.get("office_recording_input_nonce", 0)) + 1
                            )
                            state["office_ignore_audio_until"] = time.time() + 5.0
                            soft_sent_label = format_soft_message_period_label(office_now_iso)
                            category_label = (
                                state.get("office_update_category")
                                or OFFICE_UPDATE_CATEGORIES[0]
                            )
                            state["office_last_sent_label"] = (
                                f"{category_label} update sent to all Family Members. {soft_sent_label}"
                                if soft_sent_label
                                else f"{category_label} update sent to all Family Members."
                            )
                            state["office_last_sent_fingerprint"] = sent_office_fp
                            activate_send_guard(send_guard_scope)
                            st.rerun()

            if runtime_variant == VARIANT_OFFICE:
                st.markdown("**Office practical message (structured family reply)**")
                st.caption(
                    "Use this for low-risk practical communication only (for example visits, events, reminders, attendance, or item requests)."
                )
                st.caption(
                    "For urgent or medical matters, families should call the care home directly. Messages sent here are not monitored for emergencies."
                )
                practical_title = st.text_input(
                    "Practical message title",
                    key=f"office_practical_title_{resident_id}",
                    placeholder="Example: Weekend visits",
                )
                practical_body = st.text_area(
                    "Practical message",
                    key=f"office_practical_body_{resident_id}",
                    placeholder="Example: Please confirm whether you are visiting this weekend.",
                    max_chars=800,
                )
                practical_allow_note = st.checkbox(
                    "Allow short note from family (optional)",
                    value=True,
                    key=f"office_practical_allow_note_{resident_id}",
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
                practical_checkboxes = st.multiselect(
                    "Optional tick-box responses",
                    options=list(OFFICE_PRACTICAL_CHECKBOX_OPTIONS),
                    default=list(OFFICE_PRACTICAL_CHECKBOX_OPTIONS),
                    key=f"office_practical_options_{resident_id}",
                )
                if st.button(
                    f"Publish practical message for {full_name}",
                    key=f"office_practical_publish_{resident_id}",
                    use_container_width=True,
                ):
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
                    st.markdown("**Current open practical message**")
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
                            label = str(option_row.get("option_label") or "").strip()
                            if label:
                                st.markdown(f"- {label}")
                    summary = fetch_office_practical_response_summary(
                        active_message_id, access_token
                    )
                    st.caption(
                        "Responses: "
                        f"Yes {summary['choice_counts'].get('yes', 0)} | "
                        f"No {summary['choice_counts'].get('no', 0)} | "
                        f"Maybe {summary['choice_counts'].get('maybe', 0)} | "
                        f"Total {summary.get('total', 0)}"
                    )
                    option_counts = summary.get("option_counts") or {}
                    if option_counts:
                        st.caption("Tick-box selections:")
                        for option_label, option_count in option_counts.items():
                            st.markdown(f"- {option_label}: {option_count}")
                    responses = summary.get("responses") or []
                    if responses:
                        st.caption("Family responses:")
                        for response in responses:
                            contact_name = str(response.get("contact_name") or "Family Member")
                            choice_label = str(response.get("primary_choice") or "").strip().title()
                            st.markdown(f"- {contact_name}: {choice_label}")
                            selected_labels = response.get("selected_labels") or []
                            if selected_labels:
                                st.caption("Selections: " + ", ".join(selected_labels))
                            planned_visit = str(response.get("planned_visit_time") or "").strip()
                            if planned_visit:
                                st.caption(f"Planned visit: {planned_visit}")
                            note_value = str(response.get("note") or "").strip()
                            if note_value:
                                st.caption(f"Note: {note_value}")
                            if bool(response.get("share_with_family", False)):
                                st.caption("Shared with all Family Members.")
                    if st.button(
                        "Close responses for this practical message",
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


    # Navigation rendered at the top of the page.


def render_care_hub_register_family() -> None:
    require_care_access()
    if resolve_runtime_variant(route_hint=get_route()) != VARIANT_OFFICE:
        render_wrong_variant(
            "Family registration is only available in Care Hub – Office."
        )
        return
    back_route = get_office_home_route(bool(st.session_state.get("auth_uid")))
    render_page_header("Register a Family Member", show_menu=False)
    render_route_link(
        "← Back to dashboard",
        back_route,
        key="office_register_family_back_dashboard_link",
    )
    if st.button("Back to dashboard", key="office_register_family_back_dashboard_fallback"):
        set_route(back_route)
    access_token = st.session_state.get("access_token")
    render_care_home_identity_banner(access_token)
    residents = fetch_care_home_residents(access_token)
    render_office_family_registration_form(access_token, residents)


def main() -> None:
    st.set_page_config(
        page_title="voicemailcare.com",
        page_icon="🗣️",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    raw_variant = get_raw_app_variant()
    init_state()
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
            pre_auth_route = "/public/walkthrough-overview"
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
    if (
        variant_requires_auth(app_variant)
        and AUTH_COOKIE_PERSISTENCE_ENABLED
        and app_variant == VARIANT_FAMILY
    ):
        if not AUTH_COOKIE_SIGNING_KEY:
            st.error("Configuration error: AUTH_COOKIE_SIGNING_KEY is required for secure session cookies.")
            st.stop()
        restore_auth_session_from_cookie()
    if pre_auth_route in {FAMILY_LOGIN_ROUTE, MOBILE_LOGIN_ROUTE, OFFICE_LOGIN_ROUTE}:
        normalize_auth_hash_fragment_on_login_routes()
    consume_magic_link_callback()
    route = get_route()
    if route in ("/", "") and pre_auth_route not in ("/", ""):
        route = pre_auth_route
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
        redirect_to_public_landing()
    elif route == "/service-overview":
        redirect_to_public_landing()
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
    elif route == "/care-hub/care-home-banner":
        set_route("/care-hub/operational-variables")
    elif route == "/care-hub/operational-variables":
        render_care_hub_banner_settings()
    elif route == "/care-hub/security":
        render_care_hub_security()
    elif route == "/care-hub/office/qa":
        render_page_header("Office Q&A", show_variant_subheading=False)
        render_care_home_identity_banner(st.session_state.get("access_token"))
        render_route_link(
            "← Back to dashboard",
            get_office_home_route(bool(st.session_state.get("auth_uid"))),
            key="office_qa_back_dashboard_link",
        )
        render_qa_document("docs/office/common_questions_qa.md", search_key="office_qa_search")
    elif route == "/care-hub/mobile/qa":
        render_page_header("Mobile Q&A", show_variant_subheading=False)
        render_care_home_identity_banner(st.session_state.get("access_token"))
        render_route_link("Back", get_home_route(VARIANT_MOBILE), key="mobile_qa_back_link")
        render_qa_document("docs/public/12_mobile_qa.md", search_key="mobile_qa_search")
    elif route == "/family/qa":
        render_page_header("Family Q&A", show_variant_subheading=False)
        render_care_home_identity_banner(st.session_state.get("access_token"))
        render_route_link("Back", get_home_route(VARIANT_FAMILY), key="family_qa_back_link")
        render_qa_document("docs/public/11_family_qa.md", search_key="family_qa_search")
    elif route == "/docs":
        render_docs()
    elif route == "/public-docs":
        redirect_to_public_landing()
    elif route == "/public/service-overview":
        set_route("/public/walkthrough-overview")
    elif route == "/public/how-it-works":
        set_route("/public/walkthrough-overview")
    elif route == "/public/resident-participation":
        set_route("/public/walkthrough-overview")
    elif route == "/public/family-guide":
        set_route("/public/walkthrough-family")
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
    elif route == "/public/walkthrough-family":
        render_public_walkthrough_page(
            "Family Record video",
            "PUBLIC_FAMILY_RECORD_VIDEO_URL,PUBLIC_VIDEO_FAMILY_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_FAMILY_URL",
            "assets/voice-message-family-walkthrough-v1.mp4",
            [
                "How a Family Member sends Family -> Resident voice messages.",
                "How family listens to the resident's current shared message.",
                "How Office updates and practical structured replies appear in Family.",
                "Non-live expectations and calm communication boundaries.",
            ],
            fallback_doc_path="docs/public/06_family_guide.md",
        )
    elif route == "/public/walkthrough-family-flow":
        render_public_walkthrough_page(
            "Family Diagram video",
            "PUBLIC_FAMILY_DIAGRAM_VIDEO_URL,PUBLIC_VIDEO_FAMILY_FLOW_WALKTHROUGH_URL",
            "assets/voice-message-family-walkthrough-v1.mp4",
            [
                "How Family fits into the overall service flow diagram.",
                "How Family channels map to Resident and Office channels.",
                "How replacement-only message rules work in Family direction.",
                "How non-live communication boundaries are applied.",
            ],
            fallback_doc_path="docs/public/06_family_guide.md",
        )
    elif route == "/public/walkthrough-overview":
        render_public_walkthrough_page(
            "Universal Diagram video",
            "PUBLIC_UNIVERSAL_DIAGRAM_VIDEO_URL,PUBLIC_VIDEO_OVERVIEW_URL",
            "assets/voice-message-flow-overview-v1.mp4",
            [
                "How the overall service flow works across the three app interfaces.",
                "Channel boundaries and replacement-only rules.",
                "Where Office updates and practical structured messages fit.",
                "Non-live, non-urgent communication boundaries.",
            ],
        )
    elif route == "/public/walkthrough-mobile":
        render_public_walkthrough_page(
            "Care Hub – Mobile Record video",
            "PUBLIC_MOBILE_RECORD_VIDEO_URL,PUBLIC_VIDEO_MOBILE_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_MOBILE_URL",
            "assets/voice-message-mobile-walkthrough-v1.mp4",
            [
                "How staff play Family -> Resident messages to the resident.",
                "Queue behaviour: unplayed first, then fair rotating replay.",
                "How staff support Resident -> Family recording.",
                "How playback and recording fit around care routines.",
            ],
            fallback_doc_path="docs/public/02_how_it_works.md",
        )
    elif route == "/public/walkthrough-mobile-flow":
        render_public_walkthrough_page(
            "Care Hub – Mobile Diagram video",
            "PUBLIC_MOBILE_DIAGRAM_VIDEO_URL,PUBLIC_VIDEO_MOBILE_FLOW_WALKTHROUGH_URL",
            "assets/voice-message-mobile-walkthrough-v1.mp4",
            [
                "How Mobile sits within the service flow diagram.",
                "How queue order and channel boundaries fit the flow model.",
                "How Mobile playback and recording map to Family and Office channels.",
                "How non-live care-routine delivery is represented in the flow.",
            ],
            fallback_doc_path="docs/public/02_how_it_works.md",
        )
    elif route == "/public/walkthrough-office":
        render_public_walkthrough_page(
            "Care Hub – Office Record video",
            "PUBLIC_OFFICE_RECORD_VIDEO_URL,PUBLIC_VIDEO_OFFICE_APP_WALKTHROUGH_URL,PUBLIC_VIDEO_OFFICE_URL",
            "assets/voice-message-office-walkthrough-v1.mp4",
            [
                "How Office reviews resident-linked family messages.",
                "How Office publishes one-way voice updates to all Family Members.",
                "How Office sends practical text requests and reviews structured replies.",
                "How Office oversight supports low-pressure, non-urgent communication.",
            ],
            fallback_doc_path="docs/public/02_how_it_works.md",
        )
    elif route == "/public/walkthrough-office-flow":
        render_public_walkthrough_page(
            "Care Hub – Office Diagram video",
            "PUBLIC_OFFICE_DIAGRAM_VIDEO_URL,PUBLIC_VIDEO_OFFICE_FLOW_WALKTHROUGH_URL",
            "assets/voice-message-office-walkthrough-v1.mp4",
            [
                "How Office governance and oversight appear in the service flow diagram.",
                "How Office updates and practical messages connect to Family and Mobile.",
                "How one-way Office updates are represented in channel structure.",
                "How calm, non-urgent communication boundaries are enforced.",
            ],
            fallback_doc_path="docs/public/02_how_it_works.md",
        )
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
