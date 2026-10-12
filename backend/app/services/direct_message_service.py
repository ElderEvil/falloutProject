"""Direct-message service (B1): consent-gated messaging, blocks, and WS delivery.

Sends between players follow the plan: a message to a connection is stored and
pushed normally; a message to a non-connection is stored as a request
(``is_request=True``) with one open request per pair until answered. Accepting
a request promotes the sender to a connection; declining discards the request.
Blocking makes the thread read-only (bilateral from either side).

Delivery persists first, then pushes ``{"type": "direct_message", ...}`` over
the Redis-backed WebSocket manager to the recipient and echoes it to the
sender. Queries live in ``app/crud``.
"""

from collections import defaultdict, deque
from datetime import datetime
from logging import getLogger
from time import monotonic

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.db_locks import advisory_xact_lock, player_pair_lock_key
from app.core.enums import ConnectionStatus
from app.core.game_config import game_config
from app.models.connection import Connection
from app.models.direct_message import DirectMessage
from app.models.user import User
from app.schemas.connection import ConnectionRead
from app.schemas.direct_message import DirectMessageRead, DirectMessageSummary
from app.services.websocket_manager import manager
from app.utils.exceptions import FeatureDisabledException, ResourceNotFoundException, ValidationException

logger = getLogger(__name__)

#: Per-feature anti-abuse cap (the middleware adds its own IP-level limit).
MAX_SENDS_PER_WINDOW = 120
RATE_WINDOW_SECONDS = 60.0


class DirectMessageService:
    """Owns message/request rules, blocking enforcement, and delivery."""

    def __init__(self) -> None:
        self._send_history: dict[UUID4, deque[float]] = defaultdict(deque)
        self.manager = manager
        self.max_sends_per_window = MAX_SENDS_PER_WINDOW
        self.rate_window_seconds = RATE_WINDOW_SECONDS

    def ensure_enabled(self) -> None:
        if not game_config.features.player_connections:
            raise FeatureDisabledException("Player connections are disabled.")

    async def _resolve_user(self, db_session: AsyncSession, user_id: UUID4) -> User:
        user = await crud.user.get_or_none(db_session, user_id)
        if not user:
            raise ResourceNotFoundException(User, identifier=user_id)
        return user

    @staticmethod
    def _to_connection_read(connection: Connection, username: str) -> ConnectionRead:
        return ConnectionRead(
            id=connection.id,
            requester_id=connection.requester_id,
            addressee_id=connection.addressee_id,
            status=connection.status,
            counterpart_username=username,
            created_at=connection.created_at,
            responded_at=connection.responded_at,
        )

    @staticmethod
    def _to_read(message: DirectMessage) -> DirectMessageRead:
        return DirectMessageRead(
            id=message.id,
            sender_user_id=message.sender_user_id,
            recipient_user_id=message.recipient_user_id,
            body=message.body,
            is_request=message.is_request,
            created_at=message.created_at,
        )

    def _check_rate(self, user_id: UUID4) -> None:
        now = monotonic()
        history = self._send_history[user_id]
        while history and now - history[0] > self.rate_window_seconds:
            history.popleft()
        if len(history) >= self.max_sends_per_window:
            raise ValidationException("Message rate limit exceeded. Try again shortly.")
        history.append(now)

    async def send_message(
        self, db_session: AsyncSession, *, sender: User, recipient_id: UUID4, body: str
    ) -> DirectMessageRead:
        """Store a message (or a request when not yet connected) and push it over WebSockets."""
        self.ensure_enabled()
        recipient = await self._resolve_user(db_session, recipient_id)
        sender_id, recipient_pk = sender.id, recipient.id
        if recipient_pk == sender_id:
            raise ValidationException("You cannot send a message to yourself.")
        await self._lock_pair(db_session, sender_id, recipient_pk)
        await self._reject_if_blocked(db_session, sender_id, recipient_pk)
        self._check_rate(sender_id)

        connection = await crud.connection.get_by_pair(db_session, sender_id, recipient_pk)
        accepted = connection is not None and connection.status is ConnectionStatus.ACCEPTED
        if not accepted and await crud.direct_message.has_open_request(
            db_session, sender=sender_id, recipient=recipient_pk
        ):
            raise ValidationException("A request is already pending with this user.")

        try:
            message = await crud.direct_message.create_message(
                db_session,
                sender_user_id=sender_id,
                recipient_user_id=recipient_pk,
                body=body,
                is_request=not accepted,
            )
            await db_session.commit()
        except IntegrityError:
            # Defense-in-depth: a concurrent worker stored the same open request
            # first; return that row instead of surfacing a 500. Ids are captured
            # above because rollback expires the ORM objects.
            await db_session.rollback()
            existing = await crud.direct_message.get_last_between(db_session, sender=sender_id, recipient=recipient_pk)
            if existing is None:
                raise
            return self._to_read(existing)
        read = self._to_read(message)
        payload = {"type": "direct_message", "message": read.model_dump(mode="json")}
        # Multi-instance delivery: Redis pub/sub fan-out to the recipient and an
        # echo to the sender, so both clients see the message immediately. Delivery
        # is best-effort — the message is already committed, so a socket failure
        # must not turn a successful send into an HTTP 500.
        for target in (recipient_pk, sender_id):
            try:
                await self.manager.send_personal_message(payload, target)
            except Exception:
                logger.exception("Direct message %s delivery to %s failed", message.id, target)
        logger.info("Direct message %s from %s to %s", message.id, sender_id, recipient_pk)
        return read

    async def accept_request(self, db_session: AsyncSession, *, user: User, requester_id: UUID4) -> ConnectionRead:
        """Accept an open message request: the requester becomes a connection."""
        self.ensure_enabled()
        requester = await self._resolve_user(db_session, requester_id)
        requester_pk, requester_username, user_pk = requester.id, requester.username, user.id
        if requester_pk == user_pk:
            raise ValidationException("You cannot accept a request from yourself.")
        await self._lock_pair(db_session, requester_pk, user_pk)
        await self._reject_if_blocked(db_session, requester_pk, user_pk)

        existing = await crud.connection.get_by_pair(db_session, requester_pk, user_pk)
        if existing is not None and existing.status is ConnectionStatus.ACCEPTED:
            # Idempotent no-op: accepting an already-accepted pair returns the row.
            return self._to_connection_read(existing, requester_username)
        if not await crud.direct_message.has_open_request(db_session, sender=requester_pk, recipient=user_pk):
            raise ValidationException("No pending request from this user.")

        if existing is not None:
            # An equivalent PENDING row (normal invite) is promoted so either
            # accept path converges.
            connection = await crud.connection.set_status(
                db_session, existing, ConnectionStatus.ACCEPTED, responded_at=datetime.utcnow()
            )
        else:
            try:
                connection = await crud.connection.create_connection(
                    db_session, requester_id=requester_pk, addressee_id=user_pk, status=ConnectionStatus.ACCEPTED
                )
            except IntegrityError:
                # Defense-in-depth: a concurrent worker created the pair first.
                # Rollback expires the requester row, so use the captured handle.
                await db_session.rollback()
                existing = await crud.connection.get_by_pair(db_session, requester_pk, user_pk)
                if existing is None:
                    raise
                return self._to_connection_read(existing, requester_username)
        # A connected pair holds no pending requests; retire any in either direction
        # so a later revoke or block-then-unblock does not leave a phantom request.
        await crud.direct_message.clear_requests(db_session, user_a=requester_pk, user_b=user_pk)
        await db_session.commit()
        logger.info("Message request accepted: %s -> %s", requester_pk, user_pk)
        return self._to_connection_read(connection, requester_username)

    async def decline_request(self, db_session: AsyncSession, *, user: User, requester_id: UUID4) -> None:
        """Discard open requests from a user; safe to retry (no-op when none remain)."""
        self.ensure_enabled()
        requester = await self._resolve_user(db_session, requester_id)
        requester_pk, user_pk = requester.id, user.id
        await self._lock_pair(db_session, requester_pk, user_pk)
        await self._reject_if_blocked(db_session, requester_pk, user_pk)
        removed = await crud.direct_message.delete_requests_from(db_session, sender=requester_pk, recipient=user_pk)
        await db_session.commit()
        if removed:
            logger.info("Message request declined: %s -> %s", requester_pk, user_pk)

    async def get_thread(
        self, db_session: AsyncSession, *, user: User, other_id: UUID4, limit: int = 50, offset: int = 0
    ) -> list[DirectMessageRead]:
        """Chronological thread with another user; marks the recipient's reads."""
        self.ensure_enabled()
        other = await self._resolve_user(db_session, other_id)
        messages = await crud.direct_message.get_thread(
            db_session, user_a=user.id, user_b=other.id, limit=limit, offset=offset
        )
        await crud.direct_message.mark_thread_read(db_session, recipient=user.id, sender=other.id)
        await db_session.commit()
        return [self._to_read(message) for message in messages]

    async def list_conversations(
        self, db_session: AsyncSession, *, user: User, limit: int = 50
    ) -> list[DirectMessageSummary]:
        """Conversation list: last message, unread count, pending-request flag per counterpart."""
        self.ensure_enabled()
        messages = await crud.direct_message.list_for_user(db_session, user.id)
        if not messages:
            return []

        conversations: dict[UUID4, dict] = {}
        for message in messages:
            counterpart = message.recipient_user_id if message.sender_user_id == user.id else message.sender_user_id
            box = conversations.setdefault(counterpart, {"last": None, "unread": 0, "incoming_request": False})
            box["last"] = message
            if message.recipient_user_id == user.id:
                if message.read_at is None:
                    box["unread"] += 1
                if message.is_request:
                    box["incoming_request"] = True

        accepted_connections = {
            row.addressee_id if row.requester_id == user.id else row.requester_id
            for row in await crud.connection.get_for_user(db_session, user.id)
            if row.status is ConnectionStatus.ACCEPTED
        }
        usernames = await self._usernames(db_session, list(conversations))

        summaries = [
            DirectMessageSummary(
                counterpart_user_id=counterpart,
                counterpart_username=usernames.get(counterpart, ""),
                last_message=self._to_read(box["last"]),
                unread_count=box["unread"],
                has_pending_request=box["incoming_request"] and counterpart not in accepted_connections,
            )
            for counterpart, box in conversations.items()
        ]
        summaries.sort(key=lambda s: s.last_message.created_at or "", reverse=True)
        return summaries[:limit]

    async def _reject_if_blocked(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> None:
        if await crud.user_block.get_between(db_session, user_a, user_b) is not None:
            raise ValidationException("This conversation is blocked.")

    async def _lock_pair(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> None:
        """Serialize a pair-mutating operation across workers; no-op outside PostgreSQL."""
        await advisory_xact_lock(db_session, player_pair_lock_key(user_a, user_b))

    async def _usernames(self, db_session: AsyncSession, user_ids: list[UUID4]) -> dict[UUID4, str]:
        users = await crud.user.get_by_ids(user_ids, db_session)
        return {user.id: user.username for user in users}


direct_message_service = DirectMessageService()
