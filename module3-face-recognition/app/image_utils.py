"""
Image decoding, conversion, and validation utilities.
Ensures in-memory processing only with zero disk persistence.
"""
import base64
from io import BytesIO
from typing import Optional
import numpy as np
from PIL import Image


def decode_base64_image(base64_string: str) -> Optional[np.ndarray]:
    """
    Decode a base64 encoded image string into an in-memory RGB NumPy array.

    Args:
        base64_string: Raw base64 string or data URI (data:image/jpeg;base64,...)

    Returns:
        NumPy array (H, W, 3) in RGB format, or None if decoding/parsing fails.
    """
    if not base64_string or not isinstance(base64_string, str):
        return None

    try:
        # Strip header if data URI is used
        if "," in base64_string:
            base64_string = base64_string.split(",", 1)[1]

        # Fix padding if necessary
        missing_padding = len(base64_string) % 4
        if missing_padding:
            base64_string += "=" * (4 - missing_padding)

        image_bytes = base64.b64decode(base64_string)
        if not image_bytes:
            return None

        # Load with PIL in memory
        with Image.open(BytesIO(image_bytes)) as pil_img:
            # Ensure RGB format
            rgb_img = pil_img.convert("RGB")
            img_array = np.array(rgb_img, dtype=np.uint8)

        # Validate dimensions
        if img_array.ndim != 3 or img_array.shape[2] != 3:
            return None
        if img_array.shape[0] < 10 or img_array.shape[1] < 10:
            return None

        return img_array

    except Exception:
        return None
