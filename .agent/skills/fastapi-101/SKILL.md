---
name: FastAPI 101
description: Essential FastAPI patterns and best practices. Use when working with FastAPI code, endpoints, or API development.
---

# FastAPI 101

Essential FastAPI patterns, best practices, and development guidelines for building robust APIs.

## When to use this skill

- Use this when developing FastAPI endpoints and routes
- Use this when designing API schemas and models
- Use this when implementing authentication and middleware
- Use this when debugging FastAPI applications
- Use this when optimizing API performance

## How to use it

### Core FastAPI Patterns

#### 1. Endpoint Structure

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Create a new user.
    
    Args:
        user: User creation data
        db: Database session
        current_user: Authenticated user making the request
        
    Returns:
        Created user data
        
    Raises:
        HTTPException: If user creation fails
    """
    try:
        created_user = await user_service.create(db, obj_in=user)
        return UserResponse.model_validate(created_user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        )
```

#### 2. Pydantic Models

```python
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Base user model with shared fields."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50)
    is_active: bool = Field(default=True)

class UserCreate(UserBase):
    """Model for user creation requests."""
    password: str = Field(..., min_length=8, max_length=128)

class UserUpdate(BaseModel):
    """Model for user update requests."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    """Model for user response data."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

#### 3. Dependency Injection

```python
from fastapi import Depends
from sqlmodel import Session, create_engine
from typing import AsyncGenerator

# Database dependency
async def get_db() -> AsyncGenerator[Session, None]:
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Authentication dependency
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await user_service.get(db, id=user_id)
    if user is None:
        raise credentials_exception
    return user

# Optional auth dependency
async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None
```

#### 4. Error Handling

```python
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Union

class CustomException(Exception):
    """Base custom exception."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class UserNotFoundError(CustomException):
    """Raised when user is not found."""
    def __init__(self, user_id: int):
        super().__init__(
            message=f"User with ID {user_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

# Global exception handler
async def custom_exception_handler(
    request: Request, 
    exc: CustomException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

# Register in FastAPI app
app.add_exception_handler(CustomException, custom_exception_handler)
```

#### 5. Service Layer Pattern

```python
from typing import List, Optional
from sqlmodel import Session, select

class UserService:
    """Business logic layer for user operations."""
    
    def __init__(self, user_repository: UserRepository):
        self.repository = user_repository
    
    async def create(
        self, 
        db: Session, 
        obj_in: UserCreate
    ) -> User:
        """Create a new user."""
        # Business logic
        existing_user = await self.get_by_email(db, email=obj_in.email)
        if existing_user:
            raise UserAlreadyExistsError(email=obj_in.email)
        
        # Hash password
        obj_in_data = obj_in.model_dump()
        obj_in_data["password"] = get_password_hash(obj_in_data["password"])
        
        # Create user
        return await self.repository.create(db, obj_in=obj_in_data)
    
    async def get_by_email(
        self, 
        db: Session, 
        email: str
    ) -> Optional[User]:
        """Get user by email."""
        statement = select(User).where(User.email == email)
        result = await db.exec(statement)
        return result.first_one()
    
    async def get_multi(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[User]:
        """Get multiple users with pagination."""
        statement = select(User).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()

# Dependency injection for service
async def get_user_service() -> UserService:
    return UserService(user_repository)
```

#### 6. Middleware

```python
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"in {process_time:.4f}s"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

class CORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware."""
    
    def __init__(self, app, allow_origins: list = None):
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
    
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        
        if origin in self.allow_origins or "*" in self.allow_origins:
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            return response
        
        return await call_next(request)
```

#### 7. Background Tasks

```python
from fastapi import BackgroundTasks
import smtplib
from email.mime.text import MIMEText

async def send_welcome_email(email: str, username: str):
    """Send welcome email in background."""
    try:
        # Email sending logic
        message = MIMEText(f"Welcome {username}!")
        message["Subject"] = "Welcome to our service"
        message["From"] = "noreply@example.com"
        message["To"] = email
        
        # Send email (configure SMTP properly)
        # smtplib.SMTP("localhost").send_message(message)
        
        logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")

@router.post("/users/")
async def create_user_with_email(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create user and send welcome email."""
    created_user = await user_service.create(db, obj_in=user)
    
    # Add background task
    background_tasks.add_task(
        send_welcome_email, 
        user.email, 
        user.username
    )
    
    return UserResponse.model_validate(created_user)
```

#### 8. WebSocket Support

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import json

class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process message
            await manager.send_personal_message(
                f"Message received: {message['content']}", 
                websocket
            )
            
            # Broadcast to others
            await manager.broadcast(
                f"Client #{client_id} says: {message['content']}"
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")
```

#### 9. Testing Patterns

```python
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def test_user():
    return UserCreate(
        email="test@example.com",
        username="testuser",
        password="testpassword123"
    )

class TestUserEndpoints:
    """Test user endpoints."""
    
    async def test_create_user_success(
        self, 
        async_client: AsyncClient,
        test_user: UserCreate
    ):
        """Test successful user creation."""
        response = await async_client.post(
            "/users/",
            json=test_user.model_dump()
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert "id" in data
        assert "password" not in data
    
    async def test_create_user_duplicate_email(
        self, 
        async_client: AsyncClient,
        test_user: UserCreate
    ):
        """Test user creation with duplicate email."""
        # Create first user
        await async_client.post("/users/", json=test_user.model_dump())
        
        # Try to create second user with same email
        response = await async_client.post("/users/", json=test_user.model_dump())
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    async def test_get_users_requires_auth(
        self, 
        async_client: AsyncClient
    ):
        """Test that getting users requires authentication."""
        response = await async_client.get("/users/")
        
        assert response.status_code == 401
```

#### 10. Configuration Management

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # App settings
    app_name: str = "Fallout Shelter API"
    debug: bool = False
    version: str = "1.0.0"
    
    # Database
    database_url: str = "postgresql://user:pass@localhost/dbname"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    allowed_origins: list = ["*"]
    
    # External services
    redis_url: str = "redis://localhost:6379"
    email_host: str = "localhost"
    email_port: int = 587
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

# Use in FastAPI app
@lru_cache()
def get_settings() -> Settings:
    return settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version=settings.version
)
```

## Best Practices

1. **Always use async/await** for database operations
2. **Validate input with Pydantic** models
3. **Use dependency injection** for database sessions and auth
4. **Handle specific exceptions** with proper HTTP status codes
5. **Write comprehensive tests** with fixtures
6. **Use proper HTTP status codes** and error responses
7. **Implement proper logging** with context
8. **Keep endpoints focused** on single responsibilities
9. **Use service layer** for business logic
10. **Document all endpoints** with proper docstrings

## Common Pitfalls to Avoid

1. **Don't use synchronous database calls** in async endpoints
2. **Don't return raw models** - use response models
3. **Don't hardcode configuration** - use environment variables
4. **Don't ignore security** - always validate inputs and check permissions
5. **Don't skip error handling** - handle expected exceptions gracefully
6. **Don't forget to close database connections** - use context managers
7. **Don't mix sync and async code** without proper bridging
8. **Don't return sensitive data** - filter out passwords, tokens, etc.

## Performance Tips

1. **Use database connection pooling**
2. **Implement proper caching** with Redis
3. **Use pagination** for list endpoints
4. **Optimize database queries** with proper indexes
5. **Use background tasks** for long-running operations
6. **Implement rate limiting** to prevent abuse
7. **Monitor and profile** your endpoints regularly
8. **Use proper HTTP caching** headers when appropriate