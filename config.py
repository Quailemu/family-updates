import os

VALID_APP_VARIANTS: tuple[str, ...] = ("public", "family", "mobile", "office")
_LEGACY_VARIANT_ALIASES = {
    "care_hub_mobile": "mobile",
    "care_hub_office": "office",
}


def get_app_variant() -> str:
    """
    Resolve the active app variant from APP_VARIANT.

    Defaults to "public" when APP_VARIANT is unset/blank.
    Raises ValueError for invalid values to keep deployment errors explicit.
    """
    raw_value = os.getenv("APP_VARIANT", "public").strip().lower()
    candidate = raw_value or "public"
    candidate = _LEGACY_VARIANT_ALIASES.get(candidate, candidate)
    if candidate not in VALID_APP_VARIANTS:
        allowed = ", ".join(VALID_APP_VARIANTS)
        raise ValueError(
            f"Invalid APP_VARIANT '{raw_value or '(empty)'}'. "
            f"Allowed values: {allowed}."
        )
    return candidate


def get_supabase_config() -> tuple[str, str]:
    def _first_env(*names: str) -> str:
        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    url = _first_env("SUPABASE_URL", "supabase_url")
    anon_key = _first_env(
        "SUPABASE_ANON_KEY",
        "supabase_anon_key",
        "SUPABASE_ANONKEY",
        "supabase_anonkey",
    )
    return url, anon_key
