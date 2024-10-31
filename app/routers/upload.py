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

# OAuthとAPI設定
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

API_URL = "https://api.klingai.com/v1/videos/image2video"

ACCESS_KEY = "e250a0fa119449199b232e0fe32728e9"
SECRET_KEY = "0bc00ee72c694122b393772e99336ce8"

# JWTトークン生成関数
def encode_jwt_token(ak: str, sk: str) -> str:
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": ak, "exp": int(time.time()) + 1800, "nbf": int(time.time()) - 5}
    return jwt.encode(payload, sk, algorithm='HS256', headers=headers)

# レスポンスモデル
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
    """アップロードされた画像を指定されたパスに保存します。"""
    with path.open("wb") as f:
        f.write(await file.read())

async def generate_video(temp_dir: Path, prompt: str, authorization: str):
    """アップロードされた画像とプロンプトに基づいて動画を生成するリクエストを送信します。"""
    headers = {"Authorization": f"Bearer {authorization}"}
    image_path = temp_dir / "merge.jpg"
    
    async with httpx.AsyncClient() as client:
        with image_path.open('rb') as image_file:
            files = {'image': (image_path.name, image_file, 'image/jpeg')}
            data = {'prompt': prompt}

            response = await client.post(API_URL, headers=headers, files=files, data=data)
            response.raise_for_status()

    return response.json()

# Constants
ACCESS_KEY = "e250a0fa119449199b232e0fe32728e9"
SECRET_KEY = "0bc00ee72c694122b393772e99336ce8"
TEMP_DIR = Path("files/order")

# Token generation function
def encode_jwt_token(ak, sk):
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,  # Valid for 30 minutes
        "nbf": int(time.time()) - 5       # Starts 5 seconds before now
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token

# Request model
class VideoRequest(BaseModel):
    model: str = "kling-v1"
    image: str
    prompt: str = None
    negative_prompt: str = None
    cfg_scale: float = 0.5
    mode: str = "std"
    duration: int = 5
    callback_url: str = None

# Endpoint to create a video
@router.post("/v1/videos/image2video")
async def create_video(order_id, request: VideoRequest, file: UploadFile = File(...)):
    temp_dir = TEMP_DIR / request.image
    temp_dir.mkdir(parents=True, exist_ok=True)
    merge_image_path = temp_dir /order_id/ f"merge.jpg"

    try:
        # Save the uploaded image
        with open(merge_image_path, "wb") as f:
            f.write(await file.read())

        # Generate JWT token
        authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)

        # Here you would call the video generation service (mocked response)
        response_json = {
            "code": 0,
            "message": "Success",
            "data": {
                "task_id": "12345",
                "task_status": "submitted",
                "created_at": int(time.time()),
                "updated_at": int(time.time())
            },
            "request_id": "request_123"
        }

        if response_json["code"] != 0:
            raise HTTPException(status_code=400, detail=response_json["message"])

        task_data = response_json["data"]
        return {
            "code": 0,
            "message": "Success",
            "request_id": response_json["request_id"],
            "data": {
                "task_id": task_data["task_id"],
                "task_status": task_data["task_status"],
                "created_at": task_data["created_at"],
                "updated_at": task_data["updated_at"]
            }
        }

    except HTTPException as e:
        logging.error(f"HTTP error occurred: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error occurred during video creation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create video")
    finally:
        if merge_image_path.exists():
            os.remove(merge_image_path)


# タスクの状態を取得するエンドポイント
@router.get("/v1/videos/image2video/{task_id}", response_model=QueryTaskResponse)
async def query_task(task_id: str, token: str = Depends(oauth2_scheme), user: dict = Depends(get_current_user)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    headers = {"Authorization": f"Bearer {authorization}"}
    api_url = f"{API_URL}/{task_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "不明なエラー"))

    response_json = response.json()
    if response_json["code"] != 0:
        raise HTTPException(status_code=400, detail=response_json["message"])

    return response_json

# タスクの一覧を取得するエンドポイント
@router.get("/v1/videos/image2video", response_model=QueryTaskResponse)
async def query_tasks(token: str = Depends(oauth2_scheme), user: dict = Depends(get_current_user)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    headers = {"Authorization": f"Bearer {authorization}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "不明なエラー"))

    response_json = response.json()
    if response_json["code"] != 0:
        raise HTTPException(status_code=400, detail=response_json["message"])

    return response_json
