from __future__ import annotations

import db
from utils.dates import now_text


@db.backup_batch
def rename_box(case_id: int, current_box_no: int, new_box_no: int) -> None:
    current_box_no = int(current_box_no)
    new_box_no = int(new_box_no)

    if new_box_no < 1:
        raise ValueError('CTN No.는 1 이상이어야 합니다.')
    if current_box_no == new_box_no:
        return

    with db.connect() as conn:
        source = conn.execute(
            'SELECT id FROM boxes WHERE case_id=? AND box_no=?',
            (case_id, current_box_no),
        ).fetchone()
        if source is None:
            raise ValueError(f'CTN {current_box_no}을 찾을 수 없습니다.')

        duplicate = conn.execute(
            'SELECT id FROM boxes WHERE case_id=? AND box_no=?',
            (case_id, new_box_no),
        ).fetchone()
        if duplicate is not None:
            raise ValueError(f'CTN {new_box_no}은 이미 사용 중입니다. 다른 번호를 입력하세요.')

        now = now_text()
        conn.execute(
            'UPDATE boxes SET box_no=?,updated_at=? WHERE case_id=? AND box_no=?',
            (new_box_no, now, case_id, current_box_no),
        )
        conn.execute(
            'UPDATE shipment_items SET box_no=?,updated_at=? WHERE case_id=? AND box_no=?',
            (new_box_no, now, case_id, current_box_no),
        )
