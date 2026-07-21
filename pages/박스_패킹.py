from __future__ import annotations

import streamlit as st

import db


st.set_page_config(page_title='박스 패킹', page_icon='📦', layout='wide')
db.init_db()


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['stage']}"


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return '0'


st.title('박스 패킹')
st.caption('실제 출고제품을 기준으로 제품·수량과 박스번호를 연결하고, 박스별 규격과 무게를 입력합니다.')

cases = db.rows(
    "SELECT * FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소') ORDER BY expected_ship_date, created_at"
)
if not cases:
    st.info('진행 중 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='actual_packing_case')]
case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))

items = db.rows(
    '''SELECT id, business_unit, location, product_name, lot_no, expiry_date,
              requested_qty, box_no
       FROM shipment_items
       WHERE case_id=?
       ORDER BY CASE WHEN box_no IS NULL THEN 0 ELSE 1 END, box_no, id''',
    (case_id,),
)

if not items:
    st.warning('연결된 실제 출고제품이 없습니다. 먼저 실출고 연결 입력에서 실제 제품을 등록하세요.')
    st.stop()

unpacked_count = sum(1 for item in items if item['box_no'] is None)
packed_count = len(items) - unpacked_count
box_count = len({item['box_no'] for item in items if item['box_no'] is not None})
total_qty = sum(float(item['requested_qty'] or 0) for item in items)

m1, m2, m3, m4 = st.columns(4)
m1.metric('실제 출고 행', f'{len(items)}개')
m2.metric('총 출고수량', fmt_number(total_qty))
m3.metric('패킹 완료 행', f'{packed_count}개')
m4.metric('사용 박스', f'{box_count}개')

st.divider()
st.markdown('#### 실제 출고제품 선택')
st.caption('사업장·로케이션·실제 제품명·제조번호·유통기한·출고수량을 확인한 뒤 박스번호를 배정하세요.')

header = st.columns([0.55, 1.15, 1.15, 2.5, 1.35, 1.35, 0.9, 1.0])
for column, title in zip(
    header,
    ['선택', '사업장', '로케이션', '실제 제품명', '제조번호', '유통기한', '출고수량', '현재 박스'],
):
    column.markdown(f'**{title}**')

selected_ids: list[int] = []
for item in items:
    cols = st.columns([0.55, 1.15, 1.15, 2.5, 1.35, 1.35, 0.9, 1.0])
    selected = cols[0].checkbox(
        '선택',
        key=f'pack_select_{case_id}_{item["id"]}',
        label_visibility='collapsed',
    )
    if selected:
        selected_ids.append(int(item['id']))
    cols[1].write(item['business_unit'] or '-')
    cols[2].write(item['location'] or '-')
    cols[3].write(item['product_name'] or '-')
    cols[4].write(item['lot_no'] or '-')
    cols[5].write(item['expiry_date'] or '-')
    cols[6].write(fmt_number(item['requested_qty']))
    cols[7].write(f"BOX {item['box_no']}" if item['box_no'] is not None else '미패킹')

st.divider()
next_box_row = db.row('SELECT COALESCE(MAX(box_no),0)+1 AS n FROM boxes WHERE case_id=?', (case_id,))
next_box = int(next_box_row['n'] or 1)
assign_col, button_col = st.columns([1, 2])
box_no = assign_col.number_input('배정할 박스번호', min_value=1, value=next_box, step=1)

with button_col:
    st.write('')
    st.write('')
    assign_clicked = st.button('선택 제품을 박스에 배정', type='primary', use_container_width=True)

if assign_clicked:
    if not selected_ids:
        st.error('박스에 넣을 실제 출고제품을 선택하세요.')
    else:
        for item_id in selected_ids:
            db.execute(
                'UPDATE shipment_items SET box_no=?,updated_at=? WHERE id=? AND case_id=?',
                (int(box_no), db.now_text(), item_id, case_id),
            )
        db.execute(
            'INSERT OR IGNORE INTO boxes(case_id,box_no,updated_at) VALUES (?,?,?)',
            (case_id, int(box_no), db.now_text()),
        )
        db.execute(
            "UPDATE export_cases SET stage='패킹',updated_at=? WHERE id=?",
            (db.now_text(), case_id),
        )
        db.add_history(case_id, '박스 패킹', f'{len(selected_ids)}개 실제 출고 행 → BOX {int(box_no)}')
        st.success(f'{len(selected_ids)}개 실제 출고 행을 BOX {int(box_no)}에 배정했습니다.')
        st.rerun()

if selected_ids and st.button('선택 제품 박스 배정 해제'):
    for item_id in selected_ids:
        db.execute(
            'UPDATE shipment_items SET box_no=NULL,updated_at=? WHERE id=? AND case_id=?',
            (db.now_text(), item_id, case_id),
        )
    db.add_history(case_id, '박스 배정 해제', f'{len(selected_ids)}개 실제 출고 행')
    st.success('선택한 제품의 박스 배정을 해제했습니다.')
    st.rerun()

st.divider()
st.markdown('#### 번호별 박스 정보')
boxes = db.rows('SELECT * FROM boxes WHERE case_id=? ORDER BY box_no', (case_id,))
if not boxes:
    st.info('아직 생성된 박스가 없습니다.')
else:
    for box in boxes:
        box_items = db.rows(
            '''SELECT business_unit, location, product_name, lot_no, expiry_date, requested_qty
               FROM shipment_items
               WHERE case_id=? AND box_no=?
               ORDER BY id''',
            (case_id, box['box_no']),
        )
        box_qty = sum(float(item['requested_qty'] or 0) for item in box_items)
        with st.expander(
            f"BOX {box['box_no']} · {len(box_items)}개 행 · 수량 {fmt_number(box_qty)}",
            expanded=True,
        ):
            if box_items:
                st.dataframe(
                    [
                        {
                            '사업장': item['business_unit'],
                            '로케이션': item['location'],
                            '실제 제품명': item['product_name'],
                            '제조번호': item['lot_no'],
                            '유통기한': item['expiry_date'],
                            '수량': item['requested_qty'],
                        }
                        for item in box_items
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption('이 박스에 연결된 제품이 없습니다.')

            with st.form(f'box_info_{case_id}_{box["id"]}'):
                c1, c2, c3, c4 = st.columns(4)
                length = c1.number_input('가로(cm)', min_value=0.0, value=float(box['length_cm'] or 0), key=f'len_{box["id"]}')
                width = c2.number_input('세로(cm)', min_value=0.0, value=float(box['width_cm'] or 0), key=f'wid_{box["id"]}')
                height = c3.number_input('높이(cm)', min_value=0.0, value=float(box['height_cm'] or 0), key=f'hei_{box["id"]}')
                weight = c4.number_input('무게(kg)', min_value=0.0, value=float(box['weight_kg'] or 0), key=f'wei_{box["id"]}')
                save_box = st.form_submit_button('박스 정보 저장', type='primary')

            if save_box:
                db.execute(
                    'UPDATE boxes SET length_cm=?,width_cm=?,height_cm=?,weight_kg=?,updated_at=? WHERE id=?',
                    (length, width, height, weight, db.now_text(), box['id']),
                )
                db.add_history(case_id, '박스 정보 수정', f"BOX {box['box_no']}")
                st.success(f"BOX {box['box_no']} 정보를 저장했습니다.")
                st.rerun()

st.caption(f'현재 미패킹 실제 출고 행: {unpacked_count}개')
