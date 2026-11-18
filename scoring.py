"""Turns events + sign-ups into points, requirements and standing."""
from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

TZ = ZoneInfo("America/New_York")
LARGE_CHAPTER_THRESHOLD = 50  # OSFL: "> 50 members" is large


def now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def to_num(x, default=0.0) -> float:
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except ValueError:
        return default


def parse_dt(s):
    s = str(s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime().replace(tzinfo=None)
    except Exception:
        return None


def parse_tiers(s: str):
    tiers = []
    for part in str(s or "").split(","):
        if ":" in part:
            pct, pts = part.split(":", 1)
            tiers.append((to_num(pct), to_num(pts)))
    return sorted(tiers)


def is_large(size: int) -> bool:
    return size > LARGE_CHAPTER_THRESHOLD


def _fmt(n):
    n = float(n)
    return str(int(n)) if n.is_integer() else f"{n:g}"


def requirement_text(ev: dict, size: int) -> str:
    rt = ev["req_type"]
    large = is_large(size)
    lo = to_num(ev["min_large"] if large else ev["min_small"])
    if rt == "members":
        t = f"At least {_fmt(lo)} member{'s' if lo != 1 else ''}"
        if to_num(ev.get("max_attendees")):
            t += f" (no more than {_fmt(to_num(ev['max_attendees']))})"
        return t
    if rt == "percent":
        need = math.ceil(lo / 100 * size) if size else "?"
        return f"{_fmt(lo)}% of chapter ({need} members)"
    if rt == "items":
        return f"At least {_fmt(lo)} items donated"
    if rt == "tiered_percent":
        parts = [f"{_fmt(p)}% ({math.ceil(p / 100 * size) if size else '?'}) → {_fmt(pts)} pts"
                 for p, pts in parse_tiers(ev["tiers"])]
        return " · ".join(parts)
    return "TBA"


def event_counts(event_id: str, signups: pd.DataFrame) -> dict:
    s = signups[signups["event_id"] == event_id]
    active = s[s["status"].isin(["Signed Up", "Attended"])]
    attended = s[s["status"] == "Attended"]
    verified = attended[attended["verified"] == "True"]
    return {
        "signed_up": int(len(active)),
        "attended": int(len(attended)),
        "verified": int(len(verified)),
        "items_reported": int(sum(to_num(x) for x in attended["items"])),
        "items_verified": int(sum(to_num(x) for x in verified["items"])),
        "no_shows": int((s["status"] == "No-Show").sum()),
        "late_cancels": int(((s["status"] == "Cancelled") & (s["late_cancel"] == "True")).sum()),
    }


def evaluate(ev: dict, signups: pd.DataFrame, size: int) -> dict:
    """Points earned so far + what is still needed for one event."""
    c = event_counts(ev["id"], signups)
    rt = ev["req_type"]
    max_pts = to_num(ev["max_points"])
    large = is_large(size)
    lo = to_num(ev["min_large"] if large else ev["min_small"])

    if rt == "items":
        have, have_pending, need = c["items_verified"], c["items_reported"], lo
    else:
        have, have_pending = c["verified"], c["attended"]
        if rt == "members":
            need = lo
        elif rt == "percent":
            need = math.ceil(lo / 100 * size) if size else None
        elif rt == "tiered_percent":
            tiers = parse_tiers(ev["tiers"])
            need = math.ceil(tiers[0][0] / 100 * size) if (tiers and size) else None
        else:
            need = None

    # points earned
    points = 0.0
    if rt == "tiered_percent" and size:
        for pct, pts in parse_tiers(ev["tiers"]):
            if have >= math.ceil(pct / 100 * size):
                points = pts
        # next tier target
        nxt = [math.ceil(p / 100 * size) for p, _ in parse_tiers(ev["tiers"]) if have < math.ceil(p / 100 * size)]
        if points and nxt:
            need = nxt[0]
        elif points and not nxt:
            need = have
    elif need is not None and need > 0 and have >= need:
        points = max_pts

    confirmed = False
    if str(ev.get("awarded_override", "")).strip() != "":
        points = to_num(ev["awarded_override"])
        confirmed = True

    start = parse_dt(ev.get("start"))
    end = parse_dt(ev.get("end")) or start
    t = now()
    if ev.get("status") == "Cancelled":
        phase = "Cancelled"
    elif end and end < t:
        phase = "Past"
    elif start and start <= t:
        phase = "Happening"
    elif start:
        phase = "Upcoming"
    else:
        phase = "Date TBA"

    if confirmed:
        state = "✅ OSFL confirmed"
    elif phase == "Cancelled":
        state = "⛔ Cancelled"
    elif rt == "tba":
        state = "⏳ TBA"
    elif points >= max_pts and max_pts > 0:
        state = "✅ Met"
    elif points > 0:
        state = "🟡 Partial"
    elif phase == "Past":
        state = "🟠 Needs verifying" if have_pending > have else "❌ Missed"
    else:
        state = "🔵 Open"

    return {
        **c, "have": have, "have_pending": have_pending, "need": need, "points": points,
        "max_points": max_pts, "phase": phase, "state": state, "start_dt": start,
        "requirement": requirement_text(ev, size), "confirmed": confirmed,
    }


def standing(events: pd.DataFrame, signups: pd.DataFrame, size: int, cap: float) -> dict:
    rows = []
    for ev in events.to_dict("records"):
        r = evaluate(ev, signups, size)
        rows.append({**ev, **r})
    df = pd.DataFrame(rows)
    if df.empty:
        return {"table": df, "raw": 0, "total": 0, "by_sem": {}, "possible_left": 0}
    df["need"] = df["need"].astype(object).where(df["need"].notna(), None)
    df["start_dt"] = df["start_dt"].astype(object).where(df["start_dt"].notna(), None)
    raw = df["points"].sum()
    by_sem = df.groupby("semester")["points"].sum().to_dict()
    open_left = df[df["phase"].isin(["Upcoming", "Happening", "Date TBA"]) & (df["points"] < df["max_points"])]
    possible_left = float((open_left["max_points"] - open_left["points"]).sum())
    return {"table": df, "raw": raw, "total": min(raw, cap), "by_sem": by_sem,
            "possible_left": possible_left}
