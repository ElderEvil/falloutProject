import random
from enum import Enum

import logfire
from fastapi import APIRouter, Depends
from openai import Client
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.dweller import dweller as dweller_crud
from app.db.session import get_async_session
from app.models.base import SPECIALModel
from app.services.open_ai import get_chatpgt_client

router = APIRouter()


class ResponseType(str, Enum):
    text = "text"
    voice = "voice"


@router.get("/", response_model=dict[str, str])
async def test_read(client: Client = Depends(get_chatpgt_client)):
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


async def text_to_audio(
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


@router.post("/{dweller_id}", response_model=dict[str, str])
async def ask_dweller(
    dweller_id: UUID4,
    message: str,
    response_type: ResponseType = ResponseType.text,
    client: Client = Depends(get_chatpgt_client),
    db_session: AsyncSession = Depends(get_async_session),
):
    """
    Ask a Vault-Tec Dweller a question and get a response.
    :param dweller_id:
    :param message:
    :param response_type:
    :param client:
    :param db_session:
    :return: Some data
    """
    dweller = await dweller_crud.get_full_info(db_session, dweller_id)
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
    You are in the {dweller.room.name} room of the vault.
    Your outfit is {dweller.outfit.name if dweller.outfit else "Vault Suit"}.
    Your weapon is {dweller.weapon.name if dweller.weapon else "Fist"}.
    You have {dweller.stimpack} Stimpacks and {dweller.radaway} Radaways.
    Your health is {dweller.health}/{dweller.max_health}.
    Your happiness level is {dweller.happiness}/100. Don't mention this, just act accordingly.
    Your SPECIAL stats are: {special_stats}. Don't mention them until asked, use this information for acting.
    In case user asks about vault - here is the information: {vault_stats}. Say it in a natural way.
    Try to be in character and be in line with the Fallout universe.
    """
    logfire.info(dweller_prompt)

    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": dweller_prompt.strip(),
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        model="gpt-4o",
    )
    answer = response.choices[0].message.content
    logfire.info(answer)

    if response_type == ResponseType.voice:
        logfire.info("Creating audio file...")
        await text_to_audio(
            text=answer,
            voice_type=dweller.gender.value,
            file_name=f"{dweller.first_name.lower()}_{dweller.last_name.lower()}",
            client=client,
        )
        return {"Dweller": "Response audio file created"}

    return {"Dweller": f"{answer}"}
