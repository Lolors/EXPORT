from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from utils.formatters import fmt_number


PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
NAVY = '#173b5f'
BLUE = '#294f71'
TEXT = '#172033'
MUTED = '#738094'
BORDER = '#d8e0e8'
LIGHT = '#f5f8fb'
TOTAL = '#eef3f8'
WHITE = '#ffffff'


def _font(size: int, *, bold: bool = False):
    names = ['malgunbd.ttf', 'malgun.ttf'] if bold else ['malgun.ttf', 'malgunbd.ttf']
    candidates = [Path('C:/Windows/Fonts') / name for name in names]
    candidates.extend(Path('/usr/share/fonts/truetype/noto') / name for name in (
        'NotoSansCJK-Bold.ttc' if bold else 'NotoSansCJK-Regular.ttc',
    ))
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _text(value: object) -> str:
    return str(value or '').strip() or '-'


def _wrap(draw: ImageDraw.ImageDraw, text: object, font, max_width: int) -> list[str]:
    value = _text(text)
    lines: list[str] = []
    current = ''
    for character in value:
        candidate = current + character
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or ['-']


def _center_text(draw, box, text, font, fill=TEXT):
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (bbox[2] - bbox[0])) / 2
    y = top + (bottom - top - (bbox[3] - bbox[1])) / 2 - 1
    draw.text((x, y), text, font=font, fill=fill)


def _cell_text(draw, box, value, font, *, align='left', fill=TEXT, padding=6):
    left, top, right, bottom = box
    lines = _wrap(draw, value, font, max(10, right - left - padding * 2))
    line_height = max(11, font.size + 3) if hasattr(font, 'size') else 14
    total_height = len(lines) * line_height
    y = top + max(padding, (bottom - top - total_height) / 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        if align == 'center':
            x = left + (right - left - width) / 2
        elif align == 'right':
            x = right - padding - width
        else:
            x = left + padding
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def build_final_document_png(case, packed: list[dict]) -> bytes:
    image = Image.new('RGB', (PAGE_WIDTH, PAGE_HEIGHT), WHITE)
    draw = ImageDraw.Draw(image)
    margin = 48
    content_width = PAGE_WIDTH - margin * 2

    title_font = _font(29, bold=True)
    heading_font = _font(16, bold=True)
    label_font = _font(11)
    value_font = _font(14, bold=True)
    small_font = _font(11)
    table_font_size = 12 if len(packed) <= 14 else 10
    table_font = _font(table_font_size)
    table_bold = _font(table_font_size, bold=True)

    header_height = 112
    draw.rounded_rectangle((margin, 34, PAGE_WIDTH - margin, 34 + header_height), radius=14, fill=NAVY)
    draw.text((margin + 24, 55), '주문 정보 및 패킹 리스트', font=title_font, fill=WHITE)
    draw.text((margin + 25, 101), 'ORDER INFORMATION & PACKING LIST', font=small_font, fill='#dbe8f2')
    export_no = _text(case['export_no'])
    export_bbox = draw.textbbox((0, 0), export_no, font=heading_font)
    draw.text((PAGE_WIDTH - margin - 24 - (export_bbox[2] - export_bbox[0]), 79), export_no, font=heading_font, fill=WHITE)
    draw.text((PAGE_WIDTH - margin - 150, 55), 'EXPORT NO.', font=small_font, fill='#dbe8f2')

    y = 166
    info_rows = [
        [('국가 / Country', case['country']), ('바이어 / Buyer', case['buyer']),
         ('운송방식 / Transport', case['transport_mode']), ('실제출고일 / Ship Date', case['actual_ship_date'])],
        [('국내배송 방식', case['domestic_method']), ('배송 상세', case['tracking_no'] or case['driver_name']),
         ('수하인명', case['consignee_name']), ('수하인주소', case['consignee_address'])],
    ]
    box_width = content_width / 4
    for info_row in info_rows:
        row_height = 66
        draw.rounded_rectangle((margin, y, PAGE_WIDTH - margin, y + row_height), radius=7, outline=BORDER, width=2)
        for index, (label, value) in enumerate(info_row):
            left = margin + index * box_width
            if index:
                draw.line((left, y, left, y + row_height), fill=BORDER, width=1)
            draw.text((left + 10, y + 8), label, font=label_font, fill=MUTED)
            _cell_text(draw, (left + 4, y + 22, left + box_width - 4, y + row_height), value, value_font, padding=6)
        y += row_height + 9

    box_numbers = {int(row['box_no']) for row in packed}
    product_names = {_text(row['product_name']) for row in packed if _text(row['product_name']) != '-'}
    total_quantity = sum(float(row['requested_qty'] or 0) for row in packed)
    summary_values = [(f'{len(box_numbers)} CTN', '총 CTN 수'), (f'{len(product_names)} 품목', '품목 수'), (fmt_number(total_quantity), '출고 수량')]
    card_gap = 10
    card_width = (content_width - card_gap * 2) / 3
    for index, (value, label) in enumerate(summary_values):
        left = margin + index * (card_width + card_gap)
        draw.rounded_rectangle((left, y, left + card_width, y + 62), radius=7, fill=LIGHT, outline=BORDER)
        draw.text((left + 12, y + 8), label, font=label_font, fill=MUTED)
        draw.text((left + 12, y + 29), value, font=heading_font, fill=BLUE)
    y += 78

    table_width = round(PAGE_WIDTH * 150 / 210)
    table_left = (PAGE_WIDTH - table_width) // 2
    draw.text((table_left, y), 'PACKING LIST', font=heading_font, fill=BLUE)
    y += 26
    widths_mm = [12, 16, 32, 22, 20, 12, 14, 22]
    widths = [round(width * table_width / 150) for width in widths_mm]
    widths[-1] += table_width - sum(widths)
    headers = ['CTN No.', '출고처', '제품명', '제조번호', '유통기한', '수량', 'GW (kg)', 'CTN 사이즈']
    header_row_height = 38
    x = table_left
    for width, header in zip(widths, headers):
        draw.rectangle((x, y, x + width, y + header_row_height), fill=BLUE)
        _center_text(draw, (x, y, x + width, y + header_row_height), header, table_bold, WHITE)
        x += width
    y += header_row_height

    grouped: dict[int, list[dict]] = {}
    for row in packed:
        grouped.setdefault(int(row['box_no']), []).append(row)
    available_height = PAGE_HEIGHT - y - 92
    base_row_height = max(27, min(42, int(available_height / max(len(packed) + 1, 1))))

    for box_no, rows in grouped.items():
        row_heights = []
        for row in rows:
            product_lines = _wrap(draw, row['product_name'], table_font, widths[2] - 12)
            lot_lines = _wrap(draw, row['lot_no'], table_font, widths[3] - 12)
            row_heights.append(max(base_row_height, (max(len(product_lines), len(lot_lines)) * (table_font_size + 3)) + 10))
        group_top = y
        group_bottom = y + sum(row_heights)
        x = margin
        merged_values = [
            f'CTN {box_no}',
            f"{fmt_number(rows[0]['weight_kg'])} kg" if rows[0]['weight_kg'] else '-',
            (' × '.join(fmt_number(rows[0][key]) for key in ('length_cm', 'width_cm', 'height_cm')) + ' cm'
             if all(rows[0][key] for key in ('length_cm', 'width_cm', 'height_cm')) else '-'),
        ]
        merged_columns = [(0, merged_values[0]), (6, merged_values[1]), (7, merged_values[2])]
        for column, value in merged_columns:
            left = table_left + sum(widths[:column])
            draw.rectangle((left, group_top, left + widths[column], group_bottom), fill=LIGHT, outline=BORDER)
            _cell_text(draw, (left, group_top, left + widths[column], group_bottom), value, table_bold, align='center')
        for row, row_height in zip(rows, row_heights):
            values = [row['business_unit'], row['product_name'], row['lot_no'], row['expiry_date'], fmt_number(row['requested_qty'])]
            columns = [1, 2, 3, 4, 5]
            for column, value in zip(columns, values):
                left = table_left + sum(widths[:column])
                draw.rectangle((left, y, left + widths[column], y + row_height), fill=WHITE, outline=BORDER)
                _cell_text(draw, (left, y, left + widths[column], y + row_height), value, table_font,
                           align='right' if column == 5 else 'left')
            y += row_height

    total_height = 38
    draw.rectangle((table_left, y, table_left + table_width, y + total_height), fill=TOTAL, outline=BORDER)
    qty_left = table_left + sum(widths[:5])
    weight_left = table_left + sum(widths[:6])
    _cell_text(draw, (table_left, y, qty_left, y + total_height), '합계', table_bold, align='right')
    _cell_text(draw, (qty_left, y, weight_left, y + total_height), fmt_number(total_quantity), table_bold, align='right')
    total_weight = sum({int(row['box_no']): float(row['weight_kg'] or 0) for row in packed}.values())
    _cell_text(draw, (weight_left, y, weight_left + widths[6], y + total_height), f'{fmt_number(total_weight)} kg', table_bold, align='center')

    note = _text(case['note'])
    if note != '-':
        draw.text((margin, PAGE_HEIGHT - 52), f'특이사항: {note}', font=small_font, fill=MUTED)

    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()
