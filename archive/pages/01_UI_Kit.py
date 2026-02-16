from pathlib import Path

import streamlit as st

import ui_theme
from app import global_header


def render_swatches() -> None:
    st.markdown(
        """
<div class="ui-color-grid">
  <div class="ui-swatch">
    <div class="ui-swatch__chip" style="background: var(--color-primary);"></div>
    <div>Primary / Cerise</div>
    <div>#D80073</div>
  </div>
  <div class="ui-swatch">
    <div class="ui-swatch__chip" style="background: var(--color-secondary);"></div>
    <div>Secondary / Teal</div>
    <div>#0E7C86</div>
  </div>
  <div class="ui-swatch">
    <div class="ui-swatch__chip" style="background: var(--color-accent);"></div>
    <div>Accent / Lime</div>
    <div>#B9E53D</div>
  </div>
  <div class="ui-swatch">
    <div class="ui-swatch__chip" style="background: var(--color-bg);"></div>
    <div>Background</div>
    <div>#F7F7F4</div>
  </div>
  <div class="ui-swatch">
    <div class="ui-swatch__chip" style="background: var(--color-text);"></div>
    <div>Text</div>
    <div>#1F1F1F</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_buttons() -> None:
    st.markdown("#### Buttons")
    st.markdown(
        """
<div class="ui-row">
  <button class="ui-button">Primary</button>
  <button class="ui-button is-focus">Primary focus</button>
  <button class="ui-button is-disabled">Primary disabled</button>
  <button class="ui-button ui-button--secondary">Secondary</button>
  <button class="ui-button ui-button--secondary is-focus">Secondary focus</button>
  <button class="ui-button ui-button--secondary is-disabled">Secondary disabled</button>
  <button class="ui-button ui-button--tertiary">Tertiary</button>
  <button class="ui-button ui-button--tertiary is-focus">Tertiary focus</button>
  <button class="ui-button ui-button--tertiary is-disabled">Tertiary disabled</button>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption("Loading states should disable the button and swap label to Loading.")


def render_cards() -> None:
    st.markdown("#### Cards and panels")
    st.markdown(
        """
<div class="ui-row">
  <div class="ui-card" style="min-width: 220px;">
    <div style="font-weight: 600;">Standard panel</div>
    <div>Neutral framing, calm tone.</div>
  </div>
  <div class="ui-card ui-card--accent" style="min-width: 220px;">
    <div style="font-weight: 600;">Emphasized panel</div>
    <div>Cerise frame for priority.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_alerts() -> None:
    st.markdown("#### Alerts and highlights")
    st.markdown(
        """
<div class="ui-row">
  <div class="ui-alert" style="min-width: 240px;">
    <div style="font-weight: 600;">Info</div>
    <div>Secondary tone for guidance.</div>
  </div>
  <div class="ui-alert ui-alert--attention" style="min-width: 240px;">
    <div style="font-weight: 600;">Attention</div>
    <div>Use lime sparingly for focus.</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_forms() -> None:
    st.markdown("#### Form elements")
    st.text_input("Text input", placeholder="Type here")
    st.text_input("Password", type="password")
    st.selectbox("Select", ["Option one", "Option two", "Option three"])
    st.text_area("Notes", placeholder="Short note")
    st.checkbox("Checkbox")
    st.radio("Radio", ["Choice A", "Choice B"], horizontal=True)


def render_tabs() -> None:
    st.markdown("#### Tabs")
    tabs = st.tabs(["Active tab", "Inactive tab", "Another tab"])
    with tabs[0]:
        st.markdown("Active tab content.")
    with tabs[1]:
        st.markdown("Inactive tab content.")
    with tabs[2]:
        st.markdown("Another tab content.")


def render_icons() -> None:
    st.markdown("#### Icons")
    icon_paths = [
        Path("assets/icons/voice-message pilot logo.svg"),
        Path("assets/icons/grandmother-9689448.svg"),
        Path("assets/icons/grandmother-9701879.svg"),
    ]
    columns = st.columns(3)
    for idx, icon_path in enumerate(icon_paths):
        with columns[idx]:
            if not icon_path.exists():
                st.caption(f"Missing: {icon_path.name}")
                continue
            svg = icon_path.read_text(encoding="utf-8")
            st.markdown(
                f'<div class="ui-card" style="text-align: center;">{svg}'
                f'<div style="margin-top: 0.5rem;">{icon_path.name}</div></div>',
                unsafe_allow_html=True,
            )


def render_states_matrix() -> None:
    st.markdown("#### States matrix")
    st.markdown(
        """
<div class="ui-card">
  <div style="font-weight: 600; margin-bottom: 0.4rem;">Key states</div>
  <div>Buttons: idle, hover, focus, active, disabled, loading</div>
  <div>Tabs: inactive, active, focus</div>
  <div>Inputs: idle, focus, error, disabled</div>
  <div>Cards: default, emphasized, highlight strip</div>
</div>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    ui_theme.apply_theme()
    global_header()
    st.title("UI Kit / Reference")

    st.markdown("## Colors and tokens")
    render_swatches()

    st.markdown("## Typography")
    st.markdown("### Heading level 2")
    st.markdown("Body text should be calm, direct, and readable.")
    st.caption("Caption text for supporting notes.")

    st.markdown("## Components")
    render_buttons()
    render_tabs()
    render_cards()
    render_alerts()
    render_forms()
    render_icons()
    render_states_matrix()


if __name__ == "__main__":
    main()
