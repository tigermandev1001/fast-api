from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.database import init_db
from app.routers import photo, webhook, upload, media
from app.auth import create_access_token  # auth.pyからインポート
import os
from dotenv import load_dotenv
import logging
from datetime import timedelta

# .envファイルから環境変数を読み込む
load_dotenv()

# アプリケーションの初期化
app = FastAPI()
init_db()

# CORS 設定
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ログ設定
logging.basicConfig(level=logging.INFO)

# 管理者認証関数
def authenticate_admin(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    hashed_password = os.getenv("HASHED_ADMIN_PASSWORD", "yBbEQ7sBkq")
    username = os.getenv("ADMIN_USERNAME", "admin")
    if credentials.username == username and credentials.password == hashed_password:
        return {"username": credentials.username, "role": "admin"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無効なユーザー名またはパスワードです",
    )

# 管理者認証エンドポイント
@app.get("/admin/auth")
def admin_auth(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    user = authenticate_admin(credentials)
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    return {
        "message": "グローバルフォトビデオAPIへようこそ！",
        "token": access_token
    }

# ルーターのインクルード
app.include_router(photo.router)
app.include_router(webhook.router)
app.include_router(upload.router)
app.include_router(media.router)
