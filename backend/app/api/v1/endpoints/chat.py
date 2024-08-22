import json
import random
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import Client
from pydantic import UUID4, BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.db.session import get_async_session
from app.models.base import SPECIALModel
from app.models.objective import ObjectiveBase
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.open_ai import get_openai_service

router = APIRouter()


class ResponseType(StrEnum):
    text = "text"
    voice = "voice"


@router.get("/", response_model=dict[str, str])
def test_read():
    client = get_openai_service().client
    response = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "Say this is a test",
            }
        ],
        model="gpt-3.5-turbo",
    )
    print(response.choices[0].message.content)

    return {"Assistant": f"{response.choices[0].message.content}"}


def text_to_audio(
    text: str,
    voice_type: str,
    file_name: str,
    client: Client,
):
    """
    Convert text to audio file using the OpenAI API.
    """
    voice_type_map = {
        "Male": ["echo", "fable", "onyx"],
        "Female": ["nova", "shimmer"],
        None: ["alloy"],
    }
    speech_file_path = f"{file_name}.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice=random.choice(voice_type_map[voice_type]),
        input=text,
    )
    response.stream_to_file(speech_file_path)


class ObjectiveKindEnum(StrEnum):
    ANY = "Any"
    ASSIGN = "assign"
    COLLECT = "collect"
    CRAFT = "craft"
    EQUIP = "equip"
    KILL = "kill"


@router.get("/generate_objectives", response_model=list[ObjectiveBase])
def generate_objectives(
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
        client = get_openai_service().client
        response = client.chat.completions.create(
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

    special_stats = ", ".join(f"{stat}: {getattr(dweller, stat)}" for stat in SPECIALModel.__annotations__)
    vault_stats = (
        f" Average happiness: {dweller.vault.happiness}/100"
        f" Power: {dweller.vault.power}/{dweller.vault.power_max}"
        f" Food: {dweller.vault.food}/{dweller.vault.food_max}"
        f" Water: {dweller.vault.water}/{dweller.vault.water_max}"
    )

    dweller_prompt = f"""
    You are a Vault-Tec Dweller named {dweller.first_name} {dweller.last_name} in a post-apocalyptic world.
    You are {dweller.gender.value} {"Adult" if dweller.is_adult else "Child"} of level {dweller.level}.
    You are considered a {dweller.rarity.value} rarity dweller.
    You are in a vault {dweller.vault.name} with a group of other dwellers.
    You are in the {dweller.room.name if dweller.room else "a"} room of the vault.
    Your outfit is {dweller.outfit.name if dweller.outfit else "Vault Suit"}.
    Your weapon is {dweller.weapon.name if dweller.weapon else "Fist"}.
    You have {dweller.stimpack} Stimpacks and {dweller.radaway} Radaways.
    Your health is {dweller.health}/{dweller.max_health}.
    Your happiness level is {dweller.happiness}/100. Don't mention this, just act accordingly.
    Your SPECIAL stats are: {special_stats}. Don't mention them until asked, use this information for acting.
    In case user asks about vault - here is the information: {vault_stats}. Say it in a natural way.
    Try to be in character and be in line with the Fallout universe.
    """

    client = get_openai_service().client

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": dweller_prompt.strip()},
            {"role": "user", "content": message.message},
        ],
    )

    response_message = response.choices[0].message.content

    llm_int_create = LLMInteractionCreate(
        parameters=message.message,
        response=response_message,
        usage="chat_with_dweller",
        user_id=user.id,
    )
    await llm_interaction_crud.create(
        db_session,
        obj_in=llm_int_create,
    )

    return {"response": response_message}
