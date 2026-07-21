from __future__ import annotations

from datetime import date
import html

import streamlit as st
import streamlit.components.v1 as components

import db


st.set_page_config(page_title='국내배송 공유문서', page_icon='📄', layout='wide')
db.init_db()


def date_value(value: str | None):
    parsed = db.parse_date(value)
    return parsed.date() if parsed else date.today()


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['transport_mode']} · {case['stage']}"


def packing_rows(case_id: int):
    return db.rows(
        '''SELECT s.box_no, s.business_unit, s.product_name, s.lot_no, s.expiry_date,
                  s.requested_qty, b.weight_kg, b.length_cm, b.width_cm, b.height_cm
           FROM shipment_items s
           LEFT JOIN boxes b ON b.case_id=s.case_id AND b.box_no=s.box_no
           WHERE s.case_id=? AND s.box_no IS NOT NULL
           ORDER BY s.box_no, s.id''',
        (case_id,),
    )


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return ''


def render_document(case, rows) -> None:
    box_numbers = {row['box_no'] for row in rows if row['box_no'] is not None}
    product_names = {str(row['product_name']).strip() for row in rows if str(row['product_name']).strip()}
    total_qty = sum(float(row['requested_qty'] or 0) for row in rows)

    if case['domestic_method'] == '로젠택배':
        delivery_detail_label = '송장번호'
        delivery_detail = case['tracking_no'] or '-'
    elif case['domestic_method'] == '퀵배송':
        delivery_detail_label = '배송기사'
        delivery_detail = ' / '.join(part for part in [case['driver_name'], case['driver_phone']] if part) or '-'
    else:
        delivery_detail_label = '배송 상세'
        delivery_detail = '-'

    status_text = '배송 완료' if case['actual_ship_date'] and case['domestic_method'] else '작성 중'
    note_html = ''
    if case['note']:
        note_html = f'<div class="note-box"><div class="note-title">특이사항</div><div>{html.escape(case["note"])}</div></div>'

    table_parts = []
    grouped: dict[int, list] = {}
    for row in rows:
        grouped.setdefault(int(row['box_no']), []).append(row)

    for box_no, group in grouped.items():
        rowspan = len(group)
        for index, row in enumerate(group):
            table_parts.append('<tr>')
            if index == 0:
                table_parts.append(f'<td class="center merged" rowspan="{rowspan}">BOX {box_no}</td>')
            table_parts.append(f'<td>{html.escape(str(row["business_unit"] or ""))}</td>')
            table_parts.append(f'<td class="product">{html.escape(str(row["product_name"] or ""))}</td>')
            table_parts.append(f'<td>{html.escape(str(row["lot_no"] or ""))}</td>')
            table_parts.append(f'<td class="center">{html.escape(str(row["expiry_date"] or ""))}</td>')
            table_parts.append(f'<td class="right">{fmt_number(row["requested_qty"])}</td>')
            if index == 0:
                weight = f'{fmt_number(row["weight_kg"])} kg' if row['weight_kg'] else '-'
                size_values = [row['length_cm'], row['width_cm'], row['height_cm']]
                size = ' × '.join(fmt_number(value) for value in size_values) + ' cm' if all(size_values) else '-'
                table_parts.append(f'<td class="center merged" rowspan="{rowspan}">{weight}</td>')
                table_parts.append(f'<td class="center merged" rowspan="{rowspan}">{size}</td>')
            table_parts.append('</tr>')

    if not table_parts:
        table_parts.append('<tr><td colspan="8" class="empty">패킹된 제품이 없습니다.</td></tr>')

    document = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{box-sizing:border-box;}}
body {{margin:0; padding:8px; background:#f4f7fa; color:#172033; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif;}}
.export-document {{max-width:1180px; margin:0 auto 28px; background:#fff; border:1px solid #d8dee8; border-radius:14px; box-shadow:0 12px 34px rgba(30,45,70,.08); overflow:hidden;}}
.doc-header {{padding:34px 40px 28px; background:linear-gradient(135deg,#173b5f,#245d88); color:#fff; display:flex; justify-content:space-between; gap:24px; align-items:flex-start;}}
.doc-kicker {{font-size:12px; letter-spacing:2.2px; opacity:.75; font-weight:700;}}
.doc-title {{font-size:29px; font-weight:800; margin-top:7px;}}
.doc-subtitle {{font-size:13px; opacity:.78; margin-top:4px;}}
.doc-number {{text-align:right; min-width:220px;}}
.doc-number strong {{font-size:17px;}}
.status-pill {{display:inline-block; margin-top:10px; padding:6px 12px; border-radius:999px; background:rgba(255,255,255,.16); font-size:12px; font-weight:700;}}
.doc-body {{padding:30px 40px 38px;}}
.section-title {{font-size:13px; font-weight:800; color:#294f71; letter-spacing:.7px; margin:2px 0 11px;}}
.info-grid {{display:grid; grid-template-columns:repeat(4,1fr); border:1px solid #dce3eb; border-radius:9px; overflow:hidden; margin-bottom:24px;}}
.info-cell {{padding:13px 15px; border-right:1px solid #e5eaf0;}}
.info-cell:last-child {{border-right:none;}}
.info-label {{font-size:11px; color:#7c8797; margin-bottom:5px;}}
.info-value {{font-size:14px; font-weight:700; color:#1b2738; word-break:break-word;}}
.summary-grid {{display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:25px;}}
.summary-card {{border:1px solid #dce3eb; border-radius:9px; padding:15px 17px; background:#f8fafc;}}
.summary-label {{font-size:11px; color:#7b8795;}}
.summary-value {{font-size:21px; font-weight:800; color:#214f76; margin-top:3px;}}
.table-wrap {{overflow-x:auto; border:1px solid #d8e0e8; border-radius:9px;}}
.doc-table {{border-collapse:collapse; width:100%; min-width:920px; font-size:12px;}}
.doc-table th {{background:#294f71; color:#fff; padding:11px 10px; font-weight:700; text-align:left;}}
.doc-table td {{padding:11px 10px; border-right:1px solid #e0e6ed; border-bottom:1px solid #e0e6ed; vertical-align:middle;}}
.doc-table tr:last-child td {{border-bottom:none;}}
.doc-table td:last-child,.doc-table th:last-child {{border-right:none;}}
.doc-table .merged {{background:#f5f8fb; font-weight:700;}}
.doc-table .center {{text-align:center;}}
.doc-table .right {{text-align:right;}}
.doc-table .product {{font-weight:650;}}
.empty {{text-align:center; color:#7a8491; padding:28px !important;}}
.note-box {{margin-top:22px; border:1px solid #dce3eb; border-left:4px solid #294f71; border-radius:7px; padding:14px 16px; background:#fafbfd; font-size:13px;}}
.note-title {{font-size:11px; color:#778493; font-weight:800; margin-bottom:5px;}}
.doc-footer {{display:flex; justify-content:space-between; margin-top:28px; padding-top:14px; border-top:1px solid #e2e7ed; color:#8a94a1; font-size:10px;}}
@media print {{body {{background:#fff; padding:0;}} .export-document {{box-shadow:none; border:none; margin:0; max-width:none;}} .doc-header,.doc-table th {{-webkit-print-color-adjust:exact; print-color-adjust:exact;}}}}
@media(max-width:800px) {{.doc-header {{padding:25px 22px; flex-direction:column;}} .doc-number {{text-align:left;}} .doc-body {{padding:22px;}} .info-grid {{grid-template-columns:1fr 1fr;}} .info-cell {{border-bottom:1px solid #e5eaf0;}} .summary-grid {{grid-template-columns:1fr;}}}}
</style>
</head>
<body>
<div class="export-document">
  <div class="doc-header">
    <div>
      <div class="doc-kicker">EXPORT LOGISTICS DOCUMENT</div>
      <div class="doc-title">국내배송 및 패킹 내역서</div>
      <div class="doc-subtitle">Domestic Delivery & Packing Summary</div>
    </div>
    <div class="doc-number">
      <div style="font-size:11px;opacity:.72">EXPORT NO.</div>
      <strong>{html.escape(case['export_no'])}</strong><br>
      <span class="status-pill">{status_text}</span>
    </div>
  </div>
  <div class="doc-body">
    <div class="section-title">EXPORT INFORMATION</div>
    <div class="info-grid">
      <div class="info-cell"><div class="info-label">국가 / Country</div><div class="info-value">{html.escape(case['country'] or '-')}</div></div>
      <div class="info-cell"><div class="info-label">바이어 / Buyer</div><div class="info-value">{html.escape(case['buyer'] or '-')}</div></div>
      <div class="info-cell"><div class="info-label">운송방식 / Transport</div><div class="info-value">{html.escape(case['transport_mode'] or '-')}</div></div>
      <div class="info-cell"><div class="info-label">실제출고일 / Ship Date</div><div class="info-value">{html.escape(case['actual_ship_date'] or '-')}</div></div>
    </div>
    <div class="section-title">DOMESTIC DELIVERY</div>
    <div class="info-grid">
      <div class="info-cell"><div class="info-label">국내배송 방식</div><div class="info-value">{html.escape(case['domestic_method'] or '-')}</div></div>
      <div class="info-cell" style="grid-column:span 2"><div class="info-label">{delivery_detail_label}</div><div class="info-value">{html.escape(delivery_detail)}</div></div>
      <div class="info-cell"><div class="info-label">현재 단계</div><div class="info-value">{html.escape(case['stage'] or '-')}</div></div>
    </div>
    <div class="section-title">PACKING SUMMARY</div>
    <div class="summary-grid">
      <div class="summary-card"><div class="summary-label">총 박스 수</div><div class="summary-value">{len(box_numbers)} BOX</div></div>
      <div class="summary-card"><div class="summary-label">총 품목 수</div><div class="summary-value">{len(product_names)} 품목</div></div>
      <div class="summary-card"><div class="summary-label">총 수량</div><div class="summary-value">{fmt_number(total_qty)} EA</div></div>
    </div>
    <div class="section-title">PACKING DETAIL</div>
    <div class="table-wrap">
      <table class="doc-table">
        <thead><tr><th>박스</th><th>사업장</th><th>제품명</th><th>LOT</th><th>유통기한</th><th>수량</th><th>무게</th><th>박스사이즈</th></tr></thead>
        <tbody>{''.join(table_parts)}</tbody>
      </table>
    </div>
    {note_html}
    <div class="doc-footer"><span>주식회사 노투스팜 · 수출관리 시스템</span><span>Generated from Export Management System</span></div>
  </div>
</div>
</body>
</html>'''

    document_height = min(1600, max(760, 680 + len(rows) * 42))
    components.html(document, height=document_height, scrolling=True)


st.title('국내배송 공유문서')
st.caption('국내배송 정보를 입력하고, 공유하기 좋은 문서 형태로 확인합니다.')

cases = db.rows(
    "SELECT * FROM export_cases WHERE status<>'취소' AND stage<>'취소' ORDER BY COALESCE(NULLIF(actual_ship_date,''), NULLIF(expected_ship_date,''), created_at) DESC"
)
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
selected_label = st.selectbox('수출 건 선택', list(options), key='delivery_document_case')
case_id = options[selected_label]
case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
rows = packing_rows(case_id)

edit_tab, document_tab = st.tabs(['배송정보 입력', '공유용 문서'])

with edit_tab:
    st.markdown('#### 국내배송 정보')
    method = st.radio(
        '배송 방식',
        ['로젠택배', '퀵배송'],
        index=1 if case['domestic_method'] == '퀵배송' else 0,
        horizontal=True,
        key=f'doc_delivery_method_{case_id}',
    )
    with st.form(f'doc_delivery_form_{case_id}_{method}'):
        actual_ship_date = st.date_input('국내배송 일자', value=date_value(case['actual_ship_date']))
        tracking = ''
        driver = ''
        phone = ''
        if method == '로젠택배':
            tracking = st.text_input('송장번호', value=case['tracking_no'] or '')
        else:
            c1, c2 = st.columns(2)
            driver = c1.text_input('배송기사 이름', value=case['driver_name'] or '')
            phone = c2.text_input('연락처', value=case['driver_phone'] or '')

        submitted = st.form_submit_button('배송정보 저장 및 완료 처리', type='primary')

    if submitted:
        if method == '로젠택배':
            driver = ''
            phone = ''
        else:
            tracking = ''
        db.execute(
            "UPDATE export_cases SET domestic_method=?,tracking_no=?,driver_name=?,driver_phone=?,actual_ship_date=?,stage='국내배송',status='완료',updated_at=? WHERE id=?",
            (method, tracking, driver, phone, str(actual_ship_date), db.now_text(), case_id),
        )
        folder = db.sync_case_folder(case_id)
        db.add_history(case_id, '국내배송 완료', f'{method} / {folder}')
        st.success(f'저장했습니다. 폴더도 국내배송 일자에 맞게 정리했습니다.\n\n{folder}')
        st.rerun()

    st.markdown('#### 패킹 현황')
    if rows:
        st.caption(f'총 {len({row["box_no"] for row in rows})}박스 · {len(rows)}개 패킹 행')
    else:
        st.warning('패킹된 제품이 없습니다.')

with document_tab:
    toolbar1, toolbar2 = st.columns([1, 3])
    with toolbar1:
        st.button('문서 새로고침', on_click=lambda: None, use_container_width=True)
    with toolbar2:
        st.caption('공유할 때는 브라우저의 인쇄 기능(Ctrl+P)에서 PDF로 저장할 수 있습니다.')
    render_document(case, rows)
