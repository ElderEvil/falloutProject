"""Summary service: rewrite the thread summary from the messages being pruned."""

from uuid import UUID

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.chat.summary import build_summary_prompt, maybe_summarize


class Recorder:
    """Stub summariser: records prompts, returns a fixed reply."""

    def __init__(self, reply: str = "Vera lost her brother to raiders and asked the Overseer for news.") -> None:
        self.prompts: list[str] = []
        self.reply = reply
        self.error: Exception | None = None

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.reply


async def _thread(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *texts: str
) -> tuple[Conversation, list[ChatMessage]]:
    await async_session.refresh(vault, ["user"])
    conversation = await crud.conversation.get_or_create(
        async_session, vault_id=vault.id, user_id=vault.user.id, dweller_id=dweller.id
    )
    rows: list[ChatMessage] = []
    for index, text in enumerate(texts):
        from_user = index % 2 == 0
        row = ChatMessage(
            vault_id=vault.id,
            from_user_id=vault.user.id if from_user else None,
            to_dweller_id=dweller.id if from_user else None,
            from_dweller_id=None if from_user else dweller.id,
            to_user_id=None if from_user else vault.user.id,
            message_text=text,
            conversation_id=conversation.id,
        )
        async_session.add(row)
        rows.append(row)
    await async_session.flush()
    return conversation, rows


async def _stored(async_session: AsyncSession, conversation_id: UUID) -> tuple[str | None, UUID | None]:
    row = (
        await async_session.execute(
            select(Conversation.summary, Conversation.summary_through_message_id).where(
                Conversation.id == conversation_id
            )
        )
    ).one()
    return row[0], row[1]


async def test_nothing_dropped_leaves_the_thread_untouched(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, _ = await _thread(async_session, vault, dweller, "Hello.", "Hello, Overseer.")
    recorder = Recorder()

    result = await maybe_summarize(async_session, conversation, dropped=[], model=recorder)

    assert result is conversation
    assert recorder.prompts == []
    assert await _stored(async_session, conversation.id) == (None, None)


async def test_summary_covers_the_dropped_messages(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    conversation, rows = await _thread(
        async_session,
        vault,
        dweller,
        "Have you heard from Vera's brother?",
        "No. He went east with the caravan and never came back.",
        "She still asks about him.",
        "I know. I have not told her what the scouts found.",
    )
    recorder = Recorder()

    result = await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    assert result is conversation
    assert conversation.summary == recorder.reply
    assert conversation.summary_through_message_id == rows[-1].id
    assert await _stored(async_session, conversation.id) == (recorder.reply, rows[-1].id)


async def test_prompt_carries_the_existing_summary_and_both_speakers(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(
        async_session, vault, dweller, "Any news from the east?", "Only rumours, Overseer."
    )
    conversation.summary = "Vera keeps asking about her brother, who left with the caravan."
    recorder = Recorder()

    await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    prompt = recorder.prompts[0]
    assert "Vera keeps asking about her brother" in prompt
    assert "Overseer: Any news from the east?" in prompt
    assert "Dweller: Only rumours, Overseer." in prompt
    assert prompt.index("Any news from the east?") < prompt.index("Only rumours, Overseer.")
    assert str(game_config.chat.summary_max_chars) in prompt
    assert "third person" in prompt
    assert "promises" in prompt


async def test_summary_is_truncated_to_the_configured_limit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(async_session, vault, dweller, "Talk.", "Talking.")
    recorder = Recorder(reply="z" * (game_config.chat.summary_max_chars + 500))

    await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    assert conversation.summary is not None
    assert len(conversation.summary) == game_config.chat.summary_max_chars


async def test_model_failure_keeps_the_existing_summary(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(async_session, vault, dweller, "Talk.", "Talking.")
    conversation.summary = "An older summary that must survive."
    conversation.summary_through_message_id = rows[0].id
    await async_session.flush()
    recorder = Recorder()
    recorder.error = RuntimeError("provider exploded")

    result = await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    assert result is conversation
    assert await _stored(async_session, conversation.id) == (
        "An older summary that must survive.",
        rows[0].id,
    )


async def test_already_summarised_messages_are_skipped(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(
        async_session, vault, dweller, "one.", "two.", "three.", "four.", "five.", "six."
    )
    conversation.summary = "Covers the opening exchange."
    conversation.summary_through_message_id = rows[2].id
    recorder = Recorder()

    await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    prompt = recorder.prompts[0]
    assert "four." in prompt
    assert "one." not in prompt
    assert "three." not in prompt
    assert conversation.summary_through_message_id == rows[-1].id


async def test_batch_already_covered_needs_no_model_call(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(async_session, vault, dweller, "one.", "two.")
    conversation.summary = "Already covers both."
    conversation.summary_through_message_id = rows[-1].id
    recorder = Recorder()

    result = await maybe_summarize(async_session, conversation, dropped=rows, model=recorder)

    assert result is conversation
    assert recorder.prompts == []
    assert conversation.summary == "Already covers both."


async def test_blank_model_reply_leaves_the_summary_untouched(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    conversation, rows = await _thread(async_session, vault, dweller, "Talk.", "Talking.")
    conversation.summary = "Kept."

    await maybe_summarize(async_session, conversation, dropped=rows, model=Recorder(reply="   "))

    assert conversation.summary == "Kept."
    assert conversation.summary_through_message_id is None


async def test_missing_model_configuration_degrades_silently(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversation, rows = await _thread(async_session, vault, dweller, "Talk.", "Talking.")
    monkeypatch.setattr("app.services.chat.summary.get_model", lambda: None)

    result = await maybe_summarize(async_session, conversation, dropped=rows)

    assert result is conversation
    assert conversation.summary is None


def test_build_summary_prompt_handles_no_existing_summary() -> None:
    rows = [
        ChatMessage(vault_id=UUID(int=1), from_user_id=UUID(int=2), message_text="Hi."),
        ChatMessage(vault_id=UUID(int=1), from_dweller_id=UUID(int=3), message_text="Hello."),
    ]

    prompt = build_summary_prompt(None, rows)

    assert "No summary yet" in prompt
    assert "Hi." in prompt
