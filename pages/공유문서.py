from __future__ import annotations

import html
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from services import document_service, export_service, folder_service, order_service, shipment_service
from utils.formatters import fmt_number


STAGE_LABELS = {
    '주문 접수': '주문 접수',
    '주문 입력': '주문 접수',
    '제품 준비': '제품 준비',
    '실출고 입력': '출고 대기',
    '출고 대기': '출고 대기',
    '패킹': '패킹',
    '박스 패킹': '패킹',
    '패킹 진행': '패킹 진행',
    '패킹 대기': '패킹 대기',
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


def summarize_product_names(raw_names: object) -> str:
    names = [name.strip() for name in re.split(r'[,\n]+', str(raw_names or '')) if name.strip()]
    if len(names) <= 2:
        return ', '.join(names)
    return f"{', '.join(names[:2])} 외 {len(names) - 2}품목"


def quantity_with_unit(row) -> str:
    quantity = fmt_number(row['requested_qty'])
    try:
        unit = str(row['unit'] or '').strip()
    except (KeyError, IndexError):
        unit = ''
    return f'{quantity} {unit}'.strip()


def _shipment_date(case) -> str:
    return str(case['actual_ship_date'] or '').strip()


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
    box_weights = {int(row['box_no']): float(row['weight_kg'] or 0) for row in packed}
    total_weight = sum(box_weights.values())
    rows_html.append(
        '<tr class="total-row"><td colspan="5" class="right"><b>합계</b></td>'
        f'<td class="right"><b>{fmt_number(total_qty)}</b></td>'
        f'<td class="center"><b>{fmt_number(total_weight)} kg</b></td><td></td></tr>'
    )
    table_header = '<tr><th>CTN No.</th><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>수량</th><th>GW (kg)</th><th>CTN 사이즈</th></tr>'
    first_summary = f'{len({row["box_no"] for row in packed})} CTN'
    display_rows = packed
    item_count = len({str(row['product_name']).strip() for row in display_rows if str(row['product_name']).strip()})

    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}} @page{{size:A4 portrait;margin:6mm}}
html,body{{margin:0;padding:0;background:#f4f7fa;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}} body{{padding:8px}}
.toolbar{{max-width:1180px;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:8px;background:#173b5f;color:#fff;font-weight:700;padding:10px 18px;cursor:pointer}}
.document{{max-width:1180px;margin:auto;background:#fff;border:1px solid #d8dee8;border-radius:14px;overflow:hidden;box-shadow:0 12px 34px rgba(30,45,70,.08)}}
.header{{padding:30px 38px;background:linear-gradient(135deg,#173b5f,#245d88);color:#fff;display:flex;justify-content:space-between;gap:18px}} .title{{font-size:28px;font-weight:800}} .sub{{font-size:12px;opacity:.8}} .number{{text-align:right}}
.body{{padding:28px 38px 32px}} .section{{font-size:13px;font-weight:800;color:#294f71;margin:0 0 9px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dce3eb;border-radius:8px;overflow:hidden;margin-bottom:18px}} .cell{{padding:11px 13px;border-right:1px solid #e5eaf0}} .label{{font-size:9.5px;color:#7c8797}} .value{{font-size:12.5px;font-weight:700;margin-top:3px;white-space:pre-wrap;word-break:break-word}}
.summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:19px}} .card{{border:1px solid #dce3eb;border-radius:8px;padding:12px 14px;background:#f8fafc}} .card b{{font-size:18px;color:#214f76}}
.wrap{{overflow-x:auto;border:1px solid #d8e0e8;border-radius:8px}} table{{border-collapse:collapse;width:100%;min-width:900px;font-size:10.5px}} th{{background:#294f71;color:#fff;padding:8px 9px;text-align:left}} td{{padding:8px 9px;border-right:1px solid #e0e6ed;border-bottom:1px solid #e0e6ed;vertical-align:middle}} .center{{text-align:center}} .right{{text-align:right}} .merged{{background:#f5f8fb;font-weight:700}} .total-row td{{background:#eef3f8;font-weight:700}}
.note-box{{margin-top:15px;padding:11px 13px;border:1px solid #dce3eb;border-left:4px solid #294f71;border-radius:7px;font-size:10.5px}}
@media print{{html,body{{width:210mm;min-height:297mm;background:#fff;padding:0}} .toolbar{{display:none!important}} .document{{width:198mm;max-width:none;margin:0 auto;border:0;border-radius:0;box-shadow:none;overflow:visible}} .header{{padding:25px 30px}} .title{{font-size:25px}} .body{{padding:22px 30px 24px}} .grid{{margin-bottom:14px}} .cell{{padding:9px 11px}} .summary{{margin-bottom:15px}} .card{{padding:10px 12px}} .card b{{font-size:16px}} .section{{margin-bottom:6px}} .wrap{{overflow:visible}} table{{min-width:0;width:100%;font-size:9.5px;table-layout:auto}} th{{padding:6px 7px}} td{{padding:6px 7px;line-height:1.35}} .note-box{{margin-top:10px;padding:8px 10px}} .header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="document"><div class="header"><div><div class="title">주문 정보 및 패킹 리스트</div><div class="sub">ORDER INFORMATION &amp; PACKING LIST</div></div><div class="number"><small>EXPORT NO.</small><br><b>{html.escape(case['export_no'])}</b></div></div>
<div class="body"><div class="section">EXPORT INFORMATION</div><div class="grid">
<div class="cell"><div class="label">국가 / Country</div><div class="value">{html.escape(case['country'] or '-')}</div></div>
<div class="cell"><div class="label">바이어 / Buyer</div><div class="value">{html.escape(case['buyer'] or '-')}</div></div>
<div class="cell"><div class="label">운송방식 / Transport</div><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div>
<div class="cell"><div class="label">실제출고일 / Ship Date</div><div class="value">{html.escape(_shipment_date(case) or '-')}</div></div></div>
<div class="section">DOMESTIC DELIVERY</div><div class="grid">
<div class="cell"><div class="label">국내배송 방식</div><div class="value">{html.escape(case['domestic_method'] or '-')}</div></div>
<div class="cell"><div class="label">{html.escape(detail_label)}</div><div class="value">{html.escape(detail_value)}</div></div>
<div class="cell"><div class="label">수하인명</div><div class="value">{html.escape(case['consignee_name'] or '-')}</div></div>
<div class="cell"><div class="label">수하인주소</div><div class="value">{html.escape(case['consignee_address'] or '-')}</div></div></div>
<div class="section">PACKING SUMMARY</div><div class="summary"><div class="card"><small>총 CTN 수</small><br><b>{first_summary}</b></div><div class="card"><small>품목 수</small><br><b>{item_count} 품목</b></div><div class="card"><small>출고 수량</small><br><b>{fmt_number(total_qty)}</b></div></div>
<div class="section">PACKING LIST</div><div class="wrap"><table><thead>{table_header}</thead><tbody>{''.join(rows_html)}</tbody></table></div>{note_html}</div></div></body></html>'''
    components.html(document, height=min(1800, max(850, 760 + len(display_rows) * 44)), scrolling=True)


def render_shipment_product_list(case, actual_rows) -> None:
    grouped: dict[str, list] = {}
    for row in actual_rows:
        grouped.setdefault(str(row['product_name'] or '').strip() or '-', []).append(row)

    rows_html: list[str] = []
    for product_name, rows in grouped.items():
        rowspan = len(rows)
        for index, row in enumerate(rows):
            rows_html.append('<tr>')
            rows_html.append(f'<td class="center">{html.escape(str(row["business_unit"] or "-"))}</td>')
            if index == 0:
                rows_html.append(f'<td rowspan="{rowspan}" class="product merged">{html.escape(product_name)}</td>')
            rows_html.append(f'<td class="center lot">{html.escape(str(row["lot_no"] or "-"))}</td>')
            rows_html.append(f'<td class="center expiry">{html.escape(str(row["expiry_date"] or "-"))}</td>')
            rows_html.append(f'<td class="right qty">{html.escape(quantity_with_unit(row))}</td></tr>')
    if not rows_html:
        rows_html.append('<tr><td colspan="5" class="empty">입력된 출고제품이 없습니다.</td></tr>')

    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box}} @page{{size:A4 portrait;margin:12mm}}
html,body{{margin:0;padding:0;background:#eef2f6;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Arial,sans-serif}} body{{padding:10px}}
.toolbar{{width:186mm;max-width:100%;margin:0 auto 10px;text-align:right}} .print{{border:0;border-radius:7px;background:#173b5f;color:white;font-weight:700;padding:9px 16px;cursor:pointer}}
.sheet{{width:186mm;max-width:100%;margin:auto;background:white;border:1px solid #d7dee7;box-shadow:0 10px 28px rgba(30,45,70,.08)}}
.header{{padding:18px 20px 15px;border-bottom:3px solid #234f75;display:flex;justify-content:space-between;gap:20px;align-items:flex-end}} .title{{font-size:21px;font-weight:850;color:#173b5f;letter-spacing:.02em}} .export-no{{text-align:right;font-size:9px;color:#758294}} .export-no b{{display:block;font-size:13px;color:#172033;margin-top:3px}}
.meta{{display:grid;grid-template-columns:repeat(3,1fr);margin:13px 16px 12px;border:1px solid #dce3eb}} .meta div{{padding:7px 8px;border-right:1px solid #e3e8ee}} .meta div:last-child{{border-right:0}} .label{{font-size:8px;color:#7c8797}} .value{{font-size:10px;font-weight:700;margin-top:2px;word-break:break-word}}
.content{{padding:0 16px 17px}} .summary{{width:171mm;max-width:100%;margin:0 auto 5px;font-size:8.8px;color:#697586;text-align:right}}
table{{width:171mm;max-width:100%;margin:0 auto;border-collapse:collapse;table-layout:fixed;font-size:9.2px;border:1px solid #cfd8e2}} col.destination{{width:22mm}} col.product{{width:70mm}} col.lot{{width:31mm}} col.expiry{{width:28mm}} col.qty{{width:20mm}}
th{{background:#294f71;color:white;padding:6px 4px;text-align:center;font-weight:750}} td{{padding:5px 6px;border-right:1px solid #dce3ea;border-bottom:1px solid #dce3ea;vertical-align:middle;line-height:1.3}} .center{{text-align:center}} .right{{text-align:right}} .product{{white-space:normal;overflow-wrap:anywhere;word-break:keep-all;font-weight:700}} .merged{{background:#f5f8fb}} .lot,.expiry,.qty{{white-space:nowrap}} .qty{{font-weight:650}} .empty{{text-align:center;color:#8993a0;padding:20px}}
.notice{{padding:10px 20px 14px;font-size:8.2px;color:#788493;border-top:1px solid #e0e6ed}}
@media print{{html,body{{width:210mm;min-height:297mm;background:white;padding:0}} .toolbar{{display:none!important}} .sheet{{width:186mm;max-width:none;margin:0 auto;border:0;box-shadow:none}} .header{{padding:13px 15px 11px}} .title{{font-size:18px}} .meta{{margin:10px 8px}} .content{{padding:0 8px 12px}} .summary,table{{width:171mm;max-width:none}} table{{font-size:8.5px}} th{{padding:4px 3px}} td{{padding:4px}} .notice{{padding:8px 15px 0}} .header,th{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<div class="toolbar"><button class="print" onclick="window.print()">🖨 출력하기</button></div>
<div class="sheet"><div class="header"><div class="title">출고 예정 제품 리스트</div><div class="export-no">EXPORT NO.<b>{html.escape(case['export_no'] or '-')}</b></div></div>
<div class="meta"><div><span class="label">국가 / Country</span><div class="value">{html.escape(case['country'] or '-')}</div></div><div><span class="label">바이어 / Buyer</span><div class="value">{html.escape(case['buyer'] or '-')}</div></div><div><span class="label">운송방식 / Transport</span><div class="value">{html.escape(case['transport_mode'] or '-')}</div></div></div>
<div class="content"><div class="summary">총 {len(grouped)}품목 · 제조번호 기준 {len(actual_rows)}행</div><table><colgroup><col class="destination"><col class="product"><col class="lot"><col class="expiry"><col class="qty"></colgroup><thead><tr><th>출고처</th><th>제품명</th><th>제조번호</th><th>유통기한</th><th>출고수량</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>
<div class="notice">본 문서는 패킹 완료 전 작성된 출고 예정 제품 목록이며, 최종 수량 및 패킹 정보는 변경될 수 있습니다.</div></div></body></html>'''
    components.html(document, height=min(1800, max(700, 500 + len(actual_rows) * 38)), scrolling=True)


def open_selected_path(path: Path, label: str) -> None:
    try:
        path = Path(path)
        if not path.exists():
            st.error(f'{label} 경로가 없습니다: {path}')
            return
        activation_script = f'Start-Process -FilePath "{str(path).replace(chr(34), chr(34) * 2)}"'
        subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', activation_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        st.error(f'{label}을(를) 열 수 없습니다: {exc}')


st.title('공유용 자료')
st.caption('수출 건을 선택한 뒤 필요한 자료를 출력하거나 관련 폴더를 열 수 있습니다.')

cases = order_service.list_editable_cases()
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#document-case-filter-anchor) {
        width: 56vw;
        max-width: 56vw;
    }
    @media(max-width:900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#document-case-filter-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

with st.container():
    st.markdown('<span id="document-case-filter-anchor"></span>', unsafe_allow_html=True)
    now = datetime.now()
    years = sorted(
        {
            now.year,
            *{
                int(_shipment_date(case)[:4])
                for case in cases
                if _shipment_date(case)[:4].isdigit()
            },
        },
        reverse=True,
    )
    filter_cols = st.columns([1.5, 1.5, 3, 4])
    selected_year = filter_cols[0].selectbox('연도', ['전체'] + years, key='document_case_year')
    month_options: list[str | int] = ['전체'] + list(range(1, 13))
    selected_month = filter_cols[1].selectbox('월', month_options, key='document_case_month')
    countries = sorted({str(case['country']).strip() for case in cases if str(case['country']).strip()})
    selected_country = filter_cols[2].selectbox('국가', ['전체'] + countries, key='document_case_country')
    product_query = filter_cols[3].text_input('제품명 검색', key='document_case_product_search').strip().casefold()

filtered_cases = []
for case in cases:
    raw_date = _shipment_date(case)
    case_year = int(raw_date[:4]) if raw_date[:4].isdigit() else None
    case_month = int(raw_date[5:7]) if len(raw_date) >= 7 and raw_date[5:7].isdigit() else None
    if raw_date:
        if selected_year != '전체' and case_year != selected_year:
            continue
        if selected_month != '전체' and case_month != selected_month:
            continue
    if selected_country != '전체' and str(case['country']).strip() != selected_country:
        continue
    if product_query and product_query not in str(case['product_names'] or '').casefold():
        continue
    filtered_cases.append(case)

if not filtered_cases:
    st.warning('조건에 맞는 수출 건이 없습니다.')
    st.stop()

selection_rows = []
for case in filtered_cases:
    selection_rows.append(
        {
            '_case_id': int(case['id']),
            '출고일자': _shipment_date(case),
            '수출번호': case['export_no'],
            '국가': case['country'],
            '바이어': case['buyer'] or '',
            '운송방식': case['transport_mode'],
            '단계': display_stage(case['stage']),
            '주문제품': summarize_product_names(case['product_names']),
        }
    )

selection_df = pd.DataFrame(selection_rows)
selected_rows = st.dataframe(
    selection_df,
    hide_index=True,
    use_container_width=True,
    on_select='rerun',
    selection_mode='single-row',
    column_config={
        '_case_id': None,
        '출고일자': st.column_config.TextColumn('출고일자'),
        '수출번호': st.column_config.TextColumn('수출번호'),
        '국가': st.column_config.TextColumn('국가'),
        '바이어': st.column_config.TextColumn('바이어'),
        '운송방식': st.column_config.TextColumn('운송방식'),
        '단계': st.column_config.TextColumn('단계'),
        '주문제품': st.column_config.TextColumn('주문제품'),
    },
    key='document_case_table',
)

selected_indexes = selected_rows.selection.rows
if not selected_indexes:
    st.session_state.pop('document_case_id', None)
    st.session_state.pop('shared_document_view', None)
    st.info('공유용 자료를 만들 수출 건의 행을 선택하세요.')
    st.stop()

case_id = int(selection_df.iloc[int(selected_indexes[0])]['_case_id'])
previous_case_id = st.session_state.get('document_case_id')
if previous_case_id != case_id:
    st.session_state['document_case_id'] = case_id
    st.session_state.pop('shared_document_view', None)
case = export_service.get_case(case_id)

try:
    case_folder = folder_service.ensure_case_folder(case_id)
    action_cols = st.columns(5)
    if action_cols[0].button('📂 폴더 열기', use_container_width=True):
        open_selected_path(case_folder, '수출 폴더')
    if action_cols[1].button('📄 수출진행내역', use_container_width=True):
        open_selected_path(case_folder / '수출진행내역.xlsx', '수출진행내역')
    if action_cols[2].button('🖼 출고제품사진', use_container_width=True):
        open_selected_path(folder_service.category_folder(case_id, '출고사진'), '출고제품사진 폴더')
    if action_cols[3].button('📑 CI', use_container_width=True):
        open_selected_path(folder_service.category_folder(case_id, 'CI'), 'CI 폴더')
    if action_cols[4].button('🚢 Shipping Mark', use_container_width=True):
        open_selected_path(folder_service.category_folder(case_id, 'Shipping Mark'), 'Shipping Mark 폴더')
    st.caption(str(case_folder))
except Exception as exc:
    st.warning(f'수출 폴더를 준비하지 못했습니다: {exc}')

is_packing_complete = str(case['stage'] or '').strip() == '패킹 완료'
output_cols = st.columns(2)
if output_cols[0].button(
    '최종문서 출력하기',
    type='primary',
    use_container_width=True,
    disabled=not is_packing_complete,
    help=None if is_packing_complete else '패킹 완료 단계에서만 최종문서를 출력할 수 있습니다.',
):
    st.session_state['shared_document_view'] = 'final'
if output_cols[1].button('출고 예정 제품 리스트', use_container_width=True):
    st.session_state['shared_document_view'] = 'shipment_products'

if not is_packing_complete and st.session_state.get('shared_document_view') == 'final':
    st.session_state.pop('shared_document_view', None)

fresh_actual_rows = shipment_service.list_actual(case_id)
actual_rows = document_service._aggregate_actual(fresh_actual_rows)
selected_view = st.session_state.get('shared_document_view')
if selected_view == 'final':
    packed, _ = document_service.get_document_data(case_id)
    render_document(case, packed)
elif selected_view == 'shipment_products':
    render_shipment_product_list(case, actual_rows)
else:
    if not is_packing_complete:
        st.caption('최종문서는 패킹 완료 후 출력할 수 있습니다.')
    st.info('출력할 문서 종류를 선택하세요.')
