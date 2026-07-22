from __future__ import annotations

from datetime import date

import streamlit as st

import db


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


def save_order_items(case_id: int, edited) -> None:
    existing_rows = db.rows(
        '''SELECT o.id, o.product_name, o.quantity, o.unit,
                  COUNT(s.id) AS linked_count
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=?
           GROUP BY o.id, o.product_name, o.quantity, o.unit
           ORDER BY o.id''',
        (case_id,),
    )
    existing = {int(row['id']): row for row in existing_rows}
    seen_ids: set[int] = set()
    now = db.now_text()

    for _, row in edited.iterrows():
        raw_id = row.get('ID')
        order_id = int(raw_id) if raw_id not in (None, '', 0) else None
        product_name = str(row.get('제품명', '') or '').strip()
        quantity = float(row.get('수량', 0) or 0)
        unit = str(row.get('단위', 'EA') or 'EA').strip() or 'EA'

        if not product_name:
            continue

        if order_id and order_id in existing:
            seen_ids.add(order_id)
            db.execute(
                'UPDATE order_items SET product_name=?,quantity=?,unit=? WHERE id=? AND case_id=?',
                (product_name, quantity, unit, order_id, case_id),
            )
        else:
            db.execute(
                'INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',
                (case_id, product_name, quantity, unit, now),
            )

    for order_id, row in existing.items():
        if order_id in seen_ids:
            continue
        if int(row['linked_count'] or 0) > 0:
            raise ValueError(f"실출고가 연결된 주문품목 '{row['product_name']}'은 삭제할 수 없습니다. 수량·제품명 수정은 가능합니다.")
        db.execute('DELETE FROM order_items WHERE id=? AND case_id=?', (order_id, case_id))


st.title('수출 주문 입력 및 수정')
st.caption('수출 건을 생성하고 주문품목을 수정합니다. 실출고가 연결된 품목도 제품명·수량·단위를 수정할 수 있습니다.')

pd = get_pandas()

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
if not active_cases:
    st.info('수정할 진행 중 수출 건이 없습니다.')
    st.stop()

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
    '''SELECT o.id AS ID, o.product_name AS 제품명, o.quantity AS 수량, o.unit AS 단위,
              CASE WHEN EXISTS(SELECT 1 FROM shipment_items s WHERE s.order_item_id=o.id)
                   THEN '연결됨' ELSE '' END AS 실출고연결
       FROM order_items o
       WHERE o.case_id=?
       ORDER BY o.id''',
    (case_id,),
)
if existing.empty:
    existing = pd.DataFrame([{'ID': None, '제품명': '', '수량': 0.0, '단위': 'EA', '실출고연결': ''}])

st.markdown('#### 주문품목 수정')
st.caption('실출고가 연결된 행은 삭제할 수 없지만 제품명·수량·단위는 수정할 수 있습니다.')
edited = st.data_editor(
    existing,
    num_rows='dynamic',
    hide_index=True,
    use_container_width=True,
    key=f'orders_{case_id}',
    disabled=['ID', '실출고연결'],
    column_config={
        'ID': st.column_config.NumberColumn('ID'),
        '제품명': st.column_config.TextColumn('제품명', required=True),
        '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0),
        '단위': st.column_config.TextColumn('단위'),
        '실출고연결': st.column_config.TextColumn('실출고 연결'),
    },
)
if st.button('주문 목록 저장', type='primary', key=f'save_orders_{case_id}'):
    try:
        save_order_items(case_id, edited)
    except ValueError as exc:
        st.error(str(exc))
    else:
        db.sync_case_folder(case_id)
        db.add_history(case_id, '주문 목록 저장', f'{len(edited)}행')
        st.success('주문 목록을 저장했습니다.')
        st.rerun()
