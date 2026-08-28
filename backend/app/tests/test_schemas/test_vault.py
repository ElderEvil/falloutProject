from uuid import uuid4

from app.schemas.vault import MedicalTransferRequest


def test_medical_transfer_accepts_json_uuid() -> None:
    dweller_id = uuid4()

    request = MedicalTransferRequest.model_validate(
        {"dweller_id": str(dweller_id), "stimpaks": 1, "radaways": 0}
    )

    assert request.dweller_id == dweller_id
