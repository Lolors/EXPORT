from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import db
from services.workbook_service import write_case_workbook
from utils.dates import now_text, parse_date
from utils.formatters import sanitize_folder_part


def storage_root() -> Path:
    configured = db.get_setting('shared_root').strip()
    if not configured:
        return db.UPLOAD_DIR

    path = Path(configured).expanduser()

    # Windows에서 E:\ 같은 설정이 남아 있지만 해당 드라이브가 현재
    # 연결되어 있지 않은 경우 mkdir이 FileNotFoundError를 발생시킨다.
    # 드라이브/공유 루트 자체가 없으면 앱 내부 uploads 폴더로 안전하게 대체한다.
    anchor = path.anchor
    if anchor:
        try:
            if not Path(anchor).exists():
                return db.UPLOAD_DIR
        except OSError:
            return db.UPLOAD_DIR

    return path


def test_storage_root(path_text: str) -> tuple[bool, str]:
    path_text = path_text.strip()
    if not path_text:
        return False, '폴더 경로를 입력하세요.'
    try:
        path = Path(path_text).expanduser()
        anchor = path.anchor
        if anchor and not Path(anchor).exists():
            return False, f'드라이브 또는 공유 경로를 찾을 수 없습니다: {anchor}'
        path.mkdir(parents=True, exist_ok=True)
        probe = path / '.export_write_test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return True, str(path.resolve())
    except Exception as exc:
        return False, str(exc)


def order_item_summary(case_id: int) -> str:
    product_rows = db.rows(
        'SELECT product_name FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    products: list[str] = []
    seen: set[str] = set()
    for product in product_rows:
        name = sanitize_folder_part(product['product_name'], '')
        if name and name not in seen:
            products.append(name)
            seen.add(name)
    if not products:
        return ''
    if len(products) <= 2:
        return ', '.join(products)
    return f'{products[0]}, {products[1]} 외 {len(products) - 2}품목'


def case_folder_name(case) -> str:
    country = sanitize_folder_part(case['country'], '국가미입력')
    buyer = sanitize_folder_part(case['buyer'], '')
    transport = sanitize_folder_part(case['transport_mode'], '')
    summary = order_item_summary(int(case['id']))
    name = '_'.join(part for part in [country, buyer, transport, summary] if part)
    actual_ship_date = parse_date(case['actual_ship_date'] if 'actual_ship_date' in case.keys() else '')
    domestic_method = str(case['domestic_method'] if 'domestic_method' in case.keys() else '').strip()
    if actual_ship_date and domestic_method:
        name = f'{actual_ship_date.strftime("%m%d")}_{name}'
    if str(case['status']) == '취소' or str(case['stage']) == '취소':
        return name if name.startswith('[취소]') else f'[취소]{name}'
    return name.removeprefix('[취소]')


def case_folder_base(case) -> Path:
    actual = parse_date(case['actual_ship_date'] if 'actual_ship_date' in case.keys() else '')
    year = (actual or datetime.now()).strftime('%Y')
    country = sanitize_folder_part(case['country'], '국가미입력')
    return storage_root() / country / year


def unique_folder_path(base: Path, folder_name: str, current_path: Path | None = None) -> Path:
    target = base / folder_name
    if current_path and target.resolve() == current_path.resolve():
        return target
    if not target.exists():
        return target
    index = 2
    while True:
        candidate = base / f'{folder_name}_{index}'
        if current_path and candidate.resolve() == current_path.resolve():
            return candidate
        if not candidate.exists():
            return candidate
        index += 1


def _parse_timestamp(value: object) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def _workbook_needs_update(case_id: int, folder: Path) -> bool:
    workbook_path = folder / '수출진행내역.xlsx'
    if not workbook_path.exists():
        return True

    timestamps: list[datetime] = []
    queries = [
        ('SELECT updated_at AS value FROM export_cases WHERE id=?', (case_id,)),
        ('SELECT MAX(created_at) AS value FROM order_items WHERE case_id=?', (case_id,)),
        ('SELECT MAX(COALESCE(updated_at, created_at)) AS value FROM shipment_items WHERE case_id=?', (case_id,)),
        ('SELECT MAX(updated_at) AS value FROM boxes WHERE case_id=?', (case_id,)),
    ]
    for sql, params in queries:
        row = db.row(sql, params)
        parsed = _parse_timestamp(row['value'] if row else '')
        if parsed:
            timestamps.append(parsed)

    if not timestamps:
        return False
    workbook_time = datetime.fromtimestamp(workbook_path.stat().st_mtime)
    return max(timestamps) > workbook_time


def ensure_case_folder(case_id: int) -> Path:
    case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    if not case:
        raise ValueError(f'수출 건을 찾을 수 없습니다: {case_id}')
    saved_path = Path(case['folder_path']) if case['folder_path'] else None
    if saved_path and saved_path.exists():
        if _workbook_needs_update(case_id, saved_path):
            write_case_workbook(case_id, saved_path)
        return saved_path
    base = case_folder_base(case)
    base.mkdir(parents=True, exist_ok=True)
    target = unique_folder_path(base, case_folder_name(case))
    target.mkdir(parents=True, exist_ok=True)
    db.execute(
        'UPDATE export_cases SET folder_path=?,updated_at=? WHERE id=?',
        (str(target), now_text(), case_id),
    )
    write_case_workbook(case_id, target)
    return target


def refresh_attachment_paths(case_id: int, old_root: Path, new_root: Path) -> None:
    old_text = str(old_root)
    for attachment in db.rows(
        'SELECT id, stored_path FROM attachments WHERE case_id=?',
        (case_id,),
    ):
        stored = str(attachment['stored_path'])
        if stored.startswith(old_text):
            replacement = str(new_root / Path(stored).relative_to(old_root))
            db.execute('UPDATE attachments SET stored_path=? WHERE id=?', (replacement, attachment['id']))


def sync_case_folder(case_id: int) -> Path:
    case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    if not case:
        raise ValueError(f'수출 건을 찾을 수 없습니다: {case_id}')
    base = case_folder_base(case)
    current = Path(case['folder_path']) if case['folder_path'] else None
    target = unique_folder_path(base, case_folder_name(case), current)

    if current and current.exists() and current.resolve() == target.resolve():
        if _workbook_needs_update(case_id, current):
            write_case_workbook(case_id, current)
        return current

    base.mkdir(parents=True, exist_ok=True)
    if current and current.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(target))
        refresh_attachment_paths(case_id, current, target)
    else:
        target.mkdir(parents=True, exist_ok=True)
    db.execute(
        'UPDATE export_cases SET folder_path=?,updated_at=? WHERE id=?',
        (str(target), now_text(), case_id),
    )
    write_case_workbook(case_id, target)
    return target


def rebuild_all_case_folders() -> list[tuple[int, Path]]:
    return [
        (int(case['id']), sync_case_folder(int(case['id'])))
        for case in db.rows('SELECT id FROM export_cases ORDER BY id')
    ]


def move_file_to_case(case_id: int, source: Path, category: str = '출고사진') -> Path:
    folder = ensure_case_folder(case_id)
    source = Path(source)
    destination = folder / source.name
    counter = 2
    while destination.exists():
        destination = folder / f'{source.stem}_{counter}{source.suffix}'
        counter += 1
    shutil.move(str(source), str(destination))
    db.execute(
        'INSERT INTO attachments(case_id,file_name,stored_path,category,uploaded_at) VALUES (?,?,?,?,?)',
        (case_id, destination.name, str(destination), category, now_text()),
    )
    return destination
