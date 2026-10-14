# RR CalTracker — v0.6

**Snap your meal. Know your calories.**

Simple food awareness. No profile needed.

RR CalTracker exists to make people more aware of what they consume: take or upload a meal photo, review the foods and portions, then see estimated calories and macros. No app account, personal-details form, goals questionnaire, or user profile.

## What changed

- One clean photo screen, a quiet green accent, system fonts, and responsive light/dark styling.
- The headline expresses the app's purpose. Optional details and portion corrections are tucked away.
- Take a photo directly or upload one. Camera mode needs HTTPS or localhost and browser permission.
- Optional history on each browser, off by default. Meals are saved only through the Save button. Choose a 1, 7, or 14-day window, with daily calorie/macro totals.
- Delete individual meals or turn off and clear all browser history. No cross-device sync.
- Keep the polished PDF report and the USDA transient-error recovery from previous updates.

## Apply this update

Read `UPDATE_v0_6.txt` in the ZIP. These files replace matching files in your existing app; keep your current report_export.py, assets/fonts folder, launcher scripts, and secret settings.

This version needs Streamlit 1.65.0 for its browser-history component. Use the included requirements.txt.

For local Windows use, extract the update and copy the files into the existing RR_CalTracker folder. Preserve the `tests` subfolder. Place config.toml inside `.streamlit`. Run SETUP.bat if dependencies need updating, then START.bat. Keep keys in your existing local .env and never upload that file.

For your hosted app, upload/replace files in `rrvelmineti01-code/rr-caltracker-demo`, keeping the paths shown in UPDATE_v0_6.txt, commit, then reboot the Streamlit app. The update is prepared for you; it has not been uploaded to GitHub or deployed on your behalf.

## The simple flow

1. Choose Upload photo or Take photo. Show the entire meal.
2. Optionally add foods, oils, sauces, a second view, or a measured plate diameter. Keep personal information out of these inputs.
3. Select Analyze meal. If USDA is temporarily unreachable, automatic retries run; Retry nutrition preserves recognition, successful matches, and portion edits.
4. Open Review foods & portions to correct grams or select a USDA match. Totals update immediately. Unmatched foods are excluded with a visible warning; unavailable nutrients are not treated as zero.
5. Download a PDF, or optionally enable browser history and select Save meal. The demonstration meal cannot be saved as a real meal.
6. Open History to see daily totals, get a saved-meal PDF, delete meals, or change/clear history settings.

## Privacy and retention — precise behavior

The app does not ask for names, emails, age, weight, contact details, or app profiles. It adds no analytics; Streamlit usage statistics are disabled. This does not mean nothing is processed:

- Uploaded/captured photos and optional meal context reach the app server for analysis. Images are resized, orientation corrected, and image metadata removed before Google Gemini receives them. USDA receives food-search terms. Photos are not written to a server meal database or browser diary. Streamlit keeps uploaded/media data temporarily during use, and providers/hosting have their own data handling.
- Reviewed meal history is stored in localStorage for this app's browser origin only when enabled and saved. No user identifier or profile is created. Random per-meal IDs prevent duplicate saves. The saved allowlist contains food names, grams, nutrition, USDA match information, and meal/date metadata; no photos, provider keys, free-form notes, or analysis assumptions.
- Pick 1, 7, or 14 days. A meal expires when its meal date leaves that local calendar window or its original saved timestamp reaches the chosen age. Editing a retained meal does not reset that timestamp. Pruning runs on diary mount, actions, other-tab updates, and every minute while the component is open.
- Browsers cannot execute cleanup while closed. Expired entries are removed the next time the app opens. If the app is never opened again, bytes can remain in browser storage until the user clears browser/site data. Do not promise physical deletion exactly at 14 days while a browser is closed.
- Local history is not encrypted by this app. Anyone using that browser/browser profile can see it. Separate browsers/devices have independent history. Private browsing and clearing site data may remove it sooner. Changing the app's domain creates a different storage origin.
- Saving, viewing, deleting, and changing retention do not send the diary to Python or the providers. Explicitly requesting a saved-meal PDF sends only that requested snapshot to Python temporarily, to create the report. Downloaded PDFs are outside the history window and remain until the user deletes them.
- The app does not create a persistent server meal diary. The host/providers may maintain their own operational records; this code cannot control their retention.

## Existing history from older versions

v0.5 used a shared server-side SQLite diary. v0.6 never imports, reads, writes, or migrates it. Old entries are not copied into browser history because they cannot be reliably attributed to a browser without accounts. Existing `meal_history.py` and `meal_store.py` can be removed after applying this update. An old `data/meals.sqlite3` file is not automatically deleted: export any entries you want to keep, then remove the old `data` folder yourself if it exists. Never upload that folder or a secrets file to GitHub.

## Open access without platform sign-in

The application itself has no sign-up or profile flow. A private Streamlit Community Cloud deployment can still require platform sign-in for viewers. For open access, the owner must change the Streamlit app's sharing/access setting to public. The source repository can remain private. This update does not change your hosting access settings.

## Accuracy

Photo-derived portions are estimates. Hidden oils, preparation, recipe differences, and imperfect database matches affect results. USDA values per 100 g are scaled by reviewed grams in Python; Gemini identifies foods and estimates portions rather than inventing calorie totals. Portion ranges are suggestions, not validated confidence intervals. This version makes no clinical or weighed-meal accuracy claim.

## Verification

Offline Python checks (analysis requests mocked, no live keys):

    python tests/run_offline.py

Browser-state logic (developer Node.js, no npm dependencies):

    node --test tests/test_browser_history.mjs

DOM interaction tests require jsdom as a developer-only dependency (not part of app installation):

    npm install --no-save jsdom
    node --test tests/test_history_dom.mjs

The delivered version passed 35 Python checks, 11 browser-state checks, and 3 DOM interaction checks. The DOM tests exercise opt-in, explicit save, reload, safe rendering, daily totals, PDF request, expiry, cross-tab updates, deletion and opt-out. Light/dark color pairs were checked for readable contrast. Full browser/phone visual rendering and your hosted API connections still need checking on your deployed app; these checks do not claim to have verified your production instance.
