from fastapi import APIRouter

router = APIRouter()


@router.post("/")
def read_items():
    return {"message": ["Item One", "Item Two"]}