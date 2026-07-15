from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path('export.db')
UPLOAD_DIR = Path('uploads')
STAGES = ['주문 접수','제품 준비','실출고 입력','패킹','국내배송','선적 준비','선적 완료','완료','취소']
TRANSPORT_MODES = ['AIR','SEA','HAND']
INVALID_FOLDER_CHARS = '\\/ :*?"<>|'

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

def now_text() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}

def _add_column(conn: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')

def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    with connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS export_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_no TEXT NOT NULL UNIQUE,
            buyer TEXT DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            expected_ship_date TEXT DEFAULT '',
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
        ''')
        for definition in [
            "domestic_method TEXT DEFAULT ''",
            "tracking_no TEXT DEFAULT ''",
            "driver_name TEXT DEFAULT ''",
            "driver_phone TEXT DEFAULT ''",
            "note TEXT DEFAULT ''",
            "actual_ship_date TEXT DEFAULT ''",
            "folder_path TEXT DEFAULT ''",
        ]:
            _add_column(conn, 'export_cases', definition)

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

def add_history(case_id: int | None, action: str, detail: str) -> None:
    execute('INSERT INTO history(case_id, action, detail, created_at) VALUES (?,?,?,?)',
            (case_id, action, detail, now_text()))

def next_export_no() -> str:
    year = datetime.now().year
    result = row('SELECT export_no FROM export_cases WHERE export_no LIKE ? ORDER BY export_no DESC LIMIT 1',
                 (f'EXP-{year}-%',))
    if not result:
        return f'EXP-{year}-001'
    try:
        number = int(result['export_no'].split('-')[-1]) + 1
    except ValueError:
        number = 1
    return f'EXP-{year}-{number:03d}'

def active_cases(country: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소')"
    params: tuple[Any, ...] = ()
    if country:
        sql += ' AND country=?'
        params = (country,)
    return rows(sql + ' ORDER BY expected_ship_date, created_at', params)

def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None

def sanitize_folder_part(value: str | None, fallback: str = '미입력') -> str:
    text = str(value or '').strip() or fallback
    for char in INVALID_FOLDER_CHARS:
        text = text.replace(char, '_')
    text = ' '.join(text.split())
    return text.strip(' .') or fallback

def case_folder_name(case: sqlite3.Row | dict[str, Any]) -> str:
    actual = parse_date(case['actual_ship_date'] if 'actual_ship_date' in case.keys() else '')
    if not actual:
        return sanitize_folder_part(case['export_no'])

    mmdd = actual.strftime('%m%d')
    buyer = sanitize_folder_part(case['buyer'], '') if case['buyer'] else ''
    transport = sanitize_folder_part(case['transport_mode'], 'AIR')
    note = sanitize_folder_part(case['note'], case['export_no'])
    parts = [mmdd]
    if buyer:
        parts.append(buyer)
    parts.extend([transport, note])
    return '_'.join(parts)

def case_folder_base(case: sqlite3.Row | dict[str, Any]) -> Path:
    actual = parse_date(case['actual_ship_date'] if 'actual_ship_date' in case.keys() else '')
    expected = parse_date(case['expected_ship_date'] if case['expected_ship_date'] else '')
    year = (actual or expected or datetime.now()).strftime('%Y')
    country = sanitize_folder_part(case['country'], '국가미입력')
    return UPLOAD_DIR / country / year

def unique_folder_path(base: Path, folder_name: str, current_path: Path | None = None) -> Path:
    target = base / folder_name
    if current_path and target.resolve() == current_path.resolve():
        return target
    if not target.exists():
        return target
    idx = 2
    while True:
        candidate = base / f'{folder_name}_{idx}'
        if current_path and candidate.resolve() == current_path.resolve():
            return candidate
        if not candidate.exists():
            return candidate
        idx += 1

def ensure_case_folder(case_id: int) -> Path:
    case = row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    if not case:
        raise ValueError(f'수출 건을 찾을 수 없습니다: {case_id}')
    saved_path = Path(case['folder_path']) if case['folder_path'] else None
    if saved_path and saved_path.exists():
        return saved_path
    base = case_folder_base(case)
    base.mkdir(parents=True, exist_ok=True)
    target = unique_folder_path(base, case_folder_name(case))
    target.mkdir(parents=True, exist_ok=True)
    execute('UPDATE export_cases SET folder_path=?,updated_at=? WHERE id=?', (str(target), now_text(), case_id))
    return target

def refresh_attachment_paths(case_id: int, old_root: Path, new_root: Path) -> None:
    old_text = str(old_root)
    for attachment in rows('SELECT id, stored_path FROM attachments WHERE case_id=?', (case_id,)):
        stored = str(attachment['stored_path'])
        if stored.startswith(old_text):
            replacement = str(new_root / Path(stored).relative_to(old_root))
            execute('UPDATE attachments SET stored_path=? WHERE id=?', (replacement, attachment['id']))

def sync_case_folder(case_id: int) -> Path:
    case = row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    if not case:
        raise ValueError(f'수출 건을 찾을 수 없습니다: {case_id}')
    base = case_folder_base(case)
    base.mkdir(parents=True, exist_ok=True)
    target = unique_folder_path(base, case_folder_name(case), Path(case['folder_path']) if case['folder_path'] else None)
    current = Path(case['folder_path']) if case['folder_path'] else None

    if current and current.exists() and current.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(target))
        refresh_attachment_paths(case_id, current, target)
    else:
        target.mkdir(parents=True, exist_ok=True)

    execute('UPDATE export_cases SET folder_path=?,updated_at=? WHERE id=?', (str(target), now_text(), case_id))
    return target
