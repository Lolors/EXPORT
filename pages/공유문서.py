from __future__ import annotations

import html
import streamlit as st
import streamlit.components.v1 as components

import db


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return '0'


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['transport_mode']} · {case['stage']}"


def packing_rows(case_id: int):
    return db.rows(
        '''SELECT s.box_no, s.business_unit, s.product_name, s.lot_no,
                  s.expiry_date, s.requested_qty, b.weight_kg, b.length_cm,
                  b.width_cm, b.height_cm
           FROM shipment_items s
           LEFT JOIN boxes b ON b.case_id=s.case_id AND b.box_no=s.box_no
           WHERE s.case_id=? AND s.box_no IS NOT NULL
           ORDER BY s.box_no, s.id''',
        (case_id,),
    )


def actual_shipment_rows(case_id: int):
    return db.rows(
        '''SELECT s.business_unit, s.product_name, s.lot_no,
                  s.expiry_date, s.requested_qty
           FROM shipment_items s
           WHERE s.case_id=? AND s.order_item_id IS NOT NULL
           ORDER BY s.id''',
        (case_id,),
    )


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

    status_text = '배송 완료' if case['actual_ship_date'] and case['domestic_method'] else '작성 중'
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
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">BOX {box_no}</td>')
                for value in [row['business_unit'], row['product_name'], row['lot_no'], row['expiry_date']]:
                    rows_html.append(f'<td>{html.escape(str(value or ""))}</td>')
                rows_html.append(f'<td class="right">{fmt_number(row["requested_qty"])}</td>')
                if index == 0:
                    weight = f'{fmt_number(row["weight_kg"])} kg' if row['weight_kg'] else '-'
                    size_values = [row['length_cm'], row['width_cm'], row['height_cm']]
                    size = ' × '.join(fmt_number(v) for v in size_values) + ' cm' if all(size_values) else '-'
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{weight}</td>')
                    rows_html.append(f'<td rowspan="{rowspan}" class="center merged">{size}</td>')
                rows_html.append('</tr>')

        table_header = '<tr><th>박스</th><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>수량</th><th>무게</th><th>박스사이즈</th></tr>'
        section_title = 'PACKING DETAIL'
        first_summary = f'{len({row["box_no"] for row in packed})} BOX'
        first_label = '총 박스 수'
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
*{{box-sizing:border-box}} @page{{size:A4;margin:12mm}}
body{{margin:0;padding:8px;background:#f4f7fa;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}}
.toolbar{{max-width:1180px;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:8px;background:#173b5f;color:#fff;font-weight:700;padding:10px 18px;cursor:pointer}}
.document{{max-width:1180px;margin:auto;background:#fff;border:1px solid #d8dee8;border-radius:14px;overflow:hidden;box-shadow:0 12px 34px rgba(30,45,70,.08)}}
.header{{padding:30px 38px;background:linear-gradient(135deg,#173b5f,#245d88);color:#fff;display:flex;justify-content:space-between;gap:20px}} .title{{font-size:28px;font-weight:800}} .sub{{font-size:12px;opacity:.8}} .number{{text-align:right}}
.body{{padding:28px 38px 36px}} .section{{font-size:13px;font-weight:800;color:#294f71;margin:0 0 10px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dce3eb;border-radius:9px;overflow:hidden;margin-bottom:22px}} .cell{{padding:12px 14px;border-right:1px solid #e5eaf0}} .label{{font-size:10px;color:#7c8797}} .value{{font-size:13px;font-weight:700;margin-top:4px}}
.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:23px}} .card{{border:1px solid #dce3eb;border-radius:9px;padding:14px 16px;background:#f8fafc}} .card b{{font-size:20px;color:#214f76}}
.wrap{{overflow-x:auto;border:1px solid #d8e0e8;border-radius:9px}} table{{border-collapse:collapse;width:100%;min-width:{'900px' if has_packing else '680px'};font-size:11px}} th{{background:#294f71;color:#fff;padding:10px;text-align:left}} td{{padding:10px;border-right:1px solid #e0e6ed;border-bottom:1px solid #e0e6ed;vertical-align:middle}} .center{{text-align:center}} .right{{text-align:right}} .merged{{background:#f5f8fb;font-weight:700}} .empty{{text-align:center;color:#8993a0;padding:28px}}
.note-box{{margin-top:20px;padding:13px 15px;border:1px solid #dce3eb;border-left:4px solid #294f71;border-radius:7px}} .footer{{margin-top:25px;padding-top:12px;border-top:1px solid #e2e7ed;color:#8a94a1;font-size:10px;display:flex;justify-content:space-between}}
@media print{{body{{background:#fff;padding:0}} .toolbar{{display:none!important}} .document{{border:0;border-radius:0;box-shadow:none;max-width:none}} .header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}} .wrap{{overflow:visible}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="document"><div class="header"><div><div class="sub">EXPORT LOGISTICS DOCUMENT</div><div class="title">국내배송 및 패킹 내역서</div><div class="sub">Domestic Delivery & Packing Summary</div></div><div class="number"><small>EXPORT NO.</small><br><b>{html.escape(case['export_no'])}</b><br>{status_text}</div></div>
<div class="body"><div class="section">EXPORT INFORMATION</div><div class="grid">
<div class="cell"><div class="label">국가 / Country</div><div class="value">{html.escape(case['country'] or '-')}</div></div>
<div class="cell"><div class="label">바이어 / Buyer</div><div class="value">{html.escape(case['buyer'] or '-')}</div></div>
<div class="cell"><div class="label">운송방식 / Transport</div><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div>
<div class="cell"><div class="label">실제출고일 / Ship Date</div><div class="value">{html.escape(case['actual_ship_date'] or '-')}</div></div></div>
<div class="section">DOMESTIC DELIVERY</div><div class="grid"><div class="cell"><div class="label">국내배송 방식</div><div class="value">{html.escape(case['domestic_method'] or '-')}</div></div><div class="cell" style="grid-column:span 2"><div class="label">{detail_label}</div><div class="value">{html.escape(detail_value)}</div></div><div class="cell"><div class="label">현재 단계</div><div class="value">{html.escape(case['stage'] or '-')}</div></div></div>
<div class="section">{'PACKING SUMMARY' if has_packing else 'SHIPPING SUMMARY'}</div><div class="summary"><div class="card"><small>{first_label}</small><br><b>{first_summary}</b></div><div class="card"><small>실제 제품 수</small><br><b>{item_count} 품목</b></div><div class="card"><small>실제 출고수량</small><br><b>{fmt_number(total_qty)}</b></div></div>
<div class="section">{section_title}</div><div class="wrap"><table><thead>{table_header}</thead><tbody>{''.join(rows_html)}</tbody></table></div>{note_html}<div class="footer"><span>주식회사 노투스팜 · 수출관리 시스템</span><span>Generated from Export Management System</span></div></div></div></body></html>'''

    visible_rows = len(display_rows)
    components.html(document, height=min(1800, max(850, 760 + visible_rows * 44)), scrolling=True)


st.title('공유문서')
st.caption('국내배송 정보와 실제 출고제품 또는 패킹 내역을 문서로 출력합니다.')

cases = db.rows(
    "SELECT * FROM export_cases WHERE status<>'취소' AND stage<>'취소' ORDER BY COALESCE(NULLIF(actual_ship_date,''),created_at) DESC"
)
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='document_case')]
case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
packed = packing_rows(case_id)
actual_rows = actual_shipment_rows(case_id)
render_document(case, packed, actual_rows)
