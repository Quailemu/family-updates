import os

import streamlit as st


def get_supabase_config() -> tuple[str, str]:
    url = ""
    anon_key = ""

    def _clean(value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _read_value(mapping: object, key: str) -> object:
        if mapping is None:
            return None
        getter = getattr(mapping, "get", None)
        if callable(getter):
            try:
                return getter(key, None)
            except TypeError:
                # Some mapping-like objects only accept one argument.
                try:
                    return getter(key)
                except Exception:
                    return None
            except Exception:
                return None
        return None

    def _read_secret(*keys: str) -> str:
        for key in keys:
            value = _clean(_read_value(st.secrets, key))
            if value:
                return value
        return ""

    def _read_nested_block(mapping: object, section: str) -> object:
        block = _read_value(mapping, section)
        if block is None:
            block = _read_value(mapping, section.lower())
        if block is None:
            block = _read_value(mapping, section.upper())
        return block

    def _read_nested(section: str, *keys: str) -> str:
        block = _read_nested_block(st.secrets, section)
        for key in keys:
            value = _clean(_read_value(block, key))
            if value:
                return value
        return ""

    def _read_nested_path(path: tuple[str, ...], *keys: str) -> str:
        block: object = st.secrets
        for segment in path:
            block = _read_nested_block(block, segment)
            if block is None:
                return ""
        for key in keys:
            value = _clean(_read_value(block, key))
            if value:
                return value
        return ""

    try:
        url = _read_secret("SUPABASE_URL", "supabase_url")
        anon_key = _read_secret("SUPABASE_ANON_KEY", "supabase_anon_key")
        if not url:
            url = _read_nested("supabase", "SUPABASE_URL", "supabase_url", "url")
        if not anon_key:
            anon_key = _read_nested(
                "supabase",
                "SUPABASE_ANON_KEY",
                "supabase_anon_key",
                "anon_key",
                "anonKey",
            )
        if not url:
            url = _read_nested_path(
                ("connections", "supabase"),
                "SUPABASE_URL",
                "supabase_url",
                "url",
            )
        if not anon_key:
            anon_key = _read_nested_path(
                ("connections", "supabase"),
                "SUPABASE_ANON_KEY",
                "supabase_anon_key",
                "anon_key",
                "anonKey",
                "key",
            )
    except Exception:
        pass
    if not url:
        url = os.getenv("SUPABASE_URL", "").strip()
    if not anon_key:
        anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    return url, anon_key
