# 101 FastAPI Tips by [The FastAPI Expert]

This repository contains tips and tricks for FastAPI. If you have any tip that you believe is useful, feel free
to open an issue or a pull request.

Consider sponsoring me on GitHub to support my work. With your support, I will be able to create more content like this.

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor%20me%20on-GitHub-%23EA4AAA)](https://github.com/sponsors/Kludex)

> [!TIP]
> Remember to **watch this repository** to receive notifications about new tips.

## 1. Install `uvloop` and `httptools`

By default, [Uvicorn][uvicorn] doesn't come with `uvloop` and `httptools` which are faster than the default
asyncio event loop and HTTP parser. You can install them using the following command:

```bash
pip install uvloop httptools
```

> [!NOTE]
> If you're using Python 3.11+, you don't need `uvloop` because Python's default event loop is already fast enough.

## 2. Use `python-multipart` to parse form data

If you're using form data in your FastAPI application, you need to install `python-multipart`:

```bash
pip install python-multipart
```

## 3. Use `lifespan` to manage startup and shutdown events

Use `lifespan` context manager to manage startup and shutdown events instead of using `on_event` decorator:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    yield
    # Shutdown
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)
```

## 4. Use `Response` directly to return custom responses

If you need to return a custom response, use `Response` directly:

```python
from fastapi import Response

@app.get("/custom-response")
async def custom_response():
    return Response(
        content="Hello, World!",
        media_type="text/plain",
        headers={"Custom-Header": "Custom-Value"},
    )
```

## 5. Use `HTTPException` to return HTTP errors

Use `HTTPException` to return HTTP errors with proper status codes and detail messages:

```python
from fastapi import HTTPException

@app.get("/users/{user_id}")
async def read_user(user_id: int):
    if user_id == 1:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id}
```

## 6. Use `status` module to get HTTP status codes

Use `status` module from `fastapi` to get HTTP status codes:

```python
from fastapi import status

@app.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(user: User):
    # Create user
    return {"message": "User created successfully"}
```

## 7. Use `Depends` to inject dependencies

Use `Depends` to inject dependencies into your endpoints:

```python
from fastapi import Depends

async def get_current_user():
    # Get current user
    return {"username": "john.doe"}

@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
```

## 8. Use `APIRouter` to organize your routes

Use `APIRouter` to organize your routes into modules:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def read_users():
    return [{"username": "john.doe"}, {"username": "jane.doe"}]

@router.get("/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}
```

## 9. Use `Query` to add validation to query parameters

Use `Query` to add validation to query parameters:

```python
from fastapi import Query

@app.get("/users/")
async def read_users(skip: int = Query(0, ge=0), limit: int = Query(100, ge=0, le=100)):
    return {"skip": skip, "limit": limit}
```

## 10. Use `Path` to add validation to path parameters

Use `Path` to add validation to path parameters:

```python
from fastapi import Path

@app.get("/items/{item_id}")
async def read_item(item_id: int = Path(..., gt=0)):
    return {"item_id": item_id}
```

## 11. Use `Body` to add validation to request body

Use `Body` to add validation to request body:

```python
from fastapi import Body

@app.post("/items/")
async def create_item(item: dict = Body(...)):
    return item
```

## 12. Use `Form` to handle form data

Use `Form` to handle form data:

```python
from fastapi import Form

@app.post("/login/")
async def login(username: str = Form(...), password: str = Form(...)):
    return {"username": username}
```

## 13. Use `File` and `UploadFile` to handle file uploads

Use `File` and `UploadFile` to handle file uploads:

```python
from fastapi import File, UploadFile

@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    return {"filename": file.filename}
```

## 14. Use `Header` to handle header parameters

Use `Header` to handle header parameters:

```python
from fastapi import Header

@app.get("/headers/")
async def read_headers(user_agent: str = Header(...)):
    return {"User-Agent": user_agent}
```

## 15. Use `Cookie` to handle cookies

Use `Cookie` to handle cookies:

```python
from fastapi import Cookie

@app.get("/cookies/")
async def read_cookies(session_id: str = Cookie(...)):
    return {"session_id": session_id}
```

## 16. Use `Security` to handle authentication

Use `Security` to handle authentication:

```python
from fastapi import Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@app.get("/users/me")
async def read_users_me(credentials: HTTPBasicCredentials = Security(security)):
    return {"username": credentials.username, "password": credentials.password}
```

## 17. Use `OAuth2PasswordBearer` to handle OAuth2 authentication

Use `OAuth2PasswordBearer` to handle OAuth2 authentication:

```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def read_users_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

## 18. Use `BackgroundTasks` to run background tasks

Use `BackgroundTasks` to run background tasks:

```python
from fastapi import BackgroundTasks

def write_notification(email: str, message=""):
    with open("log.txt", mode="w") as email_file:
        content = f"notification for {email}: {message}"
        email_file.write(content)

@app.post("/send-notification/{email}")
async def send_notification(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(write_notification, email, message="some notification")
    return {"message": "Notification sent in the background"}
```

## 19. Use `WebSocket` to handle WebSocket connections

Use `WebSocket` to handle WebSocket connections:

```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

## 20. Use `Request` and `Response` to access request and response objects

Use `Request` and `Response` to access request and response objects:

```python
from fastapi import Request, Response

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

## 21. Use `StaticFiles` to serve static files

Use `StaticFiles` to serve static files:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

## 22. Use `ExceptionHandlers` to handle exceptions

Use `ExceptionHandlers` to handle exceptions:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"message": str(exc)},
    )
```

## 23. Use `TestClient` to test your FastAPI application

Use `TestClient` to test your FastAPI application:

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

## 24. Use `pytest` to run your tests

Use `pytest` to run your tests:

```bash
pip install pytest
pytest
```

## 25. Use `pytest-asyncio` to run async tests

Use `pytest-asyncio` to run async tests:

```bash
pip install pytest-asyncio
pytest
```

## 26. Use `httpx` to test async endpoints

Use `httpx` to test async endpoints:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_read_main():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

## 27. Use `Depends` with `async` functions

Use `Depends` with `async` functions:

```python
async def get_current_user():
    # Get current user
    return {"username": "john.doe"}

@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
```

## 28. Use `async` dependencies with `async` context managers

Use `async` dependencies with `async` context managers:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 29. Use `async` dependencies with `async` generators

Use `async` dependencies with `async` generators:

```python
async def get_db():
    async with async_session() as session:
        yield session

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 30. Use `async` dependencies with `async` context managers and `async` generators

Use `async` dependencies with `async` context managers and `async` generators:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 31. Use `async` dependencies with `async` context managers and `async` generators and `async` functions

Use `async` dependencies with `async` context managers and `async` generators and `async` functions:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 32. Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes

Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 33. Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods

Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 34. Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods and `async` properties

Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods and `async` properties:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

## 35. Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods and `async` properties and `async` descriptors

Use `async` dependencies with `async` context managers and `async` generators and `async` functions and `async` classes and `async` methods and `async` properties and `async` descriptors:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

@app.get("/users/")
async def read_users(db: AsyncSession = Depends(get_db)):
    # Use db
    pass
```

---

*Original source: [101 FastAPI Tips](https://github.com/Kludex/101-fastapi-tips) by [Kludex](https://github.com/Kludex)*