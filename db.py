from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from utils.dates import now_text

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'export.db'
UPLOAD_DIR = BASE_DIR / 'uploads'


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}


def _add_column(conn: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')


def _remove_expected_ship_date_column(conn: sqlite3.Connection) -> None:
    if 'expected_ship_date' not in _columns(conn, 'export_cases'):
        return

    conn.executescript('''
    PRAGMA foreign_keys = OFF;
    CREATE TABLE export_cases_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        export_no TEXT NOT NULL UNIQUE,
        buyer TEXT DEFAULT '',
        country TEXT NOT NULL DEFAULT '',
        transport_mode TEXT DEFAULT 'AIR',
        stage TEXT NOT NULL DEFAULT '주문 접수',
        status TEXT NOT NULL DEFAULT '진행중',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        domestic_method TEXT DEFAULT '',
        tracking_no TEXT DEFAULT '',
        driver_name TEXT DEFAULT '',
        driver_phone TEXT DEFAULT '',
        note TEXT DEFAULT '',
        actual_ship_date TEXT DEFAULT '',
        folder_path TEXT DEFAULT '',
        cancel_reason TEXT DEFAULT '',
        cancelled_at TEXT DEFAULT '',
        previous_stage TEXT DEFAULT '',
        case_type TEXT DEFAULT 'current'
    );
    INSERT INTO export_cases_new(
        id,export_no,buyer,country,transport_mode,stage,status,created_at,updated_at,
        domestic_method,tracking_no,driver_name,driver_phone,note,actual_ship_date,
        folder_path,cancel_reason,cancelled_at,previous_stage,case_type
    )
    SELECT
        id,export_no,buyer,country,transport_mode,stage,status,created_at,updated_at,
        COALESCE(domestic_method,''),COALESCE(tracking_no,''),COALESCE(driver_name,''),
        COALESCE(driver_phone,''),COALESCE(note,''),COALESCE(actual_ship_date,''),
        COALESCE(folder_path,''),COALESCE(cancel_reason,''),COALESCE(cancelled_at,''),
        COALESCE(previous_stage,''),'current'
    FROM export_cases;
    DROP TABLE export_cases;
    ALTER TABLE export_cases_new RENAME TO export_cases;
    PRAGMA foreign_keys = ON;
    ''')


def init_db() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS export_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_no TEXT NOT NULL UNIQUE,
            buyer TEXT DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            transport_mode TEXT DEFAULT 'AIR',
            stage TEXT NOT NULL DEFAULT '주문 접수',
            status TEXT NOT NULL DEFAULT '진행중',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT DEFAULT 'EA',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shipment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
            business_unit TEXT DEFAULT '',
            location TEXT DEFAULT '',
            product_name TEXT NOT NULL,
            lot_no TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            requested_qty REAL NOT NULL DEFAULT 0,
            box_no INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
            box_no INTEGER NOT NULL,
            length_cm REAL DEFAULT 0,
            width_cm REAL DEFAULT 0,
            height_cm REAL DEFAULT 0,
            weight_kg REAL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(case_id, box_no)
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES export_cases(id) ON DELETE CASCADE,
            file_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            category TEXT DEFAULT '출고사진',
            uploaded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER REFERENCES export_cases(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        ''')

        for definition in [
            "domestic_method TEXT DEFAULT ''",
            "tracking_no TEXT DEFAULT ''",
            "driver_name TEXT DEFAULT ''",
            "driver_phone TEXT DEFAULT ''",
            "note TEXT DEFAULT ''",
            "actual_ship_date TEXT DEFAULT ''",
            "folder_path TEXT DEFAULT ''",
            "cancel_reason TEXT DEFAULT ''",
            "cancelled_at TEXT DEFAULT ''",
            "previous_stage TEXT DEFAULT ''",
            "case_type TEXT DEFAULT 'current'",
        ]:
            _add_column(conn, 'export_cases', definition)

        _remove_expected_ship_date_column(conn)
        _add_column(conn, 'shipment_items', 'order_item_id INTEGER')


def rows(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def row(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(query, params).fetchone()


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connect() as conn:
        cursor = conn.execute(query, params)
        return int(cursor.lastrowid or 0)


def executemany(query: str, values: list[tuple[Any, ...]]) -> None:
    with connect() as conn:
        conn.executemany(query, values)


def get_setting(key: str, default: str = '') -> str:
    result = row('SELECT value FROM settings WHERE key=?', (key,))
    return str(result['value']) if result else default


def set_setting(key: str, value: str) -> None:
    execute(
        '''INSERT INTO settings(key,value,updated_at) VALUES (?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at''',
        (key, value, now_text()),
    )
