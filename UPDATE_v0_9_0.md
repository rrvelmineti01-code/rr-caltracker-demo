# Install the micronutrient update

This update builds on the working `main` commit `552785f` in `rrvelmineti01-code/rr-caltracker-demo`.

1. Extract the ZIP. Open `repository_update` and upload its **contents** to the existing GitHub repository root. Keep the included `tests` folder structure. Do not upload the ZIP itself or nest `repository_update` as a new folder.
2. Replace all matching files together, including `app.py`, `ui.py`, `browser_history.py`, `browser_history.js`, `browser_history.css`, `report_export.py`, `branding.py`, `README.md` and the test files. **Add `nutrition.py`** at the root; the updated app requires it. `UPDATE_v0_9_0.md` is the new installation guide.
3. Remove the old root `test_groq_integration.py`; its corrected version is now under `tests/`. No other deletion is required for this update. Existing unused legacy files are not imported by this feature.
4. Commit the changes together to `main`. Preserve existing model files, fonts, `styles.css`, requirements, Streamlit configuration and secrets. No new API key, package or secret setting is needed. Groq remains the default.
5. Reboot the Streamlit app. The footer should say **v0.9.0**. If a browser still shows the earlier interface, refresh the page; do not clear site data because that would delete local meal history.
6. Analyze a meal, check its food match and portion, and open **Nutrition for this portion**. Check **Vitamins, minerals & fiber** in the meal summary.
7. Enable history if needed, then save. The daily panel should update. Open History, find **Nutrient tracker**, and choose **Vitamins** or **Minerals**. A second save of the same reviewed meal updates that entry. Delete a test meal when finished.

The package has been tested locally with mocked photo providers, a live public USDA sample lookup, browser history interactions and a rendered PDF. Your hosted app has not been changed by this package. Test it after uploading.

Old saved meals remain readable, with missing micronutrients marked as unavailable. Partial totals sum only foods that have data. Values are estimates based on USDA food matches and reviewed weights, not daily recommended targets.
