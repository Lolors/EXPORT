from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from services import document_service, export_service
from utils.formatters import case_label, fmt_number


STAGE_LABELS = {
    '주문 접수': '주문 접수',
    '주문 입력': '주문 접수',
    '제품 준비': '제품 준비',
    '실출고 입력': '출고 대기',
    '출고 대기': '출고 대기',
    '패킹': '패킹',
    '박스 패킹': '패킹',
    '패킹 진행': '패킹 진행',
    '패킹 완료': '패킹 완료',
    '국내배송': '국내배송',
    '선적 준비': '선적 준비',
    '선적 완료': '선적 완료',
    '완료': '완료',
    '취소': '주문 취소',
    '주문 취소': '주문 취소',
}


def display_stage(value: object) -> str:
    stage = str(value or '').strip()
    return STAGE_LABELS.get(stage, stage or '-')


def render_document(case, packed, actual_rows) -> None:
    has_packing = bool(packed)

    if case['domestic_method'] == '로젠택배':
        detail_label = '송장번호'
        detail_value = case['tracking_no'] or '-'
    elif case['domestic_method'] == '퀵배송':
        detail_label = '배송기사'
        detail_value = ' / '.join(part for part in [case['driver_name'], case['driver_phone']] if part) or '-'
    else:
        detail_label = '배송 상세'
        detail_value = '-'

    status_text = display_stage(case['stage'])
    note_html = ''
    if case['note']:
        note_html = f'<div class="note-box"><b>특이사항</b><div>{html.escape(case["note"])}</div></div>'

    rows_html: list[str] = []
    if has_packing:
        grouped: dict[int, list] = {}
        for row in packed:
            grouped.setdefault(int(row['box_no']), []).append(row)

        for box_no, group in grouped.items():
            rowspan = len(group)
            for index, row in enumerate(group):
                rows_html.append('<tr>')
                if index == 0:
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">CTN {box_no}</td>')
                for value in [row['business_unit'], row['product_name'], row['lot_no'], row['expiry_date']]:
                    rows_html.append(f'<td>{html.escape(str(value or ""))}</td>')
                rows_html.append(f'<td class="right">{fmt_number(row["requested_qty"])}</td>')
                if index == 0:
                    weight = f'{fmt_number(row["weight_kg"])} kg' if row['weight_kg'] else '-'
                    size_values = [row['length_cm'], row['width_cm'], row['height_cm']]
                    size = ' × '.join(fmt_number(value) for value in size_values) + ' cm' if all(size_values) else '-'
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{weight}</td>')
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{size}</td>')
                rows_html.append('</tr>')

        total_qty = sum(float(row['requested_qty'] or 0) for row in packed)
        box_weights = {
            int(row['box_no']): float(row['weight_kg'] or 0)
            for row in packed
        }
        total_weight = sum(box_weights.values())
        rows_html.append(
            '<tr class="total-row">'
            '<td colspan="5" class="right"><b>합계</b></td>'
            f'<td class="right"><b>{fmt_number(total_qty)}</b></td>'
            f'<td class="center"><b>{fmt_number(total_weight)} kg</b></td>'
            '<td></td>'
            '</tr>'
        )

        table_header = '<tr><th>CTN No.</th><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>수량</th><th>GW (kg)</th><th>CTN 사이즈</th></tr>'
        section_title = 'PACKING LIST'
        first_summary = f'{len({row["box_no"] for row in packed})} CTN'
        first_label = '총 CTN 수'
        display_rows = packed
    else:
        for row in actual_rows:
            rows_html.append('<tr>')
            for value in [row['business_unit'], row['product_name'], row['lot_no'], row['expiry_date']]:
                rows_html.append(f'<td>{html.escape(str(value or ""))}</td>')
            rows_html.append(f'<td class="right">{fmt_number(row["requested_qty"])}</td>')
            rows_html.append('</tr>')

        if not rows_html:
            rows_html.append('<tr><td colspan="5" class="empty">입력된 실제 출고제품이 없습니다.</td></tr>')

        table_header = '<tr><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>출고수량</th></tr>'
        section_title = 'PACKING LIST'
        first_summary = '패킹 전'
        first_label = '진행 상태'
        display_rows = actual_rows

    item_count = len({str(row['product_name']).strip() for row in display_rows if str(row['product_name']).strip()})
    total_qty = sum(float(row['requested_qty'] or 0) for row in display_rows)

    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}} @page{{size:A4 portrait;margin:6mm}}
html,body{{margin:0;padding:0;background:#f4f7fa;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}}
body{{padding:8px}}
.toolbar{{max-width:1180px;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:8px;background:#173b5f;color:#fff;font-weight:700;padding:10px 18px;cursor:pointer}}
.document{{max-width:1180px;margin:auto;background:#fff;border:1px solid #d8dee8;border-radius:14px;overflow:hidden;box-shadow:0 12px 34px rgba(30,45,70,.08)}}
.header{{padding:30px 38px;background:linear-gradient(135deg,#173b5f,#245d88);color:#fff;display:flex;justify-content:space-between;gap:18px}} .title{{font-size:28px;font-weight:800}} .sub{{font-size:12px;opacity:.8}} .number{{text-align:right}}
.body{{padding:28px 38px 32px}} .section{{font-size:13px;font-weight:800;color:#294f71;margin:0 0 9px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dce3eb;border-radius:8px;overflow:hidden;margin-bottom:18px}} .cell{{padding:11px 13px;border-right:1px solid #e5eaf0}} .label{{font-size:9.5px;color:#7c8797}} .value{{font-size:12.5px;font-weight:700;margin-top:3px}}
.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:19px}} .card{{border:1px solid #dce3eb;border-radius:8px;padding:12px 14px;background:#f8fafc}} .card b{{font-size:18px;color:#214f76}}
.wrap{{overflow-x:auto;border:1px solid #d8e0e8;border-radius:8px}} table{{border-collapse:collapse;width:100%;min-width:{'900px' if has_packing else '680px'};font-size:10.5px}} th{{background:#294f71;color:#fff;padding:8px 9px;text-align:left}} td{{padding:8px 9px;border-right:1px solid #e0e6ed;border-bottom:1px solid #e0e6ed;vertical-align:middle}} .center{{text-align:center}} .right{{text-align:right}} .merged{{background:#f5f8fb;font-weight:700}} .empty{{text-align:center;color:#8993a0;padding:24px}} .total-row td{{background:#eef3f8;font-weight:700}}
.note-box{{margin-top:15px;padding:11px 13px;border:1px solid #dce3eb;border-left:4px solid #294f71;border-radius:7px;font-size:10.5px}}
@media print{{
  html,body{{width:210mm;height:297mm;background:#fff;padding:0;overflow:hidden}}
  .toolbar{{display:none!important}}
  .document{{width:198mm;height:285mm;max-width:none;margin:0 auto;border:0;border-radius:0;box-shadow:none;display:flex;flex-direction:column;overflow:hidden}}
  .header{{padding:25px 30px;flex:0 0 auto}}
  .title{{font-size:25px}}
  .body{{padding:22px 30px 24px;flex:1 1 auto;display:flex;flex-direction:column}}
  .grid{{margin-bottom:14px}}
  .cell{{padding:9px 11px}}
  .summary{{margin-bottom:15px}}
  .card{{padding:10px 12px}}
  .card b{{font-size:16px}}
  .section{{margin-bottom:6px}}
  .wrap{{overflow:visible;flex:1 1 auto;display:flex}}
  table{{min-width:0;width:100%;height:100%;font-size:9.5px;table-layout:auto}}
  thead{{height:auto}}
  tbody{{height:100%}}
  tbody tr{{height:auto}}
  th,td{{padding:6px 7px}}
  .note-box{{margin-top:10px;padding:8px 10px}}
  .header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="document"><div class="header"><div><div class="title">주문 정보 및 패킹 리스트</div><div class="sub">ORDER INFORMATION &amp; PACKING LIST</div></div><div class="number"><small>EXPORT NO.</small><br><b>{html.escape(case['export_no'])}</b><br>{html.escape(status_text)}</div></div>
<div class="body"><div class="section">EXPORT INFORMATION</div><div class="grid">
<div class="cell"><div class="label">국가 / Country</div><div class="value">{html.escape(case['country'] or '-')}</div></div>
<div class="cell"><div class="label">바이어 / Buyer</div><div class="value">{html.escape(case['buyer'] or '-')}</div></div>
<div class="cell"><div class="label">운송방식 / Transport</div><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div>
<div class="cell"><div class="label">실제출고일 / Ship Date</div><div class="value">{html.escape(case['actual_ship_date'] or '-')}</div></div></div>
<div class="section">DOMESTIC DELIVERY</div><div class="grid"><div class="cell"><div class="label">국내배송 방식</div><div class="value">{html.escape(case['domestic_method'] or '-')}</div></div><div class="cell" style="grid-column:span 2"><div class="label">{detail_label}</div><div class="value">{html.escape(detail_value)}</div></div><div class="cell"><div class="label">현재 단계</div><div class="value">{html.escape(status_text)}</div></div></div>
<div class="section">{'PACKING SUMMARY' if has_packing else 'SHIPPING SUMMARY'}</div><div class="summary"><div class="card"><small>{first_label}</small><br><b>{first_summary}</b></div><div class="card"><small>품목 수</small><br><b>{item_count} 품목</b></div><div class="card"><small>출고 수량</small><br><b>{fmt_number(total_qty)}</b></div></div>
<div class="section">{section_title}</div><div class="wrap"><table><thead>{table_header}</thead><tbody>{''.join(rows_html)}</tbody></table></div>{note_html}</div></div></body></html>'''

    visible_rows = len(display_rows)
    components.html(document, height=min(1800, max(850, 760 + visible_rows * 44)), scrolling=True)


st.title('공유문서')
st.caption('국내배송 정보와 실제 출고제품 또는 패킹 내역을 문서로 출력합니다.')

cases = export_service.list_cases()
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

options = {
    f"{case['transport_mode']} · {case_label(case)}": int(case['id'])
    for case in cases
}
case_id = options[st.selectbox('수출 건 선택', list(options), key='document_case')]
case = export_service.get_case(case_id)
packed, actual_rows = document_service.get_document_data(case_id)
render_document(case, packed, actual_rows)
