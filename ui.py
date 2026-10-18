"""Small presentation helpers. No profiles, analytics, or provider requests."""
from html import escape
from pathlib import Path
import streamlit as st
from branding import APP_NAME, DISPLAY_NAME, APP_MARK, APP_TAGLINE, VERSION


def html(markup):
    st.html(markup)


def apply_style():
    st.html(Path(__file__).with_name("styles.css").read_text(encoding="utf-8"))


def section(number, title, subtitle):
    html(f'<div class="section-heading"><div><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div></div>')


def brand():
    with st.container(key="brand"):
        left, right = st.columns([4, 1], vertical_alignment="center")
        with left:
            html(f'<span class="brand-mark" aria-hidden="true">{escape(APP_MARK)}</span>')
            st.title(DISPLAY_NAME)
        with right:
            page = st.session_state.get("app-page", "Meal")
            if st.button("Meal" if page == "History" else "History", key="nav_toggle", width="stretch"):
                st.session_state["app-page"] = "Meal" if page == "History" else "History"
                st.rerun()


def phase_navigation(has_result):
    phase = st.session_state.get("meal_phase", "Photos")
    if not has_result:
        phase = "Photos"
        st.session_state["meal_phase"] = phase
    left, right = st.columns(2)
    for column, name, number in [(left, "Photos", "1"), (right, "Review", "2")]:
        with column:
            if st.button(f"{number} · {name}", key=f"phase_{name.lower()}",
                         type="primary" if phase == name else "secondary", width="stretch",
                         disabled=name == "Review" and not has_result):
                st.session_state["meal_phase"] = name
                st.rerun()
    return phase


def phase_visibility(phase, page="Meal"):
    # Retain upload/text/portion widgets while switching panels. The camera
    # itself is unmounted in Review to stop its live capture stream.
    hidden = ["phase_navigation", "photo_stage", "review_stage"] if page == "History" else (["photo_stage"] if phase == "Review" else ["review_stage"])
    rules = "".join(f".st-key-{name} {{display:none!important;}}" for name in hidden)
    html(f"<style>{rules}</style>")


def hero():
    first, separator, last = APP_TAGLINE.partition(". ")
    headline = escape(first) + (f'.<br><span>{escape(last)}</span>' if separator else '')
    html(f'''<div class="hero"><div class="eyebrow">CALORIES, AT A GLANCE</div>
    <h2>{headline}</h2>
    <p>Photo-based calorie estimates. No profile needed.</p></div>''')


def macro_balance(totals):
    names = ["Protein", "Carbs", "Fat"]
    if any(totals[name] is None for name in names):
        return
    energies = [max(0, totals[name]) * factor for name, factor in zip(names, [4, 4, 9])]
    total = sum(energies)
    if total <= 0:
        return
    percentages = [100 * value / total for value in energies]
    segments = ''.join(f'<span class="macro-{name.lower()}" style="width:{value:.3f}%"></span>' for name, value in zip(names, percentages))
    labels = ''.join(f'<span><i class="macro-{name.lower()}"></i>{name} {value:.0f}%</span>' for name, value in zip(names, percentages))
    html(f'<div class="macro-chart"><div class="macro-bar" role="img" aria-label="Approximate macro energy split">{segments}</div><div class="macro-legend">{labels}</div><small>Approximate energy split using 4 / 4 / 9 kcal per gram; may differ from USDA calories.</small></div>')


def food_heading(index, name, matched, demo=False):
    html(f'<div class="food-heading"><h3>{escape(name)}</h3></div>')


def footer():
    with st.expander("Our purpose & your privacy"):
        st.write(f"We built {APP_NAME} to help you estimate meal calories from a photo. Review the foods and portions, then see estimated calories and macros.")
        st.write("No app accounts or profiles. We don’t ask for your name, email, age, weight, or other personal details. Please keep faces and personal information out of meal photos and notes.")
        st.write("Photos are resized and image metadata is removed before analysis. Photos and optional meal context are processed temporarily by the app and sent to the photo-analysis provider named at the top of the app (Groq or Google Gemini). Food search terms go to USDA. These providers and the hosting platform have their own data handling; this is not an offline tool.")
        st.write("History is off by default. If you enable it, only meals you choose to save are stored on this browser, without photos. Choose a 1, 7, or 14-day window. Expired entries are removed while the app is open or on your next visit; a closed browser cannot run cleanup. No cross-device sync. Anyone using this browser can see its saved meals.")
        st.write("You can delete meals or turn off and clear history. Downloading a saved-meal PDF sends that one saved meal to the app temporarily to create the report. Downloaded PDFs remain until you delete them yourself.")
        st.caption("The app has no added analytics and does not keep a server meal diary. The hosting platform may still maintain operational logs. A private Streamlit deployment may require platform sign-in; a public deployment removes that access step.")
    html(f'<footer class="rr-footer"><b>{escape(APP_NAME)}</b><span>No account or profile.</span><small>Photo estimates · v{VERSION}</small></footer>')
