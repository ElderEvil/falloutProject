import logfire
import openai

from app.core.config import settings

client = openai.Client(
    api_key=settings.OPENAI_API_KEY,
)

logfire.instrument_openai(client)

response = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "Say this is a test",
        }
    ],
    model="gpt-3.5",
)
print(response.choices[0].text)
