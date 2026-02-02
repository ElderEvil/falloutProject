import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import UUID4, BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.db.session import get_async_session
from app.models.chat_message import ChatMessageCreate, ChatMessageRead
from app.models.objective import ObjectiveBase
from app.schemas.common import ObjectiveKindEnum
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.conversation_service import conversation_service
from app.services.open_ai import get_ai_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/generate_objectives", response_model=list[ObjectiveBase])
async def generate_objectives(
    objective_kind: ObjectiveKindEnum,
    objective_count: int = 3,
):
    instructions = """
    You are an assistant for Vault-Tec Overseer who is in charge of assigning objectives to vault dwellers.
    Objectives and rewards should be in line with the Fallout universe.
    Respond with JSON object containing the generated objectives and rewards.
    Make sure to include various rewards such as caps, lunchboxes, Mr. Handy, and Nuka-Cola Quantum.
    There must be 1 lunchbox/quantum/mr. handy reward maximum per set of objectives.

    Example request: {"objective_kind": "Any", "objective_count": 4}
    Example response:
    [
        {
            "challenge": "Assign 3 dwellers in the right room",
            "reward": "25 caps"
        },
        {
            "challenge": "Collect 100 food",
            "reward": "50 caps"
        },
        {
            "challenge": "Craft 5 outfits",
            "reward": "Nuka-Cola Quantum"
        },
        {
            "challenge": "Kill 100 creatures in the Wasteland",
            "reward": "	1 lunchbox"
        }
    ]
    """
    try:
        # Use AsyncOpenAI for async operations
        from openai import AsyncOpenAI

        from app.core.config import settings

        async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await async_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": f"Give {objective_count} {objective_kind} objectives"},
            ],
        )
        generated_objectives = response.choices[0].message.content
        generated_objectives_json = json.loads(generated_objectives)

        # Parse the JSON into the ObjectiveResponseModelList
        return [ObjectiveBase(**obj) for obj in generated_objectives_json]
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Failed to generate objectives") from e


class ChatMessage(BaseModel):
    message: str


@router.post("/{dweller_id}")
async def chat_with_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    message: ChatMessage,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    dweller = await dweller_crud.get_full_info(db_session, dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    # Build dweller prompt using shared method
    dweller_prompt = conversation_service._build_dweller_prompt(dweller, for_audio=False)

    # Use multi-provider chat completion
    ai_service = get_ai_service()
    response_message = await ai_service.chat_completion(
        [
            {"role": "system", "content": dweller_prompt.strip()},
            {"role": "user", "content": message.message},
        ]
    )

    # Save LLM interaction statistics
    llm_int_create = LLMInteractionCreate(
        parameters=message.message,
        response=response_message,
        usage="chat_with_dweller",
        user_id=user.id,
    )
    llm_interaction = await llm_interaction_crud.create(
        db_session,
        obj_in=llm_int_create,
    )

    # Save user message to chat history
    await chat_message_crud.create_message(
        db_session,
        obj_in=ChatMessageCreate(
            vault_id=dweller.vault.id,
            from_user_id=user.id,
            to_dweller_id=dweller.id,
            message_text=message.message,
        ),
    )

    # Save dweller response to chat history
    await chat_message_crud.create_message(
        db_session,
        obj_in=ChatMessageCreate(
            vault_id=dweller.vault.id,
            from_dweller_id=dweller.id,
            to_user_id=user.id,
            message_text=response_message,
            llm_interaction_id=llm_interaction.id,  # Link to AI stats
        ),
    )

    return {"response": response_message}


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


@router.post("/{dweller_id}/voice")
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
            msg = "Empty audio file"
            raise HTTPException(status_code=400, detail=msg)  # noqa: TRY301

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

        # Return audio bytes directly for immediate playback
        if return_audio:
            return Response(
                content=result["dweller_audio_bytes"],
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": 'inline; filename="dweller_response.mp3"',
                    "X-Transcription": result["transcription"],
                    "X-Response-Text": result["dweller_response"],
                },
            )

        # Or return JSON with all details
        return {
            "transcription": result["transcription"],
            "user_audio_url": result["user_audio_url"],
            "dweller_response": result["dweller_response"],
            "dweller_audio_url": result["dweller_audio_url"],
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error processing voice chat")
        raise HTTPException(status_code=500, detail=f"Error processing audio: {e!s}") from e
