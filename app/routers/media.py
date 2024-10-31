from fastapi import FastAPI,APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
import mimetypes

app = FastAPI()
router = APIRouter()

# Directory where your media files are stored
MEDIA_DIR = Path("/files")

def validate_token(token: str) -> bool:
    # Implement your token validation logic here
    return True

@app.get("/files/{order_id}/{media_type:path}")
async def get_media(order_id: str, media_type: str, token: str = Query(...)):
    # Token validation
    if not validate_token(token):
        raise HTTPException(status_code=403, detail="無効または期限切れのトークンです。")
    
    # Construct the file path
    file_path = MEDIA_DIR / order_id / media_type
    
    # Check if the file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。")
    
    # Detect media type (MIME type) dynamically
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"
    
    return FileResponse(file_path, media_type=mime_type)

app.include_router(router)

