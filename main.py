from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.database import init_db
from app.routers import photo, webhook, upload

# アプリケーションの初期化
app = FastAPI()
init_db()
app.include_router(photo.router)
app.include_router(webhook.router)
app.include_router(upload.router)

# セキュリティとパスワードハッシュ
security = HTTPBasic()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT設定
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ハッシュ化されたパスワード（本番では環境変数を推奨）
hashed_password = password_context.hash("yBbEQ7sBkq")

# 管理者ユーザー認証
def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username == "admin" and password_context.verify(credentials.password, hashed_password):
        return {"username": credentials.username, "role": "admin"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無効なユーザー名またはパスワードです",
        headers={"WWW-Authenticate": "Basic"},
    )

# JWTアクセストークンの生成
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# トークン付きのメッセージを返すエンドポイント
@app.get("/admin/auth")
def read_root(credentials: HTTPBasicCredentials = Depends(security)):
    user = authenticate_admin(credentials)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    
    return {
        "message": "写真ビデオ API へようこそ!",
        "token": access_token
    }
