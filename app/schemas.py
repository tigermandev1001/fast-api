from pydantic import BaseModel
from typing import Optional

class PhotoCreate(BaseModel):
    photo_url: str
    user_id: str
