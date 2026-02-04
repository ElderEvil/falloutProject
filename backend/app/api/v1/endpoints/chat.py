import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import UUID4, BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.db.session import get_async_session
from app.models.chat_message import ChatMessageRead
from app.schemas.chat import DwellerChatResponse, DwellerVoiceChatResponse
from app.services.chat_service import chat_service
from app.services.conversation_service import conversation_service
from app.services.websocket_manager import manager
from app.utils.exceptions import ValidationException

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    message: str


@router.post("/{dweller_id}", response_model=DwellerChatResponse)
async def chat_with_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    message: ChatMessage,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Send a text message to a dweller and get a response."""
    try:
        response = await chat_service.process_text_message(
            db_session=db_session,
            user=user,
            dweller_id=dweller_id,
            message_text=message.message,
        )

        # Emit WebSocket notifications after REST response is ready (non-fatal)
        try:
            if response.happiness_impact:
                await manager.send_chat_message(
                    {
                        "type": "happiness_update",
                        "happiness_impact": response.happiness_impact.model_dump(mode="json"),
                        "message_id": str(response.dweller_message_id),
                    },
                    user_id=user.id,
                    dweller_id=dweller_id,
                )

            if response.action_suggestion and response.action_suggestion.action_type != "no_action":
                await manager.send_chat_message(
                    {
                        "type": "action_suggestion",
                        "action_suggestion": response.action_suggestion.model_dump(mode="json"),
                        "message_id": str(response.dweller_message_id),
                    },
                    user_id=user.id,
                    dweller_id=dweller_id,
                )
        except Exception:
            logger.exception("Failed to send WebSocket notification, continuing with REST response")

        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/history/{dweller_id}", response_model=list[ChatMessageRead])
async def get_chat_history(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = 100,
    offset: int = 0,
):
    """Get conversation history between user and dweller"""
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


@router.post("/{dweller_id}/voice", response_model=DwellerVoiceChatResponse)
async def voice_chat_with_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    audio_file: Annotated[UploadFile, File()],
    *,
    return_audio: bool = True,
):
    """
    Send an audio message to a dweller and receive an audio response.

    Upload an audio file (WebM, MP3, WAV), it will be:
    1. Transcribed to text (STT)
    2. Processed by the dweller's AI (LLM)
    3. Converted to audio response (TTS)
    4. Saved to chat history

    Args:
        dweller_id: UUID of the dweller to chat with
        user: Current authenticated user
        db_session: Database session
        audio_file: Audio file upload (WebM, MP3, WAV, etc.)
        return_audio: If True, returns audio bytes; if False, returns JSON with URLs

    Returns:
        Audio response (MP3) or JSON with transcription and audio URL
    """
    try:
        # Read audio file
        audio_bytes = await audio_file.read()

        if len(audio_bytes) == 0:
            raise ValidationException(detail="Empty audio file")

        # Get filename for format detection
        filename = audio_file.filename or "audio.webm"

        # Process the audio conversation
        result = await conversation_service.process_audio_message(
            db_session=db_session,
            user=user,
            dweller_id=dweller_id,
            audio_bytes=audio_bytes,
            audio_filename=filename,
        )

        # Emit WebSocket notifications (non-fatal)
        try:
            if result["happiness_impact"]:
                await manager.send_chat_message(
                    {
                        "type": "happiness_update",
                        "happiness_impact": result["happiness_impact"].model_dump(mode="json"),
                        "message_id": str(result["dweller_message_id"]),
                    },
                    user_id=user.id,
                    dweller_id=dweller_id,
                )

            if result["action_suggestion"] and result["action_suggestion"].action_type != "no_action":
                await manager.send_chat_message(
                    {
                        "type": "action_suggestion",
                        "action_suggestion": result["action_suggestion"].model_dump(mode="json"),
                        "message_id": str(result["dweller_message_id"]),
                    },
                    user_id=user.id,
                    dweller_id=dweller_id,
                )
        except Exception:
            logger.exception("Failed to send WebSocket notification, continuing with REST response")

        # Return audio bytes directly for immediate playback
        if return_audio:
            return Response(
                content=result["dweller_audio_bytes"],
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": 'inline; filename="dweller_response.mp3"',
                    "X-Transcription": result["transcription"],
                    "X-Response-Text": result["dweller_response"],
                    "X-Message-Id": str(result["dweller_message_id"]),
                },
            )

        # Build JSON response with all details including happiness and action suggestion
        response = DwellerVoiceChatResponse(
            transcription=result["transcription"],
            user_audio_url=result["user_audio_url"],
            dweller_response=result["dweller_response"],
            dweller_audio_url=result["dweller_audio_url"],
            dweller_message_id=result["dweller_message_id"],
            happiness_impact=result["happiness_impact"],
            action_suggestion=result["action_suggestion"],
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error processing voice chat")
        raise HTTPException(status_code=500, detail=f"Error processing audio: {e!s}") from e
    else:
        return response
