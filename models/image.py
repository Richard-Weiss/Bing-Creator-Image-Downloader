from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class Image:
    """
    This class is used to represent a single image and its properties.
    """
    image_urls: List[Tuple[int, str]]
    index: str
    prompt: str
    page_url: str
    collection_name: str = 'Collection'
    date_modified: str = None
    creation_date: str = None
    used_image_url: str = None
    file_name: str = None
    is_thumbnail: bool = False
    is_success: bool = False
    reason: str = None
    attempts: int = 0
