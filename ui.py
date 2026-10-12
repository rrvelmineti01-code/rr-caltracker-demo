"""Presentation helpers; no provider requests or private data."""
from html import escape
from pathlib import Path

import streamlit as st


def html(markup):
    st.html(markup)


def apply_style():
    st.html(Path(__file__).with_name("styles.css").read_text(encoding="utf-8"))


def section(number, title, subtitle):
    html(f'<div class="section-heading"><span class="section-number">{number}</span>'
         f'<div><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div></div>')


def brand():
    with st.container(key="brand"):
        left, right = st.columns([3, 1], vertical_alignment="center")
        with left:
            html('<span class="brand-mark" aria-hidden="true">RR<span>↗</span></span>')
            st.title("RR CalTracker")
        with right:
            html('<div class="brand-badge"><span></span> Meal studio</div>')


def hero():
    html('''<div class="hero"><div class="eyebrow">A LITTLE CLARITY, EVERY MEAL</div>
    <h2>Know what’s<br>on your <span>plate.</span></h2>
    <p>Turn a meal photo into a clearer picture of your calories and macros.<br class="desktop-break">
    Review the portions. Make it your own.</p></div>''')


def steps(active):
    items = [("Upload", "Your meal photo"), ("Review", "Foods & portions"), ("Explore", "Calories & macros")]
    parts = []
    for index, (label, note) in enumerate(items, 1):
        state = "done" if index < active else "active" if index == active else "pending"
        number = "✓" if index < active else str(index).zfill(2)
        current = ' aria-current="step"' if index == active else ""
        parts.append(f'<li class="{state}"{current}><span class="step-index">{number}</span>'
                     f'<div><strong>{label}</strong><small>{note}</small></div></li>')
    html('<ol class="steps" aria-label="Meal analysis steps">' + "".join(parts) + '</ol>')


def plate():
    """A bundled vector illustration, not a photograph or analyzed meal."""
    return '''<svg viewBox="0 0 400 300" role="img" aria-label="Illustration of a balanced plate">
    <ellipse cx="205" cy="258" rx="128" ry="15" fill="#0e3029" opacity=".12"/>
    <circle cx="200" cy="144" r="126" fill="#f3eee1"/><circle cx="200" cy="144" r="112" fill="#fffdf7"/>
    <circle cx="200" cy="144" r="96" fill="#f4f0e5" stroke="#e5dfd0" stroke-width="2"/>
    <path d="M128 97c35-27 67-20 69 18 3 24-9 48-27 50-32 2-66-15-42-68" fill="#e4c9a1"/>
    <g fill="#fff8e5" stroke="#d4b88d" stroke-width="1.2">
    <ellipse cx="144" cy="110" rx="12" ry="4" transform="rotate(-28 144 110)"/>
    <ellipse cx="163" cy="103" rx="12" ry="4" transform="rotate(35 163 103)"/>
    <ellipse cx="178" cy="116" rx="12" ry="4" transform="rotate(-20 178 116)"/>
    <ellipse cx="137" cy="129" rx="12" ry="4" transform="rotate(25 137 129)"/>
    <ellipse cx="159" cy="126" rx="12" ry="4" transform="rotate(-38 159 126)"/>
    <ellipse cx="179" cy="137" rx="12" ry="4" transform="rotate(35 179 137)"/>
    <ellipse cx="148" cy="145" rx="12" ry="4" transform="rotate(-15 148 145)"/>
    <ellipse cx="163" cy="155" rx="12" ry="4" transform="rotate(25 163 155)"/></g>
    <g transform="rotate(-18 211 189)"><rect x="157" y="167" width="109" height="49" rx="23" fill="#c77342"/>
    <path d="M177 176l-6 28m27-30-6 34m26-34-6 35m26-31-6 27" stroke="#915c36" stroke-width="5" stroke-linecap="round"/>
    <path d="M173 168c15-5 46-4 68 0" stroke="#f6b975" stroke-width="4" stroke-linecap="round"/></g>
    <g fill="#527959"><path d="M235 118l-12 37h12l10-33m27 2-9 35h12l7-34" fill="#a4b879"/>
    <circle cx="230" cy="102" r="20"/><circle cx="250" cy="108" r="19"/><circle cx="222" cy="118" r="17"/>
    <circle cx="273" cy="114" r="20"/><circle cx="289" cy="130" r="16"/><circle cx="264" cy="133" r="19"/>
    <circle cx="236" cy="98" r="10" fill="#6c9564"/><circle cx="281" cy="111" r="10" fill="#6c9564"/></g>
    <g fill="#cb6047"><circle cx="131" cy="187" r="14"/><circle cx="274" cy="174" r="12"/></g>
    <g stroke="#f7c99c" stroke-width="2"><path d="M125 181l10 9m-10 0 10-9m134-12 10 9m-10 0 10-9"/></g>
    <path d="M326 67v124m-9-124v36c0 13 18 13 18 0V67m-9 57v90" fill="none" stroke="#b7c4af" stroke-width="5" stroke-linecap="round"/>
    </svg>'''


def guide():
    html('<div class="guide-card"><div class="eyebrow">GOOD FOOD. A CLEARER PICTURE.</div>'
         + plate() + '''<h3>Small details.<br>Better context.</h3>
         <p>A clear photo helps you review your meal with more confidence.</p>
         <div class="guide-tip"><b>01</b><span>Photograph the whole plate from above.</span></div>
         <div class="guide-tip"><b>02</b><span>Add a side view to show portion height.</span></div>
         <div class="guide-tip"><b>03</b><span>Include any known oils, sauces, or weights.</span></div>
         <div class="guide-foot">Photo portions are estimates. You’re in control of the final amounts.</div></div>''')


def empty_results():
    html('''<div class="empty-results"><div class="eyebrow">YOUR MEAL, AT A GLANCE</div>
    <h3>Clarity starts with a photo.</h3><p>Your calories and macros will appear here after analysis.</p>
    <div class="empty-metrics"><div><span>Calories</span><b>—</b><small>kcal</small></div>
    <div><span>Protein</span><b>—</b><small>g</small></div><div><span>Carbs</span><b>—</b><small>g</small></div>
    <div><span>Fat</span><b>—</b><small>g</small></div></div></div>''')


def macro_balance(totals):
    """Show relative macro energy only; USDA calories remain the main total."""
    names = ["Protein", "Carbs", "Fat"]
    if any(totals[name] is None for name in names):
        return
    energies = [max(0, totals[name]) * factor for name, factor in zip(names, [4, 4, 9])]
    total = sum(energies)
    if total <= 0:
        return
    percentages = [100 * value / total for value in energies]
    segments = ''.join(f'<span class="macro-{name.lower()}" style="width:{value:.3f}%"></span>'
                       for name, value in zip(names, percentages))
    labels = ''.join(f'<span><i class="macro-{name.lower()}"></i>{name} {value:.0f}%</span>'
                     for name, value in zip(names, percentages))
    html(f'<div class="macro-chart"><div class="macro-chart-title">Macro energy balance</div>'
         f'<div class="macro-bar" role="img" aria-label="Protein {percentages[0]:.0f} percent, '
         f'carbs {percentages[1]:.0f} percent, fat {percentages[2]:.0f} percent">{segments}</div>'
         f'<div class="macro-legend">{labels}</div>'
         '<small>Approximate split using 4 / 4 / 9 kcal per gram; may differ from database calories.</small></div>')


def food_heading(index, name, matched, demo=False):
    status = "Sample data" if demo else "Match to review" if matched else "Match needed"
    html(f'<div class="food-heading"><div><span class="food-index">{index+1:02d}</span>'
         f'<h3>{escape(name)}</h3></div><span class="food-status">{status}</span></div>')


def footer():
    html('''<footer class="rr-footer"><b>RR CalTracker</b><span>Made for a more mindful plate.</span>
    <small>Photo estimates · Review before using · POC v0.5</small></footer>''')
