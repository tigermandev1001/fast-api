import os
import hmac
import hashlib
import time
import base64
from fastapi import APIRouter, FastAPI, HTTPException, Query
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from pathlib import Path
from PIL import Image

app = FastAPI()

router = APIRouter()

# 50文字の秘密鍵を生成する関数（32バイト + パディング）
def generate_secret_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()  # 32バイト = 256ビット

IMAGE_DIR = Path("files/product")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

# Secret key and token functions
SECRET_KEY = "IF4ogCin288G-Tgz5F3fpsuBD_0tmBDcu32xcbwPEklzyT_-eTINA8ehP2wlhAeh1j4"

def generate_token(file_name: str, expiration_seconds: int = 3600) -> str:
    expire_time = int(time.time()) + expiration_seconds
    data = f"{file_name}:{expire_time}"
    signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(f"{data}:{signature.hex()}".encode()).decode()
    return token

def validate_token(token: str) -> bool:
    try:
        decoded_token = base64.urlsafe_b64decode(token).decode()
        data, signature = decoded_token.rsplit(":", 1)
        file_name, expire_time = data.split(":")
        
        if int(expire_time) < int(time.time()):
            return False
        
        expected_signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature.hex()):
            return False
        
        return True
    except Exception:
        return False

# 画像の位置調整と合成用の関数
def combine_images(user_image_path, model_image_path, output_path):
    # モデル画像とユーザー画像の読み込み
    model_image = Image.open(model_image_path).convert("RGBA")
    user_image = Image.open(user_image_path).convert("RGBA")
    
    # アバターサイズを定義
    avatar_size = (100, 100)

    # ユーザーアバターのリサイズ
    user_avatar = user_image.resize(avatar_size, Image.LANCZOS)
    model_avatar = model_image.resize(avatar_size, Image.LANCZOS)

    # 合成画像キャンバス作成
    combined_width = avatar_size[0] * 2
    combined_height = avatar_size[1]
    combined_image = Image.new("RGBA", (combined_width, combined_height), (255, 255, 255, 0))

    # ユーザーアバターとモデルアバターを合成
    combined_image.paste(user_avatar, (0, 0))
    combined_image.paste(model_avatar, (avatar_size[0], 0))

    # RGB変換とJPEG保存
    combined_image = combined_image.convert("RGB")
    combined_image.save(output_path, format="JPEG")
    print(f"合成画像が保存されました: {output_path}")

# メディアURL生成
def generate_media_url(product_id: str, media_type: str) -> str:
    file_name = f"{product_id}/{media_type}"
    token = generate_token(file_name)
    return f"https://memory.blotocol.net/files/{file_name}?token={token}"

# 画像ダウンロードと合成
def download_images_and_combine(image_urls: list, product_id: str):
    product_dir = IMAGE_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)

    if len(image_urls) < 3:
        print("画像が不足しています。ユーザー、モデル、商品画像が必要です。")
        return []

    # 画像のURL順にユーザー画像、モデル画像、商品画像を設定
    user_image_url = image_urls[0]
    model_image_url = image_urls[1]
    product_image_url = image_urls[2]

    try:
        # ユーザー画像のダウンロード
        user_image_path = product_dir / "origine.jpg"
        with requests.get(user_image_url, stream=True) as response:
            response.raise_for_status()
            with open(user_image_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        print(f"ユーザー画像がダウンロードされました: {user_image_path}")

        # モデル画像のダウンロード
        model_image_path = product_dir / "model_image.jpg"
        with requests.get(model_image_url, stream=True) as response:
            response.raise_for_status()
            with open(model_image_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        print(f"モデル画像がダウンロードされました: {model_image_path}")

        # ユーザー画像とモデル画像の合成
        combined_image_path = product_dir / "merge.jpg"
        combine_images(user_image_path, model_image_path, combined_image_path)

        # 商品画像のダウンロード
        product_image_path = product_dir / "product_image.jpg"
        with requests.get(product_image_url, stream=True) as response:
            response.raise_for_status()
            with open(product_image_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        print(f"商品画像がダウンロードされました: {product_image_path}")

        return [str(user_image_path), str(combined_image_path), str(product_image_path)]
    except requests.RequestException as e:
        print(f"画像のダウンロードに失敗しました: {e}")
        return []

def download_images_concurrently(image_urls: list, product_id: str, max_workers: int = 5) -> list:
    """Download images concurrently and return their local file paths."""
    image_paths = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(combine_images, url, product_id, index): url
            for index, url in enumerate(image_urls)
        }
        for future in as_completed(future_to_url):
            file_path = future.result()
            if file_path:
                image_paths.append(file_path)
    return image_paths

@app.get("/generate-url")
async def get_media_url(product_id: str, media_type: str):
    media_url = generate_media_url(product_id, media_type)
    return {"media_url": media_url}

@app.get("/files/{order_id}/{media_type:path}")
async def get_media(order_id: str, media_type: str, token: str = Query(...)):
    if not validate_token(token):
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
    
    file_path = IMAGE_DIR / f"{order_id}/{media_type}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    return {"message": f"Providing {media_type} from {file_path}"}
