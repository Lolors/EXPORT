from __future__ import annotations

import json
import os
import sqlite3
import string
from datetime import datetime
from pathlib import Path

USB_MARKER_NAME = '.export_usb.json'
USB_STORAGE_ID = 'NOHTUS_EXPORT_USB'
USB_DB_DIR = 'EXPORT_DB'
USB_DB_NAME = 'export.db'
DB_VERSION = 1


def _candidate_roots() -> list[Path]:
    if os.name != 'nt':
        return []
    roots: list[Path] = []
    for letter in string.ascii_uppercase:
        root = Path(f'{letter}:\\')
        try:
            if root.exists():
                roots.append(root)
        except OSError:
            continue
    return roots


def read_usb_marker(root: Path) -> dict:
    marker = root / USB_MARKER_NAME
    try:
        data = json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def is_export_usb(root: Path) -> bool:
    return read_usb_marker(root).get('storage_id') == USB_STORAGE_ID


def find_export_usb() -> Path | None:
    for root in _candidate_roots():
        if is_export_usb(root):
            return root
    return None


def drive_root_for(path: Path) -> Path | None:
    resolved = Path(path).expanduser()
    if os.name != 'nt' or not resolved.drive:
        return None
    return Path(f'{resolved.drive}\\')


def register_export_usb(path: Path) -> Path:
    root = drive_root_for(path)
    if root is None or not root.exists():
        raise ValueError('Windows USB 드라이브 경로를 선택하세요.')
    marker = root / USB_MARKER_NAME
    marker.write_text(
        json.dumps(
            {
                'storage_id': USB_STORAGE_ID,
                'version': 1,
                'registered_at': datetime.now().isoformat(timespec='seconds'),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    return root


def usb_database_path(root: Path | None = None) -> Path | None:
    usb_root = root or find_export_usb()
    if usb_root is None:
        return None
    return usb_root / USB_DB_DIR / USB_DB_NAME


def database_info(path: Path) -> dict:
    if not path.exists():
        return {'exists': False, 'version': 0, 'modified_at': None, 'size': 0}
    version = DB_VERSION
    try:
        with sqlite3.connect(path, timeout=5.0) as conn:
            row = conn.execute('PRAGMA user_version').fetchone()
            version = int(row[0] or DB_VERSION) if row else DB_VERSION
    except sqlite3.Error:
        version = 0
    stat = path.stat()
    return {
        'exists': True,
        'version': version,
        'modified_at': datetime.fromtimestamp(stat.st_mtime),
        'size': stat.st_size,
    }


def compare_databases(local_path: Path, usb_path: Path | None) -> dict:
    local = database_info(local_path)
    usb = database_info(usb_path) if usb_path else {'exists': False, 'version': 0, 'modified_at': None, 'size': 0}
    usb_is_newer = bool(
        usb['exists']
        and (
            usb['version'] > local['version']
            or (
                usb['version'] == local['version']
                and usb['modified_at']
                and (not local['modified_at'] or usb['modified_at'] > local['modified_at'])
            )
        )
    )
    return {'local': local, 'usb': usb, 'usb_is_newer': usb_is_newer}


def safe_backup_database(local_path: Path, usb_root: Path | None = None) -> Path | None:
    root = usb_root or find_export_usb()
    if root is None or not local_path.exists():
        return None
    destination = root / USB_DB_DIR / USB_DB_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.db.tmp')
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(local_path, timeout=10.0) as source:
        with sqlite3.connect(temporary, timeout=10.0) as target:
            source.backup(target)
            target.execute(f'PRAGMA user_version = {DB_VERSION}')
            target.commit()
    temporary.replace(destination)
    return destination


def restore_database_from_usb(local_path: Path, usb_path: Path) -> Path:
    if not usb_path.exists():
        raise FileNotFoundError('USB 백업 DB를 찾을 수 없습니다.')
    temporary = local_path.with_suffix('.db.restore.tmp')
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(usb_path, timeout=10.0) as source:
        with sqlite3.connect(temporary, timeout=10.0) as target:
            source.backup(target)
            target.commit()
    temporary.replace(local_path)
    return local_path
