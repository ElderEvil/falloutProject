from fastapi import FastAPI, Depends
from sqlmodel import Session
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.endpoints.api import api_router
from app.db.base import create_db_and_tables, get_session

app = FastAPI()


@app.on_event("startup")
def startup_event(db: Session = Depends(get_session)):
    create_db_and_tables()


@app.on_event("shutdown")
def shutdown_event(db: Session = Depends(get_session)):
    ...


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"message": "Bad request"},
    )


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {'healthcheck': 'Everything OK!'}


app.include_router(api_router, prefix="/database")
