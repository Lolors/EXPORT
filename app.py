from __future__ import annotations

from datetime import date

import streamlit as st

import db


st.set_page_config(page_title='수출관리', page_icon='🌏', layout='wide')


@st.cache_resource
def initialize_database() -> bool:
    db.init_db()
    return True


initialize_database()


def get_pandas():
    import pandas as pd
    return pd


def dataframe(query: str, params: tuple = ()):
    pd = get_pandas()
    return pd.DataFrame([dict(row) for row in db.rows(query, params)])


def date_value(value: str | None):
    parsed = db.parse_date(value)
    return parsed.date() if parsed else date.today()


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['stage']}"


def replace_order_items(case_id: int, edited) -> None:
    linked_count = db.row(
        '''SELECT COUNT(*) AS count
           FROM shipment_items s
           JOIN order_items o ON o.id=s.order_item_id
           WHERE o.case_id=?''',
        (case_id,),
    )['count']
    if linked_count:
        raise ValueError('이미 실제 출고제품이 연결되어 있어 주문품목을 전체 교체할 수 없습니다. 먼저 실출고 입력 내용을 정리하세요.')

    db.execute('DELETE FROM order_items WHERE case_id=?', (case_id,))
    values = []
    for _, row in edited.iterrows():
        product_name = str(row.get('제품명', '') or '').strip()
        if not product_name:
            continue
        values.append((
            case_id,
            product_name,
            float(row.get('수량', 0) or 0),
            str(row.get('단위', 'EA') or 'EA'),
            db.now_text(),
        ))
    if values:
        db.executemany(
            'INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',
            values,
        )


st.title('수출관리')
st.caption('중복된 구형 작업 화면을 제거하고 최신 작업 흐름으로 통합했습니다.')

st.markdown('### 작업 메뉴')
menu_cols = st.columns(3)
with menu_cols[0]:
    st.page_link('pages/실출고_입력.py', label='📦 실출고 입력', use_container_width=True)
with menu_cols[1]:
    st.page_link('pages/박스_패킹.py', label='📦 박스 패킹', use_container_width=True)
with menu_cols[2]:
    st.page_link('pages/국내배송_공유문서.py', label='📄 국내배송 공유문서', use_container_width=True)

st.divider()

overview_tab, order_tab = st.tabs(['오버뷰', '수출 주문 입력'])

with overview_tab:
    st.subheader('진행 중 수출')
    cases = db.active_cases()
    if not cases:
        st.info('현재 진행 중인 수출 건이 없습니다.')

    for case in cases:
        orders = db.rows(
            '''SELECT o.id, o.product_name, o.quantity, o.unit,
                      COALESCE(SUM(s.requested_qty),0) AS actual_qty
               FROM order_items o
               LEFT JOIN shipment_items s ON s.order_item_id=o.id
               WHERE o.case_id=?
               GROUP BY o.id, o.product_name, o.quantity, o.unit
               ORDER BY o.id''',
            (case['id'],),
        )
        title = case_label(case)
        if case['note']:
            title += f" · {case['note']}"

        with st.expander(title):
            if orders:
                pd = get_pandas()
                st.dataframe(
                    pd.DataFrame([
                        {
                            '주문품목': order['product_name'],
                            '주문수량': order['quantity'],
                            '실출고수량': order['actual_qty'],
                            '단위': order['unit'],
                        }
                        for order in orders
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption('주문품목이 아직 입력되지 않았습니다.')

            cols = st.columns(5)
            cols[0].metric('국가', case['country'])
            cols[1].metric('운송', case['transport_mode'])
            cols[2].metric('예상 출고일', case['expected_ship_date'] or '-')
            cols[3].metric('단계', case['stage'])
            cols[4].metric('비고', case['note'] or '-')
            st.caption(f"폴더: {case['folder_path'] or '아직 생성되지 않음'}")

    st.divider()
    st.subheader('수출 폴더 관리')
    configured_root = db.get_setting('shared_root').strip()
    st.code(configured_root or str(db.UPLOAD_DIR.resolve()))
    folder_confirm = st.checkbox(
        '기존 폴더를 현재 국가 / 연도 / 수출건 구조로 이동·정리하는 것에 동의합니다.',
        key='folder_rebuild_confirm',
    )
    if st.button('모든 수출 폴더 재생성·정리', type='primary', disabled=not folder_confirm):
        all_cases = db.rows('SELECT id, export_no FROM export_cases ORDER BY id')
        successes: list[str] = []
        failures: list[str] = []
        progress = st.progress(0, text='수출 폴더를 확인하고 있습니다.')
        total = max(len(all_cases), 1)
        for index, case in enumerate(all_cases, start=1):
            try:
                folder = db.sync_case_folder(int(case['id']))
                successes.append(f"{case['export_no']} → {folder}")
            except Exception as exc:
                failures.append(f"{case['export_no']}: {exc}")
            progress.progress(index / total, text=f'{index}/{len(all_cases)} 처리 중')
        progress.empty()
        if successes:
            db.add_history(None, '전체 수출 폴더 재정리', f'{len(successes)}건 완료 / {len(failures)}건 실패')
            st.success(f'{len(successes)}건의 폴더를 생성·정리했습니다.')
        if failures:
            st.error('일부 폴더를 처리하지 못했습니다.\n\n' + '\n'.join(f'- {item}' for item in failures))

with order_tab:
    pd = get_pandas()
    st.subheader('수출 주문 등록')

    with st.form('new_case'):
        st.text_input('수출번호', value=db.next_export_no(), disabled=True)
        c1, c2, c3 = st.columns(3)
        country = c1.text_input('국가 *')
        buyer = c2.text_input('바이어 (선택)')
        expected = c3.date_input('예상출고일')
        transport = c1.selectbox('운송방식', db.TRANSPORT_MODES)
        note = c2.text_input('비고')
        submitted = st.form_submit_button('수출 건 생성', type='primary')

    if submitted:
        if not country.strip():
            st.error('국가는 필수입니다.')
        else:
            export_no = db.next_export_no()
            now = db.now_text()
            case_id = db.execute(
                '''INSERT INTO export_cases(
                       export_no,buyer,country,expected_ship_date,transport_mode,
                       stage,status,note,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (export_no, buyer.strip(), country.strip(), str(expected), transport,
                 '주문 접수', '진행중', note.strip(), now, now),
            )
            db.ensure_case_folder(case_id)
            db.add_history(case_id, '수출 건 생성', export_no)
            st.session_state['order_case_id'] = case_id
            st.success(f'{export_no} 생성 완료')
            st.rerun()

    active_cases = db.active_cases()
    if active_cases:
        options = {case_label(case): int(case['id']) for case in active_cases}
        selected_case_id = st.session_state.get('order_case_id')
        labels = list(options)
        default_index = 0
        if selected_case_id in options.values():
            default_index = list(options.values()).index(selected_case_id)
        case_id = options[st.selectbox('주문을 수정할 수출 건', labels, index=default_index)]
        case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))

        with st.form(f'case_edit_{case_id}'):
            st.markdown('#### 기본 정보 수정')
            c1, c2, c3 = st.columns(3)
            new_country = c1.text_input('국가 *', value=case['country'])
            new_buyer = c2.text_input('바이어 (선택)', value=case['buyer'])
            new_expected = c3.date_input('예상출고일', value=date_value(case['expected_ship_date']))
            transport_index = db.TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in db.TRANSPORT_MODES else 0
            new_transport = c1.selectbox('운송방식', db.TRANSPORT_MODES, index=transport_index)
            new_note = c2.text_input('비고', value=case['note'])
            save_basic = st.form_submit_button('기본 정보 저장')

        if save_basic:
            if not new_country.strip():
                st.error('국가는 필수입니다.')
            else:
                db.execute(
                    '''UPDATE export_cases
                       SET country=?,buyer=?,expected_ship_date=?,transport_mode=?,note=?,updated_at=?
                       WHERE id=?''',
                    (new_country.strip(), new_buyer.strip(), str(new_expected), new_transport,
                     new_note.strip(), db.now_text(), case_id),
                )
                db.sync_case_folder(case_id)
                db.add_history(case_id, '수출 기본 정보 수정', f'{new_country} / {new_transport}')
                st.success('기본 정보를 저장했습니다.')
                st.rerun()

        existing = dataframe(
            'SELECT product_name AS 제품명, quantity AS 수량, unit AS 단위 FROM order_items WHERE case_id=? ORDER BY id',
            (case_id,),
        )
        if existing.empty:
            existing = pd.DataFrame([{'제품명': '', '수량': 0.0, '단위': 'EA'}])

        edited = st.data_editor(
            existing,
            num_rows='dynamic',
            hide_index=True,
            use_container_width=True,
            key=f'orders_{case_id}',
            column_config={
                '제품명': st.column_config.TextColumn('제품명', required=True),
                '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0),
                '단위': st.column_config.TextColumn('단위'),
            },
        )
        if st.button('주문 목록 저장', type='primary', key=f'save_orders_{case_id}'):
            try:
                replace_order_items(case_id, edited)
            except ValueError as exc:
                st.error(str(exc))
            else:
                db.sync_case_folder(case_id)
                db.add_history(case_id, '주문 목록 저장', f'{len(edited)}행')
                st.success('주문 목록을 저장했습니다.')
                st.rerun()
