from __future__ import annotations

import db
from utils.dates import now_text


def save_delivery(
    case_id: int,
    *,
    method: str,
    actual_ship_date: str,
    tracking_no: str = '',
    driver_name: str = '',
    driver_phone: str = '',
) -> None:
    db.execute(
        """UPDATE export_cases
           SET domestic_method=?,tracking_no=?,driver_name=?,driver_phone=?,
               actual_ship_date=?,stage='국내배송',status='완료',updated_at=?
           WHERE id=?""",
        (
            method,
            tracking_no.strip(),
            driver_name.strip(),
            driver_phone.strip(),
            actual_ship_date,
            now_text(),
            case_id,
        ),
    )
