import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.crud.user_profile import profile_crud
from app.schemas.user import UserCreate
from app.schemas.user_profile import ProfileUpdate
from app.tests.factory.users import create_fake_user


@pytest.mark.asyncio
async def test_get_profile_by_user_id(async_session: AsyncSession) -> None:
    """Test getting profile by user ID."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    # Profile should be auto-created
    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile is not None
    assert profile.user_id == user.id
    assert profile.bio is None
    assert profile.avatar_url is None
    assert profile.total_dwellers_created == 0
    assert profile.total_caps_earned == 0
    assert profile.total_explorations == 0
    assert profile.total_rooms_built == 0


@pytest.mark.asyncio
async def test_create_profile_for_user(async_session: AsyncSession) -> None:
    """Test manually creating a profile for a user."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    # Get the auto-created profile
    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile is not None
    assert profile.user_id == user.id


@pytest.mark.asyncio
async def test_update_profile(async_session: AsyncSession) -> None:
    """Test updating a user profile."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile is not None

    # Update profile
    update_data = ProfileUpdate(
        bio="I love Fallout!",
        avatar_url="https://example.com/avatar.png",
        preferences={"theme": "dark", "language": "en"},
    )
    updated_profile = await profile_crud.update(async_session, id=profile.id, obj_in=update_data)

    assert updated_profile.bio == "I love Fallout!"
    assert updated_profile.avatar_url == "https://example.com/avatar.png"
    assert updated_profile.preferences == {"theme": "dark", "language": "en"}
    assert updated_profile.total_dwellers_created == 0


@pytest.mark.asyncio
async def test_increment_statistic(async_session: AsyncSession) -> None:
    """Test incrementing a statistic field."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    # Increment total_dwellers_created
    updated_profile = await profile_crud.increment_statistic(async_session, user.id, "total_dwellers_created", 1)
    assert updated_profile is not None
    assert updated_profile.total_dwellers_created == 1

    # Increment again by 5
    updated_profile = await profile_crud.increment_statistic(async_session, user.id, "total_dwellers_created", 5)
    assert updated_profile.total_dwellers_created == 6


@pytest.mark.asyncio
async def test_increment_caps_earned(async_session: AsyncSession) -> None:
    """Test incrementing caps earned statistic."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    # Increment total_caps_earned by 100
    updated_profile = await profile_crud.increment_statistic(async_session, user.id, "total_caps_earned", 100)
    assert updated_profile is not None
    assert updated_profile.total_caps_earned == 100

    # Increment again by 250
    updated_profile = await profile_crud.increment_statistic(async_session, user.id, "total_caps_earned", 250)
    assert updated_profile.total_caps_earned == 350


@pytest.mark.asyncio
async def test_increment_multiple_statistics(async_session: AsyncSession) -> None:
    """Test incrementing multiple different statistics."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    # Increment different stats
    await profile_crud.increment_statistic(async_session, user.id, "total_dwellers_created", 3)
    await profile_crud.increment_statistic(async_session, user.id, "total_explorations", 5)
    await profile_crud.increment_statistic(async_session, user.id, "total_rooms_built", 2)

    # Verify all were incremented
    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile.total_dwellers_created == 3
    assert profile.total_explorations == 5
    assert profile.total_rooms_built == 2
    assert profile.total_caps_earned == 0  # Should remain 0


@pytest.mark.asyncio
async def test_profile_preferences_json(async_session: AsyncSession) -> None:
    """Test that preferences are stored as JSON/dict."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    profile = await profile_crud.get_by_user_id(async_session, user.id)

    # Update with complex preferences
    complex_prefs = {
        "ui": {"theme": "dark", "font_size": 14},
        "gameplay": {"difficulty": "hard", "auto_save": True},
        "audio": {"music_volume": 80, "sfx_volume": 90},
    }
    update_data = ProfileUpdate(preferences=complex_prefs)
    updated_profile = await profile_crud.update(async_session, id=profile.id, obj_in=update_data)

    assert updated_profile.preferences == complex_prefs
    assert updated_profile.preferences["ui"]["theme"] == "dark"
    assert updated_profile.preferences["gameplay"]["difficulty"] == "hard"
