"""Meal-log controls and date-based history, shared by laptop and phone clients."""
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4

import streamlit as st

import meal_store as store
import ui
from report_export import build_meal_pdf


def local_today():
    # A visible user-selected date remains authoritative, including backdated entries.
    return datetime.now().astimezone().date()


def metric_value(value, name):
    unit = "kcal" if name == "Calories" else "g"
    return "Unavailable" if value is None else f"{value:,.0f} {unit}"


def render_save(payload, saved):
    if payload.get("demo"):
        st.caption("Sample meals are for exploring the interface and are not added to your meal history.")
        return
    token = saved.setdefault("log_token", str(uuid4()))
    st.subheader("Add to your meal history")
    st.caption("Choose the date you ate this meal. You can add multiple meals in any category.")
    with st.form("save-" + token):
        left, right = st.columns(2)
        eaten_on = left.date_input("Meal date", value=local_today())
        category = right.selectbox("Meal category", store.CATEGORIES)
        title = st.text_input("Meal name (optional)", max_chars=120,
                              placeholder="e.g. Chicken and rice")
        submit = st.form_submit_button("Save meal to history", width="stretch")
    if submit:
        try:
            store.save_meal(token, eaten_on, category, title, payload)
            saved["logged"] = True
            st.success(f"Meal saved for {eaten_on:%d %b %Y} · {category}.")
        except (sqlite3.Error, OSError):
            st.error("The meal could not be saved. Check that the project folder is writable, then try again.")
        except ValueError as error:
            st.error(str(error))
    if saved.get("logged"):
        st.caption("Saving this review again updates the same entry. Analyze a new meal to log another serving.")


def render_history():
    ui.section("04", "Your meal history", "Pick a date to review your meals, or compare the past 7 or 14 days.")
    st.caption("This POC has one shared diary on the laptop running the app. Dates default to the laptop's local date.")
    chosen = st.date_input("Calendar · select a day", value=local_today(), key="history-day")
    window = st.radio("Review period ending on the selected day", ("Selected day", "7 days", "14 days"), horizontal=True)
    length = {"Selected day": 1, "7 days": 7, "14 days": 14}[window]
    start = chosen - timedelta(days=length - 1)
    try:
        meals = store.list_meals(start, chosen)
    except (sqlite3.Error, OSError, ValueError):
        st.error("Meal history could not be opened. Check the project folder and keep the data folder intact.")
        return
    day_meals = [m for m in meals if m["meal_date"] == chosen.isoformat()]
    totals = store.summarize(day_meals)
    st.subheader(f"{chosen:%A, %d %B %Y}")
    if not day_meals:
        st.info("No meals logged for this date. Choose another day or save a reviewed meal.")
    else:
        columns = st.columns(4)
        for column, name in zip(columns, store.NUTRIENTS):
            column.metric(name, metric_value(totals[name], name))
        st.caption(f"{len(day_meals)} saved meal(s). Totals include only what you logged.")
        if totals["Partial"]:
            st.warning("Some saved meals are partial estimates. Their totals exclude unmatched foods.")
        for category in store.CATEGORIES:
            group = [m for m in day_meals if m["category"] == category]
            st.markdown(f"**{category}**")
            if not group:
                st.caption("No meals logged.")
            for item in group:
                render_entry(item)
    if length > 1:
        st.subheader(f"{length}-day comparison · {start:%d %b} to {chosen:%d %b %Y}")
        daily = store.daily_summaries(meals, start, chosen)
        st.dataframe(daily, hide_index=True, width="stretch",
                     column_config={"Calories": st.column_config.NumberColumn("Calories (kcal)", format="%.0f"),
                                    **{n: st.column_config.NumberColumn(n + " (g)", format="%.1f")
                                       for n in ("Protein", "Carbs", "Fat")}})
        logged_days = sum(row["Meals"] > 0 for row in daily)
        summary = store.summarize(meals)
        st.caption(f"{len(meals)} meals across {logged_days} logged day(s). Blank nutrient values mean unavailable or no meals logged; they are not zero.")
        if summary["Calories"] is not None:
            label = "Known logged calories" if summary["Partial"] else "Logged calories"
            st.write(f"{label}: **{summary['Calories']:,.0f} kcal** over this period.")
        try:
            previous = store.list_meals(chosen - timedelta(days=1), chosen - timedelta(days=1))
            prev_totals = store.summarize(previous)
            if totals["Calories"] is not None and prev_totals["Calories"] is not None:
                delta = totals["Calories"] - prev_totals["Calories"]
                st.write(f"Selected day versus previous day: **{delta:+,.0f} kcal** in logged meals.")
        except (sqlite3.Error, OSError):
            st.warning("The previous day's comparison could not be loaded.")
    st.caption("Keep the project's data folder when applying updates. Saved logs remain until you delete them.")


def render_entry(item):
    snapshot = item["snapshot"]
    with st.expander(item["title"] + " · " + metric_value(snapshot["totals"].get("Calories"), "Calories")):
        st.caption("Partial estimate" if snapshot.get("partial") else "Reviewed meal estimate")
        st.dataframe([{"Food": food["name"], "Portion (g)": food["grams"],
                       "Calories (kcal)": food.get("nutrients", {}).get("Calories")}
                      for food in snapshot["foods"]], hide_index=True, width="stretch")
        with st.form(f"edit-log-{item['id']}"):
            new_date = st.date_input("Change date", value=datetime.fromisoformat(item["meal_date"]).date())
            category = st.selectbox("Change category", store.CATEGORIES, index=store.CATEGORIES.index(item["category"]))
            title = st.text_input("Change meal name", value=item["title"], max_chars=120)
            update = st.form_submit_button("Update meal details")
        if update:
            try:
                store.change_meal_details(item["id"], new_date, category, title)
                st.rerun()
            except (sqlite3.Error, OSError, ValueError):
                st.error("Meal details could not be updated. Try again.")
        report = dict(snapshot)
        report["assumptions"] = [f"Logged for {item['meal_date']} · {item['category']} · {item['title']}",
                                 *report.get("assumptions", [])]
        st.download_button("Download saved meal PDF", data=build_meal_pdf(report),
                           file_name=f"RR_meal_{item['meal_date']}_{item['id']}.pdf",
                           mime="application/pdf", key=f"history-pdf-{item['id']}")
        confirmed = st.checkbox("Confirm deletion of this meal", key=f"confirm-delete-{item['id']}")
        if st.button("Delete meal", key=f"delete-{item['id']}", disabled=not confirmed):
            try:
                store.delete_meal(item["id"])
                st.rerun()
            except (sqlite3.Error, OSError):
                st.error("The meal could not be deleted. Try again.")
