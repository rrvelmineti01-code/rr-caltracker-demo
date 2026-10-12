# RR CalTracker — v0.5 Meal studio + saved history

A Python/Streamlit proof of concept for demonstrating a complete meal-photo workflow in your browser:

1. Upload a JPG, PNG, or WEBP meal photo.
2. Gemini identifies foods and suggests edible weights and plausible portion ranges.
3. USDA supplies candidate nutrition matches.
4. Review each match and edit portions; Python recalculates calories, protein, carbs, and fat automatically.
5. Download a styled PDF of the reviewed meal.
6. Save it under a date and meal category, then review daily or 7/14-day history.

This package runs on your laptop. It does not create a hosted website or sharing URL. Camera capture and micronutrient reporting are outside this POC's scope.

## New interface

The meal studio uses an ivory and forest-green palette, a bundled plate illustration, clear step indicators, spacious upload controls, and editable food cards. Calories and macros appear above the review cards and update when you change a portion. On phones, the layout stacks and the nutrition cards become a two-column grid. A macro-energy bar shows the approximate protein/carbohydrate/fat split using 4/4/9 kcal per gram; USDA calories remain the displayed meal total.

**Try a sample meal** opens an interactive, clearly labelled demonstration without API calls or credentials. Its illustrative values are not photo-analysis results or live USDA data. You can change weights, download a sample PDF clearly marked SAMPLE MEAL, and close it. Uploading your own photo exits the sample. The font uses your device's sans-serif family with Segoe UI first on Windows; no external font or image downloads are required.

## Fresh installation from the complete ZIP

Before deleting your old folder, copy its `.env` somewhere safe. Extract this ZIP into a new folder, copy the saved `.env` beside the new `app.py`, and double-click **SETUP.bat**. It creates a new `.venv`, installs the dependencies, and keeps an existing `.env`. If none is present, it creates one from `.env.example` and opens it in Notepad for your keys.

Double-click **START.bat** for laptop use. For phone use, stop the laptop launcher with Ctrl+C and double-click **START_MOBILE.bat**. Open the printed address for your connected Wi-Fi adapter on your phone. Both devices must use the same trusted Wi-Fi and the laptop must stay awake.

The `.venv` directory is created locally rather than bundled: Python environments cannot be reliably copied between Windows installations. Private API keys are not included. The Windows batch launchers have been reviewed but cannot be executed in this Linux verification environment.

## Update your existing Windows installation

1. Stop the app with Ctrl+C.
2. Extract the full ZIP into a temporary folder. Copy the contents of its `RR_CalTracker` folder into your working project folder and replace project files.
3. Keep your `.env`, `.venv`, and any existing `data` folder. The ZIP contains no keys, virtual environment, or personal meal database.
4. If v0.4.1 already works, no dependency reinstall is needed. Otherwise run `SETUP.bat` once for the PDF dependencies.
5. Run `START_MOBILE.bat` or `START.bat` and refresh the browser.

For a fresh installation, copy your saved `.env` beside `app.py`, run `SETUP.bat`, then launch as before. Keep your previous installation until the new one works. Future changes can be distributed as only the affected files; this release is the complete package requested.

## Calendar and meal history

After analyzing a real photo and reviewing food matches and portions, use **Add to your meal history**. Select the date you ate the meal and Breakfast, Lunch, Dinner, or Snack. Give it an optional name and click **Save meal to history**. Dates default to the laptop's local clock; you can backdate a meal. Multiple meals can share a date and category. Saving the same reviewed meal again updates its existing entry, including edited portions, rather than duplicating it. Analyze a new meal to add another serving.

Open **Meal history** from the sidebar (expand the sidebar menu on a phone). The calendar date picker chooses the day; the review-period control selects that day or the 7/14 days ending on it. Daily calories and macros appear with meal categories and an exact daily comparison table. When both days have known logged calories, the period view also shows the selected day's difference from the previous day.

Expand a saved meal to see its foods, download its PDF, change its date/category/name, or delete it after confirming deletion. Saved portions and nutrition are a snapshot of the reviewed result; old meals do not require another AI call. Historical portion edits are not implemented in this release. Re-saving a still-open review updates that entry.

Days without logs are blank, not zero intake. Missing nutrition remains unavailable. Partial meals are labelled and exclude unmatched foods; period totals cover only logged meals. Sample meals cannot enter the real diary. Nothing before this update is recovered automatically: earlier meals were not persisted. You can analyze earlier photos and save them under their original dates.

The diary is a SQLite database created automatically at `data/meals.sqlite3` next to `app.py`. Logs survive app and laptop restarts and are not limited to 14 days. To back up or move the diary, stop the app and copy the complete `data` folder. Preserve it during updates. Both laptop and phone browsers use the same database when connected to this laptop-hosted instance. This POC has one shared diary, with no separate user accounts; anyone able to open the app can view and modify that diary. It does not sync independent installations or upload the diary to a cloud database.

## Use the app on your phone over home Wi-Fi

Your phone and laptop must be connected to the same trusted Wi-Fi network, and the laptop must remain awake with the app running.

1. Stop the current app with Ctrl+C. From your original project folder, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

2. Open a second PowerShell window and run:

```powershell
ipconfig
```

3. Under the connected Wi-Fi adapter, find its **IPv4 Address**. On your phone, type `http://`, that IPv4 address, and `:8501` into Safari or Chrome. Use the laptop's actual address, not `localhost` or `0.0.0.0`.
4. The upload control lets you choose a supported image from your phone. A phone may offer camera capture through its file picker, but a dedicated camera flow is not implemented.

If Windows Firewall asks about Python, allow access on your trusted private network. If the page does not load, check that both devices are on the same non-guest Wi-Fi and the laptop is still running the app. Guest networks may block connections between devices. VPN routing or firewall settings can also prevent access. Do not turn off the firewall or configure router port forwarding for this POC.

Anyone who can reach this unauthenticated app on the local network can use its analysis workflow and consume the configured API quota. Use a trusted network. This local address will not work away from that network; access from anywhere needs a hosted deployment with appropriate access controls and server-side secrets. The previous version worked on your phone. This redesigned version still needs visual checking on your devices.

## New installation

From the folder containing `app.py`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Fill in `GEMINI_API_KEY` and `USDA_API_KEY` locally. `GEMINI_MODEL` selects the Gemini model; keep a model already working with your account. Save and run the launch command. Do not share `.env` or include it in a portfolio upload.

## A short demonstration

1. Choose a clearly lit meal with two or three visible foods, and upload it.
2. Name the foods and preparation in the description. Include known oil, butter, or sauce amounts.
3. Click **Analyze meal** once. Check food identities and the cooking state of each USDA match.
4. Change a suggested portion to a weighed amount and select the kitchen-scale checkbox. Calories and macros should update without reanalyzing the photo.
5. Download the reviewed result to show the food weights, database IDs, totals, and assumptions.

Describe the output as an estimated nutrition calculation. Do not present photo-derived grams or model-suggested ranges as measured quantities.

## PDF meal report

**Download meal report (PDF)** replaces the JSON download. The report includes calories/macros, the macro-energy split when data is complete, reviewed food weights, per-food nutrients, database matches and IDs, portion notes, and assumptions. Missing nutrients remain unavailable and partial results list excluded foods. Sample exports are clearly labelled. The creation time is shown in UTC. The PDF uses the same reviewed values as the app and is generated without another AI call.

A small sample is included at `examples/RR_CalTracker_sample.pdf`. The PDF layout has been rendered and visually checked, including normal, partial, and lengthy reports with wrapped rows and repeated table headers. Fonts are bundled for consistent appearance on Windows; their license is in `assets/fonts/LICENSE.txt`.

## Optional portion context

Under **Add a side view or plate measurement**, upload an angled side photo of the SAME unchanged meal. Keep the full plate rim visible in both photos. For a round plate, enter its measured outer diameter in centimetres, edge to edge through the centre. No plate size is assumed if the measurement is blank.

Gemini receives both views in one request and is instructed to count each food once, consider its footprint and visible height, and state unresolved assumptions. The app does not perform calibrated depth sensing, construct a 3D mesh, or directly measure volume or mass. Better accuracy has not yet been demonstrated; it needs comparison with weighed meals.

The portion-based calorie range varies only food weights while keeping USDA matches fixed. It is not a validated statistical confidence interval and does not capture recipe, hidden-oil, food-identity, or database-match errors. An edited estimated weight rescales its suggested range; marking a weight as measured replaces that range with the entered weight. Nutrition values remain estimates even when a portion is weighed.

## Error handling and data flow

- USDA errors preserve identified foods. Use **Retry missing nutrition lookups** after resolving a key, connection, or quota problem.
- Foods without database matches are excluded and totals are labeled partial.
- Missing nutrient data remains unavailable, rather than being counted as zero.
- Changing either photo, the description, or plate diameter clears the prior analysis.
- Portion and match edits do not make another Gemini call. USDA searches are cached temporarily.

On Analyze, resized photos and the description/plate measurement are sent to Google. Nutrition search text goes to USDA. Photos are not saved by this app to disk; the optional PDF download contains reviewed portions, nutrition, and estimate notes, not photos or keys. PDF generation happens in memory on your laptop without an additional provider call. Keys go in HTTP headers and provider error bodies are not displayed. Providers' terms, retention policies, quotas, and billing settings apply.

## Validation

All 23 offline checks passed. Existing checks cover the image/portion workflow, error handling, sample mode, and PDF output. New checks cover persistent storage across fresh connections, category/date filtering, repeated-save duplicate prevention, multiple servings, unknown/partial totals, metadata edits, deletion, excluding demo/invalid data, and the real review → portion edit → save → fresh app session → history → 14-day view → delete flow. Provider responses are simulated. The offline runner blocks network connections and unmocked HTTP requests:

```powershell
.\.venv\Scripts\python.exe tests\run_offline.py
```

Live API calls, the final appearance on your phone, and Windows launchers still need checking on your devices. Existing nutrition estimates are unchanged and do not establish measured 3D accuracy.

## References

- Gemini multiple-image input: https://ai.google.dev/gemini-api/docs/generate-content/image-understanding
- Gemini REST: https://ai.google.dev/api/generate-content
- USDA API: https://fdc.nal.usda.gov/api-guide/
- Streamlit network configuration: https://docs.streamlit.io/develop/api-reference/configuration/config.toml
- Streamlit server architecture: https://docs.streamlit.io/develop/concepts/architecture/architecture
