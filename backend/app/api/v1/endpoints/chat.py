"""Chat endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.db.session import get_async_session
from app.models.chat_message import ChatMessage as ChatMessageRow
from app.models.chat_message import ChatMessageRead
from app.schemas.chat import ChatMessage, DwellerChatResponse, DwellerVoiceChatResponse
from app.services.chat_service import chat_service
from app.services.conversation_service import conversation_service

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/{dweller_id}", response_model=DwellerChatResponse)
async def chat_with_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    message: ChatMessage,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerChatResponse:
    """Send a text message and publish the resulting chat notifications."""
    response = await chat_service.process_text_message(
        db_session=db_session,
        user=user,
        dweller_id=dweller_id,
        message_text=message.message,
    )
    await chat_service.send_chat_notification(
        user_id=user.id,
        dweller_id=dweller_id,
        dweller_message_id=response.dweller_message_id,
        happiness_impact=response.happiness_impact,
        action_suggestion=response.action_suggestion,
    )
    return response


@router.get("/history/{dweller_id}", response_model=list[ChatMessageRead])
async def get_chat_history(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = 100,
    offset: int = 0,
) -> list[ChatMessageRow]:
    """Get conversation history between user and dweller.

    Returns:
        list[ChatMessageRead]: List of chat messages.

    Raises:
        HTTPException: 404 if dweller not found.
    """
    dweller = await dweller_crud.get(db_session, dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    return await chat_message_crud.get_conversation(
        db_session,
        user_id=user.id,
        dweller_id=dweller.id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{dweller_id}/voice",
    response_model=DwellerVoiceChatResponse,
    responses={400: {"description": "Empty audio file"}},
)
async def voice_chat_with_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    audio_file: Annotated[UploadFile, File()],
    *,
    return_audio: bool = True,
) -> Response | DwellerVoiceChatResponse:
    """Transcribe audio, generate a reply, and return MP3 bytes or conversation metadata."""
    result = await conversation_service.process_audio_message(
        db_session=db_session,
        user=user,
        dweller_id=dweller_id,
        audio_bytes=await audio_file.read(),
        audio_filename=audio_file.filename or "audio.webm",
    )
    if return_audio:
        return Response(
            content=result.dweller_audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": 'inline; filename="dweller_response.mp3"',
                "X-Transcription": result.transcription,
                "X-Response-Text": result.dweller_response,
                "X-Message-Id": str(result.dweller_message_id),
            },
        )
    return result
