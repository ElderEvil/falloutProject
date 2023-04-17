from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import Session, SQLModel, create_engine, select

from Game.Items.models.weapons import WeaponCreate, Weapon, WeaponRead, WeaponUpdate
from Game.Items.router import router as item_router

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(item_router, prefix="/database", tags=["database"])


@app.post("/weapons/", response_model=WeaponRead)
def create_weapon(*, session: Session = Depends(get_session), weapon: WeaponCreate):
    db_weapon = Weapon.from_orm(weapon)
    session.add(db_weapon)
    session.commit()
    session.refresh(db_weapon)
    return db_weapon


@app.get("/weapons/", response_model=list[WeaponRead])
def read_weapons(
        *,
        session: Session = Depends(get_session),
        offset: int = 0,
        limit: int = Query(default=100, lte=100),
):
    weapons = session.exec(select(Weapon).offset(offset).limit(limit)).all()
    return weapons


@app.get("/weapons/{weapon_id}", response_model=WeaponRead)
def read_weapon(*, session: Session = Depends(get_session), weapon_id: int):
    weapon = session.get(Weapon, weapon_id)
    if not weapon:
        raise HTTPException(status_code=404, detail="Hero not found")
    return weapon


@app.patch("/weapons/{weapon_id}", response_model=WeaponRead)
def update_weapon(
        *, session: Session = Depends(get_session), weapon_id: int, weapon: WeaponUpdate
):
    db_weapon = session.get(Weapon, weapon_id)
    if not db_weapon:
        raise HTTPException(status_code=404, detail="Weapon not found")
    weapon_data = weapon.dict(exclude_unset=True)
    for key, value in weapon_data.items():
        setattr(db_weapon, key, value)
    session.add(db_weapon)
    session.commit()
    session.refresh(db_weapon)
    return db_weapon


@app.delete("/weapons/{weapon_id}")
def delete_weapon(*, session: Session = Depends(get_session), weapon_id: int):
    weapon = session.get(Weapon, weapon_id)
    if not weapon:
        raise HTTPException(status_code=404, detail="Weapon not found")
    session.delete(weapon)
    session.commit()
    return {"ok": True}
