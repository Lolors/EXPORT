from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path("export.db")
UPLOAD_DIR = Path("uploads")

STAGES = [
    "문의",
    "견적",
    "PO 수령",
    "제품 준비",
    "포장",
    "서류 준비",
    "출고 대기",
    "선적",
    "통관",
    "완료",
    "취소",
]

DEFAULT_DOCUMENTS = [
    "Proforma Invoice",
    "Purchase Order",
    "Commercial Invoice",
    "Packing List",
    "COA",
    "MSDS",
    "Certificate of Origin",
    "Export Declaration",
    "AWB / B/L",
]


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS export_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                export_no TEXT NOT NULL UNIQUE,
                buyer TEXT NOT NULL,
                country TEXT DEFAULT '',
                manager TEXT DEFAULT '',
                expected_ship_date TEXT DEFAULT '',
                stage TEXT NOT NULL DEFAULT '문의',
                status TEXT NOT NULL DEFAULT '진행중',
                invoice_no TEXT DEFAULT '',
                incoterms TEXT DEFAULT '',
                transport_mode TEXT DEFAULT '',
                port_loading TEXT DEFAULT '',
                final_destination TEXT DEFAULT '',
                memo TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                spec TEXT DEFAULT '',
                unit TEXT DEFAULT 'EA',
                hs_code TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS packing_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
                box_no INTEGER NOT NULL,
                marks TEXT DEFAULT '',
                product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
                product_name TEXT NOT NULL,
                lot_no TEXT DEFAULT '',
                expiry_date TEXT DEFAULT '',
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT DEFAULT 'EA',
                net_weight REAL DEFAULT 0,
                gross_weight REAL DEFAULT 0,
                length_cm REAL DEFAULT 0,
                width_cm REAL DEFAULT 0,
                height_cm REAL DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
                doc_name TEXT NOT NULL,
                is_done INTEGER NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(case_id, doc_name)
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                category TEXT DEFAULT '',
                uploaded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER REFERENCES export_cases(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def rows(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def row(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(query, params).fetchone()


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cur = conn.execute(query, params)
        return int(cur.lastrowid or 0)


def add_history(case_id: int | None, action: str, detail: str) -> None:
    execute(
        "INSERT INTO history(case_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (case_id, action, detail, now_text()),
    )


def next_export_no() -> str:
    year = datetime.now().year
    result = row(
        "SELECT export_no FROM export_cases WHERE export_no LIKE ? ORDER BY export_no DESC LIMIT 1",
        (f"EXP-{year}-%",),
    )
    if not result:
        return f"EXP-{year}-001"
    last = result["export_no"].split("-")[-1]
    return f"EXP-{year}-{int(last) + 1:03d}"


def create_default_documents(case_id: int) -> None:
    with connect() as conn:
        for name in DEFAULT_DOCUMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO documents(case_id, doc_name, updated_at) VALUES (?, ?, ?)",
                (case_id, name, now_text()),
            )


def case_summary() -> list[sqlite3.Row]:
    return rows(
        """
        SELECT c.*,
               COUNT(DISTINCT p.id) AS packing_lines,
               COUNT(DISTINCT a.id) AS attachment_count,
               SUM(CASE WHEN d.is_done = 1 THEN 1 ELSE 0 END) AS done_docs,
               COUNT(DISTINCT d.id) AS total_docs
        FROM export_cases c
        LEFT JOIN packing_items p ON p.case_id = c.id
        LEFT JOIN attachments a ON a.case_id = c.id
        LEFT JOIN documents d ON d.case_id = c.id
        GROUP BY c.id
        ORDER BY c.created_at DESC
        """
    )
