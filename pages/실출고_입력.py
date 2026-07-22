from __future__ import annotations

import streamlit as st

import db


st.set_page_config(page_title='실출고 입력', page_icon='📦', layout='wide')
db.init_db()


def ensure_order_item_link_column() -> None:
    columns = {row['name'] for row in db.rows('PRAGMA table_info(shipment_items)')}
    if 'order_item_id' not in columns:
        db.execute('ALTER TABLE shipment_items ADD COLUMN order_item_id INTEGER REFERENCES order_items(id)')


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return '0'


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['stage']}"


def order_state(order_qty: float, linked_qty: float) -> tuple[str, str]:
    if order_qty > 0 and linked_qty >= order_qty:
        return '🟢', '확보 완료'
    if linked_qty > 0:
        return '🟡', '일부 확보'
    return '🔴', '미확보'


def linked_rows(order_item_id: int):
    return db.rows(
        '''SELECT id, business_unit, product_name, lot_no, expiry_date,
                  requested_qty, box_no
           FROM shipment_items
           WHERE order_item_id=?
           ORDER BY id''',
        (order_item_id,),
    )


ensure_order_item_link_column()
pd = __import__('pandas')

st.title('실출고 입력')
st.caption('주문품목별로 실제 출고제품의 사업장, 제품명, 제조번호, 유통기한과 수량을 연결합니다.')

cases = db.rows(
    "SELECT * FROM export_cases WHERE status<>'취소' AND stage NOT IN ('완료','취소') ORDER BY expected_ship_date, created_at"
)
if not cases:
    st.info('진행 중인 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='linked_shipment_case')]
orders = db.rows('SELECT id, product_name, quantity, unit FROM order_items WHERE case_id=? ORDER BY id', (case_id,))

if not orders:
    st.warning('먼저 주문품목을 입력하세요.')
    st.stop()

unlinked_count = db.row(
    'SELECT COUNT(*) AS count FROM shipment_items WHERE case_id=? AND order_item_id IS NULL',
    (case_id,),
)['count']
if unlinked_count:
    st.warning(f'구형 실출고 데이터 중 주문품목에 연결되지 않은 행이 {unlinked_count}개 있습니다. 최신 입력 방식으로 다시 연결해 주세요.')

for order in orders:
    order_id = int(order['id'])
    order_qty = float(order['quantity'] or 0)
    unit = str(order['unit'] or 'EA')
    current = linked_rows(order_id)
    linked_qty = sum(float(row['requested_qty'] or 0) for row in current)
    icon, state = order_state(order_qty, linked_qty)

    with st.expander(
        f"{icon} {order['product_name']} · 주문 {fmt_number(order_qty)} {unit} · 실출고 {fmt_number(linked_qty)} {unit} · {state}",
        expanded=linked_qty < order_qty,
    ):
        st.caption('한 주문품목에 실제 제품이나 제조번호가 여러 개면 행을 추가해 각각 입력하세요.')

        if current:
            source = pd.DataFrame([
                {
                    '사업장': row['business_unit'] or '',
                    '실제 제품명': row['product_name'] or '',
                    '제조번호': row['lot_no'] or '',
                    '유통기한': row['expiry_date'] or '',
                    '출고수량': float(row['requested_qty'] or 0),
                }
                for row in current
            ])
        else:
            source = pd.DataFrame([{
                '사업장': '',
                '실제 제품명': '',
                '제조번호': '',
                '유통기한': '',
                '출고수량': 0.0,
            }])

        edited = st.data_editor(
            source,
            num_rows='dynamic',
            use_container_width=True,
            hide_index=True,
            key=f'linked_order_editor_{order_id}',
            column_config={
                '사업장': st.column_config.TextColumn('사업장'),
                '실제 제품명': st.column_config.TextColumn('실제 제품명', required=True),
                '제조번호': st.column_config.TextColumn('제조번호'),
                '유통기한': st.column_config.TextColumn('유통기한', help='예: 2028-07-01'),
                '출고수량': st.column_config.NumberColumn('출고수량', min_value=0.0, step=1.0),
            },
        )

        preview_qty = sum(float(value or 0) for value in edited.get('출고수량', []))
        preview_icon, preview_state = order_state(order_qty, preview_qty)
        st.info(f'{preview_icon} 입력 합계 {fmt_number(preview_qty)} / 주문 {fmt_number(order_qty)} {unit} · {preview_state}')

        if st.button('이 주문품목의 실출고 저장', type='primary', key=f'save_linked_order_{order_id}'):
            values = []
            invalid_row = False
            for _, row in edited.iterrows():
                actual_name = str(row.get('실제 제품명', '') or '').strip()
                qty = float(row.get('출고수량', 0) or 0)
                has_any_value = any(
                    str(row.get(column, '') or '').strip()
                    for column in ['사업장', '실제 제품명', '제조번호', '유통기한']
                ) or qty > 0
                if not has_any_value:
                    continue
                if not actual_name:
                    invalid_row = True
                    break
                values.append((
                    case_id,
                    order_id,
                    str(row.get('사업장', '') or '').strip(),
                    '',
                    actual_name,
                    str(row.get('제조번호', '') or '').strip(),
                    str(row.get('유통기한', '') or '').strip(),
                    qty,
                    None,
                    db.now_text(),
                    db.now_text(),
                ))

            if invalid_row:
                st.error('입력된 행에는 실제 제품명이 필요합니다.')
            else:
                db.execute('DELETE FROM shipment_items WHERE case_id=? AND order_item_id=?', (case_id, order_id))
                if values:
                    db.executemany(
                        '''INSERT INTO shipment_items(
                               case_id, order_item_id, business_unit, location, product_name,
                               lot_no, expiry_date, requested_qty, box_no, created_at, updated_at
                           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                        values,
                    )
                db.execute(
                    "UPDATE export_cases SET stage='실출고 입력', updated_at=? WHERE id=?",
                    (db.now_text(), case_id),
                )
                db.add_history(
                    case_id,
                    '주문품목별 실출고 저장',
                    f"{order['product_name']} · {fmt_number(preview_qty)} / {fmt_number(order_qty)} {unit}",
                )
                st.success('저장했습니다.')
                st.rerun()

st.divider()
all_linked_qty = db.row(
    'SELECT COALESCE(SUM(requested_qty),0) AS quantity FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
    (case_id,),
)['quantity']
st.caption(f'현재 주문품목에 연결된 전체 실출고 수량: {fmt_number(all_linked_qty)}')
