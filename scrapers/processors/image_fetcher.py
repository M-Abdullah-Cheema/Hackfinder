import aiohttp
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles async memory downloading and image sanitization for OCR."""

    @staticmethod
    async def fetch_and_preprocess(url: str) -> Image.Image | None:
        """Downloads an image directly into RAM and optimizes it for text extraction."""
        try:
            # 1. Async download into a byte buffer
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Failed to fetch image at {url} (Status: {response.status})")
                        return None
                    image_bytes = await response.read()

            # 2. Open image purely in memory (No disk I/O)
            img = Image.open(io.BytesIO(image_bytes))

            # 3. Preprocessing: Convert to Grayscale
            gray_img = img.convert('L')

            # 4. Preprocessing: Apply Binarization Thresholding (High Contrast)
            # Pixels brighter than 150 become pure white (255), everything else becomes pure black (0)
            threshold = 150
            binary_img = gray_img.point(lambda p: 255 if p > threshold else 0)

            return binary_img

        except Exception as e:
            logger.error(f"❌ Error processing image {url}: {str(e)}")
            return None