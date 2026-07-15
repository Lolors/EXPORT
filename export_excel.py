from __future__ import annotations

from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import db

BLUE = "315B7D"
LIGHT_BLUE = "D9E5F0"
PALE = "EAF1F8"
BORDER = "B8C2CC"


def _border(style: str = "thin") -> Border:
    side = Side(style=style, color=BORDER)
    return Border(top=side, bottom=side, left=side, right=side)


def _write_pair(ws, row: int, label1: str, value1, label2: str, value2) -> None:
    ws[f"A{row}"] = label1
    ws[f"B{row}"] = value1
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
    ws[f"F{row}"] = label2
    ws[f"G{row}"] = value2
    ws.merge_cells(start_row=row, start_column=7, end_row=row, end_column=10)
    for cell in (ws[f"A{row}"], ws[f"F{row}"]):
        cell.fill = PatternFill("solid", fgColor=LIGHT_BLUE)
        cell.font = Font(bold=True)
    for col in range(1, 11):
        ws.cell(row, col).border = _border()
        ws.cell(row, col).alignment = Alignment(vertical="center", wrap_text=True)


def build_packing_list(case_id: int, include_lot: bool = False, include_expiry: bool = False) -> bytes:
    case = db.row("SELECT * FROM export_cases WHERE id = ?", (case_id,))
    if not case:
        raise ValueError("수출 건을 찾을 수 없습니다.")

    items = db.rows("SELECT * FROM packing_items WHERE case_id = ? ORDER BY box_no, id", (case_id,))

    wb = Workbook()
    ws = wb.active
    ws.title = "Packing List"

    ws.merge_cells("A1:J2")
    ws["A1"] = "PACKING LIST"
    ws["A1"].font = Font(size=20, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = PatternFill("solid", fgColor=PALE)

    ws.merge_cells("A4:E4")
    ws.merge_cells("F4:J4")
    ws["A4"] = "EXPORTER / SHIPPER"
    ws["F4"] = "CONSIGNEE"
    for cell in (ws["A4"], ws["F4"]):
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")

    ws.merge_cells("A5:E8")
    ws.merge_cells("F5:J8")
    ws["A5"] = "NOTUSPHARM CO., LTD.\nRepresentative: Noh Jin-kook\nRepublic of Korea"
    ws["F5"] = f"{case['buyer']}\n{case['country']}"
    for row_num in range(5, 9):
        for col in range(1, 11):
            ws.cell(row_num, col).alignment = Alignment(vertical="top", wrap_text=True)
            ws.cell(row_num, col).border = _border()

    _write_pair(ws, 10, "Packing List No.", case["export_no"], "Invoice No.", case["invoice_no"])
    _write_pair(ws, 11, "Date", case["expected_ship_date"], "Country of Destination", case["country"])
    _write_pair(ws, 12, "Mode of Transport", case["transport_mode"], "Terms of Delivery", case["incoterms"])
    _write_pair(ws, 13, "Port of Loading", case["port_loading"], "Final Destination", case["final_destination"])

    headers = ["BOX NO.", "MARKS", "PRODUCT DESCRIPTION"]
    if include_lot:
        headers.append("LOT NO.")
    if include_expiry:
        headers.append("EXPIRY DATE")
    headers += ["QTY", "UNIT", "N.W. (KG)", "G.W. (KG)", "MEASUREMENT (CM)"]

    start_row = 16
    for idx, header in enumerate(headers, 1):
        cell = ws.cell(start_row, idx, header)
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _border()

    total_qty = 0.0
    total_net = 0.0
    gross_by_box: dict[int, float] = {}
    cbm_by_box: dict[int, float] = {}

    row_num = start_row + 1
    for item in items:
        measurement = f"{item['length_cm']:g} × {item['width_cm']:g} × {item['height_cm']:g}"
        values = [item["box_no"], item["marks"], item["product_name"]]
        if include_lot:
            values.append(item["lot_no"])
        if include_expiry:
            values.append(item["expiry_date"])
        values += [item["quantity"], item["unit"], item["net_weight"], item["gross_weight"], measurement]

        for idx, value in enumerate(values, 1):
            cell = ws.cell(row_num, idx, value)
            cell.alignment = Alignment(horizontal="center" if idx != 3 else "left", vertical="center", wrap_text=True)
            cell.border = _border()

        total_qty += float(item["quantity"] or 0)
        total_net += float(item["net_weight"] or 0)
        box_no = int(item["box_no"])
        gross_by_box[box_no] = max(gross_by_box.get(box_no, 0), float(item["gross_weight"] or 0))
        cbm_by_box[box_no] = max(
            cbm_by_box.get(box_no, 0),
            float(item["length_cm"] or 0) * float(item["width_cm"] or 0) * float(item["height_cm"] or 0) / 1_000_000,
        )
        row_num += 1

    total_row = row_num + 1
    last_col = len(headers)
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=max(3, last_col - 5))
    ws.cell(total_row, 1, "TOTAL")
    ws.cell(total_row, last_col - 4, total_qty)
    ws.cell(total_row, last_col - 3, "UNITS")
    ws.cell(total_row, last_col - 2, total_net)
    ws.cell(total_row, last_col - 1, sum(gross_by_box.values()))
    ws.cell(total_row, last_col, f"{len(gross_by_box)} CARTONS")
    for col in range(1, last_col + 1):
        cell = ws.cell(total_row, col)
        cell.fill = PatternFill("solid", fgColor=LIGHT_BLUE)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = _border("medium")

    summary_row = total_row + 2
    summary = [
        ("TOTAL PACKAGES", f"{len(gross_by_box)} CARTONS", "TOTAL QUANTITY", total_qty),
        ("TOTAL NET WEIGHT", f"{total_net:.2f} KG", "TOTAL GROSS WEIGHT", f"{sum(gross_by_box.values()):.2f} KG"),
        ("TOTAL VOLUME", f"{sum(cbm_by_box.values()):.3f} CBM", "SHIPMENT TYPE", "NON-DANGEROUS GOODS"),
    ]
    for offset, (a, b, c, d) in enumerate(summary):
        r = summary_row + offset
        _write_pair(ws, r, a, b, c, d)

    note_row = summary_row + 5
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 1, end_column=last_col)
    ws.cell(note_row, 1, "We hereby certify that the information contained in this Packing List is true and correct.")
    ws.cell(note_row, 1).alignment = Alignment(wrap_text=True, vertical="center")
    ws.cell(note_row, 1).font = Font(italic=True)

    sign_row = note_row + 4
    ws.merge_cells(start_row=sign_row, start_column=max(1, last_col - 3), end_row=sign_row, end_column=last_col)
    ws.cell(sign_row, max(1, last_col - 3), "Authorized Signature")
    ws.cell(sign_row, max(1, last_col - 3)).alignment = Alignment(horizontal="center")
    ws.cell(sign_row, max(1, last_col - 3)).font = Font(bold=True)
    ws.cell(sign_row, max(1, last_col - 3)).border = Border(top=Side(style="thin", color="333333"))

    widths = [10, 15, 36, 15, 14, 10, 10, 12, 12, 20]
    for idx in range(1, last_col + 1):
        ws.column_dimensions[get_column_letter(idx)].width = widths[min(idx - 1, len(widths) - 1)]
    ws.freeze_panes = "A16"

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()
