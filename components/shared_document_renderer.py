from __future__ import annotations

import html
import re
import unicodedata

import streamlit as st
import streamlit.components.v1 as components

from services.shared_document_view_service import quantity_with_unit, shipment_date
from utils.formatters import fmt_number


def render_document(case, packed, actual_rows=None) -> None:
    if not packed:
        st.warning('패킹 완료된 CTN 정보가 없어 최종문서를 출력할 수 없습니다.')
        return

    if case['domestic_method'] == '로젠택배':
        detail_label = '송장번호'
        detail_value = case['tracking_no'] or '-'
    elif case['domestic_method'] == '퀵배송':
        detail_label = '배송기사'
        detail_value = ' / '.join(part for part in [case['driver_name'], case['driver_phone']] if part) or '-'
    else:
        detail_label = '배송 상세'
        detail_value = '-'

    note_html = ''
    if case['note']:
        note_html = f'<div class="note-box"><b>특이사항</b><div>{html.escape(case["note"])}</div></div>'

    rows_html: list[str] = []
    grouped: dict[int, list] = {}
    for row in packed:
        grouped.setdefault(int(row['box_no']), []).append(row)
    for box_no, group in grouped.items():
        rowspan = len(group)
        for index, row in enumerate(group):
            rows_html.append('<tr>')
            if index == 0:
                rows_html.append(f'<td rowspan="{rowspan}" class="center merged">CTN {box_no}</td>')
            detail_values = [row['business_unit'], row['product_name'], row['lot_no'], row['expiry_date']]
            detail_classes = ['center', '', 'center', 'center']
            for value, css_class in zip(detail_values, detail_classes):
                class_attr = f' class="{css_class}"' if css_class else ''
                rows_html.append(f'<td{class_attr}>{html.escape(str(value or ""))}</td>')
            rows_html.append(f'<td class="right">{fmt_number(row["requested_qty"])}</td>')
            if index == 0:
                weight = f'{fmt_number(row["weight_kg"])} kg' if row['weight_kg'] else '-'
                size_values = [row['length_cm'], row['width_cm'], row['height_cm']]
                size = ' × '.join(fmt_number(value) for value in size_values) + ' cm' if all(size_values) else '-'
                rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{weight}</td>')
                rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{size}</td>')
            rows_html.append('</tr>')

    total_qty = sum(float(row['requested_qty'] or 0) for row in packed)
    box_weights = {int(row['box_no']): float(row['weight_kg'] or 0) for row in packed}
    total_weight = sum(box_weights.values())
    rows_html.append(
        '<tr class="total-row"><td colspan="5" class="right"><b>합계</b></td>'
        f'<td class="right"><b>{fmt_number(total_qty)}</b></td>'
        f'<td class="center"><b>{fmt_number(total_weight)} kg</b></td><td></td></tr>'
    )
    table_columns = '<colgroup><col style="width:10%"><col style="width:9%"><col style="width:24%"><col style="width:14%"><col style="width:12%"><col style="width:7%"><col style="width:9%"><col style="width:15%"></colgroup>'
    table_header = '<tr><th>CTN No.</th><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>수량</th><th>GW (kg)</th><th>CTN 사이즈</th></tr>'
    first_summary = f'{len({row["box_no"] for row in packed})} CTN'
    display_rows = packed
    item_count = len({str(row['product_name']).strip() for row in display_rows if str(row['product_name']).strip()})
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}} @page{{size:A4 portrait;margin:6mm}}
html,body{{margin:0;padding:0;background:#f4f7fa;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}} body{{padding:8px}}
.toolbar{{width:198mm;max-width:100%;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:8px;background:#173b5f;color:#fff;font-weight:700;padding:10px 18px;cursor:pointer}}
.document{{width:198mm;max-width:100%;margin:auto;background:#fff;border:0;border-radius:0;overflow:visible;box-shadow:none}}
.header{{padding:16px 22px;background:linear-gradient(135deg,#173b5f,#245d88);color:#fff;display:flex;justify-content:space-between;gap:16px}} .title{{font-size:20px;font-weight:800}} .sub{{font-size:9px;opacity:.8}} .number{{text-align:right}}
.body{{padding:12px 8px 10px}} .section{{font-size:13px;font-weight:800;color:#294f71;margin:0 0 3px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dce3eb;border-radius:7px;overflow:hidden;margin-bottom:7px}} .cell{{padding:5px 6px;border-right:1px solid #e5eaf0}} .label{{font-size:11px;color:#7c8797}} .value{{font-size:13px;font-weight:700;margin-top:2px;white-space:pre-wrap;word-break:break-word}}
.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:20px}} .card{{border:1px solid #dce3eb;border-radius:7px;padding:5px 7px;background:#f8fafc}} .card b{{font-size:16px;color:#214f76}}
.wrap{{width:100%;max-width:100%;margin:0 auto;overflow:hidden;border:1px solid #d8e0e8;border-radius:7px}} table{{border-collapse:collapse;width:100%;max-width:100%;min-width:0;table-layout:fixed;font-size:11.67px}} th{{background:#294f71;color:#fff;padding:6px 4px;text-align:center;white-space:nowrap;line-height:1.2}} td{{padding:6px 4px;border-right:1px solid #e0e6ed;border-bottom:1px solid #e0e6ed;vertical-align:middle;line-height:1.2;overflow-wrap:anywhere}} tr{{break-inside:avoid}} .center{{text-align:center}} .right{{text-align:right}} .merged{{background:#f5f8fb;font-weight:700;white-space:nowrap}} .total-row td{{background:#eef3f8;font-weight:700}}
.note-box{{width:100%;margin:6px auto 0;padding:5px 7px;border:1px solid #dce3eb;border-left:4px solid #294f71;border-radius:7px;font-size:8px}}
@media print{{html,body{{width:210mm;height:297mm;background:#fff;padding:0}} .toolbar{{display:none!important}} .document{{width:198mm;max-width:none;margin:0 auto}} .header,th,.merged,.total-row td{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="document"><div class="header"><div><div class="title">주문 정보 및 패킹 리스트</div><div class="sub">ORDER INFORMATION &amp; PACKING LIST</div></div><div class="number"><small>EXPORT NO.</small><br><b>{html.escape(case['export_no'])}</b></div></div>
<div class="body"><div class="section">EXPORT INFORMATION</div><div class="grid">
<div class="cell"><div class="label">국가 / Country</div><div class="value">{html.escape(case['country'] or '-')}</div></div>
<div class="cell"><div class="label">바이어 / Buyer</div><div class="value">{html.escape(case['buyer'] or '-')}</div></div>
<div class="cell"><div class="label">운송방식 / Transport</div><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div>
<div class="cell"><div class="label">출고일 / Ship Date</div><div class="value">{html.escape(shipment_date(case) or '-')}</div></div></div>
<div class="section">DOMESTIC DELIVERY</div><div class="grid">
<div class="cell"><div class="label">국내배송 방식</div><div class="value">{html.escape(case['domestic_method'] or '-')}</div></div>
<div class="cell"><div class="label">{html.escape(detail_label)}</div><div class="value">{html.escape(detail_value)}</div></div>
<div class="cell"><div class="label">수하인명</div><div class="value">{html.escape(case['consignee_name'] or '-')}</div></div>
<div class="cell"><div class="label">수하인주소</div><div class="value">{html.escape(case['consignee_address'] or '-')}</div></div></div>
<div class="section">PACKING SUMMARY</div><div class="summary"><div class="card"><small>총 CTN 수</small><br><b>{first_summary}</b></div><div class="card"><small>품목 수</small><br><b>{item_count} 품목</b></div><div class="card"><small>출고 수량</small><br><b>{fmt_number(total_qty)}</b></div></div>
<div class="section">PACKING LIST</div><div class="wrap"><table>{table_columns}<thead>{table_header}</thead><tbody>{''.join(rows_html)}</tbody></table></div>{note_html}</div></div></body></html>'''
    st.markdown(
        '''
        <style>
        div[data-testid="stElementContainer"]:has(iframe[title="streamlit_components.core.html"]),
        div[data-testid="stCustomComponentV1"]:has(iframe[title="streamlit_components.core.html"]) {
            width: 100vw !important;
            max-width: 100vw !important;
        }
        @media (max-width: 900px) {
            div[data-testid="stElementContainer"]:has(iframe[title="streamlit_components.core.html"]),
            div[data-testid="stCustomComponentV1"]:has(iframe[title="streamlit_components.core.html"]) {
                width: 100% !important;
                max-width: 100% !important;
            }
        }
        </style>
        ''',
        unsafe_allow_html=True,
    )
    components.html(document, height=min(1800, max(850, 760 + len(display_rows) * 44)), scrolling=True)


def render_shipment_product_list(case, actual_rows) -> None:
    destination_order = {
        '노투스팜': 0,
        '노투스': 1,
        'NOH': 2,
        '비자료': 3,
    }

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
                        f'<td rowspan="{product_rowspan}" class="product merged">'
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
.meta{{display:grid;grid-template-columns:repeat(3,1fr);margin:13px 16px 12px;border:1px solid #dce3eb}} .meta div{{padding:7px 8px;border-right:1px solid #e3e8ee}} .meta div:last-child{{border-right:0}} .label{{font-size:12px;color:#7c8797}} .value{{font-size:14px;font-weight:700;margin-top:2px;word-break:break-word}}
.content{{padding:0 16px 17px}} .summary{{width:133mm;max-width:100%;margin:0 auto 5px;font-size:8.8px;color:#697586;text-align:right}}
table{{width:133mm;max-width:100%;margin:0 auto;border-collapse:collapse;table-layout:fixed;font-size:9.2px;border:1px solid #cfd8e2}} col.destination{{width:18mm}} col.product{{width:43mm}} col.lot{{width:28mm}} col.expiry{{width:24mm}} col.qty{{width:12mm}} col.unit{{width:8mm}}
th{{background:#294f71;color:white;padding:6px 4px;text-align:center;font-weight:750}} td{{padding:5px 5px;border-right:1px solid #dce3ea;border-bottom:1px solid #dce3ea;vertical-align:middle;line-height:1.3}} .center{{text-align:center}} .right{{text-align:right}} .product{{white-space:normal;overflow-wrap:anywhere;word-break:keep-all;font-weight:700;text-align:left;padding-left:8px}} .destination{{font-weight:700}} .merged{{background:#f5f8fb}} .lot,.expiry,.unit{{white-space:nowrap}} .qty{{white-space:nowrap;font-weight:650;padding-left:3px;padding-right:3px}} .unit{{padding-left:2px;padding-right:2px}} .empty{{text-align:center;color:#8993a0;padding:20px}}
.notice{{padding:10px 20px 14px;font-size:8.2px;color:#788493;border-top:1px solid #e0e6ed}}
@media print{{html,body{{width:210mm;min-height:297mm;background:white;padding:0}} .toolbar{{display:none!important}} .sheet{{width:148mm;max-width:none;margin:0 auto;border:0;box-shadow:none}} .header{{padding:13px 15px 11px}} .title{{font-size:18px}} .meta{{margin:10px 8px}} .content{{padding:0 8px 12px}} .summary,table{{width:133mm;max-width:none}} table{{font-size:8.5px}} th{{padding:4px 3px}} td{{padding:4px}} .product{{padding-left:6px}} .qty,.unit{{padding-left:2px;padding-right:2px}} .notice{{padding:8px 15px 0}} .header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="sheet"><div class="header"><div class="title">출고 예정 제품 리스트</div><div class="export-no">EXPORT NO.<b>{html.escape(case['export_no'] or '-')}</b></div></div>
<div class="meta"><div><span class="label">국가 / Country</span><div class="value">{html.escape(case['country'] or '-')}</div></div><div><span class="label">바이어 / Buyer</span><div class="value">{html.escape(case['buyer'] or '-')}</div></div><div><span class="label">운송방식 / Transport</span><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div></div>
<div class="content"><div class="summary">총 {item_count}품목 · 제조번호 기준 {total_lines}행</div><table><colgroup><col class="destination"><col class="product"><col class="lot"><col class="expiry"><col class="qty"><col class="unit"></colgroup><thead><tr><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>출고수량</th><th>단위</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>
<div class="notice">본 문서는 패킹 완료 전 작성된 출고 예정 제품 목록이며, 최종 수량 및 패킹 정보는 변경될 수 있습니다.</div></div></body></html>'''
    components.html(document, height=min(1800, max(700, 500 + len(sorted_rows) * 38)), scrolling=True)


