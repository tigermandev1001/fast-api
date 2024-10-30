from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.database import init_db
from app.routers import photo, webhook, upload
import os
from dotenv import load_dotenv
import logging

# .envファイルから環境変数を読み込む
load_dotenv()

# アプリケーションの初期化
app = FastAPI()

# データベースの初期化
init_db()

# ログ設定
logging.basicConfig(level=logging.INFO)

@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logging.info(f"Request: {request.method} {request.url} - Status: {response.status_code}")
    return response

# CORS 設定（本番環境では、環境変数で指定したドメインのみ許可するのが望ましい）
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# セキュリティおよびパスワードハッシュ設定
security = HTTPBasic()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 環境変数を使用したセキュリティ設定
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ハッシュ化されたパスワード（本番環境では環境変数を使用）
hashed_password = password_context.hash(os.getenv("ADMIN_PASSWORD", "yBbEQ7sBkq"))

# 管理者認証関数
def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username == os.getenv("ADMIN_USERNAME", "admin") and password_context.verify(credentials.password, hashed_password):
        return {"username": credentials.username, "role": "admin"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無効なユーザー名またはパスワードです",
        headers={"WWW-Authenticate": "Basic"},
    )

# JWT アクセストークン生成
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 保護されたルート用のトークン認証
def get_current_user(token: str = Header(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです",
        )

# 管理者認証エンドポイント
@app.get("/admin/auth")
def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    user = authenticate_admin(credentials)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    
    return {
        "message": "グローバルフォトビデオAPIへようこそ！",
        "token": access_token
    }

# JWTトークンを使用した保護されたルートの例
@app.get("/admin/protected")
def protected_route(user: dict = Depends(get_current_user)):
    return {"message": "保護された管理者ルートへようこそ", "user": user}

# ルーターのインクルード
app.include_router(photo.router)
app.include_router(webhook.router)
app.include_router(upload.router)
