"""Small presentation helpers. No profiles, analytics, or provider requests."""
from html import escape
from pathlib import Path
import streamlit as st


def html(markup):
    st.html(markup)


def apply_style():
    st.html(Path(__file__).with_name("styles.css").read_text(encoding="utf-8"))


def section(number, title, subtitle):
    html(f'<div class="section-heading"><div><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div></div>')


def brand():
    with st.container(key="brand"):
        st.title("RR CalTracker")


def hero():
    html('''<div class="hero"><div class="eyebrow">AWARENESS STARTS WITH A PHOTO</div>
    <h2>Snap your meal.<br><span>Know your calories.</span></h2>
    <p>Simple food awareness. No profile needed.</p>
    <div class="hero-note">Photo → Review → Calories<span>History is optional. Up to 14 days, on this browser.</span></div></div>''')


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
        st.write("We built RR CalTracker to make food awareness simple: take a photo, review an estimate, and understand what you’re consuming.")
        st.write("No app accounts or profiles. We don’t ask for your name, email, age, weight, or other personal details. Please keep faces and personal information out of meal photos and notes.")
        st.write("Photos are resized and image metadata is removed before analysis. Photos and optional meal context are processed temporarily by the app and sent to Google Gemini. Food search terms go to USDA. These providers and the hosting platform have their own data handling; this is not an offline tool.")
        st.write("History is off by default. If you enable it, only meals you choose to save are stored on this browser, without photos. Choose a 1, 7, or 14-day window. Expired entries are removed while the app is open or on your next visit; a closed browser cannot run cleanup. No cross-device sync. Anyone using this browser can see its saved meals.")
        st.write("You can delete meals or turn off and clear history. Downloading a saved-meal PDF sends that one saved meal to the app temporarily to create the report. Downloaded PDFs remain until you delete them yourself.")
        st.caption("The app has no added analytics and does not keep a server meal diary. The hosting platform may still maintain operational logs. A private Streamlit deployment may require platform sign-in; a public deployment removes that access step.")
    html('<footer class="rr-footer"><b>RR CalTracker</b><span>A little awareness, every meal.</span><small>Photo estimates · v0.6</small></footer>')
