from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from utils.dates import now_text

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'export.db'
UPLOAD_DIR = BASE_DIR / 'uploads'
STAGES = ['주문 접수','제품 준비','실출고 입력','패킹','국내배송','선적 준비','선적 완료','완료','취소']
TRANSPORT_MODES = ['AIR','SEA','HAND']


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
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}


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
        cur = conn.execute(query, params)
        return int(cur.lastrowid or 0)


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


# 이전 페이지 코드와의 호환용 얇은 위임 함수. 새 코드는 services/utils를 직접 사용합니다.
def add_history(case_id: int | None, action: str, detail: str) -> None:
    from services.history_service import add
    add(case_id, action, detail)


def next_export_no(prefix: str = 'EXP', year: int | None = None) -> str:
    from utils.numbering import next_export_no as generate
    return generate(prefix, year)


def active_cases(country: str | None = None):
    from services.export_service import active_cases as get_active_cases
    return get_active_cases(country)


def parse_date(value: str | None):
    from utils.dates import parse_date as parse
    return parse(value)


def storage_root():
    from services.folder_service import storage_root as get_root
    return get_root()


def test_storage_root(path_text: str):
    from services.folder_service import test_storage_root as test
    return test(path_text)


def order_item_summary(case_id: int):
    from services.folder_service import order_item_summary as summarize
    return summarize(case_id)


def case_folder_name(case):
    from services.folder_service import case_folder_name as build
    return build(case)


def case_folder_base(case):
    from services.folder_service import case_folder_base as build
    return build(case)


def ensure_case_folder(case_id: int):
    from services.folder_service import ensure_case_folder as ensure
    return ensure(case_id)


def sync_case_folder(case_id: int):
    from services.folder_service import sync_case_folder as sync
    return sync(case_id)


def rebuild_all_case_folders():
    from services.folder_service import rebuild_all_case_folders as rebuild
    return rebuild()


def move_file_to_case(case_id: int, source: Path, category: str = '출고사진'):
    from services.folder_service import move_file_to_case as move
    return move(case_id, source, category)


def write_case_workbook(case_id: int, folder: Path | None = None):
    from services.folder_service import ensure_case_folder
    from services.workbook_service import write_case_workbook as write
    return write(case_id, folder or ensure_case_folder(case_id))
