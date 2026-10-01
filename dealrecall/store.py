"""Local CRM ledger. Hindsight is what the agent remembers; this is what the rep sees."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from dealrecall.seed import COMMITMENTS, DEALS, INTERACTIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    stage TEXT NOT NULL,
    value_inr INTEGER NOT NULL,
    segment TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY,
    document_id TEXT UNIQUE,
    deal_slug TEXT NOT NULL,
    happened_on TEXT NOT NULL,
    contact TEXT,
    type TEXT,
    notes TEXT,
    outcome TEXT,
    tactic TEXT,
    result TEXT,
    retained INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS commitments (
    id INTEGER PRIMARY KEY,
    deal_slug TEXT NOT NULL,
    what TEXT NOT NULL,
    who TEXT NOT NULL,
    due_on TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS approval_sessions (
    id TEXT PRIMARY KEY,
    deal_slug TEXT,
    deal_name TEXT,
    operation_type TEXT NOT NULL,
    requesting_user TEXT NOT NULL,
    required_second_user TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    user_a_salt TEXT,
    user_a_hash TEXT,
    user_a_verified INTEGER NOT NULL DEFAULT 0,
    user_b_salt TEXT,
    user_b_hash TEXT,
    user_b_verified INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    payload_json TEXT NOT NULL,
    committed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id TEXT NOT NULL,
    deal_slug TEXT,
    deal_name TEXT,
    operation TEXT NOT NULL,
    requesting_user TEXT NOT NULL,
    approving_user TEXT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT
);
"""


def slugify(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "deal"


def format_inr(value: int) -> str:
    lakhs = value / 100_000
    if lakhs >= 1 and value % 100_000 == 0:
        return f"Rs {lakhs:.0f}L"
    if lakhs >= 1:
        return f"Rs {lakhs:.1f}L"
    return f"Rs {value:,}"


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            self._seed_crm(conn)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _seed_crm(self, conn: sqlite3.Connection) -> None:
        count = conn.execute("SELECT COUNT(*) AS n FROM deals").fetchone()["n"]
        if count:
            return
        conn.executemany(
            "INSERT INTO deals (slug, name, stage, value_inr, segment) VALUES (?, ?, ?, ?, ?)",
            [(d["slug"], d["name"], d["stage"], d["value_inr"], d["segment"]) for d in DEALS],
        )
        conn.executemany(
            """
            INSERT INTO interactions (
                document_id, deal_slug, happened_on, contact, type, notes, outcome, tactic, result, retained
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            [
                (
                    i["document_id"],
                    i["deal_slug"],
                    i["happened_on"],
                    i["contact"],
                    i["type"],
                    i["notes"],
                    i["outcome"],
                    i["tactic"],
                    i["result"],
                )
                for i in INTERACTIONS
            ],
        )
        conn.executemany(
            "INSERT INTO commitments (deal_slug, what, who, due_on, status) VALUES (?, ?, ?, ?, ?)",
            [(c["deal_slug"], c["what"], c["who"], c["due_on"], c["status"]) for c in COMMITMENTS],
        )

    def deals(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM deals ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def get_deal(self, slug: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM deals WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def get_deal_by_name(self, name: str) -> dict | None:
        target = name.strip().lower()
        for deal in self.deals():
            if deal["name"].strip().lower() == target:
                return deal
        return None

    def set_stage(self, slug: str, stage: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE deals SET stage = ? WHERE slug = ?", (stage, slug))

    def ensure_deal(self, name: str) -> dict:
        existing = self.get_deal_by_name(name)
        if existing:
            return existing
        slug = slugify(name)
        base = slug
        n = 2
        while self.get_deal(slug):
            slug = f"{base}-{n}"
            n += 1
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO deals (slug, name, stage, value_inr, segment) VALUES (?, ?, ?, ?, ?)",
                (slug, name.strip(), "Discovery", 0, "Unspecified"),
            )
        return self.get_deal(slug)

    def interactions(self, slug: str | None = None) -> list[dict]:
        sql = "SELECT * FROM interactions"
        args: tuple = ()
        if slug:
            sql += " WHERE deal_slug = ?"
            args = (slug,)
        sql += " ORDER BY happened_on, id"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def pending_retention(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM interactions WHERE retained = 0 ORDER BY happened_on, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_retained(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        with self._conn() as conn:
            conn.executemany(
                "UPDATE interactions SET retained = 1 WHERE document_id = ?",
                [(doc_id,) for doc_id in document_ids],
            )

    def add_interaction(
        self,
        *,
        document_id: str,
        deal_slug: str,
        happened_on: str,
        contact: str,
        type_: str,
        notes: str,
        outcome: str,
        tactic: str,
        result: str,
    ) -> dict:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO interactions (
                    document_id, deal_slug, happened_on, contact, type, notes, outcome, tactic, result, retained
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (document_id, deal_slug, happened_on, contact, type_, notes, outcome, tactic, result),
            )
            row = conn.execute(
                "SELECT * FROM interactions WHERE document_id = ?", (document_id,)
            ).fetchone()
        return dict(row)

    def get_interaction(self, document_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM interactions WHERE document_id = ?", (document_id,)).fetchone()
        return dict(row) if row else None

    def update_interaction(self, document_id: str, updates: dict) -> dict | None:
        allowed = {"happened_on", "contact", "type", "notes", "outcome", "tactic", "result", "retained"}
        fields = []
        args = []
        for k, v in updates.items():
            if k in allowed:
                fields.append(f"{k} = ?")
                args.append(v)
        if not fields:
            return self.get_interaction(document_id)
        args.append(document_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE interactions SET {', '.join(fields)} WHERE document_id = ?", args)
        return self.get_interaction(document_id)

    def commitments(self, slug: str | None = None, status: str | None = None) -> list[dict]:
        sql = "SELECT * FROM commitments WHERE 1 = 1"
        args: list[str] = []
        if slug:
            sql += " AND deal_slug = ?"
            args.append(slug)
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY due_on, id"
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def add_commitment(self, deal_slug: str, what: str, who: str, due_on: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO commitments (deal_slug, what, who, due_on, status) VALUES (?, ?, ?, ?, 'open')",
                (deal_slug, what.strip(), who.strip(), due_on),
            )

    def set_commitment_status(self, commitment_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE commitments SET status = ? WHERE id = ?",
                (status, commitment_id),
            )

    def get_commitment(self, commitment_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM commitments WHERE id = ?", (commitment_id,)).fetchone()
        return dict(row) if row else None

    def meta_get(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def meta_set(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def update_deal(
        self,
        slug: str,
        name: str | None = None,
        stage: str | None = None,
        value_inr: int | None = None,
        segment: str | None = None,
    ) -> None:
        updates = []
        args = []
        if name is not None:
            updates.append("name = ?")
            args.append(name.strip())
        if stage is not None:
            updates.append("stage = ?")
            args.append(stage.strip())
        if value_inr is not None:
            updates.append("value_inr = ?")
            args.append(value_inr)
        if segment is not None:
            updates.append("segment = ?")
            args.append(segment.strip())
        if not updates:
            return
        args.append(slug)
        with self._conn() as conn:
            conn.execute(f"UPDATE deals SET {', '.join(updates)} WHERE slug = ?", args)

    def delete_deal(self, slug: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM commitments WHERE deal_slug = ?", (slug,))
            conn.execute("DELETE FROM interactions WHERE deal_slug = ?", (slug,))
            conn.execute("DELETE FROM deals WHERE slug = ?", (slug,))

    def delete_interaction(self, document_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM interactions WHERE document_id = ?", (document_id,))

    def update_commitment(
        self,
        commitment_id: int,
        what: str | None = None,
        who: str | None = None,
        due_on: str | None = None,
        status: str | None = None,
    ) -> None:
        updates = []
        args = []
        if what is not None:
            updates.append("what = ?")
            args.append(what.strip())
        if who is not None:
            updates.append("who = ?")
            args.append(who.strip())
        if due_on is not None:
            updates.append("due_on = ?")
            args.append(due_on.strip())
        if status is not None:
            updates.append("status = ?")
            args.append(status.strip())
        if not updates:
            return
        args.append(commitment_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE commitments SET {', '.join(updates)} WHERE id = ?", args)

    def delete_commitment(self, commitment_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM commitments WHERE id = ?", (commitment_id,))

    def create_approval_session(self, session_dict: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO approval_sessions (
                    id, deal_slug, deal_name, operation_type, requesting_user, required_second_user,
                    status, created_at, expires_at, user_a_salt, user_a_hash, user_a_verified,
                    user_b_salt, user_b_hash, user_b_verified, attempts, max_attempts,
                    payload_json, committed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_dict["id"],
                    session_dict.get("deal_slug") or "",
                    session_dict.get("deal_name") or "",
                    session_dict["operation_type"],
                    session_dict["requesting_user"],
                    session_dict["required_second_user"],
                    session_dict["status"],
                    session_dict["created_at"],
                    session_dict["expires_at"],
                    session_dict.get("user_a_salt"),
                    session_dict.get("user_a_hash"),
                    1 if session_dict.get("user_a_verified") else 0,
                    session_dict.get("user_b_salt"),
                    session_dict.get("user_b_hash"),
                    1 if session_dict.get("user_b_verified") else 0,
                    session_dict.get("attempts", 0),
                    session_dict.get("max_attempts", 5),
                    session_dict["payload_json"],
                    1 if session_dict.get("committed") else 0,
                ),
            )

    def get_approval_session(self, approval_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM approval_sessions WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["user_a_verified"] = bool(d["user_a_verified"])
        d["user_b_verified"] = bool(d["user_b_verified"])
        d["committed"] = bool(d["committed"])
        return d

    def update_approval_session(self, approval_id: str, updates: dict) -> None:
        fields = []
        args = []
        for k, v in updates.items():
            fields.append(f"{k} = ?")
            if isinstance(v, bool):
                args.append(1 if v else 0)
            else:
                args.append(v)
        args.append(approval_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE approval_sessions SET {', '.join(fields)} WHERE id = ?", args)

    def record_audit(
        self,
        *,
        approval_id: str,
        deal_slug: str,
        deal_name: str,
        operation: str,
        requesting_user: str,
        approving_user: str,
        status: str,
        details: str = "",
        timestamp: str | None = None,
    ) -> dict:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_log (
                    approval_id, deal_slug, deal_name, operation, requesting_user, approving_user, timestamp, status, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (approval_id, deal_slug, deal_name, operation, requesting_user, approving_user, ts, status, details),
            )
            row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def audit_logs(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


def is_overdue(due_on: str, today: date | None = None) -> bool:
    today = today or date.today()
    return date.fromisoformat(due_on) < today
