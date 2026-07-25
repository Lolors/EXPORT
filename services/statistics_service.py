from __future__ import annotations

from datetime import date

import pandas as pd

import db


STATISTICS_COLUMNS = [
    'case_id',
    '출고일자',
    '수출번호',
    '국가',
    '바이어',
    '제품명',
    '출고수량',
    '단위',
]


def shipment_rows(start_date: date, end_date: date) -> pd.DataFrame:
    """Return actual shipment rows for completed and historical export cases."""
    rows = db.rows(
        '''
        SELECT
            c.id AS case_id,
            substr(c.actual_ship_date, 1, 10) AS ship_date,
            c.export_no,
            COALESCE(c.country, '') AS country,
            COALESCE(c.buyer, '') AS buyer,
            COALESCE(NULLIF(TRIM(s.product_name), ''), o.product_name, '') AS product_name,
            COALESCE(s.requested_qty, 0) AS shipped_qty,
            COALESCE(NULLIF(TRIM(o.unit), ''), 'EA') AS unit
        FROM export_cases c
        JOIN shipment_items s
          ON s.case_id = c.id
        LEFT JOIN order_items o
          ON o.id = s.order_item_id
         AND o.case_id = c.id
        WHERE c.status != '취소'
          AND TRIM(COALESCE(c.actual_ship_date, '')) != ''
          AND date(substr(c.actual_ship_date, 1, 10)) BETWEEN date(?) AND date(?)
          AND COALESCE(s.requested_qty, 0) > 0
        ORDER BY date(substr(c.actual_ship_date, 1, 10)) DESC, c.id DESC, s.id
        ''',
        (start_date.isoformat(), end_date.isoformat()),
    )

    if not rows:
        return pd.DataFrame(columns=STATISTICS_COLUMNS)

    frame = pd.DataFrame(
        [
            {
                'case_id': int(row['case_id']),
                '출고일자': str(row['ship_date'] or ''),
                '수출번호': str(row['export_no'] or ''),
                '국가': str(row['country'] or '').strip() or '미입력',
                '바이어': str(row['buyer'] or '').strip(),
                '제품명': str(row['product_name'] or '').strip() or '미입력',
                '출고수량': float(row['shipped_qty'] or 0),
                '단위': str(row['unit'] or 'EA').strip() or 'EA',
            }
            for row in rows
        ]
    )
    return frame[STATISTICS_COLUMNS]


def normalize_text(value: object) -> str:
    return ''.join(str(value or '').strip().casefold().split())


def filter_rows(
    frame: pd.DataFrame,
    countries: list[str] | None = None,
    product_query: str = '',
) -> pd.DataFrame:
    filtered = frame.copy()

    if countries:
        filtered = filtered[filtered['국가'].isin(countries)]

    normalized_query = normalize_text(product_query)
    if normalized_query:
        filtered = filtered[
            filtered['제품명'].map(normalize_text).str.contains(normalized_query, regex=False)
        ]

    return filtered.reset_index(drop=True)


def country_product_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['국가', '제품명', '단위', '출고수량', '출고건수'])

    summary = (
        frame.groupby(['국가', '제품명', '단위'], as_index=False)
        .agg(
            출고수량=('출고수량', 'sum'),
            출고건수=('case_id', 'nunique'),
        )
        .sort_values(['국가', '출고수량', '제품명'], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    return summary


def product_country_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['제품명', '국가', '단위', '출고수량', '출고건수'])

    summary = (
        frame.groupby(['제품명', '국가', '단위'], as_index=False)
        .agg(
            출고수량=('출고수량', 'sum'),
            출고건수=('case_id', 'nunique'),
        )
        .sort_values(['제품명', '출고수량', '국가'], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    return summary


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['월', '단위', '출고수량'])

    monthly = frame.copy()
    monthly['월'] = monthly['출고일자'].str.slice(0, 7)
    return (
        monthly.groupby(['월', '단위'], as_index=False)['출고수량']
        .sum()
        .sort_values(['월', '단위'])
        .reset_index(drop=True)
    )
