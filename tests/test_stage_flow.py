from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import db
from services import stage_service
from utils.dates import now_text


class StageFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        self.original_upload_dir = db.UPLOAD_DIR
        db.DB_PATH = Path(self.temp_dir.name) / 'test.db'
        db.UPLOAD_DIR = Path(self.temp_dir.name) / 'uploads'
        db._initialize_database_runtime.cache_clear()
        db.init_db.cache_clear()
        self.backup_patch = patch.object(db, 'backup_to_usb', return_value=None)
        self.backup_patch.start()
        db.init_db()

    def tearDown(self) -> None:
        self.backup_patch.stop()
        db.DB_PATH = self.original_db_path
        db.UPLOAD_DIR = self.original_upload_dir
        db._initialize_database_runtime.cache_clear()
        db.init_db.cache_clear()
        self.temp_dir.cleanup()

    def _create_case(self) -> int:
        now = now_text()
        case_id = db.execute(
            '''INSERT INTO export_cases(
                   export_no,country,stage,status,created_at,updated_at,case_type
               ) VALUES (?,?,?,?,?,?,?)''',
            ('TEST-001', 'KR', '주문 접수', '진행중', now, now, 'current'),
        )
        for product in ('A', 'B'):
            db.execute(
                '''INSERT INTO order_items(case_id,product_name,quantity,unit,created_at)
                   VALUES (?,?,?,?,?)''',
                (case_id, product, 100, 'EA', now),
            )
        return case_id

    def test_each_order_item_must_be_complete_before_packing_complete(self) -> None:
        case_id = self._create_case()
        orders = db.rows('SELECT id,product_name FROM order_items WHERE case_id=? ORDER BY id', (case_id,))
        now = now_text()

        db.execute(
            '''INSERT INTO shipment_items(
                   case_id,order_item_id,product_name,requested_qty,box_no,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)''',
            (case_id, orders[0]['id'], 'A', 100, 1, now, now),
        )
        self.assertEqual('패킹 대기', stage_service.sync_case_stage(case_id))

        db.execute(
            '''INSERT INTO shipment_items(
                   case_id,order_item_id,product_name,requested_qty,box_no,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?)''',
            (case_id, orders[1]['id'], 'B', 100, None, now, now),
        )
        self.assertEqual('패킹 대기', stage_service.sync_case_stage(case_id))

        db.execute(
            'UPDATE shipment_items SET box_no=1 WHERE case_id=? AND order_item_id=?',
            (case_id, orders[1]['id']),
        )
        self.assertEqual('패킹 완료', stage_service.sync_case_stage(case_id))


if __name__ == '__main__':
    unittest.main()
