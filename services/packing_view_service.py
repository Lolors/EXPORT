from __future__ import annotations


def packing_summary(items: list) -> dict:
    unpacked_count = sum(1 for item in items if item['box_no'] is None)
    packed_count = len(items) - unpacked_count
    box_count = len({item['box_no'] for item in items if item['box_no'] is not None})
    total_quantity = sum(float(item['requested_qty'] or 0) for item in items)
    return {
        'row_count': len(items),
        'total_quantity': total_quantity,
        'packed_count': packed_count,
        'unpacked_count': unpacked_count,
        'box_count': box_count,
    }


def items_by_box(items: list) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for item in items:
        if item['box_no'] is None:
            continue
        grouped.setdefault(int(item['box_no']), []).append(item)
    return grouped


def product_summary(items: list, *, visible_count: int = 2) -> str:
    names: list[str] = []
    for item in items:
        name = str(item['product_name'] or '').strip()
        if name and name not in names:
            names.append(name)
    if not names:
        return '-'
    result = ', '.join(names[:visible_count])
    remaining = len(names) - visible_count
    return f'{result} 외 {remaining}품목' if remaining > 0 else result
