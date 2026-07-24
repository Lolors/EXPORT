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


def _aggregate_packed(rows, boxes_by_no: dict[int, object]) -> list[dict]:
    grouped: dict[tuple[int, str, str, str, str], dict] = {}
    for row in rows:
        if row['box_no'] is None:
            continue

        box_no = int(row['box_no'])
        business = _text(row['business_unit'])
        product = _text(row['product_name'])
        lot = _text(row['lot_no'])
        expiry = _text(row['expiry_date'])
        key = (box_no, business, product, lot, expiry)
        box = boxes_by_no.get(box_no)

        if key not in grouped:
            grouped[key] = {
                'box_no': box_no,
                'business_unit': business,
                'product_name': product,
                'lot_no': lot,
                'expiry_date': expiry,
                'requested_qty': 0.0,
                'weight_kg': box['weight_kg'] if box else 0,
                'length_cm': box['length_cm'] if box else 0,
                'width_cm': box['width_cm'] if box else 0,
                'height_cm': box['height_cm'] if box else 0,
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
    """Read the current packing state directly from the canonical shipment rows."""
    current_rows = shipment_service.list_case_items(case_id)
    boxes_by_no = {
        int(box['box_no']): box
        for box in packing_service.list_boxes(case_id)
    }
    packed = _aggregate_packed(current_rows, boxes_by_no)
    actual = _aggregate_actual(current_rows)
    return packed, actual
