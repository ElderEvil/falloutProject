from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from sqlalchemy import event, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

FaultHook = Callable[[str], object]


@asynccontextmanager
async def fail_sql(async_session: AsyncSession, predicate: FaultHook, message: str) -> AsyncGenerator[None]:
    """Raise at the first statement matching ``predicate`` while the block runs."""
    connection = (await async_session.connection()).sync_connection

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if predicate(statement):
            raise RuntimeError(message)

    event.listen(connection, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(connection, "before_cursor_execute", hook)


@asynccontextmanager
async def record_statements(async_session: AsyncSession) -> AsyncGenerator[tuple[list[str], list[int]]]:
    """Record every statement and the statement index at which each commit was issued."""
    connection = (await async_session.connection()).sync_connection
    statements: list[str] = []
    commit_marks: list[int] = []

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if not statement.lower().startswith(("savepoint", "release savepoint", "rollback to savepoint", "begin")):
            statements.append(statement)

    original_commit = async_session.commit

    async def counting_commit() -> None:
        await original_commit()
        # Recorded after the flush: the commit itself emits the staged writes.
        commit_marks.append(len(statements))

    event.listen(connection, "before_cursor_execute", hook)
    async_session.commit = counting_commit  # type: ignore[method-assign]
    try:
        yield statements, commit_marks
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def counting_commit(session: AsyncSession) -> list[int]:
    """Replace ``session.commit`` with one that appends to the returned list."""
    commits: list[int] = []
    original_commit = session.commit

    async def counted() -> None:
        commits.append(1)
        await original_commit()

    session.commit = counted  # type: ignore[method-assign]
    return commits


@asynccontextmanager
async def fresh_session(db_connection) -> AsyncGenerator[AsyncSession]:
    """A clean session for reading the outcome the poisoned one cannot report."""
    async with AsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as session:
        yield session


async def count_rows(session: AsyncSession, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())
