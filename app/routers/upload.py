from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import httpx
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..crud import create_photo
from ..schemas import PhotoCreate

router = APIRouter()

KLING_API_URL = "https://api.klingai.com/v1/generate"  
KLING_API_KEY = "e250a0fa119449199b232e0fe32728e9"

@router.post("/upload/")
async def upload_photo(file: UploadFile = File(...), prompt: str = ""):
    # Upload the photo and prompt to KLING AI
    files = {'file': (file.filename, await file.read(), file.content_type)}
    headers = {"Authorization": f"Bearer {KLING_API_KEY}"}
    data = {"prompt": prompt}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(KLING_API_URL, headers=headers, data=data, files=files)
        
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)

