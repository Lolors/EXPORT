from __future__ import annotations

from pathlib import Path

import db


def _style_sheet(ws, widths: dict[str, float]) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    header_fill = PatternFill('solid', fgColor='D9EAF7')
    section_fill = PatternFill('solid', fgColor='EAF2F8')
    thin = Side(style='thin', color='B8C2CC')
    for row_cells in ws.iter_rows():
        for cell in row_cells:
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            if cell.row == 1:
                cell.font = Font(bold=True, size=14)
            if cell.value is not None:
                cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row_idx in range(1, ws.max_row + 1):
        first = ws.cell(row_idx, 1)
        if first.value in {'기본 정보', '주문 목록', '실출고 진행 상황', '국내배송 정보'}:
            for cell in ws[row_idx]:
                cell.fill = section_fill
                cell.font = Font(bold=True)
        elif row_idx in {3, 11}:
            for cell in ws[row_idx]:
                cell.fill = header_fill
                cell.font = Font(bold=True)
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    ws.freeze_panes = 'A2'


def write_case_workbook(case_id: int, folder: Path) -> Path:
    from openpyxl import Workbook

    case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    if not case:
        raise ValueError(f'수출 건을 찾을 수 없습니다: {case_id}')
    folder.mkdir(parents=True, exist_ok=True)
    workbook_path = folder / '수출진행내역.xlsx'
    orders = db.rows(
        'SELECT product_name, quantity, unit, created_at FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    shipments = db.rows(
        '''SELECT o.product_name AS order_product_name, o.quantity AS order_quantity, o.unit,
                  s.business_unit, s.product_name AS actual_product_name, s.lot_no,
                  s.expiry_date, s.requested_qty, s.box_no, s.updated_at
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=? ORDER BY o.id, s.id''',
        (case_id,),
    )

    wb = Workbook()
    ws1 = wb.active
    ws1.title = '주문 접수 내역'
    ws1.append(['주문 접수 내역'])
    ws1.append(['기본 정보'])
    ws1.append(['수출번호', '국가', '바이어', '운송방식', '진행단계', '상태', '비고', '생성일', '수정일'])
    ws1.append([case['export_no'], case['country'], case['buyer'], case['transport_mode'], case['stage'], case['status'], case['note'], case['created_at'], case['updated_at']])
    ws1.append([])
    ws1.append(['주문 목록'])
    ws1.append(['제품명', '수량', '단위', '등록일'])
    for item in orders:
        ws1.append([item['product_name'], item['quantity'], item['unit'], item['created_at']])
    _style_sheet(ws1, {'A': 28, 'B': 14, 'C': 18, 'D': 14, 'E': 16, 'F': 12, 'G': 30, 'H': 20, 'I': 20})

    ws2 = wb.create_sheet('실출고 진행 상황')
    ws2.append(['실출고 진행 상황'])
    ws2.append(['주문제품', '주문수량', '단위', '사업장', '제품명', '제조번호', '유통기한', '출고수량', '박스번호', '수정일'])
    for item in shipments:
        ws2.append([item['order_product_name'], item['order_quantity'], item['unit'], item['business_unit'] or '', item['actual_product_name'] or '', item['lot_no'] or '', item['expiry_date'] or '', item['requested_qty'] or 0, item['box_no'] or '', item['updated_at'] or ''])
    _style_sheet(ws2, {'A': 28, 'B': 14, 'C': 10, 'D': 16, 'E': 28, 'F': 18, 'G': 16, 'H': 14, 'I': 12, 'J': 20})

    ws3 = wb.create_sheet('국내배송 정보')
    ws3.append(['국내배송 정보'])
    ws3.append(['항목', '내용'])
    for label, value in [
        ('국내배송 방식', case['domestic_method']), ('국내배송 일자', case['actual_ship_date']),
        ('송장번호', case['tracking_no']), ('배송기사 이름', case['driver_name']),
        ('배송기사 연락처', case['driver_phone']), ('현재 단계', case['stage']),
        ('상태', case['status']), ('비고', case['note']), ('취소 사유', case['cancel_reason']),
        ('취소 일시', case['cancelled_at']), ('최종 수정일', case['updated_at']),
    ]:
        ws3.append([label, value or ''])
    _style_sheet(ws3, {'A': 24, 'B': 48})
    wb.save(workbook_path)
    return workbook_path
