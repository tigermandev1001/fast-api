from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.database import init_db
from app.routers import photo, webhook, upload
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Application Initialization
app = FastAPI()

# Database Initialization
init_db()

# Routers Inclusion
app.include_router(photo.router)
app.include_router(webhook.router)
app.include_router(upload.router)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security and Password Hashing
security = HTTPBasic()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Environment Variables for Security Settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Hashed Password (Use environment variables for production)
hashed_password = password_context.hash(os.getenv("ADMIN_PASSWORD", "yBbEQ7sBkq"))

# Admin Authentication Function
def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username == os.getenv("ADMIN_USERNAME", "admin") and password_context.verify(credentials.password, hashed_password):
        return {"username": credentials.username, "role": "admin"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無効なユーザー名またはパスワードです",
        headers={"WWW-Authenticate": "Basic"},
    )

# JWT Access Token Generation
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Token Message Endpoint
@app.get("/admin/auth")
def read_root(credentials: HTTPBasicCredentials = Depends(security)):
    user = authenticate_admin(credentials)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)
    
    return {
        "message": "グローバルフォトビデオAPIへようこそ！",
        "token": access_token
    }
