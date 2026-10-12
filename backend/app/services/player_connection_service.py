"""Player-to-player connection and blocking service (A1 + A2 identity).

Owns all connection/block rules: feature gating, username discovery, consent
(idempotent invite/accept), bilateral-by-enforcement blocking, and the read
shapes. Queries live in ``app/crud``; this module raises no HTTP exceptions.
"""

from collections.abc import Sequence
from datetime import datetime
from logging import getLogger

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.db_locks import advisory_xact_lock, player_pair_lock_key
from app.core.enums import ConnectionStatus
from app.core.game_config import game_config
from app.models.connection import Connection
from app.models.user import User
from app.models.user_block import UserBlock
from app.schemas.connection import ConnectionRead
from app.schemas.user_block import UserBlockRead
from app.utils.exceptions import FeatureDisabledException, ResourceNotFoundException, ValidationException

logger = getLogger(__name__)


class PlayerConnectionService:
    """Consent-gated connections and bilateral blocking between players."""

    def ensure_enabled(self) -> None:
        if not game_config.features.player_connections:
            raise FeatureDisabledException("Player connections are disabled.")

    async def _resolve_user_by_username(self, db_session: AsyncSession, username: str) -> User:
        user = await crud.user.get_by_username(db_session, username=username)
        if not user:
            raise ResourceNotFoundException(User, identifier=username, identifier_type="username")
        return user

    async def _resolve_user_by_id(self, db_session: AsyncSession, user_id: UUID4) -> User:
        user = await crud.user.get_or_none(db_session, user_id)
        if not user:
            raise ResourceNotFoundException(User, identifier=user_id)
        return user

    async def _ensure_not_blocked(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> None:
        if await crud.user_block.get_between(db_session, user_a, user_b) is not None:
            raise ValidationException("This action is blocked.")

    async def _lock_pair(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> None:
        """Serialize a pair-mutating operation across workers; no-op outside PostgreSQL."""
        await advisory_xact_lock(db_session, player_pair_lock_key(user_a, user_b))

    async def _usernames(self, db_session: AsyncSession, user_ids: Sequence[UUID4]) -> dict[UUID4, str]:
        users = await crud.user.get_by_ids(list(set(user_ids)), db_session)
        return {user.id: user.username for user in users}

    @staticmethod
    def _to_connection_read(connection: Connection, counterpart_username: str) -> ConnectionRead:
        return ConnectionRead(
            id=connection.id,
            requester_id=connection.requester_id,
            addressee_id=connection.addressee_id,
            status=connection.status,
            counterpart_username=counterpart_username,
            created_at=connection.created_at,
            responded_at=connection.responded_at,
        )

    async def invite(self, db_session: AsyncSession, *, user: User, username: str) -> ConnectionRead:
        """Invite a user by exact public `username`; idempotent per unordered pair."""
        self.ensure_enabled()
        addressee = await self._resolve_user_by_username(db_session, username)
        user_id, addressee_id, addressee_username = user.id, addressee.id, addressee.username
        if addressee_id == user_id:
            raise ValidationException("You cannot invite yourself.")
        await self._lock_pair(db_session, user_id, addressee_id)
        await self._ensure_not_blocked(db_session, user_id, addressee_id)

        existing = await crud.connection.get_by_pair(db_session, user_id, addressee_id)
        if existing is not None:
            # Idempotent no-op: a pending invite already exists (or the pair is
            # already connected), so re-inviting must not duplicate the row.
            return self._to_connection_read(existing, addressee_username)

        try:
            connection = await crud.connection.create_connection(
                db_session, requester_id=user_id, addressee_id=addressee_id, status=ConnectionStatus.PENDING
            )
            await db_session.commit()
        except IntegrityError:
            # Defense-in-depth: a concurrent worker inserted the same unordered
            # pair first; return its row instead of surfacing a 500. Ids/username
            # are captured above because rollback expires the ORM objects.
            await db_session.rollback()
            existing = await crud.connection.get_by_pair(db_session, user_id, addressee_id)
            if existing is None:
                raise
            return self._to_connection_read(existing, addressee_username)
        logger.info("Connection invite from %s to %s", user_id, addressee_id)
        return self._to_connection_read(connection, addressee_username)

    async def accept(self, db_session: AsyncSession, *, user: User, connection_id: UUID4) -> ConnectionRead:
        """Accept a pending invite (addressee only); idempotent when already accepted."""
        self.ensure_enabled()
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None:
            raise ResourceNotFoundException(Connection, identifier=connection_id)
        if connection.addressee_id != user.id:
            raise ValidationException("Only the addressee can accept a pending invite.")
        await self._lock_pair(db_session, connection.requester_id, connection.addressee_id)
        # Re-read under the pair lock: a concurrent decline/revoke may have removed
        # the row, and a concurrent accept may have already promoted it.
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None:
            raise ResourceNotFoundException(Connection, identifier=connection_id)
        if connection.addressee_id != user.id:
            raise ValidationException("Only the addressee can accept a pending invite.")
        if connection.status is ConnectionStatus.ACCEPTED:
            username = await self._usernames(db_session, [connection.requester_id])
            return self._to_connection_read(connection, username[connection.requester_id])
        await self._ensure_not_blocked(db_session, connection.requester_id, connection.addressee_id)

        connection = await crud.connection.set_status(
            db_session, connection, ConnectionStatus.ACCEPTED, responded_at=datetime.utcnow()
        )
        # A connected pair holds no pending requests; retire any in either direction
        # so a later revoke or block-then-unblock does not leave a phantom request.
        await crud.direct_message.clear_requests(
            db_session, user_a=connection.requester_id, user_b=connection.addressee_id
        )
        await db_session.commit()
        logger.info("Connection accepted: %s", connection.id)
        username = await self._usernames(db_session, [connection.requester_id])
        return self._to_connection_read(connection, username[connection.requester_id])

    async def decline(self, db_session: AsyncSession, *, user: User, connection_id: UUID4) -> None:
        """Decline a pending invite; safe to retry (absent rows are a no-op)."""
        self.ensure_enabled()
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None:
            return
        if connection.addressee_id != user.id:
            raise ValidationException("Only the addressee can decline a pending invite.")
        await self._lock_pair(db_session, connection.requester_id, connection.addressee_id)
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None or connection.status is not ConnectionStatus.PENDING:
            return
        await crud.connection.delete_row(db_session, connection)
        await db_session.commit()
        logger.info("Connection declined: %s", connection.id)

    async def revoke(self, db_session: AsyncSession, *, user: User, connection_id: UUID4) -> None:
        """Revoke a pending invite (requester) or sever an accepted connection (either side)."""
        self.ensure_enabled()
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None:
            raise ResourceNotFoundException(Connection, identifier=connection_id)
        if connection.requester_id != user.id and connection.addressee_id != user.id:
            raise ResourceNotFoundException(Connection, identifier=connection_id)
        await self._lock_pair(db_session, connection.requester_id, connection.addressee_id)
        connection = await crud.connection.get_by_id(db_session, connection_id)
        if connection is None:
            # A concurrent revoke already removed it; revocation is idempotent.
            return
        await crud.connection.delete_row(db_session, connection)
        await db_session.commit()
        logger.info("Connection revoked: %s", connection.id)

    async def list_connections(self, db_session: AsyncSession, *, user: User) -> list[ConnectionRead]:
        """All rows the user participates in (accepted and pending, both directions)."""
        self.ensure_enabled()
        rows = await crud.connection.get_for_user(db_session, user.id)
        counterpart_ids = [row.addressee_id if row.requester_id == user.id else row.requester_id for row in rows]
        usernames = await self._usernames(db_session, counterpart_ids)
        return [
            self._to_connection_read(row, usernames.get(other_id, ""))
            for row, other_id in zip(rows, counterpart_ids, strict=False)
        ]

    async def block(self, db_session: AsyncSession, *, user: User, user_id: UUID4) -> UserBlockRead:
        """Block a user; bilateral and immediate. Idempotent when already blocked."""
        self.ensure_enabled()
        target = await self._resolve_user_by_id(db_session, user_id)
        blocker_id, target_id, target_username = user.id, target.id, target.username
        if target_id == blocker_id:
            raise ValidationException("You cannot block yourself.")
        await self._lock_pair(db_session, blocker_id, target_id)
        existing = await crud.user_block.get_between(db_session, blocker_id, target_id)
        if existing is not None:
            # Already blocked in either direction: a reciprocal block is a no-op
            # that returns the canonical row rather than inserting a second one.
            return self._to_block_read(existing, target_username, blocked_id=target_id)
        try:
            block = await crud.user_block.create_block(db_session, blocker_id=blocker_id, blocked_id=target_id)
        except IntegrityError:
            # Rollback expires the ORM objects, so use the ids/username captured above.
            await db_session.rollback()
            existing = await crud.user_block.get_between(db_session, blocker_id, target_id)
            if existing is None:
                raise
            return self._to_block_read(existing, target_username, blocked_id=target_id)
        # A block severs any existing connection rows: invites and messages are
        # blocked both ways immediately, and the ability to connect must be
        # re-earned after an unblock (the old connection is not restored).
        await crud.connection.delete_between(db_session, blocker_id, target_id)
        # Discard open requests in both directions, so a blocked pair is not left
        # with a phantom pending request that resurfaces after an unblock.
        await crud.direct_message.delete_requests_from(db_session, sender=blocker_id, recipient=target_id)
        await crud.direct_message.delete_requests_from(db_session, sender=target_id, recipient=blocker_id)
        await db_session.commit()
        logger.info("User %s blocked %s", blocker_id, target_id)
        return self._to_block_read(block, target_username, blocked_id=target_id)

    async def unblock(self, db_session: AsyncSession, *, user: User, user_id: UUID4) -> None:
        """Remove a block; safe to retry (absent rows are a no-op)."""
        self.ensure_enabled()
        target = await self._resolve_user_by_id(db_session, user_id)
        blocker_id, target_id = user.id, target.id
        await self._lock_pair(db_session, blocker_id, target_id)
        block = await crud.user_block.get_block(db_session, blocker_id=blocker_id, blocked_id=target_id)
        if block is None:
            return
        await crud.user_block.delete_row(db_session, block)
        await db_session.commit()
        logger.info("User %s unblocked %s", blocker_id, target_id)

    async def list_blocks(self, db_session: AsyncSession, *, user: User) -> list[UserBlockRead]:
        """The blocker's own block list."""
        self.ensure_enabled()
        rows = await crud.user_block.list_for_blocker(db_session, user.id)
        usernames = await self._usernames(db_session, [row.blocked_id for row in rows])
        return [self._to_block_read(row, usernames.get(row.blocked_id, "")) for row in rows]

    @staticmethod
    def _to_block_read(block: UserBlock, blocked_username: str, blocked_id: UUID4 | None = None) -> UserBlockRead:
        return UserBlockRead(
            id=block.id,
            blocked_id=blocked_id if blocked_id is not None else block.blocked_id,
            blocked_username=blocked_username,
            created_at=block.created_at,
        )


player_connection_service = PlayerConnectionService()
