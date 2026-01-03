import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


async def image_url_to_bytes(url: str) -> bytes | None:
    """Fetch an image from a URL and return its bytes."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error("Error fetching image from URL", exc_info=True, extra={"url": url, "error": str(e)})  # noqa: G201
            return None
        else:
            return response.content


def generate_thumbnail(image_bytes: bytes, max_size: tuple[int, int] = (256, 256)) -> bytes:
    """Generate a thumbnail from an image."""
    image = Image.open(io.BytesIO(image_bytes))
    image.thumbnail(max_size)
    thumbnail_bytes = io.BytesIO()
    image.save(thumbnail_bytes, format="JPEG")
    return thumbnail_bytes.getvalue()
