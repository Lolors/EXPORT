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


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    type_label = '과거' if case['case_type'] == 'historical' else '진행'
    return f"[{type_label}] {case['export_no']} · {case['country']}{buyer} · {case['stage']}"


def sync_historical_shipments(case_id: int) -> None:
    case = db.row('SELECT case_type FROM export_cases WHERE id=?', (case_id,))
    if not case or case['case_type'] != 'historical':
        return

    now = db.now_text()
    orders = db.rows(
        'SELECT id, product_name, quantity FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    order_ids = {int(row['id']) for row in orders}

    for order in orders:
        shipment = db.row(
            'SELECT id FROM shipment_items WHERE case_id=? AND order_item_id=? ORDER BY id LIMIT 1',
            (case_id, order['id']),
        )
        if shipment:
            db.execute(
                '''UPDATE shipment_items
                   SET product_name=?,requested_qty=?,updated_at=?
                   WHERE id=?''',
                (order['product_name'], order['quantity'], now, shipment['id']),
            )
            db.execute(
                'DELETE FROM shipment_items WHERE case_id=? AND order_item_id=? AND id<>?',
                (case_id, order['id'], shipment['id']),
            )
        else:
            db.execute(
                '''INSERT INTO shipment_items(
                       case_id,order_item_id,business_unit,location,product_name,
                       lot_no,expiry_date,requested_qty,box_no,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (case_id, order['id'], '', '', order['product_name'], '', '',
                 order['quantity'], None, now, now),
            )

    linked = db.rows(
        'SELECT id, order_item_id FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
        (case_id,),
    )
    for shipment in linked:
        if int(shipment['order_item_id']) not in order_ids:
            db.execute('DELETE FROM shipment_items WHERE id=?', (shipment['id'],))


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
    case = db.row('SELECT case_type FROM export_cases WHERE id=?', (case_id,))
    historical = bool(case and case['case_type'] == 'historical')

    for _, row in edited.iterrows():
        raw_id = row.get('_id')
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
        if not historical and int(row['linked_count'] or 0) > 0:
            raise ValueError(f"실출고가 연결된 주문품목 '{row['product_name']}'은 삭제할 수 없습니다. 수량·제품명 수정은 가능합니다.")
        db.execute('DELETE FROM shipment_items WHERE case_id=? AND order_item_id=?', (case_id, order_id))
        db.execute('DELETE FROM order_items WHERE id=? AND case_id=?', (order_id, case_id))

    sync_historical_shipments(case_id)


st.title('수출 주문 입력 및 수정')
st.caption('현재 진행 건은 주문목록을 등록하고, 과거 수출 건은 주문목록을 실출고 제품으로도 자동 저장합니다.')

pd = get_pandas()

st.markdown('#### 수출 주문 등록')
case_type_label = st.radio(
    '등록 유형',
    ['현재 진행 건', '과거 수출 건'],
    horizontal=True,
    key='new_case_type',
)
is_historical = case_type_label == '과거 수출 건'

c1, c2 = st.columns(2)
country = c1.text_input('국가 *', key='new_country')
buyer = c2.text_input('바이어 (선택)', key='new_buyer')
transport = c1.selectbox('운송방식', db.TRANSPORT_MODES, key='new_transport')
note = c2.text_input('비고', key='new_note')

historical_date = None
if is_historical:
    historical_date = st.date_input(
        '과거 수출일',
        value=date.today(),
        help='수출번호의 연도와 폴더 연도를 결정하며, 국내배송 완료일로 저장됩니다.',
        key='historical_export_date',
    )
    export_no_preview = db.next_export_no('HIS', historical_date.year)
else:
    export_no_preview = db.next_export_no('EXP')

st.text_input('수출번호', value=export_no_preview, disabled=True, key='new_export_no')

st.markdown('#### 주문 목록' if not is_historical else '#### 실출고 제품 목록')
if is_historical:
    st.caption('과거 수출 건에서는 아래 목록이 주문목록과 실출고 제품에 동시에 저장됩니다.')
new_order_source = pd.DataFrame([{'제품명': '', '수량': 0.0, '단위': 'EA'}])
new_orders = st.data_editor(
    new_order_source,
    num_rows='dynamic',
    hide_index=True,
    use_container_width=True,
    key='new_order_items',
    column_config={
        '제품명': st.column_config.TextColumn('제품명', required=True),
        '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0),
        '단위': st.column_config.TextColumn('단위'),
    },
)

if st.button('수출 건 생성', type='primary', key='create_case'):
    valid_orders = []
    for _, row in new_orders.iterrows():
        product_name = str(row.get('제품명', '') or '').strip()
        if not product_name:
            continue
        valid_orders.append((
            product_name,
            float(row.get('수량', 0) or 0),
            str(row.get('단위', 'EA') or 'EA').strip() or 'EA',
        ))

    if not country.strip():
        st.error('국가는 필수입니다.')
    elif not valid_orders:
        st.error('제품을 한 개 이상 입력하세요.')
    else:
        prefix = 'HIS' if is_historical else 'EXP'
        number_year = historical_date.year if historical_date else None
        export_no = db.next_export_no(prefix, number_year)
        now = db.now_text()
        case_type = 'historical' if is_historical else 'current'
        actual_ship_date = str(historical_date) if historical_date else ''
        stage = '완료' if is_historical else '주문 접수'
        status = '완료' if is_historical else '진행중'
        case_id = db.execute(
            '''INSERT INTO export_cases(
                   export_no,buyer,country,transport_mode,stage,status,note,
                   actual_ship_date,case_type,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (export_no, buyer.strip(), country.strip(), transport, stage, status,
             note.strip(), actual_ship_date, case_type, now, now),
        )

        for product_name, quantity, unit in valid_orders:
            order_id = db.execute(
                'INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',
                (case_id, product_name, quantity, unit, now),
            )
            if is_historical:
                db.execute(
                    '''INSERT INTO shipment_items(
                           case_id,order_item_id,business_unit,location,product_name,
                           lot_no,expiry_date,requested_qty,box_no,created_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (case_id, order_id, '', '', product_name, '', '', quantity,
                     None, now, now),
                )

        db.sync_case_folder(case_id)
        history_detail = f'{export_no} / 제품 {len(valid_orders)}개'
        if is_historical:
            history_detail += ' / 주문목록=실출고'
        db.add_history(case_id, '수출 건 생성', history_detail)
        st.session_state['order_case_id'] = case_id
        st.success(f'{export_no} 생성 완료')
        st.rerun()

# 수정 영역은 사용자가 수출 건을 선택한 뒤에만 주문품목까지 조회한다.
cases = db.rows(
    '''SELECT id, export_no, buyer, country, transport_mode, stage, status,
              note, actual_ship_date, case_type, created_at
       FROM export_cases
       WHERE stage<>'취소'
       ORDER BY created_at DESC'''
)
if not cases:
    st.info('수정할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
selected_case_id = st.session_state.get('order_case_id')
labels = list(options)
default_index = 0
if selected_case_id in options.values():
    default_index = list(options.values()).index(selected_case_id)
case_id = options[st.selectbox('주문을 수정할 수출 건', labels, index=default_index)]

case_map = {int(row['id']): row for row in cases}
case = case_map[case_id]

with st.form(f'case_edit_{case_id}'):
    st.markdown('#### 기본 정보 수정')
    c1, c2 = st.columns(2)
    new_country = c1.text_input('국가 *', value=case['country'])
    new_buyer = c2.text_input('바이어 (선택)', value=case['buyer'])
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
               SET country=?,buyer=?,transport_mode=?,note=?,updated_at=?
               WHERE id=?''',
            (new_country.strip(), new_buyer.strip(), new_transport,
             new_note.strip(), db.now_text(), case_id),
        )
        db.sync_case_folder(case_id)
        db.add_history(case_id, '수출 기본 정보 수정', f'{new_country} / {new_transport}')
        st.success('기본 정보를 저장했습니다.')
        st.rerun()

existing = dataframe(
    '''SELECT o.id AS _id, o.product_name AS 제품명, o.quantity AS 수량, o.unit AS 단위
       FROM order_items o
       WHERE o.case_id=?
       ORDER BY o.id''',
    (case_id,),
)
if existing.empty:
    existing = pd.DataFrame([{'_id': None, '제품명': '', '수량': 0.0, '단위': 'EA'}])

historical_case = case['case_type'] == 'historical'
st.markdown('#### 실출고 제품 수정' if historical_case else '#### 주문품목 수정')
if historical_case:
    st.caption('과거 수출 건에서는 수정한 내용이 주문목록과 실출고 제품에 함께 반영됩니다.')
else:
    st.caption('실출고가 연결된 행은 삭제할 수 없지만 제품명·수량·단위는 수정할 수 있습니다.')
edited = st.data_editor(
    existing,
    num_rows='dynamic',
    hide_index=True,
    use_container_width=True,
    key=f'orders_{case_id}',
    column_order=['제품명', '수량', '단위'],
    column_config={
        '_id': None,
        '제품명': st.column_config.TextColumn('제품명', required=True),
        '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0),
        '단위': st.column_config.TextColumn('단위'),
    },
)
if st.button('목록 저장' if historical_case else '주문 목록 저장', type='primary', key=f'save_orders_{case_id}'):
    try:
        save_order_items(case_id, edited)
    except ValueError as exc:
        st.error(str(exc))
    else:
        db.sync_case_folder(case_id)
        action = '과거 실출고 목록 저장' if historical_case else '주문 목록 저장'
        db.add_history(case_id, action, f'{len(edited)}행')
        st.success('목록을 저장했습니다.')
        st.rerun()
