import logfire
import openai

from app.core.config import settings

client = openai.Client(
    api_key=settings.OPENAI_API_KEY,
)


async def get_chatpgt_client():
    logfire.instrument_openai(client)
    return client


async def generate_image(prompt: str):
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url


async def generate_completion(messages: list[dict[str, str]]):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    return response.choices[0].message.content


async def generate_completion_json(prompt: str):
    response = client.chat.completions.create(
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


async def generate_speech_from_text(text_input: str, speech_file_path: str):
    response = client.audio.speech.create(
        model="tts-1",
        voice="echo",
        input=text_input,
    )
    response.stream_to_file(speech_file_path)
    return speech_file_path
