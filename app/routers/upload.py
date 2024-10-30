from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import time
import jwt
import requests
import os
from pathlib import Path

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

# 画像をアップロードし動画を生成するエンドポイント
@router.post("/v1/videos/image2video/{product_id}", response_model=QueryTaskResponse)
async def create_video(product_id: str, file: UploadFile = File(...), prompt: str = "", token: str = Depends(oauth2_scheme)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    temp_dir = Path(f"files/product/{product_id}")
    temp_dir.mkdir(parents=True, exist_ok=True)
    merge_image_path = temp_dir / "merge.jpg"

    # アップロードされた画像を一時ディレクトリに保存
    with merge_image_path.open("wb") as f:
        f.write(await file.read())

    # APIヘッダーとデータの設定
    headers = {"Authorization": f"Bearer {authorization}"}
    files = {'image': (merge_image_path.name, open(merge_image_path, 'rb'), 'image/jpeg')}
    data = {'prompt': prompt}

    # APIリクエストを送信
    response = requests.post(API_URL, headers=headers, files=files, data=data)

    # エラーチェックと処理
    if response.status_code != 200:
        os.remove(merge_image_path)
        error_message = response.json().get("message", "不明なエラー")
        raise HTTPException(status_code=response.status_code, detail=error_message)

    response_json = response.json()
    if response_json["code"] != 0:  # 0が成功コードと仮定
        os.remove(merge_image_path)
        raise HTTPException(status_code=400, detail=response_json["message"])

    # タスクIDを使用して動画ファイルを生成（ダミー処理）
    task_data = response_json["data"]
    task_id = task_data["task_id"]
    generated_video_path = temp_dir / f"{task_id}.mp4"

    with open(generated_video_path, "w", encoding="utf-8") as f:
        f.write("これはダミーファイルです")

    os.remove(merge_image_path)

    return {
        "code": 0,
        "message": "成功",
        "request_id": response_json["request_id"],
        "data": {
            "task_id": task_id,
            "task_status": task_data["task_status"],
            "created_at": task_data["created_at"],
            "updated_at": task_data["updated_at"]
        }
    }

# タスクの状態を取得するエンドポイント
@router.get("/v1/videos/image2video/{task_id}", response_model=QueryTaskResponse)
async def query_task(task_id: str, token: str = Depends(oauth2_scheme)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    headers = {"Authorization": f"Bearer {authorization}"}
    api_url = f"{API_URL}/{task_id}"

    response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "不明なエラー"))

    response_json = response.json()
    if response_json["code"] != 0:
        raise HTTPException(status_code=400, detail=response_json["message"])

    return response_json

# タスクの一覧を取得するエンドポイント
@router.get("/v1/videos/image2video", response_model=QueryTaskResponse)
async def query_tasks(token: str = Depends(oauth2_scheme)):
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)
    headers = {"Authorization": f"Bearer {authorization}"}
    response = requests.get(API_URL, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "不明なエラー"))

    response_json = response.json()
    if response_json["code"] != 0:
        raise HTTPException(status_code=400, detail=response_json["message"])

    return response_json
