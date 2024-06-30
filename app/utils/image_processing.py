import httpx


async def image_url_to_bytes(url: str) -> bytes | None:
    """Fetch an image from a URL and return its bytes."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.content
        except httpx.RequestError as e:
            print(f"Error fetching image: {e}")
            return None
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
