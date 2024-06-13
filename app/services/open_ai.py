import logfire
import openai

from app.core.config import settings

client = openai.Client(
    api_key=settings.OPENAI_API_KEY,
)


async def get_chatpgt_client():
    logfire.instrument_openai(client)
    return client
