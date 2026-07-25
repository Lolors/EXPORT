from __future__ import annotations

import re
import unicodedata
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('공유문서.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

replacement = r"""def render_shipment_product_list(case, actual_rows) -> None:
    destination_order = {
        '노투스팜': 0,
        '노투스': 1,
        'NOH': 2,
        '비자료': 3,
    }
    unit_order = {'BOX': 0, 'PK': 1, 'EA': 2}

    def normalize_product_group_name(value: object) -> str:
        text = unicodedata.normalize('NFKC', str(value or ''))
        text = text.replace('\u200b', '').replace('\ufeff', '')
        text = re.sub(r'\s+', ' ', text).strip()
        return text.casefold()

    sorted_rows = sorted(
        actual_rows,
        key=lambda row: (
            destination_order.get(str(row['business_unit'] or '').strip(), 99),
            str(row['business_unit'] or '').strip().casefold(),
            normalize_product_group_name(row['product_name']),
            str(row['lot_no'] or '').strip().casefold(),
            str(row['expiry_date'] or '').strip(),
        ),
    )

    destination_groups: dict[str, list] = {}
    for row in sorted_rows:
        destination = str(row['business_unit'] or '').strip() or '-'
        destination_groups.setdefault(destination, []).append(row)

    rows_html: list[str] = []
    unique_products: set[str] = set()

    for destination, destination_rows in destination_groups.items():
        destination_rowspan = len(destination_rows)
        product_groups: dict[str, dict[str, object]] = {}
        subtotal_by_unit: dict[str, float] = {}

        for row in destination_rows:
            raw_product_name = str(row['product_name'] or '').strip() or '-'
            product_key = normalize_product_group_name(raw_product_name) or '-'
            if product_key not in product_groups:
                product_groups[product_key] = {
                    'display_name': re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', raw_product_name)).strip() or '-',
                    'rows': [],
                }
            product_groups[product_key]['rows'].append(row)
            unique_products.add(product_key)

            try:
                unit = str(row['unit'] or '').strip() or '-'
            except (KeyError, IndexError):
                unit = '-'
            subtotal_by_unit[unit] = subtotal_by_unit.get(unit, 0.0) + float(row['requested_qty'] or 0)

        destination_written = False
        for product_group in product_groups.values():
            product_name = str(product_group['display_name'])
            product_rows = product_group['rows']
            product_rowspan = len(product_rows)
            for product_index, row in enumerate(product_rows):
                rows_html.append('<tr>')
                if not destination_written:
                    rows_html.append(
                        f'<td rowspan="{destination_rowspan}" class="center merged destination">'
                        f'{html.escape(destination)}</td>'
                    )
                    destination_written = True
                if product_index == 0:
                    rows_html.append(
                        f'<td rowspan="{product_rowspan}" class="center product merged">'
                        f'{html.escape(product_name)}</td>'
                    )
                rows_html.append(f'<td class="center lot">{html.escape(str(row["lot_no"] or "-"))}</td>')
                rows_html.append(f'<td class="center expiry">{html.escape(str(row["expiry_date"] or "-"))}</td>')
                rows_html.append(f'<td class="right qty">{html.escape(fmt_number(row["requested_qty"]))}</td>')
                try:
                    unit = str(row['unit'] or '').strip() or '-'
                except (KeyError, IndexError):
                    unit = '-'
                rows_html.append(f'<td class="center unit">{html.escape(unit)}</td>')
                rows_html.append('</tr>')

        ordered_subtotals = sorted(
            subtotal_by_unit.items(),
            key=lambda item: (unit_order.get(item[0], 99), item[0]),
        )
        subtotal_quantities = '<br>'.join(html.escape(fmt_number(quantity)) for _, quantity in ordered_subtotals)
        subtotal_units = '<br>'.join(html.escape(unit) for unit, _ in ordered_subtotals)
        rows_html.append(
            f'<tr class="subtotal-row"><td colspan="4" class="right subtotal-label">'
            f'{html.escape(destination)} 소계</td>'
            f'<td class="right qty subtotal-qty">{subtotal_quantities}</td>'
            f'<td class="center unit subtotal-unit">{subtotal_units}</td></tr>'
        )

    if not rows_html:
        rows_html.append('<tr><td colspan="6" class="empty">입력된 출고제품이 없습니다.</td></tr>')

    item_count = len(unique_products)
    total_lines = len(sorted_rows)
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}} @page{{size:A4 portrait;margin:15mm}}
html,body{{margin:0;padding:0;background:#eef2f6;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}} body{{padding:10px}}
.toolbar{{width:148mm;max-width:100%;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:7px;background:#173b5f;color:white;font-weight:700;padding:9px 16px;cursor:pointer}}
.sheet{{width:148mm;max-width:100%;margin:auto;background:white;border:1px solid #d7dee7;box-shadow:0 10px 28px rgba(30,45,70,.08)}}
.header{{padding:18px 20px 15px;border-bottom:3px solid #234f75;display:flex;justify-content:space-between;gap:20px;align-items:flex-end}} .title{{font-size:21px;font-weight:850;color:#173b5f;letter-spacing:.02em}} .export-no{{text-align:right;font-size:9px;color:#758294}} .export-no b{{display:block;font-size:13px;color:#172033;margin-top:3px}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);margin:13px 16px 12px;border:1px solid #dce3eb}} .meta div{{padding:7px 8px;border-right:1px solid #e3e8ee}} .meta div:last-child{{border-right:0}} .label{{font-size:8px;color:#7c8797}} .value{{font-size:10px;font-weight:700;margin-top:2px;word-break:break-word}}
.content{{padding:0 16px 17px}} .summary{{width:133mm;max-width:100%;margin:0 auto 5px;font-size:8.8px;color:#697586;text-align:right}}
table{{width:133mm;max-width:100%;margin:0 auto;border-collapse:collapse;table-layout:fixed;font-size:9.2px;border:1px solid #cfd8e2}} col.destination{{width:18mm}} col.product{{width:43mm}} col.lot{{width:28mm}} col.expiry{{width:24mm}} col.qty{{width:12mm}} col.unit{{width:8mm}}
th{{background:#294f71;color:white;padding:6px 4px;text-align:center;font-weight:750}} td{{padding:5px 5px;border-right:1px solid #dce3ea;border-bottom:1px solid #dce3ea;vertical-align:middle;line-height:1.3}} .center{{text-align:center}} .right{{text-align:right}} .product{{white-space:normal;overflow-wrap:anywhere;word-break:keep-all;font-weight:700;text-align:center}} .destination{{font-weight:700}} .merged{{background:#f5f8fb}} .lot,.expiry,.unit{{white-space:nowrap}} .qty{{white-space:nowrap;font-weight:650;padding-left:3px;padding-right:3px}} .unit{{padding-left:2px;padding-right:2px}} .empty{{text-align:center;color:#8993a0;padding:20px}}
.subtotal-row td{{background:#dfeaf4!important;border-top:2px solid #9fb4c8;font-weight:800;color:#173b5f}} .subtotal-label{{padding-right:8px}} .subtotal-qty,.subtotal-unit{{line-height:1.55}}
.notice{{padding:10px 20px 14px;font-size:8.2px;color:#788493;border-top:1px solid #e0e6ed}}
@media print{{html,body{{width:210mm;min-height:297mm;background:white;padding:0}} .toolbar{{display:none!important}} .sheet{{width:148mm;max-width:none;margin:0 auto;border:0;box-shadow:none}} .header{{padding:13px 15px 11px}} .title{{font-size:18px}} .meta{{margin:10px 8px}} .content{{padding:0 8px 12px}} .summary,table{{width:133mm;max-width:none}} table{{font-size:8.5px}} th{{padding:4px 3px}} td{{padding:4px}} .qty,.unit{{padding-left:2px;padding-right:2px}} .subtotal-row td,.header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}} .notice{{padding:8px 15px 0}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="sheet"><div class="header"><div class="title">출고 예정 제품 리스트</div><div class="export-no">EXPORT NO.<b>{html.escape(case['export_no'] or '-')}</b></div></div>
<div class="meta"><div><span class="label">국가 / Country</span><div class="value">{html.escape(case['country'] or '-')}</div></div><div><span class="label">바이어 / Buyer</span><div class="value">{html.escape(case['buyer'] or '-')}</div></div><div><span class="label">운송방식 / Transport</span><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div></div>
<div class="content"><div class="summary">총 {item_count}품목 · 제조번호 기준 {total_lines}행</div><table><colgroup><col class="destination"><col class="product"><col class="lot"><col class="expiry"><col class="qty"><col class="unit"></colgroup><thead><tr><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>출고수량</th><th>단위</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>
<div class="notice">본 문서는 패킹 완료 전 작성된 출고 예정 제품 목록이며, 최종 수량 및 패킹 정보는 변경될 수 있습니다.</div></div></body></html>'''
    components.html(document, height=min(1800, max(700, 500 + len(sorted_rows) * 38)), scrolling=True)


"""

pattern = r'def render_shipment_product_list\(case, actual_rows\) -> None:.*?(?=def open_selected_path\()'
patched, count = re.subn(pattern, lambda _match: replacement, source, count=1, flags=re.S)
if count != 1:
    raise RuntimeError('출고 예정 제품 리스트 렌더링 함수를 교체하지 못했습니다.')

exec(compile(patched, str(SOURCE_PATH), 'exec'), globals(), globals())
