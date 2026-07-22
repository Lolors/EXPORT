from __future__ import annotations

import db
from utils.dates import now_text


def add(case_id: int | None, action: str, detail: str) -> None:
    db.execute(
        'INSERT INTO history(case_id, action, detail, created_at) VALUES (?,?,?,?)',
        (case_id, action, detail, now_text()),
    )


def list_for_case(case_id: int):
    return db.rows(
        'SELECT action, detail, created_at FROM history WHERE case_id=? ORDER BY id DESC',
        (case_id,),
    )
