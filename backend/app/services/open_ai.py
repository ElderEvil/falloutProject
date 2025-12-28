import logging
from functools import lru_cache

import openai

from app.core.config import settings
from app.utils.image_processing import image_url_to_bytes

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.client = openai.Client(api_key=settings.OPENAI_API_KEY)

    def get_chatgpt_client(self):
        return self.client

    async def generate_image(self, *, prompt: str, return_bytes: bool = False):
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url

        return await image_url_to_bytes(url) if return_bytes else url

    async def generate_audio(self, text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
        """
        Generates audio from text using OpenAI's TTS API.
        Returns the audio content as bytes.
        """
        try:
            with self.client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
            ) as response:
                return response.read()
        except Exception as e:
            err_msg = f"Error generating audio from text: {e}"
            logger.exception(err_msg)
            raise

    async def generate_completion(self, messages: list[dict[str, str]]):
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return response.choices[0].message.content

    async def generate_completion_json(self, prompt: str):
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. "
                        "You must assist the user in generating a response to the following prompt in JSON format."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

    async def generate_speech_from_text(self, text_input: str, speech_file_path: str):
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="echo",
            input=text_input,
        )
        response.stream_to_file(speech_file_path)
        return speech_file_path


@lru_cache
def get_openai_service() -> OpenAIService:
    return OpenAIService()
