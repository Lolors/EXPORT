from __future__ import annotations

from services import packing_service, shipment_service


def get_document_data(case_id: int):
    """Return packing rows and actual shipment rows for shareable documents."""
    return packing_service.list_packed_rows(case_id), shipment_service.list_actual(case_id)
