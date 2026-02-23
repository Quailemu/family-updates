import os

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
