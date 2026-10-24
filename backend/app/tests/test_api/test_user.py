from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.utils.user import user_authentication_headers

pytestmark = pytest.mark.asyncio(scope="module")


async def create_isolated_user_with_token(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> tuple[dict[str, str], dict]:
    """
    Create an isolated user and return auth token headers along with user data.

    This ensures tests don't share state with other tests using shared fixtures.

    :param async_client: Test HTTP client
    :param async_session: Database session
    :returns: Tuple of (token_headers, user_data_dict)
    """
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    token_headers = await user_authentication_headers(
        client=async_client,
        email=user_data["email"],
        password=user_data["password"],
    )

    return token_headers, {"id": str(user.id), **user_data}


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_create_user_new_email(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_data = create_fake_user()
    response = await async_client.post(
        "/users/",
        headers=superuser_token_headers,
        json=user_data,
    )
    assert 200 <= response.status_code < 300
    created_user = response.json()
    user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert user
    assert user.email == created_user["email"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_get_existing_user(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)
    user_id = user.id
    response = await async_client.get(
        f"/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert 200 <= response.status_code < 300
    api_user = response.json()
    existing_user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert existing_user
    assert existing_user.email == api_user["email"]


@pytest.mark.asyncio
async def test_create_user_by_normal_user(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_data = create_fake_user()
    response = await async_client.post(
        "/users/",
        headers=normal_user_token_headers,
        json=user_data,
    )
    # Insufficient privileges is an authorization failure, not a bad request.
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reading_another_user_hides_existence(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """An existing id another user may not see reads as 404, not a distinguishable 403.

    A 403 for an existing id and a 404 for an unknown one would let a regular
    user probe which user ids exist.
    """
    other = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))

    existing = await async_client.get(f"/users/{other.id}", headers=normal_user_token_headers)
    unknown = await async_client.get(f"/users/{uuid4()}", headers=normal_user_token_headers)

    assert existing.status_code == 404
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_reading_own_user_still_works(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """The self-read path is unaffected by the existence-hiding pre-check."""
    me = await crud.user.get_by_email(db_session=async_session, email=settings.EMAIL_TEST_USER)

    response = await async_client.get(f"/users/{me.id}", headers=normal_user_token_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(me.id)


@pytest.mark.asyncio
async def test_retrieve_users(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_1_data = create_fake_user()
    user_1_in = UserCreate(**user_1_data)
    await crud.user.create(db_session=async_session, obj_in=user_1_in)

    user_2_data = create_fake_user()
    user_2_in = UserCreate(**user_2_data)
    await crud.user.create(db_session=async_session, obj_in=user_2_in)

    response = await async_client.get("/users/", headers=superuser_token_headers)
    all_users = response.json()

    assert len(all_users) > 1
    for item in all_users:
        assert "email" in item


# =============================================================================
# Profile Tests (migrated from test_profile.py)
# =============================================================================


@pytest.mark.asyncio
async def test_update_profile_partial(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Test partially updating profile (only bio) with isolated user."""
    # Create isolated user to avoid shared state issues
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    # First, get the profile to ensure it exists
    await async_client.get("/users/me/profile", headers=token_headers)

    update_data = {"bio": "Updated bio only"}
    response = await async_client.put("/users/me/profile", json=update_data, headers=token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == update_data["bio"]


@pytest.mark.asyncio
async def test_update_profile_preferences_nested_round_trip(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Test nested preferences dict round-trips through PUT/GET profile."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    # First, get the profile to ensure it exists
    await async_client.get("/users/me/profile", headers=token_headers)

    preferences = {
        "sound": {"muted": False, "volumes": {"ui": 0.2, "sfx": 0.5, "music": 0.9}},
        "theme": "fnv",
        "notifications": {"version": 1, "disabled_categories": ["advancement"]},
    }
    response = await async_client.put(
        "/users/me/profile",
        json={"preferences": preferences},
        headers=token_headers,
    )
    assert response.status_code == 200
    assert response.json()["preferences"] == preferences

    response = await async_client.get("/users/me/profile", headers=token_headers)
    assert response.status_code == 200
    persisted = response.json()["preferences"]
    assert persisted == preferences
    # Persisted as a nested object, not a serialized JSON string
    assert isinstance(persisted, dict)
    assert isinstance(persisted["sound"], dict)
    assert isinstance(persisted["sound"]["volumes"], dict)


@pytest.mark.asyncio
async def test_update_profile_bio_only_preserves_preferences(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Test a bio-only update leaves existing preferences untouched."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    # First, get the profile to ensure it exists
    await async_client.get("/users/me/profile", headers=token_headers)

    preferences = {
        "sound": {"muted": False, "volumes": {"ui": 0.2, "sfx": 0.5, "music": 0.9}},
        "theme": "fnv",
    }
    response = await async_client.put(
        "/users/me/profile",
        json={"preferences": preferences},
        headers=token_headers,
    )
    assert response.status_code == 200

    response = await async_client.put("/users/me/profile", json={"bio": "Updated bio only"}, headers=token_headers)
    assert response.status_code == 200
    assert response.json()["bio"] == "Updated bio only"
    assert response.json()["preferences"] == preferences

    response = await async_client.get("/users/me/profile", headers=token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == "Updated bio only"
    assert profile["preferences"] == preferences


@pytest.mark.asyncio
async def test_profile_rejects_unknown_notification_category(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Notification preferences cannot be bypassed with an arbitrary category payload."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    await async_client.get("/users/me/profile", headers=token_headers)

    response = await async_client.put(
        "/users/me/profile",
        json={"preferences": {"notifications": {"version": 1, "disabled_categories": ["combat_defeat"]}}},
        headers=token_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_profile_endpoints_require_authentication(async_client: AsyncClient) -> None:
    """Test profile endpoints reject requests without auth headers."""
    response = await async_client.get("/users/me/profile")
    assert response.status_code == 401

    response = await async_client.put("/users/me/profile", json={"bio": "No auth"})
    assert response.status_code == 401


# =============================================================================
# Account secret exposure / mass-assignment tests
# =============================================================================


@pytest.mark.asyncio
async def test_read_user_me_excludes_server_only_secret_fields(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """GET /users/me serializes verification status but never the stored secrets."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert user is not None
    user.email_verification_token = "verification-secret"
    user.password_reset_token = "reset-secret"
    user.password_reset_expires = datetime.now(tz=UTC).replace(tzinfo=None)
    async_session.add(user)
    await async_session.commit()

    response = await async_client.get("/users/me", headers=token_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["email_verified"] is False
    assert "email_verification_token" not in payload
    assert "password_reset_token" not in payload
    assert "password_reset_expires" not in payload


@pytest.mark.asyncio
async def test_admin_update_cannot_mass_assign_verification_state(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """An admin payload cannot flip verification state through the generic update route."""
    _, user_data = await create_isolated_user_with_token(async_client, async_session)

    response = await async_client.put(
        f"/users/{user_data['id']}",
        json={"email_verified": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    stored = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert stored is not None
    assert stored.email_verified is False


@pytest.mark.asyncio
async def test_update_me_applies_username_and_email_together(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Sending username and email in one request persists both, not just the username."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    new_username = f"nyx_{uuid4().hex[:8]}"
    new_email = f"{uuid4().hex[:8]}@example.com"

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        response = await async_client.put(
            "/users/me",
            json={"username": new_username, "email": new_email},
            headers=token_headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == new_username
    assert payload["email"] == new_email

    stored = await crud.user.get_by_email(db_session=async_session, email=new_email)
    assert stored is not None
    assert stored.username == new_username


@pytest.mark.parametrize("password", ["short", "x" * 129])
async def test_update_me_rejects_passwords_outside_policy(
    async_client: AsyncClient,
    async_session: AsyncSession,
    password: str,
) -> None:
    """The account-update path enforces the same 8-128 password bounds as registration."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    response = await async_client.put(
        "/users/me",
        json={"password": password},
        headers=token_headers,
    )

    assert response.status_code == 400
    assert "8 and 128" in response.json()["detail"]


@pytest.mark.parametrize(
    "operation", ["create-admin", "promote", "demote", "deactivate-admin", "reactivate-admin", "edit-admin"]
)
async def test_secondary_admin_cannot_bypass_first_superuser_policy_via_user_api(
    async_client, async_session, superuser, operation
):
    from app.core.security import create_access_token

    actor = await crud.user.create(async_session, UserCreate(**create_fake_user(), is_superuser=True))
    regular = await crud.user.create(async_session, UserCreate(**create_fake_user()))
    headers = {"Authorization": f"Bearer {create_access_token(str(actor.id))}"}
    if operation == "create-admin":
        response = await async_client.post(
            "/users/", headers=headers, json={**create_fake_user(), "is_superuser": True}
        )
    else:
        target = regular if operation == "promote" else superuser
        payload = {
            "promote": {"is_superuser": True},
            "demote": {"is_superuser": False},
            "deactivate-admin": {"is_active": False},
            "reactivate-admin": {"is_active": True},
            "edit-admin": {"username": "ChangedAdministrator"},
        }[operation]
        response = await async_client.put(f"/users/{target.id}", headers=headers, json=payload)
    assert response.status_code == 403
    await async_session.refresh(superuser)
    assert superuser.is_superuser
    assert superuser.is_active


async def test_secondary_admin_can_still_update_regular_users(async_client, async_session):
    from app.core.security import create_access_token

    actor = await crud.user.create(async_session, UserCreate(**create_fake_user(), is_superuser=True))
    target = await crud.user.create(async_session, UserCreate(**create_fake_user()))
    response = await async_client.put(
        f"/users/{target.id}",
        headers={"Authorization": f"Bearer {create_access_token(str(actor.id))}"},
        json={"username": "UpdatedRegularUser"},
    )
    assert response.status_code == 200
    await async_session.refresh(target)
    assert target.username == "UpdatedRegularUser"


@pytest.mark.parametrize(
    "payload", [{"is_superuser": False}, {"is_active": False}, {"is_superuser": None}, {"is_active": None}]
)
async def test_user_api_protects_first_superuser_and_rejects_null_flags(
    async_client, async_session, superuser, superuser_token_headers, payload
):
    response = await async_client.put(f"/users/{superuser.id}", headers=superuser_token_headers, json=payload)
    assert response.status_code == 400
    await async_session.refresh(superuser)
    assert superuser.is_active
    assert superuser.is_superuser
    assert superuser.is_first_superuser


async def test_user_api_deactivation_pauses_vault_and_keeps_data(
    async_client, async_session, superuser_token_headers, vault
):
    from app.crud.game_state import game_state_crud

    response = await async_client.put(
        f"/users/{vault.user_id}", headers=superuser_token_headers, json={"is_active": False}
    )
    assert response.status_code == 200
    user = await crud.user.get(async_session, vault.user_id)
    assert user.is_active is False
    assert user.is_deleted is False
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert state.is_paused
