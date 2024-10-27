from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import time
import jwt
import requests
import os

router = APIRouter()

# 認証の設定
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# アクセスキーとシークレットキーを設定
ACCESS_KEY = "e250a0fa119449199b232e0fe32728e9"  # アクセスキーを入力してください
SECRET_KEY = "0bc00ee72c694122b393772e99336ce8"  # シークレットキーを入力してください

# JWTトークンを生成する関数
def encode_jwt_token(ak: str, sk: str) -> str:
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,  # 有効時間30分
        "nbf": int(time.time()) - 5  # 現在時刻から5秒前に開始
    }
    token = jwt.encode(payload, sk, algorithm='HS256', headers=headers)
    return token

# リクエストボディのモデル
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

# 画像をアップロードし、動画を生成するエンドポイント
@router.post("/v1/videos/image2video/{order_id}", response_model=QueryTaskResponse)
async def create_video(order_id: str, file: UploadFile = File(...), token: str = Depends(oauth2_scheme)):
    # JWTトークンの生成
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)

    # 一時ファイルを保存
    original_image_path = f"./files/order/{order_id}/original.jpg"
    os.makedirs(os.path.dirname(original_image_path), exist_ok=True)  # ディレクトリがなければ作成
    with open(original_image_path, "wb") as f:
        f.write(await file.read())

    # APIリクエストを送信
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {authorization}"
    }
    
    api_url = "https://api.klingai.com/v1/videos/image2video"
    # 画像ファイルのパスを指定
    data = {"image_url": f"file://{os.path.abspath(original_image_path)}"}
    response = requests.post(api_url, headers=headers, json=data)
    
    if response.status_code != 200:
        os.remove(original_image_path)  # エラー時には画像ファイルを削除
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "Unknown error"))
    
    # 生成された動画のファイル名を取得（例としてtask_idを使用）
    task_data = response.json().get("data", {})
    task_id = task_data.get("task_id")
    generated_video_path = f"./files/order/{order_id}/{task_id}.mp4"
    
    # 動画ファイルを保存する処理をここに追加
    # ここではダミー処理としてファイルを作成しています
    # 本来は、APIから返された動画のダウンロード処理を実装する必要があります
    with open(generated_video_path, "w", encoding="utf-8") as f:  # 通常のテキストモードで開く
        f.write("このファイルはダミーです")  # UTF-8で書き込む

    # 一時ファイルを削除
    os.remove(original_image_path)

    return {
        "code": 200,
        "message": "Success",
        "request_id": "dummy_request_id",  # 実際のrequest_idに置き換える
        "data": {
            "task_id": task_id,
            "task_status": "生成中",  # 実際のステータスに置き換える
            "created_at": int(time.time()),
            "updated_at": int(time.time())
        }
    }


# タスクの状態を取得するエンドポイント
@router.get("/v1/videos/image2video/{task_id}", response_model=QueryTaskResponse)
async def query_task(task_id: str, token: str = Depends(oauth2_scheme)):
    # JWTトークンの生成
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)

    # APIリクエストを送信
    headers = {
        "Authorization": f"Bearer {authorization}"
    }
    api_url = f"https://api.klingai.com/v1/videos/image2video/{task_id}"
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "Unknown error"))

    return response.json()

# タスクの一覧を取得するエンドポイント
@router.get("/v1/videos/image2video", response_model=QueryTaskResponse)
async def query_tasks(token: str = Depends(oauth2_scheme)):
    # JWTトークンの生成
    authorization = encode_jwt_token(ACCESS_KEY, SECRET_KEY)

    # APIリクエストを送信
    headers = {
        "Authorization": f"Bearer {authorization}"
    }
    api_url = "https://api.klingai.com/v1/videos/image2video"
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json().get("message", "Unknown error"))

    return response.json()
