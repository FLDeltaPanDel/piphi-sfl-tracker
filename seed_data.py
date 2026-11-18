"""
Events from the 2026-2027 Florida Greek Standards — Student Life Initiatives sheet
(UF Office of Sorority & Fraternity Life, last updated 10/11/2026).

These are only the starting data. Everything here can be edited, added to or
deleted from the Admin page of the app as OSFL updates the sheet.

req_type values
  members        -> chapter must send at least min_large / min_small members
  percent        -> at least min_large / min_small PERCENT of the chapter
  items          -> chapter must donate at least min_large / min_small items
  tiered_percent -> points depend on % of chapter attending (tiers = "pct:points,...")
  tba            -> requirement / points not announced yet

"Large" = chapter with more than 50 members, "small" = 50 or fewer
(you can override the size in Admin > Settings).
"""

FALL = "Fall 2026"
SPRING = "Spring 2027"

SURVEY = "https://ufl.qualtrics.com/jfe/form/SV_agcFuuJx6z3L2Gq"


def _e(semester, name, start, when, pts, req, large=0, small=0, *, end="", tiers="",
       max_att="", link="", notes=""):
    return {
        "semester": semester, "name": name, "start": start, "end": end, "when": when,
        "max_points": pts, "req_type": req, "min_large": large, "min_small": small,
        "tiers": tiers, "max_attendees": max_att, "link": link, "notes": notes,
        "status": "Open", "awarded_override": "",
    }


SEED_EVENTS = [
    # ---------------- FALL 2026 ----------------
    _e(FALL, "SFL Experiential Learning Survey Completion", "2026-08-03 00:00", "Open Aug 3 – Sep 18",
       10, "percent", 25, 50, end="2026-09-18 23:59", link=SURVEY,
       notes="Log each member who completed the survey as 'Attended'."),
    _e(FALL, "Housing Move-In", "2026-08-15 08:00", "Aug 15 & 16", 10, "members", 10, 5,
       end="2026-08-16 18:00", link="https://ufl.qualtrics.com/jfe/form/SV_9pruhQPtoIkSxKe"),
    _e(FALL, "Class Photo Florida Legacy Line Staffing", "2026-08-19 18:15", "8/19 6:15–8pm", 5, "members", 5, 2,
       link="https://ufl.qualtrics.com/jfe/form/SV_ePOo3Zon9MkVPj8"),
    _e(FALL, "Gator Day of Service", "2026-09-11 08:00", "Fri 9/11", 5, "members", 5, 2,
       link="https://givepul.se/wmi6ua"),
    _e(FALL, "NHPW: Museum Attendance", "2026-09-21 09:00", "Any time 9/21–9/25, 9am–5pm", 15, "percent", 20, 20,
       end="2026-09-25 17:00"),
    _e(FALL, "NHPW: Mocha Monday", "2026-09-21 09:00", "9/21 9–11am", 5, "members", 5, 2),
    _e(FALL, "NHPW: Escape Room", "2026-09-21 16:00", "9/21 4–8pm", 5, "members", 5, 2,
       notes="Registration TBA on the OSFL sheet."),
    _e(FALL, "NHPW: Lunch & Learn", "2026-09-22 12:00", "9/22 12–1:30pm", 5, "members", 5, 2),
    _e(FALL, "NHPW: Bingo Night", "2026-09-23 14:00", "9/23 2–4pm", 10, "members", 10, 5),
    _e(FALL, "NHPW: Bracelet Making", "2026-09-23 16:00", "9/23 4–8pm", 5, "members", 5, 2),
    _e(FALL, "NHPW: Campus Partner Tabling Fair", "2026-09-24 11:00", "9/24 11am–1pm", 10, "members", 10, 5),
    _e(FALL, "NHPW: Coffee w/ a Cop", "2026-09-25 09:00", "9/25 9–11am", 5, "members", 5, 2),
    _e(FALL, "MDS: HiPer Gator Facility Tour", "2026-10-15 12:30", "10/15 12:30–2pm", 10, "members", 1, 1,
       max_att=1, link="https://givepul.se/puu56y",
       notes="Limited capacity — send no more than 1 member."),
    _e(FALL, "SFL/FGA Safety Isn't Scary Haunted House", "2026-10-18 19:00", "Sun 10/18 7–10pm @ Phi Kappa Tau",
       10, "members", 5, 2),
    _e(FALL, "DRC Accessible Day at the Lake", "2026-10-21 11:00", "10/21 11am–3pm", 10, "members", 5, 2),
    _e(FALL, "MDS: Life After College Workshop", "2026-10-21 14:00", "10/21 2–3pm", 5, "members", 5, 2,
       link="https://givepul.se/pp1t4a"),
    _e(FALL, "UF Greeks x UF Women's Soccer v. Auburn", "2026-10-22 19:00", "Thu 10/22 @ 7pm", 10, "members", 10, 5),
    _e(FALL, "GatorWell Monster Mash", "2026-10-27 16:00", "10/27 4–7pm, Reitz Tabling Area", 5, "members", 5, 2),
    _e(FALL, "All Greeks Day of Service — Volunteering", "2026-10-29 08:00", "10/29", 10, "members", 5, 2,
       link="https://givepul.se/ua8ji6"),
    _e(FALL, "All Greeks Day of Service — Clothing Drive", "2026-10-26 08:00", "10/26–10/29", 5, "items", 50, 25,
       end="2026-10-29 23:59"),
    _e(FALL, "MDS: Plan It. Build It. Bring It to Life.", "2026-11-12 13:00", "Thu 11/12 1–2pm", 5, "members", 5, 2,
       link="https://givepul.se/dvpu8d"),
    _e(FALL, "Presidential Inauguration Student Event", "2026-11-20 13:00", "Fri 11/20 1–3pm, Reitz Union North Lawn",
       20, "tiered_percent", tiers="25:10,50:15,75:20",
       notes="10 pts for 25% of members, 15 pts for 50%, 20 pts for 75%."),
    _e(FALL, "Chop & Chomp Food Drive vs. FSU", "", "Date TBA", 5, "items", 50, 25),

    # ---------------- SPRING 2027 ----------------
    _e(SPRING, "MLK Service Day", "2027-01-18 08:00", "Mon Jan 18, 2027", 15, "members", 5, 2,
       notes="Registration TBA."),
    _e(SPRING, "Career Showcase Volunteering", "", "Date TBA", 5, "members", 5, 2,
       notes="Registration TBA."),
    _e(SPRING, "Mocktail Mania", "", "TBA", 0, "tba",
       notes="Events and points TBA — update when OSFL posts details."),
]

DEFAULT_SETTINGS = {
    "chapter_name": "Pi Beta Phi",
    "chapter_size_override": "",   # blank = count active members on the roster
    "points_cap": "70",
    "admin_pin": "pibetaphi",      # change this on first login (or set admin_pin in secrets)
    "access_code": "",             # optional code members must enter to open the app
}
