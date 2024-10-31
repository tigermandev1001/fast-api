import os
import hmac
import hashlib
import time
import base64
from fastapi import APIRouter, UploadFile, File, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
import httpx
from pathlib import Path
from PIL import Image
import logging

app = FastAPI()
router = APIRouter()

# 定数
SECRET_KEY = "IF4ogCin288G-Tgz5F3fpsuBD_0tmBDcu32xcbwPEklzyT_-eTINA8ehP2wlhAeh1j4"
IMAGE_DIR = Path("files/order")
MODEL_DIR = Path("files/model")

# 必要なディレクトリを作成
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# トークン生成関数（有効期限付き）
def generate_token(file_name: str, expiration_seconds: int = 3600) -> str:
    expire_time = int(time.time()) + expiration_seconds
    data = f"{file_name}:{expire_time}"
    signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(f"{data}:{signature.hex()}".encode()).decode()
    return token

# トークン検証関数
def validate_token(token: str) -> bool:
    try:
        decoded_token = base64.urlsafe_b64decode(token).decode()
        data, signature = decoded_token.rsplit(":", 1)
        file_name, expire_time = data.split(":")

        if int(expire_time) < int(time.time()):
            return False

        expected_signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected_signature.hex())
    except Exception:
        return False

# 画像を結合する関数
def combine_images(original_image_path: Path, model_image_path: Path, output_path: Path):
    model_image = Image.open(model_image_path).convert("RGBA")
    original_image = Image.open(original_image_path).convert("RGBA")

    # アバターサイズを定義
    avatar_size = (100, 100)

    # ユーザー画像とモデル画像をリサイズ
    user_avatar = original_image.resize(avatar_size, Image.LANCZOS)
    model_avatar = model_image.resize(avatar_size, Image.LANCZOS)

    # 結合画像のキャンバスを作成
    combined_image = Image.new("RGBA", (avatar_size[0] * 2, avatar_size[1]), (255, 255, 255, 0))

    # 両方のアバターを貼り付け
    combined_image.paste(user_avatar, (0, 0))
    combined_image.paste(model_avatar, (avatar_size[0], 0))

    # RGB JPEGとして保存
    combined_image.convert("RGB").save(output_path, format="JPEG")
    print(f"結合画像が保存されました: {output_path}")

# メディアURL生成関数
def generate_media_url(order_id: str, media_type: str) -> str:
    file_name = f"{order_id}/{media_type}"
    token = generate_token(file_name)
    return f"https://memory.blotocol.net/files/{file_name}?token={token}"

# 画像をダウンロードして結合する関数
async def download_images_and_combine(image_url: str, order_id: str, product_id: str, image_model: UploadFile):
    order_dir = IMAGE_DIR / str(order_id)
    order_dir.mkdir(parents=True, exist_ok=True)

    # ユーザー画像をダウンロード
    original_image_path = order_dir / "original.jpg"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()  # ステータスコードを確認
            with open(original_image_path, "wb") as f:
                f.write(response.content)
        print(f"ユーザー画像がダウンロードされました: {original_image_path}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"ユーザー画像のダウンロードに失敗しました: {e}")

    # アップロードされたモデル画像を保存
    image_model_path = MODEL_DIR / f"{product_id}.jpg"

    logging.info(f"受信した注文データ: {image_url}, 注文ID: {order_id}, 商品ID: {product_id}")
    
 

    # 画像を結合
    combined_image_path = order_dir / "merge.jpg"
    combine_images(original_image_path, image_model_path, combined_image_path)
    print(f"結合画像が作成されました: {combined_image_path}")

    return {"combined_image_url": generate_media_url(order_id, "merge.jpg")}

# 画像アップロードと結合のエンドポイント
@router.post("/combine-images/")
async def combine_images_endpoint(image_url: str, order_id: str, product_id: str, image_model: UploadFile = File(...)):
    urls = await download_images_and_combine(image_url, order_id, product_id, image_model)
    return urls

# メディアURL生成エンドポイント
@app.get("/generate-url")
async def get_media_url(order_id: str, media_type: str):
    media_url = generate_media_url(order_id, media_type)
    return {"media_url": media_url}

app.include_router(router)
