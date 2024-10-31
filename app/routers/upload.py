from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import time
import jwt
import httpx  # httpxをインポート
import os
from pathlib import Path
import logging
from app.auth import get_current_user 

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# API URLと認証情報
API_URL = "https://api.klingai.com/v1/videos/image2video"
ACCESS_KEY = "e250a0fa119449199b232e0fe32728e9"
SECRET_KEY = "0bc00ee72c694122b393772e99336ce8"

def encode_jwt_token(ak: str, sk: str) -> str:
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": ak, "exp": int(time.time()) + 1800, "nbf": int(time.time()) - 5}
    return jwt.encode(payload, sk, algorithm='HS256', headers=headers)
class VideoRequest(BaseModel):
    model: str = "kling-v1"
    image: str
    prompt: str = None
    negative_prompt: str = None
    cfg_scale: float = 0.5
    mode: str = "std"
    duration: int = 5
    callback_url: str = None

class TaskResponse(BaseModel):
    task_id: str
    task_status: str
    created_at: int
    updated_at: int

class QueryTaskResponse(BaseModel):
    code: int
    message: str
    request_id: str
    data: TaskResponse

async def save_uploaded_image(file: UploadFile, path: Path):
    with path.open("wb") as f:
        f.write(await file.read())

@router.post("/v1/videos/image2video")
async def create_video(order_id, request: VideoRequest, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    temp_dir = Path("files/order") / request.image
    temp_dir.mkdir(parents=True, exist_ok=True)
    merge_image_path = temp_dir /order_id/ f"merge.jpg"

    try:
        # アップロードされた画像を保存
        with open(merge_image_path, "wb") as f:
            f.write(await file.read())

        # JWTトークン生成
        authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)

        # 動画生成APIにリクエスト送信
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {authorization}"}
            files = {'image': (merge_image_path.name, open(merge_image_path, 'rb'), 'image/jpeg')}
            response = await client.post(API_URL, headers=headers, files=files, data=request.dict())
            response.raise_for_status()

        response_json = response.json()
        if response_json["code"] != 0:
            raise HTTPException(status_code=400, detail=response_json["message"])

        return response_json

    except HTTPException as e:
        logging.error(f"HTTP error occurred: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error occurred during video creation: {e}")
        raise HTTPException(status_code=500, detail="動画の作成に失敗しました")
    finally:
        if merge_image_path.exists():
            os.remove(merge_image_path)

@router.get("/v1/videos/image2video/{task_id}", response_model=QueryTaskResponse)
async def query_task(task_id: str, token: str = Depends(oauth2_scheme), user: dict = Depends(get_current_user)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    headers = {"Authorization": f"Bearer {authorization}"}
    api_url = f"{API_URL}/{task_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "不明なエラー"))

    return response.json()

