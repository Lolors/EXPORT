from __future__ import annotations

from datetime import date
from pathlib import Path
import html
import time

import streamlit as st

import db

MAX_PHOTO_SIZE = 800
JPEG_QUALITY = 92

st.set_page_config(page_title='수출관리', page_icon='🌏', layout='wide')


@st.cache_resource
def initialize_database() -> bool:
    """Streamlit 프로세스에서 데이터베이스 초기화를 한 번만 실행합니다."""
    db.init_db()
    return True


initialize_database()


def get_pandas():
    import pandas as pd
    return pd


def dataframe(query, params=()):
    pd = get_pandas()
    return pd.DataFrame([dict(r) for r in db.rows(query, params)])


def rerun():
    st.rerun()


def date_value(value: str | None):
    parsed = db.parse_date(value)
    return parsed.date() if parsed else date.today()


def case_label(r):
    note = f" | {r['note']}" if 'note' in r.keys() and r['note'] else ''
    return f"{r['export_no']} | {r['country']} | {r['buyer'] or '바이어 미입력'} | {r['stage']}{note}"


def choose_active_case(key, country=None):
    cases = db.active_cases(country)
    if not cases:
        return None
    options = {case_label(r): int(r['id']) for r in cases}
    return options[st.selectbox('진행 중 수출 건', list(options), key=key)]


def replace_order_items(case_id, edited):
    db.execute('DELETE FROM order_items WHERE case_id=?', (case_id,))
    vals = []
    for _, r in edited.iterrows():
        name = str(r.get('제품명', '')).strip()
        if name:
            vals.append((case_id, name, float(r.get('수량', 0) or 0), str(r.get('단위', 'EA') or 'EA'), db.now_text()))
    if vals:
        db.executemany('INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)', vals)


def save_shipment_editor(case_id, edited):
    db.execute('DELETE FROM shipment_items WHERE case_id=?', (case_id,))
    vals = []
    for _, r in edited.iterrows():
        name = str(r.get('제품명', '')).strip()
        if name:
            vals.append((
                case_id,
                str(r.get('사업장', '')),
                str(r.get('로케이션', '')),
                name,
                str(r.get('LOT', '')),
                str(r.get('유통기한', '')),
                float(r.get('요청수량', 0) or 0),
                None,
                db.now_text(),
                db.now_text(),
            ))
    if vals:
        db.executemany(
            '''INSERT INTO shipment_items(case_id,business_unit,location,product_name,lot_no,expiry_date,requested_qty,box_no,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            vals,
        )


def optimize_uploaded_photo(uploaded_file, output_path: Path) -> None:
    """사진 메뉴에서 저장할 때만 Pillow를 불러옵니다."""
    from io import BytesIO
    from PIL import Image, ImageOps

    with Image.open(BytesIO(uploaded_file.getvalue())) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((MAX_PHOTO_SIZE, MAX_PHOTO_SIZE), Image.Resampling.LANCZOS)

        if output_path.suffix.lower() == '.png':
            image.save(output_path, format='PNG', optimize=True)
            return

        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, 'white')
            alpha = image.getchannel('A')
            background.paste(image.convert('RGB'), mask=alpha)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        image.save(output_path, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)


@st.cache_resource
def enable_heic_support() -> bool:
    """출고 사진 메뉴에 들어왔을 때만 HEIC 라이브러리를 등록합니다."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        return True
    except Exception:
        return False


def render_packing_preview(preview) -> None:
    pd = get_pandas()
    if preview.empty:
        st.info('패킹된 제품이 없습니다.')
        return

    columns = ['박스번호', '사업장', '제품명', 'LOT', '유통기한', '수량', '무게', '박스사이즈']
    styles = '''
    <style>
    .packing-table-wrap {overflow-x:auto; border:1px solid #d9dee7; border-radius:10px;}
    table.packing-table {border-collapse:collapse; width:100%; min-width:880px; font-size:15px;}
    .packing-table th {background:#f5f7fa; color:#5f6878; font-weight:500; text-align:left; padding:14px 12px; border-bottom:1px solid #d9dee7; white-space:nowrap;}
    .packing-table td {padding:14px 12px; border-bottom:1px solid #e5e9f0; border-right:1px solid #e5e9f0; vertical-align:middle; white-space:nowrap;}
    .packing-table td:last-child, .packing-table th:last-child {border-right:none;}
    .packing-table tr:last-child td {border-bottom:none;}
    .packing-table .merged {text-align:center; font-weight:500; background:#fbfcfe;}
    .packing-table .qty {text-align:right;}
    </style>
    '''
    parts = [styles, "<div class='packing-table-wrap'><table class='packing-table'><thead><tr>"]
    parts.extend(f'<th>{html.escape(col)}</th>' for col in columns)
    parts.append('</tr></thead><tbody>')

    for _, group in preview.groupby('박스번호', sort=False, dropna=False):
        rowspan = len(group)
        for row_index, (_, row) in enumerate(group.iterrows()):
            parts.append('<tr>')
            if row_index == 0:
                parts.append(f"<td class='merged' rowspan='{rowspan}'>{html.escape(str(row['박스번호']))}</td>")
            for col in ['사업장', '제품명', 'LOT', '유통기한']:
                value = '' if pd.isna(row[col]) else str(row[col])
                parts.append(f'<td>{html.escape(value)}</td>')
            qty = '' if pd.isna(row['수량']) else f"{float(row['수량']):g}"
            parts.append(f"<td class='qty'>{html.escape(qty)}</td>")
            if row_index == 0:
                weight = '' if pd.isna(row['무게']) else str(row['무게'])
                size = '' if pd.isna(row['박스사이즈']) else str(row['박스사이즈'])
                parts.append(f"<td class='merged' rowspan='{rowspan}'>{html.escape(weight)}</td>")
                parts.append(f"<td class='merged' rowspan='{rowspan}'>{html.escape(size)}</td>")
            parts.append('</tr>')

    parts.append('</tbody></table></div>')
    st.markdown(''.join(parts), unsafe_allow_html=True)


def completed_case_search(start_date, end_date, country, buyer_keyword, product_keyword, note_keyword):
    query = '''
        SELECT DISTINCT
               c.id,
               c.export_no AS 수출번호,
               c.country AS 국가,
               c.buyer AS 바이어,
               c.transport_mode AS 운송방식,
               c.actual_ship_date AS 실제출고일,
               c.expected_ship_date AS 예상출고일,
               c.status AS 상태,
               c.stage AS 단계,
               c.note AS 비고,
               c.folder_path AS 폴더
        FROM export_cases c
        LEFT JOIN order_items o ON o.case_id = c.id
        WHERE (c.status IN ('완료','취소') OR c.stage IN ('완료','취소'))
          AND date(COALESCE(NULLIF(c.actual_ship_date,''), NULLIF(c.expected_ship_date,''), substr(c.created_at,1,10))) BETWEEN date(?) AND date(?)
    '''
    params = [str(start_date), str(end_date)]
    if country != '전체':
        query += ' AND c.country = ?'
        params.append(country)
    if buyer_keyword.strip():
        query += ' AND c.buyer LIKE ?'
        params.append(f"%{buyer_keyword.strip()}%")
    if product_keyword.strip():
        query += ' AND o.product_name LIKE ?'
        params.append(f"%{product_keyword.strip()}%")
    if note_keyword.strip():
        query += ' AND c.note LIKE ?'
        params.append(f"%{note_keyword.strip()}%")
    query += " ORDER BY COALESCE(NULLIF(c.actual_ship_date,''), NULLIF(c.expected_ship_date,''), c.created_at) DESC, c.export_no DESC"
    return dataframe(query, tuple(params))


st.title('수출관리')
st.caption('Export Management System')
menu = st.sidebar.radio(
    '메뉴',
    ['오버뷰', '수출 주문 입력', '실출고 입력', '박스 패킹', '패킹 결과·배송·엑셀', '출고 사진'],
    label_visibility='collapsed',
)

if menu == '오버뷰':
    st.subheader('진행중 수출')
    cases = db.active_cases()
    if not cases:
        st.info('현재 진행 중인 수출 건이 없습니다.')
    for c in cases:
        orders = db.rows('SELECT product_name,quantity,unit FROM order_items WHERE case_id=? ORDER BY id', (c['id'],))
        title = f"{c['export_no']} · {c['country']} · {c['stage']}" + (f" · {c['buyer']}" if c['buyer'] else '')
        if c['note']:
            title += f" · {c['note']}"
        with st.expander(title):
            if orders:
                pd = get_pandas()
                st.dataframe(
                    pd.DataFrame([{'제품명': o['product_name'], '수량': o['quantity'], '단위': o['unit']} for o in orders]),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption('주문 제품이 아직 입력되지 않았습니다.')
            cols = st.columns(5)
            cols[0].metric('국가', c['country'])
            cols[1].metric('운송', c['transport_mode'])
            cols[2].metric('예상 출고일', c['expected_ship_date'] or '-')
            cols[3].metric('단계', c['stage'])
            cols[4].metric('비고', c['note'] or '-')
            st.caption(f"폴더: {c['folder_path'] or '아직 생성되지 않음'}")

    st.divider()
    st.subheader('수출 폴더 관리')
    configured_root = db.get_setting('shared_root').strip()
    st.caption(
        '내 폴더를 나중에 지정했거나 국가·연도·출고일을 수정한 경우, 모든 수출 건의 폴더를 현재 설정에 맞게 다시 생성하거나 이동합니다.'
    )
    st.code(configured_root or str(db.UPLOAD_DIR.resolve()))
    folder_confirm = st.checkbox(
        '기존 폴더를 현재 내 폴더의 국가 / 연도 / 수출건 구조로 이동·정리하는 것에 동의합니다.',
        key='folder_rebuild_confirm',
    )
    if st.button('모든 수출 폴더 재생성·정리', type='primary', disabled=not folder_confirm):
        if configured_root:
            root_ok, root_message = db.test_storage_root(configured_root)
        else:
            root_ok, root_message = True, str(db.UPLOAD_DIR.resolve())

        if not root_ok:
            st.error(f'내 폴더에 연결할 수 없어 작업을 중단했습니다.\n\n{root_message}')
        else:
            all_cases = db.rows('SELECT id, export_no FROM export_cases ORDER BY id')
            succeeded = []
            failures = []
            progress = st.progress(0, text='수출 폴더를 확인하고 있습니다.')
            total = max(len(all_cases), 1)
            for index, case_row in enumerate(all_cases, start=1):
                try:
                    folder = db.sync_case_folder(int(case_row['id']))
                    succeeded.append(f"{case_row['export_no']} → {folder}")
                except Exception as exc:
                    failures.append(f"{case_row['export_no']}: {exc}")
                progress.progress(index / total, text=f'{index}/{len(all_cases)} 처리 중')
            progress.empty()
            if succeeded:
                db.add_history(None, '전체 수출 폴더 재정리', f'{len(succeeded)}건 완료 / {len(failures)}건 실패')
                st.success(f'{len(succeeded)}건의 폴더를 현재 구조에 맞게 생성·정리했습니다.')
                with st.expander('처리된 폴더 보기'):
                    st.code('\n'.join(succeeded))
            if failures:
                st.error('일부 폴더를 처리하지 못했습니다.\n\n' + '\n'.join(f'- {item}' for item in failures))

    st.divider()
    st.subheader('완료/취소 수출 검색')
    country_rows = db.rows(
        "SELECT DISTINCT country FROM export_cases WHERE (status IN ('완료','취소') OR stage IN ('완료','취소')) AND country<>'' ORDER BY country"
    )
    countries = ['전체'] + [r['country'] for r in country_rows]
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    search_start = c1.date_input('시작일', value=date(date.today().year, 1, 1), key='completed_start')
    search_end = c2.date_input('종료일', value=date.today(), key='completed_end')
    search_country = c3.selectbox('국가', countries, key='completed_country')
    c4, c5, c6 = st.columns(3)
    buyer_keyword = c4.text_input('바이어 검색', key='completed_buyer')
    product_keyword = c5.text_input('제품명 검색', key='completed_product')
    note_keyword = c6.text_input('비고 검색', key='completed_note')
    if search_start > search_end:
        st.error('시작일은 종료일보다 늦을 수 없습니다.')
    else:
        result = completed_case_search(search_start, search_end, search_country, buyer_keyword, product_keyword, note_keyword)
        if result.empty:
            st.info('검색 결과가 없습니다.')
        else:
            st.dataframe(result.drop(columns=['id']), hide_index=True, use_container_width=True)

elif menu == '수출 주문 입력':
    pd = get_pandas()
    st.subheader('수출 주문 등록')
    with st.form('new_case'):
        st.text_input('수출번호', value=db.next_export_no(), disabled=True)
        c1, c2, c3 = st.columns(3)
        country = c1.text_input('국가 *')
        buyer = c2.text_input('바이어 (선택)')
        expected = c3.date_input('예상출고일')
        transport = c1.selectbox('운송방식', db.TRANSPORT_MODES)
        stage = c2.selectbox('현재 진행 단계', db.STAGES[:5])
        note = c3.text_input('비고', help='완료 후 폴더명에 사용됩니다. 예: 메디풀 7월 발주, 리쥬란 샘플')
        submitted = st.form_submit_button('수출 건 생성')
    if submitted:
        if not country.strip():
            st.error('국가는 필수입니다.')
        else:
            no = db.next_export_no()
            now = db.now_text()
            cid = db.execute(
                '''INSERT INTO export_cases(export_no,buyer,country,expected_ship_date,transport_mode,stage,status,note,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (no, buyer, country, str(expected), transport, stage, '진행중', note, now, now),
            )
            db.ensure_case_folder(cid)
            db.add_history(cid, '수출 건 생성', no)
            st.session_state['order_case'] = cid
            st.success(f'{no} 생성 완료')
    cid = st.session_state.get('order_case')
    active = db.active_cases()
    opts = {case_label(r): int(r['id']) for r in active}
    if opts:
        cid = opts[st.selectbox(
            '주문 목록을 입력할 수출 건',
            list(opts),
            index=list(opts.values()).index(cid) if cid in opts.values() else 0,
        )]
        case = db.row('SELECT * FROM export_cases WHERE id=?', (cid,))
        with st.form(f'case_edit_{cid}'):
            st.markdown('#### 기본 정보 수정')
            c1, c2, c3 = st.columns(3)
            new_country = c1.text_input('국가 *', value=case['country'])
            new_buyer = c2.text_input('바이어 (선택)', value=case['buyer'])
            new_expected = c3.date_input('예상출고일', value=date_value(case['expected_ship_date']))
            new_transport = c1.selectbox('운송방식', db.TRANSPORT_MODES, index=db.TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in db.TRANSPORT_MODES else 0)
            new_stage = c2.selectbox('현재 진행 단계', db.STAGES[:5], index=db.STAGES[:5].index(case['stage']) if case['stage'] in db.STAGES[:5] else 0)
            new_note = c3.text_input('비고', value=case['note'])
            if st.form_submit_button('기본 정보 저장'):
                if not new_country.strip():
                    st.error('국가는 필수입니다.')
                else:
                    db.execute(
                        'UPDATE export_cases SET country=?,buyer=?,expected_ship_date=?,transport_mode=?,stage=?,note=?,updated_at=? WHERE id=?',
                        (new_country, new_buyer, str(new_expected), new_transport, new_stage, new_note, db.now_text(), cid),
                    )
                    db.sync_case_folder(cid)
                    db.add_history(cid, '수출 기본 정보 수정', f'{new_country} / {new_transport} / {new_note}')
                    st.success('기본 정보를 저장했습니다.')
                    rerun()
        old = dataframe('SELECT product_name AS 제품명, quantity AS 수량, unit AS 단위 FROM order_items WHERE case_id=?', (cid,))
        if old.empty:
            old = pd.DataFrame([{'제품명': '', '수량': 0, '단위': 'EA'}])
        edited = st.data_editor(old, num_rows='dynamic', use_container_width=True, key=f'orders_{cid}')
        if st.button('주문 목록 저장'):
            replace_order_items(cid, edited)
            db.add_history(cid, '주문 목록 저장', f'{len(edited)}행')
            st.success('저장했습니다.')
            rerun()

elif menu == '실출고 입력':
    pd = get_pandas()
    st.subheader('실제 출고 제품 입력')
    countries = [r['country'] for r in db.rows("SELECT DISTINCT country FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소') ORDER BY country")]
    if not countries:
        st.info('진행 중 수출 건이 없습니다.')
        st.stop()
    country = st.selectbox('국가', countries)
    cid = choose_active_case('ship_case', country)
    if not cid:
        st.stop()
    st.markdown('#### 주문 목록')
    st.dataframe(dataframe('SELECT product_name AS 제품명, quantity AS 수량, unit AS 단위 FROM order_items WHERE case_id=?', (cid,)), hide_index=True, use_container_width=True)
    st.markdown('#### 실제 출고 목록')
    st.caption('WMS에서 사업장, 로케이션, 제품명, LOT, 유통기한, 요청수량 6개 열을 복사해 첫 셀에 붙여넣으세요. 행 추가도 가능합니다.')
    old = dataframe(
        '''SELECT business_unit AS 사업장, location AS 로케이션, product_name AS 제품명, lot_no AS LOT,
                  expiry_date AS 유통기한, requested_qty AS 요청수량
           FROM shipment_items WHERE case_id=? ORDER BY id''',
        (cid,),
    )
    if old.empty:
        old = pd.DataFrame([{'사업장': '', '로케이션': '', '제품명': '', 'LOT': '', '유통기한': '', '요청수량': 0}])
    edited = st.data_editor(old, num_rows='dynamic', use_container_width=True, key=f'ship_{cid}')
    if st.button('실출고 목록 저장'):
        save_shipment_editor(cid, edited)
        db.execute("UPDATE export_cases SET stage='실출고 입력',updated_at=? WHERE id=?", (db.now_text(), cid))
        db.add_history(cid, '실출고 목록 저장', f'{len(edited)}행')
        st.success('저장했습니다.')
        rerun()

elif menu == '박스 패킹':
    st.subheader('박스 패킹')
    cid = choose_active_case('pack_case')
    if not cid:
        st.info('진행 중 수출 건이 없습니다.')
        st.stop()
    items = db.rows('SELECT * FROM shipment_items WHERE case_id=? ORDER BY id', (cid,))
    if not items:
        st.warning('먼저 실출고 목록을 입력하세요.')
        st.stop()
    selected = []
    for item in items:
        c1, c2, c3 = st.columns([6, 2, 2])
        label = f"{item['product_name']} · {item['lot_no']} · {item['requested_qty']:g}"
        if c1.checkbox(label, key=f"sel_{item['id']}"):
            selected.append(item['id'])
        c2.write(item['location'])
        c3.write(f"BOX {item['box_no']}" if item['box_no'] else '미패킹')
    next_box = db.row('SELECT COALESCE(MAX(box_no),0)+1 AS n FROM boxes WHERE case_id=?', (cid,))['n']
    box_no = st.number_input('배정할 박스번호', min_value=1, value=int(next_box), step=1)
    if st.button('선택 제품 패킹'):
        if not selected:
            st.error('제품을 선택하세요.')
        else:
            for iid in selected:
                db.execute('UPDATE shipment_items SET box_no=?,updated_at=? WHERE id=?', (box_no, db.now_text(), iid))
            db.execute('INSERT OR IGNORE INTO boxes(case_id,box_no,updated_at) VALUES (?,?,?)', (cid, box_no, db.now_text()))
            db.add_history(cid, '박스 패킹', f'{len(selected)}개 행 → BOX {box_no}')
            rerun()
    st.markdown('#### 박스 정보')
    boxes = db.rows('SELECT * FROM boxes WHERE case_id=? ORDER BY box_no', (cid,))
    for b in boxes:
        with st.form(f"box_{b['id']}"):
            st.write(f"**BOX {b['box_no']}**")
            c1, c2, c3, c4 = st.columns(4)
            length = c1.number_input('가로(cm)', 0.0, value=float(b['length_cm']), key=f"l{b['id']}")
            width = c2.number_input('세로(cm)', 0.0, value=float(b['width_cm']), key=f"w{b['id']}")
            height = c3.number_input('높이(cm)', 0.0, value=float(b['height_cm']), key=f"h{b['id']}")
            weight = c4.number_input('무게(kg)', 0.0, value=float(b['weight_kg']), key=f"kg{b['id']}")
            saved = st.form_submit_button('박스 정보 저장')
        if saved:
            db.execute(
                'UPDATE boxes SET length_cm=?,width_cm=?,height_cm=?,weight_kg=?,updated_at=? WHERE id=?',
                (length, width, height, weight, db.now_text(), b['id']),
            )
            db.add_history(cid, '박스 정보 수정', f"BOX {b['box_no']}")
            st.success('저장되었습니다.')

elif menu == '패킹 결과·배송·엑셀':
    pd = get_pandas()
    st.subheader('패킹 결과 및 국내배송')
    cid = choose_active_case('result_case')
    if not cid:
        st.stop()
    case = db.row('SELECT * FROM export_cases WHERE id=?', (cid,))
    summary_parts = [case['country']]
    if case['buyer']:
        summary_parts.append(case['buyer'])
    summary_parts.append(f"운송방식: {case['transport_mode'] or '-'}")
    if case['note']:
        summary_parts.append(f"비고: {case['note']}")
    st.info(' | '.join(summary_parts))
    st.caption('완료 후 폴더명: 바이어가 있으면 MMDD_바이어_운송방식_비고, 바이어가 없으면 MMDD_운송방식_비고')
    preview = dataframe(
        '''SELECT s.box_no AS 박스번호,s.business_unit AS 사업장,s.product_name AS 제품명,
                  s.lot_no AS LOT,s.expiry_date AS 유통기한,s.requested_qty AS 수량,b.weight_kg AS 무게,
                  printf('%g x %g x %g',b.length_cm,b.width_cm,b.height_cm) AS 박스사이즈
           FROM shipment_items s LEFT JOIN boxes b ON b.case_id=s.case_id AND b.box_no=s.box_no
           WHERE s.case_id=? AND s.box_no IS NOT NULL ORDER BY s.box_no,s.id''',
        (cid,),
    )
    if not preview.empty:
        preview['무게'] = preview['무게'].apply(lambda value: f'{float(value):g} kg' if pd.notna(value) else '')
        preview['박스사이즈'] = preview['박스사이즈'].apply(lambda value: f'{value} cm' if value else '')
    render_packing_preview(preview)

    method = st.radio(
        '국내배송',
        ['로젠택배', '퀵배송'],
        index=0 if case['domestic_method'] != '퀵배송' else 1,
        horizontal=True,
        key=f'delivery_method_{cid}',
    )
    with st.form(f'delivery_{cid}_{method}'):
        actual_ship_date = st.date_input('실제출고일', value=date_value(case['actual_ship_date']), key=f'actual_ship_date_{cid}_{method}')
        tracking = ''
        driver = ''
        phone = ''
        if method == '로젠택배':
            tracking = st.text_input('송장번호', value=case['tracking_no'], key=f'tracking_{cid}_{method}')
        else:
            c1, c2 = st.columns(2)
            driver = c1.text_input('배송기사 이름', value=case['driver_name'], key=f'driver_{cid}_{method}')
            phone = c2.text_input('연락처', value=case['driver_phone'], key=f'phone_{cid}_{method}')
        if st.form_submit_button('배송정보 저장'):
            if method == '로젠택배':
                driver = ''
                phone = ''
            else:
                tracking = ''
            db.execute(
                "UPDATE export_cases SET domestic_method=?,tracking_no=?,driver_name=?,driver_phone=?,actual_ship_date=?,stage='국내배송',status='완료',updated_at=? WHERE id=?",
                (method, tracking, driver, phone, str(actual_ship_date), db.now_text(), cid),
            )
            folder = db.sync_case_folder(cid)
            db.add_history(cid, '국내배송 완료', f'{method} / {folder}')
            st.success(f'국내배송 정보가 저장되어 수출 건이 완료 처리되었습니다. 폴더: {folder}')
            time.sleep(1)
            rerun()

    excel_key = f'packing_excel_{cid}'
    if st.button('엑셀 파일 준비', key=f'prepare_excel_{cid}'):
        with st.spinner('엑셀 파일을 만드는 중입니다.'):
            from export_excel import build_packing_export
            st.session_state[excel_key] = build_packing_export(cid)
    if excel_key in st.session_state:
        st.download_button(
            '전체 화면 엑셀로 내보내기',
            st.session_state[excel_key],
            file_name=f"{case['export_no']}_packing.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key=f'download_excel_{cid}',
        )

elif menu == '출고 사진':
    heic_enabled = enable_heic_support()
    st.subheader('출고 증빙 사진')
    cid = choose_active_case('photo_case')
    if not cid:
        st.stop()
    case = db.row('SELECT * FROM export_cases WHERE id=?', (cid,))
    case_folder = db.ensure_case_folder(cid)
    st.caption('업로드한 사진은 방향을 자동 보정하고, 긴 변 800px 이하로 축소해 저장합니다.')
    if not heic_enabled:
        st.caption('HEIC/HEIF 지원 라이브러리가 없어 JPG, PNG, WEBP만 업로드할 수 있습니다.')
    st.caption(f'저장 폴더: {case_folder}')
    upload_types = ['jpg', 'jpeg', 'png', 'webp']
    if heic_enabled:
        upload_types.extend(['heic', 'heif'])
    files = st.file_uploader('사진 업로드', type=upload_types, accept_multiple_files=True)
    if st.button('사진 저장') and files:
        folder = case_folder / '출고사진'
        folder.mkdir(parents=True, exist_ok=True)
        existing_count = db.row(
            "SELECT COUNT(*) AS count FROM attachments WHERE case_id=? AND category='출고사진'",
            (cid,),
        )['count']
        saved_count = 0
        failures = []
        for sequence, uploaded in enumerate(files, start=int(existing_count) + 1):
            is_png = Path(uploaded.name).suffix.lower() == '.png'
            extension = '.png' if is_png else '.jpg'
            stored_name = f"{case['export_no']}_{sequence:03d}{extension}"
            stored_path = folder / stored_name
            try:
                optimize_uploaded_photo(uploaded, stored_path)
                db.execute(
                    'INSERT INTO attachments(case_id,file_name,stored_path,category,uploaded_at) VALUES (?,?,?,?,?)',
                    (cid, stored_name, str(stored_path), '출고사진', db.now_text()),
                )
                saved_count += 1
            except Exception as exc:
                failures.append(f'{uploaded.name}: {exc}')
        if saved_count:
            db.add_history(cid, '출고 사진 업로드', f'{saved_count}장 최적화 저장')
            st.success(f'{saved_count}장의 사진을 최적화하여 저장했습니다.')
        if failures:
            st.error('일부 사진을 변환하지 못했습니다.\n\n' + '\n'.join(f'- {failure}' for failure in failures))
        if saved_count and not failures:
            rerun()

    photos = db.rows(
        "SELECT * FROM attachments WHERE case_id=? AND category='출고사진' ORDER BY uploaded_at DESC",
        (cid,),
    )
    if photos:
        cols = st.columns(4)
        for i, photo in enumerate(photos):
            path = Path(photo['stored_path'])
            if path.exists():
                cols[i % 4].image(str(path), caption=photo['file_name'], use_container_width=True)
