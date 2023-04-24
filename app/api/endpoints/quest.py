from fastapi_crudrouter import SQLAlchemyCRUDRouter

from app.api.models.quest import Quest, QuestRead, QuestCreate, QuestUpdate
from app.db.base import get_session

router = SQLAlchemyCRUDRouter(
    schema=QuestRead,
    create_schema=QuestCreate,
    update_schema=QuestUpdate,
    db_model=Quest,
    db=get_session,
    delete_all_route=False,
    get_one_route=False
)
