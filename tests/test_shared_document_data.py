from __future__ import annotations

import unittest

from services.document_service import _build_shipment_product_rows


class SharedDocumentDataTests(unittest.TestCase):
    def test_uses_order_data_when_product_has_not_arrived(self) -> None:
        orders = [
            {'id': 1, 'product_name': '주문 제품 A', 'quantity': 100, 'unit': 'BOX'},
        ]

        rows = _build_shipment_product_rows(orders, [])

        self.assertEqual([{
            'business_unit': '',
            'product_name': '주문 제품 A',
            'lot_no': '',
            'expiry_date': '',
            'unit': 'BOX',
            'requested_qty': 100.0,
        }], rows)

    def test_uses_received_product_data_instead_of_order_data(self) -> None:
        orders = [
            {'id': 1, 'product_name': '주문명', 'quantity': 100, 'unit': 'BOX'},
        ]
        actual = [{
            'order_item_id': 1,
            'business_unit': '노투스팜',
            'product_name': '실제 입고 제품명',
            'lot_no': 'LOT-01',
            'expiry_date': '2028-12-31',
            'unit': 'BOX',
            'requested_qty': 100,
        }]

        rows = _build_shipment_product_rows(orders, actual)

        self.assertEqual(1, len(rows))
        self.assertEqual('실제 입고 제품명', rows[0]['product_name'])
        self.assertEqual('노투스팜', rows[0]['business_unit'])
        self.assertEqual('LOT-01', rows[0]['lot_no'])
        self.assertEqual('2028-12-31', rows[0]['expiry_date'])
        self.assertEqual(100.0, rows[0]['requested_qty'])

    def test_partial_arrival_fills_only_outstanding_quantity_from_order(self) -> None:
        orders = [
            {'id': 1, 'product_name': '주문 제품 A', 'quantity': 100, 'unit': 'EA'},
            {'id': 2, 'product_name': '주문 제품 B', 'quantity': 50, 'unit': 'BOX'},
        ]
        actual = [{
            'order_item_id': 1,
            'business_unit': '노투스',
            'product_name': '실제 제품 A',
            'lot_no': 'LOT-A',
            'expiry_date': '2029-01-01',
            'unit': 'EA',
            'requested_qty': 40,
        }]

        rows = _build_shipment_product_rows(orders, actual)
        by_name = {row['product_name']: row for row in rows}

        self.assertEqual({'실제 제품 A', '주문 제품 A', '주문 제품 B'}, set(by_name))
        self.assertEqual(40.0, by_name['실제 제품 A']['requested_qty'])
        self.assertEqual(60.0, by_name['주문 제품 A']['requested_qty'])
        self.assertEqual(50.0, by_name['주문 제품 B']['requested_qty'])
        self.assertEqual(150.0, sum(row['requested_qty'] for row in rows))


if __name__ == '__main__':
    unittest.main()
