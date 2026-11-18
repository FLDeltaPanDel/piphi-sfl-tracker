"""
Storage for the SFL tracker.

Two backends with the same interface:
  * SQLiteStore      – a local file (data/sfl.db). Great for testing or a host with a
                       persistent disk.
  * GoogleSheetStore – a Google Sheet. Use this when deploying to Streamlit Community
                       Cloud, whose disk is wiped on every restart. It's also handy:
                       you can open the sheet and see/edit everything directly.

Every value is stored as text; the app converts types when it loads a table.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from typing import Dict, List

import pandas as pd

TABLES: Dict[str, List[str]] = {
    "events": ["id", "semester", "name", "start", "end", "when", "max_points", "req_type",
               "min_large", "min_small", "tiers", "max_attendees", "link", "notes",
               "status", "awarded_override"],
    "members": ["name", "active", "email", "role"],
    "signups": ["id", "event_id", "member", "status", "items", "verified",
                "signed_up_at", "updated_at", "late_cancel", "note"],
    "settings": ["key", "value"],
}


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def _clean(df: pd.DataFrame, table: str) -> pd.DataFrame:
    cols = TABLES[table]
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols].fillna("").astype(str)
    df = df.replace({"nan": "", "None": "", "NaT": "", "<NA>": ""})
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- SQLite
class SQLiteStore:
    name = "Local file (SQLite)"

    def __init__(self, path: str = "data/sfl.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        with self._conn() as con:
            for t, cols in TABLES.items():
                col_sql = ", ".join(f'"{c}" TEXT' for c in cols)
                con.execute(f'CREATE TABLE IF NOT EXISTS "{t}" ({col_sql})')

    def _conn(self):
        return sqlite3.connect(self.path, timeout=10)

    def read(self, table: str) -> pd.DataFrame:
        with self._conn() as con:
            df = pd.read_sql(f'SELECT * FROM "{table}"', con)
        return _clean(df, table)

    def write(self, table: str, df: pd.DataFrame) -> None:
        df = _clean(df, table)
        cols = TABLES[table]
        with self._conn() as con:
            con.execute(f'DELETE FROM "{table}"')
            ph = ", ".join("?" for _ in cols)
            con.executemany(f'INSERT INTO "{table}" VALUES ({ph})', df.values.tolist())

    def append(self, table: str, row: dict) -> None:
        cols = TABLES[table]
        vals = [str(row.get(c, "") if row.get(c) is not None else "") for c in cols]
        with self._conn() as con:
            con.execute(f'INSERT INTO "{table}" VALUES ({", ".join("?" for _ in cols)})', vals)

    def update(self, table: str, key_col: str, key: str, changes: dict) -> None:
        if not changes:
            return
        sets = ", ".join(f'"{c}" = ?' for c in changes)
        with self._conn() as con:
            con.execute(f'UPDATE "{table}" SET {sets} WHERE "{key_col}" = ?',
                        [str(v) for v in changes.values()] + [str(key)])


# ---------------------------------------------------------------- Google Sheets
class GoogleSheetStore:
    name = "Google Sheet"

    def __init__(self, service_account_info: dict, sheet_url: str):
        import gspread  # imported here so local use doesn't need it

        gc = gspread.service_account_from_dict(dict(service_account_info))
        self.sh = gc.open_by_url(sheet_url) if sheet_url.startswith("http") else gc.open_by_key(sheet_url)
        existing = {ws.title: ws for ws in self.sh.worksheets()}
        self.ws = {}
        for t, cols in TABLES.items():
            ws = existing.get(t) or self.sh.add_worksheet(title=t, rows=200, cols=len(cols))
            if ws.row_values(1) != cols:
                if not ws.row_values(1):
                    ws.update([cols], "A1")
            self.ws[t] = ws

    def read(self, table: str) -> pd.DataFrame:
        values = self.ws[table].get_all_values()
        if not values:
            return _clean(pd.DataFrame(columns=TABLES[table]), table)
        header, rows = values[0], values[1:]
        return _clean(pd.DataFrame(rows, columns=header), table)

    def write(self, table: str, df: pd.DataFrame) -> None:
        df = _clean(df, table)
        ws = self.ws[table]
        ws.clear()
        ws.update([TABLES[table]] + df.values.tolist(), "A1")

    def append(self, table: str, row: dict) -> None:
        cols = TABLES[table]
        self.ws[table].append_row([str(row.get(c, "") or "") for c in cols],
                                  value_input_option="RAW")

    def update(self, table: str, key_col: str, key: str, changes: dict) -> None:
        ws = self.ws[table]
        cols = TABLES[table]
        keys = ws.col_values(cols.index(key_col) + 1)
        try:
            r = keys.index(str(key)) + 1
        except ValueError:
            return
        current = ws.row_values(r) + [""] * (len(cols) - len(ws.row_values(r)))
        for c, v in changes.items():
            current[cols.index(c)] = str(v)
        ws.update([current[: len(cols)]], f"A{r}", value_input_option="RAW")
