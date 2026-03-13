import streamlit as st

TOKENS = {
    "primary": "#4FB7C2",
    "cream": "#FFFFFF",
    "tab_pale": "#CCF4F6",
    "secondary": "#0E7C86",
    "accent": "#B9E53D",
    "bg": "#F7F7F4",
    "panel": "#FFFFFF",
    "text": "#1F1F1F",
    "inactive_text": "rgba(31,31,31,0.45)",
    "muted": "#5B6570",
    "border": "#D8D6D2",
    "radius": "8px",
}


def inject_css() -> None:
    st.markdown(
        f"""
<style>
:root {{
  --color-primary: {TOKENS["primary"]};
  --color-secondary: {TOKENS["secondary"]};
  --color-accent: {TOKENS["accent"]};
  --color-bg: {TOKENS["bg"]};
  --color-panel: {TOKENS["panel"]};
  --color-text: {TOKENS["text"]};
  --color-muted: {TOKENS["muted"]};
  --color-border: {TOKENS["border"]};
  --radius: {TOKENS["radius"]};
}}

html, body, [class*="css"] {{
  font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
  color: var(--color-text);
}}

.stApp {{
  background: var(--color-bg);
}}

.ui-header {{
  margin-bottom: 1.2rem;
}}

.ui-header__title {{
  font-weight: 700;
  font-size: 1.7rem;
  color: var(--color-text);
}}

.ui-header__subtitle {{
  font-size: 1rem;
  color: var(--color-muted);
}}

.ui-caption {{
  margin-top: 0.4rem;
  font-size: 0.9rem;
  color: var(--color-muted);
}}

div.stButton > button {{
  background: var(--color-primary);
  color: #ffffff;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius);
  padding: 0.55rem 1rem;
  font-weight: 600;
}}

div.stButton > button:hover {{
  filter: brightness(0.95);
}}

div.stButton > button:disabled {{
  background: #E7E3E1;
  border-color: #E7E3E1;
  color: #8B8580;
}}

input, textarea, select {{
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius) !important;
  padding: 0.55rem 0.6rem !important;
}}

input:focus, textarea:focus, select:focus, button:focus {{
  outline: 3px solid var(--color-accent) !important;
  outline-offset: 2px;
}}

.ui-card {{
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
}}

.ui-card--accent {{
  border-left: 6px solid var(--color-primary);
}}

.ui-alert {{
  border: 1px solid var(--color-border);
  border-left: 6px solid var(--color-secondary);
  padding: 0.85rem 1rem;
  border-radius: var(--radius);
  background: #ffffff;
}}

.ui-alert--attention {{
  border-left-color: var(--color-accent);
}}

.ui-color-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
}}

.ui-swatch {{
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 0.75rem;
  background: #ffffff;
}}

.ui-swatch__chip {{
  width: 100%;
  height: 52px;
  border-radius: calc(var(--radius) - 2px);
  margin-bottom: 0.5rem;
}}

.ui-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
}}

.ui-button {{
  border-radius: var(--radius);
  border: 1px solid transparent;
  padding: 0.45rem 0.9rem;
  font-weight: 600;
  background: var(--color-primary);
  color: #ffffff;
}}

.ui-button--secondary {{
  background: #ffffff;
  color: var(--color-secondary);
  border-color: var(--color-secondary);
}}

.ui-button--tertiary {{
  background: transparent;
  color: var(--color-secondary);
  border-color: transparent;
}}

.ui-button.is-disabled {{
  background: #E7E3E1;
  color: #8B8580;
  border-color: #E7E3E1;
}}

.ui-button.is-focus {{
  outline: 3px solid var(--color-accent);
  outline-offset: 2px;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def apply_theme() -> None:
    inject_css()
