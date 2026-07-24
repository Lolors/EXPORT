from __future__ import annotations

from services import packing_service, shipment_service


BUSINESS_ORDER = {
    '노투스팜': 0,
    '노투스': 1,
    'NOH': 2,
    '비자료': 3,
}


def _text(value: object) -> str:
    return str(value or '').strip()


def _business_sort_key(value: object) -> tuple[int, str]:
    text = _text(value)
    return BUSINESS_ORDER.get(text, 99), text.casefold()


def _aggregate_actual(rows) -> list[dict]:
    grouped: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        business = _text(row['business_unit'])
        product = _text(row['product_name'])
        lot = _text(row['lot_no'])
        expiry = _text(row['expiry_date'])
        key = (business, product, lot, expiry)
        if key not in grouped:
            grouped[key] = {
                'business_unit': business,
                'product_name': product,
                'lot_no': lot,
                'expiry_date': expiry,
                'requested_qty': 0.0,
            }
        grouped[key]['requested_qty'] += float(row['requested_qty'] or 0)

    return sorted(
        grouped.values(),
        key=lambda row: (
            _business_sort_key(row['business_unit']),
            _text(row['product_name']).casefold(),
            _text(row['lot_no']).casefold(),
            _text(row['expiry_date']),
        ),
    )


def _aggregate_packed(rows) -> list[dict]:
    grouped: dict[tuple[int, str, str, str, str], dict] = {}
    for row in rows:
        box_no = int(row['box_no'])
        business = _text(row['business_unit'])
        product = _text(row['product_name'])
        lot = _text(row['lot_no'])
        expiry = _text(row['expiry_date'])
        key = (box_no, business, product, lot, expiry)
        if key not in grouped:
            grouped[key] = {
                'box_no': box_no,
                'business_unit': business,
                'product_name': product,
                'lot_no': lot,
                'expiry_date': expiry,
                'requested_qty': 0.0,
                'weight_kg': row['weight_kg'],
                'length_cm': row['length_cm'],
                'width_cm': row['width_cm'],
                'height_cm': row['height_cm'],
            }
        grouped[key]['requested_qty'] += float(row['requested_qty'] or 0)

    return sorted(
        grouped.values(),
        key=lambda row: (
            int(row['box_no']),
            _business_sort_key(row['business_unit']),
            _text(row['product_name']).casefold(),
            _text(row['lot_no']).casefold(),
            _text(row['expiry_date']),
        ),
    )


def get_document_data(case_id: int):
    """Return grouped and sorted packing/shipment rows for shareable documents."""
    packed = _aggregate_packed(packing_service.list_packed_rows(case_id))
    actual = _aggregate_actual(shipment_service.list_actual(case_id))
    return packed, actual
