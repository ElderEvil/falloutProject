import io
import logging
from urllib.parse import urlparse

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
            logger.warning(
                "Error fetching image from host",
                extra={"host": urlparse(url).hostname, "error_type": type(e).__name__},
            )
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
