# 🍷 SFL Points Tracker

This app tracks your chapter's **Florida Greek Standards: Student Life Initiatives** points
(UF Office of Sorority & Fraternity Life). It runs in a phone's web browser, and members can
add it to their home screen so it opens like a regular app.

It comes loaded with every Fall 2026 and Spring 2027 initiative from the OSFL sheet updated
10/11/2026. You can edit, add or cancel events from the Admin page whenever OSFL changes the sheet.

## What it does

| Page | Who | What |
|---|---|---|
| 🏠 Standing | everyone | Points out of the 70-point cap, points per semester, points still available, events coming up that need more people, no-show risk |
| 📅 Events | everyone | Each event shows its requirement and progress. Members can sign up, cancel (with a warning inside 48 hrs), tap "I attended", or log donated items |
| 🙋 Me | each member | Their own sign-ups, attendance and no-shows |
| 📊 Engagement | everyone | Leaderboard, a member × event grid, and a list of members who haven't engaged yet, by semester or for the whole year. Downloads as CSV |
| 🔐 Admin | you (PIN) | Verify attendance, add attendance from OSFL sign-in sheets, mark no-shows, edit events, manage the roster, change settings, back up and restore |

**How points are counted.** A member's tap on "I attended" only counts as self-reported.
Points count once an admin verifies the attendance. If OSFL awards a different number than the app
calculated, enter it in the **OSFL awarded** column of the Events editor and it will replace the calculation.
Chapters with more than 50 members use the "large chapter" minimums. The chapter size comes from the
active roster, or you can enter it yourself in Settings.

Requirement types: `members` (minimum headcount), `percent` (% of chapter), `items`
(donation drives), `tiered_percent` (e.g. Inauguration `25:10,50:15,75:20`), `tba`.

---

## 1. Try it on your laptop (5 min)

```bash
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501. The default admin PIN is `pibetaphi`. Change it right away in Admin → Settings.
For this test, data is saved in `data/sfl.db`.

## 2. Put it online so members can use it on their phones (free)

The app runs on **Streamlit Community Cloud**, which is free. That host erases its disk whenever the app restarts, so the data is kept in a **Google Sheet** instead. You can also open that sheet yourself to see the raw data.

**A. Create the Google Sheet + a service account (one time, about 10 min)**
1. Create a blank Google Sheet named "SFL Tracker Data" and copy its URL.
2. Go to https://console.cloud.google.com, create a project, and enable the **Google Sheets API** and the **Google Drive API**.
3. Go to IAM & Admin → Service Accounts → Create. Open the account, then Keys → Add key → JSON. A JSON file downloads.
4. Share the Google Sheet with the service account's `client_email` and give it **Editor** access.

**B. Deploy**
1. Upload this folder to a GitHub repo. Leave out `secrets.toml` and `data/`, which `.gitignore` already excludes.
2. Go to https://share.streamlit.io, choose New app, pick the repo, and set the main file to `app.py`.
3. Open App → Settings → **Secrets** and paste in the contents of `.streamlit/secrets.toml.example`.
   Fill in `sheet_url`, the fields from the JSON key under `[gcp_service_account]`, and an `admin_pin`.
4. Deploy. On first launch the app creates its tabs in the sheet (`events`, `members`, `signups`, `settings`)
   and fills in the events.

**C. Share it with the chapter**
- Send everyone the app URL. On iPhone: Safari → Share → **Add to Home Screen**. On Android: Chrome → ⋮ → **Add to Home screen**.
- Optional: in Admin → Settings, set a **member access code** so only your chapter can open the app.

## 3. First things to do as admin
1. **Roster**: paste every member's name, one per line, and choose *Add names*.
2. **Settings**: change the PIN. If the app's roster isn't your full chapter, enter the chapter size.
3. **Attendance**: for Fall events that already happened, choose the event, then *Add verified attendance*
   using OSFL's records. This brings your points up to date.
4. When OSFL updates the sheet, edit the **Events** tab: add a row, change the date or requirement, set the status
   to *Cancelled*, or enter *OSFL awarded* points.

## Notes
- If two admins edit the Events or Roster table at the same moment, the last save wins. Member sign-ups are
  saved one row at a time, so they don't overwrite each other.
- Members choose their own name, so there are no individual logins. Use the access code if you want the app kept private.
- Admin → Backup downloads all the data as CSV files.

## Files
`app.py` (the app) · `scoring.py` (points and requirement logic) · `storage.py` (SQLite or Google Sheet storage) ·
`seed_data.py` (OSFL event list, defaults) · `requirements.txt` · `.streamlit/` (theme and secrets template)
