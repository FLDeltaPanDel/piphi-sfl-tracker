"""
SFL Points Tracker — Florida Greek Standards: Student Life Initiatives
Run locally:   streamlit run app.py
"""
from __future__ import annotations

import io
import zipfile
from datetime import timedelta

import pandas as pd
import streamlit as st

import scoring as sc
from seed_data import DEFAULT_SETTINGS, SEED_EVENTS
from storage import TABLES, GoogleSheetStore, SQLiteStore, new_id

st.set_page_config(page_title="SFL Points Tracker", page_icon="🍷", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .block-container {padding-top: 1.2rem; padding-bottom: 4rem;}
  div[data-testid="stMetricValue"] {font-size: 1.6rem;}
  .small {font-size: .85rem; opacity: .75;}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ storage
def _secret(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


@st.cache_resource
def get_store():
    sa, url = _secret("gcp_service_account"), _secret("sheet_url")
    if sa and url:
        return GoogleSheetStore(sa, url)
    return SQLiteStore(_secret("db_path", "data/sfl.db"))


store = get_store()


@st.cache_data(ttl=15, show_spinner=False)
def _read(table: str) -> pd.DataFrame:
    return store.read(table)


def read(table):
    return _read(table).copy()


def changed():
    _read.clear()


def seed_if_empty():
    if read("events").empty:
        df = pd.DataFrame(SEED_EVENTS)
        df.insert(0, "id", [new_id() for _ in range(len(df))])
        store.write("events", df)
    s = read("settings")
    missing = {k: v for k, v in DEFAULT_SETTINGS.items() if k not in set(s["key"])}
    for k, v in missing.items():
        store.append("settings", {"key": k, "value": v})
    changed()


seed_if_empty()


def settings() -> dict:
    s = read("settings")
    d = dict(DEFAULT_SETTINGS)
    d.update(dict(zip(s["key"], s["value"])))
    return d


def save_setting(key, value):
    if key in set(read("settings")["key"]):
        store.update("settings", "key", key, {"value": value})
    else:
        store.append("settings", {"key": key, "value": value})
    changed()


S = settings()
members = read("members")
active_members = sorted(members[members["active"] != "False"]["name"].tolist(), key=str.lower)
events = read("events")
signups = read("signups")
size_override = int(sc.to_num(S["chapter_size_override"]))
CHAPTER_SIZE = size_override or len(active_members)
CAP = sc.to_num(S["points_cap"], 70)
stand = sc.standing(events, signups, CHAPTER_SIZE, CAP)
T = stand["table"]

# ------------------------------------------------------------------ access gate
if S.get("access_code") and not st.session_state.get("in"):
    st.title("🍷 SFL Points Tracker")
    code = st.text_input("Chapter access code", type="password")
    if st.button("Enter", type="primary"):
        if code == S["access_code"]:
            st.session_state["in"] = True
            st.rerun()
        st.error("That code isn't right — ask your Panhellenic delegate.")
    st.stop()

# ------------------------------------------------------------------ helpers
def fmt_date(dt):
    if dt is None or pd.isna(dt):
        return "TBA"
    return dt.strftime("%a %b %-d") + ("" if dt.strftime("%H:%M") == "00:00" else dt.strftime(", %-I:%M%p").lower())


def my_signup(event_id, name):
    m = signups[(signups["event_id"] == event_id) & (signups["member"] == name)]
    return m.iloc[-1].to_dict() if len(m) else None


def upsert_signup(event_id, name, **changes):
    existing = my_signup(event_id, name)
    stamp = sc.now().strftime("%Y-%m-%d %H:%M")
    if existing:
        store.update("signups", "id", existing["id"], {**changes, "updated_at": stamp})
    else:
        row = {"id": new_id(), "event_id": event_id, "member": name, "status": "Signed Up",
               "items": "", "verified": "False", "signed_up_at": stamp, "updated_at": stamp,
               "late_cancel": "False", "note": ""}
        row.update(changes)
        store.append("signups", row)
    changed()


def semesters():
    order = list(dict.fromkeys(events["semester"].tolist()))
    return order or ["Fall 2026", "Spring 2027"]


def tier_label():
    return f"{'Large' if sc.is_large(CHAPTER_SIZE) else 'Small'} chapter (" \
           f"{'>' if sc.is_large(CHAPTER_SIZE) else '≤'}50 members)"


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown(f"### 🍷 {S['chapter_name']}")
    st.caption(f"Data stored in: {store.name}")

# tap-friendly nav across the top (works well on phones)
PAGES = ["🏠 Standing", "📅 Events", "🙋 Me", "📊 Engagement", "🔐 Admin"]
page = st.segmented_control("Page", PAGES, default=PAGES[0], label_visibility="collapsed",
                            key="topnav") or PAGES[0]

who = st.session_state.get("who")


def pick_me(container=st):
    global who
    if not active_members:
        container.info("No roster yet — an admin needs to add members (Admin → Roster).")
        return None
    idx = active_members.index(who) if who in active_members else None
    who = container.selectbox("Who are you?", active_members, index=idx, placeholder="Pick your name")
    st.session_state["who"] = who
    return who


# ================================================================== STANDING
if page == "🏠 Standing":
    st.title("SFL Standing")
    st.caption(f"Florida Greek Standards · Student Life Initiatives · {tier_label()} · size used: "
               f"{CHAPTER_SIZE}{' (override)' if size_override else ''}")

    if CHAPTER_SIZE == 0:
        st.warning("Add your roster (Admin → Roster) or set the chapter size (Admin → Settings) "
                   "so percent-based requirements can be calculated.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Points (capped)", f"{sc._fmt(stand['total'])} / {sc._fmt(CAP)}")
    c2.metric("Still available", sc._fmt(stand["possible_left"]))
    c3.metric("Raw total", sc._fmt(stand["raw"]), help="Before the cap is applied.")
    st.progress(min(1.0, stand["total"] / CAP if CAP else 0))

    sems = semesters()
    cols = st.columns(len(sems))
    for col, sem in zip(cols, sems):
        col.metric(sem, f"{sc._fmt(stand['by_sem'].get(sem, 0))} pts")

    # ---- alerts
    if not T.empty:
        soon = T[(T["phase"].isin(["Upcoming", "Happening"])) & (T["state"] != "✅ Met")]
        soon = soon[soon["start_dt"].notna()]
        soon = soon[soon["start_dt"] <= sc.now() + timedelta(days=21)].sort_values("start_dt")
        if len(soon):
            st.subheader("⚠️ Coming up")
            for r in soon.to_dict("records"):
                need = r["need"] if r["need"] is not None else "?"
                short = (need - r["signed_up"]) if isinstance(need, (int, float)) else None
                hrs = (r["start_dt"] - sc.now()).total_seconds() / 3600
                msg = f"**{r['name']}** — {fmt_date(r['start_dt'])} · {r['signed_up']} signed up, need {need}"
                if short and short > 0:
                    msg += f" · **{int(short)} more needed**"
                if 0 < hrs < 48:
                    msg += " · ⏰ inside the 48-hr no-show window"
                (st.error if short and short > 0 else st.info)(msg)

        pen = T[(T["no_shows"] > 0) | (T["late_cancels"] > 0)]
        if len(pen):
            st.subheader("🚩 No-show risk")
            st.caption("OSFL penalizes members who are registered and don't show without 48 hrs notice.")
            st.dataframe(pen[["name", "no_shows", "late_cancels"]].rename(
                columns={"name": "Event", "no_shows": "No-shows", "late_cancels": "Late cancels"}),
                hide_index=True, width="stretch")

        verify = T[T["have_pending"] > T["have"]]
        if len(verify):
            st.info(f"📝 {len(verify)} event(s) have self-reported attendance waiting for an admin to "
                    "verify (Admin → Attendance). Points only count once verified.")

    # ---- per-semester tables
    for sem in sems:
        st.subheader(sem)
        d = T[T["semester"] == sem].copy()
        if d.empty:
            st.caption("No events yet.")
            continue
        d = d.sort_values("start_dt", na_position="last")
        d["Date"] = d["start_dt"].apply(fmt_date)
        d["Progress"] = d.apply(lambda r: f"{r['have']}" + (f" / {r['need']}" if r["need"] is not None else "")
                                + ("" if r["req_type"] != "items" else " items"), axis=1)
        d["Points"] = d.apply(lambda r: f"{sc._fmt(r['points'])} / {sc._fmt(r['max_points'])}", axis=1)
        st.dataframe(d[["state", "name", "Date", "Progress", "Points"]].rename(
            columns={"state": "Status", "name": "Event"}), hide_index=True, width="stretch")
    st.caption("Progress counts verified attendance only. Points cap: "
               f"{sc._fmt(CAP)} for the year (edit in Admin → Settings).")


# ================================================================== EVENTS
elif page == "📅 Events":
    st.title("Events")
    me = pick_me()
    view = st.segmented_control("Show", ["Upcoming", *semesters(), "All"], default="Upcoming",
                                key="evview") or "Upcoming"
    d = T.copy()
    if view == "Upcoming":
        d = d[d["phase"].isin(["Upcoming", "Happening", "Date TBA"])]
    elif view != "All":
        d = d[d["semester"] == view]
    d = d.sort_values("start_dt", na_position="last")
    if d.empty:
        st.info("Nothing here yet.")

    for r in d.to_dict("records"):
        title = f"{r['state'].split(' ')[0]} {fmt_date(r['start_dt'])} · {r['name']} · {sc._fmt(r['max_points'])} pts"
        with st.expander(title):
            st.markdown(f"**When:** {r['when'] or fmt_date(r['start_dt'])}  \n"
                        f"**Requirement:** {r['requirement']}  \n"
                        f"**Points earned:** {sc._fmt(r['points'])} / {sc._fmt(r['max_points'])}")
            if r["notes"]:
                st.caption(r["notes"])
            if r["link"]:
                st.link_button("Official registration / sign-up ↗", r["link"])

            need = r["need"]
            if r["req_type"] == "items":
                st.write(f"🧺 **{r['items_verified']}** verified items · {r['items_reported']} reported"
                         + (f" · goal {int(need)}" if need else ""))
            else:
                st.write(f"👥 **{r['signed_up']}** signed up · {r['attended']} attended · "
                         f"**{r['verified']}** verified" + (f" · need {int(need)}" if need else ""))
            if need:
                st.progress(min(1.0, r["have"] / need))

            going = signups[(signups["event_id"] == r["id"]) & signups["status"].isin(["Signed Up", "Attended"])]
            if len(going):
                st.caption("Going / went: " + ", ".join(sorted(going["member"].tolist())))

            if r["phase"] == "Cancelled" or r["req_type"] == "tba":
                continue
            if not me:
                st.caption("Pick your name at the top to sign up.")
                continue

            mine = my_signup(r["id"], me)
            status = mine["status"] if mine else None
            k = r["id"]
            hrs_left = (r["start_dt"] - sc.now()).total_seconds() / 3600 if r["start_dt"] is not None and not pd.isna(r["start_dt"]) else None

            if r["req_type"] == "items":
                n = st.number_input("Items you donated", min_value=1, step=1, key=f"it{k}")
                if st.button("Log my donation", key=f"don{k}", type="primary"):
                    store.append("signups", {"id": new_id(), "event_id": k, "member": me, "status": "Attended",
                                             "items": int(n), "verified": "False",
                                             "signed_up_at": sc.now().strftime("%Y-%m-%d %H:%M"),
                                             "updated_at": sc.now().strftime("%Y-%m-%d %H:%M"),
                                             "late_cancel": "False", "note": ""})
                    changed(); st.toast("Donation logged — thank you!"); st.rerun()
                continue

            st.write(f"Your status: **{status or 'Not signed up'}**"
                     + (" ✔️ verified" if mine and mine["verified"] == "True" else ""))
            b1, b2, b3 = st.columns(3)
            cap_full = sc.to_num(r["max_attendees"]) and r["signed_up"] >= sc.to_num(r["max_attendees"])
            if status in (None, "Cancelled") and r["phase"] != "Past":
                if cap_full:
                    b1.warning("Spots full")
                elif b1.button("Sign me up", key=f"su{k}", type="primary"):
                    upsert_signup(k, me, status="Signed Up", late_cancel="False")
                    st.toast("You're signed up! Don't forget the official registration link.")
                    st.rerun()
            if status == "Signed Up":
                if b2.button("Cancel", key=f"cx{k}"):
                    late = hrs_left is not None and hrs_left < 48
                    upsert_signup(k, me, status="Cancelled", late_cancel=str(late))
                    if late:
                        st.warning("This is inside 48 hours — tell your delegate right away so OSFL "
                                   "doesn't count a no-show.")
                    st.rerun()
            if status in (None, "Signed Up", "Cancelled") and (r["phase"] in ("Past", "Happening")
                                                               or (hrs_left is not None and hrs_left < 24)):
                if b3.button("I attended", key=f"at{k}"):
                    upsert_signup(k, me, status="Attended", verified="False")
                    st.toast("Logged! An admin will verify it."); st.rerun()


# ================================================================== ME
elif page == "🙋 Me":
    st.title("My engagement")
    me = pick_me()
    if me:
        mine = signups[signups["member"] == me].merge(
            events[["id", "name", "semester", "max_points"]], left_on="event_id", right_on="id", how="left")
        att = mine[mine["status"] == "Attended"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Events attended", int(att["event_id"].nunique()))
        c2.metric("Verified", int(att[att["verified"] == "True"]["event_id"].nunique()))
        c3.metric("No-shows", int((mine["status"] == "No-Show").sum()))
        if mine.empty:
            st.info("You haven't signed up for anything yet — check the Events tab!")
        else:
            show = mine[["semester", "name", "status", "verified", "items"]].rename(columns={
                "semester": "Semester", "name": "Event", "status": "Status", "verified": "Verified",
                "items": "Items"})
            show["Verified"] = show["Verified"].map({"True": "✔️"}).fillna("")
            st.dataframe(show, hide_index=True, width="stretch")


# ================================================================== ENGAGEMENT
elif page == "📊 Engagement":
    st.title("Chapter engagement")
    sem = st.segmented_control("Semester", [*semesters(), "Whole year"],
                               default=semesters()[-1], key="engsem") or semesters()[-1]
    ev = events if sem == "Whole year" else events[events["semester"] == sem]
    su = signups[signups["event_id"].isin(ev["id"])]

    tsem = T[T["id"].isin(ev["id"])] if not T.empty else T
    c1, c2, c3 = st.columns(3)
    c1.metric("Points", sc._fmt(tsem["points"].sum() if len(tsem) else 0))
    c2.metric("Events met", f"{int((tsem['state'].str.startswith('✅')).sum()) if len(tsem) else 0} / {len(tsem)}")
    engaged = su[su["status"] == "Attended"]["member"].nunique()
    c3.metric("Members engaged", f"{engaged} / {len(active_members)}")

    if not active_members:
        st.info("Add your roster in Admin → Roster to see member engagement.")
    else:
        rows = []
        for m in active_members:
            s = su[su["member"] == m]
            att = s[s["status"] == "Attended"]
            rows.append({"Member": m,
                         "Attended": int(att["event_id"].nunique()),
                         "Verified": int(att[att["verified"] == "True"]["event_id"].nunique()),
                         "Signed up": int((s["status"] == "Signed Up").sum()),
                         "No-shows": int((s["status"] == "No-Show").sum()),
                         "Late cancels": int(((s["status"] == "Cancelled") & (s["late_cancel"] == "True")).sum()),
                         "Items": int(sum(sc.to_num(x) for x in att["items"]))})
        board = pd.DataFrame(rows).sort_values(["Verified", "Attended"], ascending=False)
        st.subheader("Leaderboard")
        st.dataframe(board, hide_index=True, width="stretch")

        zero = board[board["Attended"] == 0]["Member"].tolist()
        if zero:
            with st.expander(f"Not engaged yet this {('year' if sem == 'Whole year' else 'semester')} ({len(zero)})"):
                st.write(", ".join(zero))

        st.subheader("Member × event grid")
        st.caption("✅ verified · 📝 self-reported · 🗓️ signed up · ❌ no-show · ↩️ cancelled")
        sym = {"Signed Up": "🗓️", "No-Show": "❌", "Cancelled": "↩️"}
        evs = ev.copy()
        evs["dt"] = evs["start"].apply(sc.parse_dt)
        evs = evs.sort_values("dt", na_position="last")
        grid = pd.DataFrame(index=active_members, columns=evs["name"].tolist()).fillna("")
        name_of = dict(zip(evs["id"], evs["name"]))
        for s in su.to_dict("records"):
            if s["member"] in grid.index and s["event_id"] in name_of:
                v = ("✅" if s["verified"] == "True" else "📝") if s["status"] == "Attended" else sym.get(s["status"], "")
                grid.loc[s["member"], name_of[s["event_id"]]] = v
        st.dataframe(grid, width="stretch")
        st.download_button("Download engagement (CSV)", board.to_csv(index=False).encode(),
                           file_name=f"engagement_{sem.replace(' ', '_')}.csv", mime="text/csv")


# ================================================================== ADMIN
elif page == "🔐 Admin":
    st.title("Admin")
    pin = _secret("admin_pin") or S["admin_pin"]
    if not st.session_state.get("admin"):
        p = st.text_input("Admin PIN", type="password")
        if st.button("Unlock", type="primary"):
            if p == str(pin):
                st.session_state["admin"] = True
                st.rerun()
            st.error("Wrong PIN.")
        st.stop()
    if pin == DEFAULT_SETTINGS["admin_pin"] and not _secret("admin_pin"):
        st.warning("You're still using the default admin PIN — change it in the Settings tab.")

    t1, t2, t3, t4, t5 = st.tabs(["Attendance", "Events", "Roster", "Settings", "Backup"])

    # ---------------- Attendance
    with t1:
        opts = T.sort_values("start_dt", na_position="last") if not T.empty else T
        labels = {r["id"]: f"{fmt_date(r['start_dt'])} · {r['name']}" for r in opts.to_dict("records")}
        eid = st.selectbox("Event", list(labels), format_func=labels.get)
        if eid:
            ev_row = T[T["id"] == eid].iloc[0]
            st.caption(f"{ev_row['requirement']} · currently {ev_row['state']}")
            s = signups[signups["event_id"] == eid].copy()
            s["verified"] = s["verified"] == "True"
            s["items"] = pd.to_numeric(s["items"], errors="coerce")
            edited = st.data_editor(
                s[["id", "member", "status", "verified", "items", "note"]],
                column_config={
                    "id": None,
                    "member": st.column_config.TextColumn("Member", disabled=True),
                    "status": st.column_config.SelectboxColumn(
                        "Status", options=["Signed Up", "Attended", "No-Show", "Cancelled"], required=True),
                    "verified": st.column_config.CheckboxColumn("Verified"),
                    "items": st.column_config.NumberColumn("Items", min_value=0, step=1),
                    "note": st.column_config.TextColumn("Note"),
                }, hide_index=True, width="stretch", key=f"ed{eid}")
            c1, c2 = st.columns(2)
            if c1.button("Save changes", type="primary"):
                orig = s.set_index("id")
                for r in edited.to_dict("records"):
                    o = orig.loc[r["id"]]
                    ch = {}
                    for col in ("status", "note"):
                        if str(r[col] or "") != str(o[col] or ""):
                            ch[col] = r[col] or ""
                    if bool(r["verified"]) != bool(o["verified"]):
                        ch["verified"] = str(bool(r["verified"]))
                    ri = "" if pd.isna(r["items"]) else int(r["items"])
                    oi = "" if pd.isna(o["items"]) else int(o["items"])
                    if ri != oi:
                        ch["items"] = ri
                    if ch:
                        store.update("signups", "id", r["id"], ch)
                changed(); st.success("Saved."); st.rerun()
            if c2.button("Verify everyone marked Attended"):
                for r in s[(s["status"] == "Attended") & (~s["verified"])].to_dict("records"):
                    store.update("signups", "id", r["id"], {"verified": "True"})
                changed(); st.rerun()
            if ev_row["phase"] == "Past" and (s["status"] == "Signed Up").any():
                if st.button("Mark remaining 'Signed Up' as No-Show"):
                    for r in s[s["status"] == "Signed Up"].to_dict("records"):
                        store.update("signups", "id", r["id"], {"status": "No-Show"})
                    changed(); st.rerun()

            st.markdown("**Add verified attendance** (e.g. from the OSFL sign-in sheet)")
            already = set(s[s["status"] == "Attended"]["member"])
            add = st.multiselect("Members", [m for m in active_members if m not in already], key=f"add{eid}")
            items = 0
            if ev_row["req_type"] == "items":
                items = st.number_input("Items each", min_value=0, step=1, key=f"addit{eid}")
            if st.button("Add as attended + verified", disabled=not add):
                for m in add:
                    upsert_signup(eid, m, status="Attended", verified="True", items=items or "")
                    signups = read("signups")
                st.rerun()

    # ---------------- Events
    with t2:
        st.caption("Edit any cell, add a row at the bottom, or select rows and press Delete. "
                   "Dates: YYYY-MM-DD HH:MM. Use 'OSFL awarded' to enter the points OSFL actually "
                   "gave — it overrides the calculation.")
        e = events.copy()
        for c in ("max_points", "min_large", "min_small", "max_attendees", "awarded_override"):
            e[c] = pd.to_numeric(e[c], errors="coerce")
        edited = st.data_editor(
            e, num_rows="dynamic", hide_index=True, width="stretch", key="evedit",
            column_order=["semester", "name", "start", "end", "when", "max_points", "req_type",
                          "min_large", "min_small", "tiers", "max_attendees", "status",
                          "awarded_override", "link", "notes"],
            column_config={
                "semester": st.column_config.SelectboxColumn(
                    "Semester", options=sorted(set(semesters()) | {"Fall 2026", "Spring 2027", "Fall 2027"}),
                    required=True),
                "name": st.column_config.TextColumn("Event", required=True, width="medium"),
                "start": st.column_config.TextColumn("Start", help="YYYY-MM-DD HH:MM (blank = TBA)"),
                "end": st.column_config.TextColumn("End", help="Only for multi-day windows"),
                "when": st.column_config.TextColumn("When (display)"),
                "max_points": st.column_config.NumberColumn("Max pts", min_value=0, step=1),
                "req_type": st.column_config.SelectboxColumn(
                    "Requirement", options=["members", "percent", "items", "tiered_percent", "tba"], required=True),
                "min_large": st.column_config.NumberColumn("Min (>50)", help="members / % / items"),
                "min_small": st.column_config.NumberColumn("Min (≤50)"),
                "tiers": st.column_config.TextColumn("Tiers", help="e.g. 25:10,50:15,75:20"),
                "max_attendees": st.column_config.NumberColumn("Max sent"),
                "status": st.column_config.SelectboxColumn("Status", options=["Open", "Cancelled"]),
                "awarded_override": st.column_config.NumberColumn("OSFL awarded"),
                "link": st.column_config.LinkColumn("Link"),
                "notes": st.column_config.TextColumn("Notes"),
            })
        if st.button("Save events", type="primary"):
            out = edited.copy()
            out["id"] = [i if isinstance(i, str) and i else new_id() for i in out.get("id", [""] * len(out))]
            out["status"] = out["status"].fillna("Open").replace("", "Open")
            for c in ("max_points", "min_large", "min_small", "max_attendees", "awarded_override"):
                out[c] = out[c].apply(lambda v: "" if pd.isna(v) else sc._fmt(v))
            out = out[out["name"].astype(str).str.strip() != ""]
            store.write("events", out)
            changed(); st.success("Events saved."); st.rerun()
        with st.expander("Reset events to the official FGS sheet"):
            st.write("Replaces ALL events with the 10/11/2026 OSFL list. Sign-ups for events that no "
                     "longer exist will stop counting.")
            if st.checkbox("I understand") and st.button("Reset events"):
                df = pd.DataFrame(SEED_EVENTS)
                df.insert(0, "id", [new_id() for _ in range(len(df))])
                store.write("events", df)
                changed(); st.rerun()

    # ---------------- Roster
    with t3:
        st.caption(f"{len(active_members)} active members. Uncheck 'active' instead of deleting "
                   "so history is kept.")
        m = members.copy()
        m["active"] = m["active"] != "False"
        ed = st.data_editor(m, num_rows="dynamic", hide_index=True, width="stretch", key="rosted",
                            column_config={"name": st.column_config.TextColumn("Name", required=True),
                                           "active": st.column_config.CheckboxColumn("Active", default=True),
                                           "email": st.column_config.TextColumn("Email"),
                                           "role": st.column_config.TextColumn("Role")})
        if st.button("Save roster", type="primary"):
            ed = ed[ed["name"].astype(str).str.strip() != ""].copy()
            ed["name"] = ed["name"].str.strip()
            ed = ed.drop_duplicates("name")
            ed["active"] = ed["active"].fillna(True).astype(bool).astype(str)
            store.write("members", ed)
            changed(); st.success("Roster saved."); st.rerun()

        st.markdown("**Bulk add** — paste names, one per line (e.g. straight from a spreadsheet column)")
        txt = st.text_area("Names", height=150, label_visibility="collapsed")
        if st.button("Add names"):
            existing = set(members["name"])
            new = [n.strip() for n in txt.splitlines() if n.strip() and n.strip() not in existing]
            for n in dict.fromkeys(new):
                store.append("members", {"name": n, "active": "True", "email": "", "role": ""})
            changed(); st.success(f"Added {len(new)} members."); st.rerun()

    # ---------------- Settings
    with t4:
        with st.form("settings"):
            name = st.text_input("Chapter name", S["chapter_name"])
            size = st.number_input("Chapter size override (0 = count active roster)", min_value=0, step=1,
                                   value=size_override,
                                   help="OSFL thresholds use total chapter size. Set this if your roster "
                                        "in the app isn't complete.")
            cap = st.number_input("Points cap for Student Life Initiatives", min_value=0, step=5, value=int(CAP))
            code = st.text_input("Member access code (blank = no code)", S["access_code"])
            newpin = st.text_input("New admin PIN (blank = keep)", type="password")
            if st.form_submit_button("Save settings", type="primary"):
                save_setting("chapter_name", name)
                save_setting("chapter_size_override", str(int(size)) if size else "")
                save_setting("points_cap", str(int(cap)))
                save_setting("access_code", code)
                if newpin:
                    save_setting("admin_pin", newpin)
                st.success("Saved."); st.rerun()
        if _secret("admin_pin"):
            st.caption("Admin PIN is set in the app secrets, so it overrides the one here.")

    # ---------------- Backup
    with t5:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for t in TABLES:
                z.writestr(f"{t}.csv", read(t).to_csv(index=False))
        st.download_button("Download full backup (.zip of CSVs)", buf.getvalue(),
                           file_name=f"sfl_backup_{sc.now():%Y%m%d}.zip", mime="application/zip")
        st.markdown("**Restore one table from CSV**")
        tbl = st.selectbox("Table", list(TABLES))
        up = st.file_uploader("CSV", type="csv")
        if up and st.button(f"Replace '{tbl}' with this file"):
            store.write(tbl, pd.read_csv(up, dtype=str).fillna(""))
            changed(); st.success("Restored."); st.rerun()
        if st.button("Log out of admin"):
            st.session_state["admin"] = False
            st.rerun()
