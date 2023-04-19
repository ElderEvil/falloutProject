from fastapi import FastAPI, Depends
from sqlmodel import Session
from starlette import status

from app.api.endpoints.api import api_router
from app.db.base import create_db_and_tables, get_session
from utils.db_init import populate_junk, populate_weapons
from utils.dump_table import dump_junk, dump_weapons

app = FastAPI()


@app.on_event("startup")
def startup_event(db: Session = Depends(get_session)):
    create_db_and_tables()
    # populate_junk(db)
    # populate_weapons(db)


@app.on_event("shutdown")
def shutdown_event(db: Session = Depends(get_session)):
    # dump_junk(db)
    # dump_weapons(db)
    with open("log.txt", mode="a") as log:
        log.write("Application shutdown")


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {'healthcheck': 'Everything OK!'}


app.include_router(api_router, prefix="/database")
