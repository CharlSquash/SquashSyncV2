# core/utils.py
import re

def parse_grade_from_string(grade_str: str):
    """
    Parses a grade string (e.g., 'Grade 8', '8', 'Gr 8') and returns an integer.
    Returns None if parsing fails.
    """
    if not grade_str:
        return None
    # Find the first number in the string
    match = re.search(r'\d+', grade_str)
    if match:
        return int(match.group(0))
    # Handle special cases like 'Grade R'
    if 'r' in grade_str.lower():
        return 0
    return None

import os
import io
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

def process_profile_image(image_field, original_filename=None):
    """
    Processes a profile image:
    - Opens the image from the field.
    - Applies EXIF transposition.
    - Resizes to max 300x300 (thumbnail).
    - Converts to JPEG (unless it was PNG/GIF and we want to keep transparency, but the original logic converted to JPEG).
    - Returns a tuple (filename_to_save, content_file).
    
    :param image_field: The ImageFieldFile instance (e.g. self.photo).
    :param original_filename: Optional original filename to use as base.
    :return: (filename_to_save, content_file)
    """
    if not image_field or not hasattr(image_field, 'path') or not image_field.path:
        raise ValueError("Invalid image field or path missing")

    filename_base = original_filename if original_filename else image_field.name
    filename_to_save = os.path.basename(filename_base)

    img = Image.open(image_field.path)
    img = ImageOps.exif_transpose(img)

    max_size = (300, 300)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    img_format = img.format if img.format else 'JPEG'
    buffer = io.BytesIO()
    save_kwargs = {'format': img_format, 'optimize': True}

    # Convert to RGB and JPEG if not PNG (matches original logic which seemed to prefer JPEG for everything except maybe PNG, 
    # but the original logic actually forced JPEG if mode was RGBA/P unless it was PNG? 
    # Let's look closely at the original logic:
    # if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG': -> convert to RGB, format=JPEG
    # if img_format.upper() == 'JPEG': -> quality=85
    
    if img.mode in ("RGBA", "P") and img_format.upper() != 'PNG':
        img = img.convert("RGB")
        img_format = 'JPEG'
        filename_to_save = os.path.splitext(filename_to_save)[0] + '.jpg'
        save_kwargs['format'] = 'JPEG'

    if img_format.upper() == 'JPEG':
        save_kwargs['quality'] = 85

    img.save(buffer, **save_kwargs)
    resized_image = ContentFile(buffer.getvalue())
    
    return filename_to_save, resized_image