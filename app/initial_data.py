import logging

from fastapi import Depends
from sqlmodel import Session

from app.db.base import get_session
from app.db.init_db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init(db: Session = Depends(get_session)) -> None:
    init_db(db)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
