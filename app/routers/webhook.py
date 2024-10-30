from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order, OrderItem, Product  # Ensure these models are SQLAlchemy models
from pydantic import BaseModel
from datetime import datetime
import json
import hmac
import base64
import logging
from app.routers.photo import download_images_and_combine
from app.routers.upload import create_video
from pathlib import Path
from fastapi import UploadFile
from io import BytesIO


router = APIRouter()

# Pydantic models for request validation
class OrderItemUpdate(BaseModel):
    product_id: int
    branch_no: int
    status: int

class ProductCreate(BaseModel):
    product_id: int
    name: str
    prompt: str
    bmg: str

# ShopifyからのHMAC署名を検証する関数
# HMAC署名を検証する関数
async def verify_webhook(request: Request, secret: str):
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if hmac_header is None:
        return False

    body = await request.body()
    calculated_hmac = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, digestmod="sha256").digest()
    ).decode("utf-8")
    return hmac.compare_digest(hmac_header, calculated_hmac)

# 注文Webhookハンドラー
@router.post("/orders/create")
async def handle_order_webhook(request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    if not await verify_webhook(request, SHOPIFY_SECRET):
        logging.error("無効なHMAC署名: リクエスト拒否")
        raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        payload = await request.json()
        # logging.info(f"受信した注文データ: {payload}")

        if request.headers.get("X-Shopify-Topic") == "orders/create":
            order_id = payload["id"]
            customer_id = payload.get("customer", {}).get("id") if payload.get("customer") else None
            email = payload.get("customer", {}).get("email") if payload.get("customer") else None
            
            created_at = datetime.strptime(payload["created_at"], "%Y-%m-%dT%H:%M:%S%z")

            if customer_id is None:
                logging.warning(f"注文 {order_id} に顧客データがありません。注文の作成をスキップします。")
                return {"message": "注文の処理には顧客情報が必要です。"}

            db_order = Order(
                order_id=str(order_id),
                created_at=created_at,
                customer_id=str(customer_id), 
                email=email
            )
            db.add(db_order)
            db.commit()
            logging.info(f"注文 {order_id} がデータベースに保存されました")

            for item in payload.get("line_items", []):
                order_item = OrderItem(
                    order_item_id=item["id"],
                    order_id=str(order_id),
                    product_id=item["product_id"],
                    branch_no=0,
                    status=1
                )
                db.add(order_item)

            db.commit()
            logging.info(f"注文アイテムがデータベースに保存されました (注文ID: {order_id})")
            return {"message": "注文が受信され、処理されました。"}

    except Exception as e:
        logging.error(f"データベースへの保存中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=400, detail="注文の処理中にエラーが発生しました。")


# 注文API

# 注文一覧
@router.get("/orders/")
async def list_orders(order_id: str = None, customer_id: str = None, email: str = None, created_date: str = None, db: Session = Depends(get_db)):
    query = db.query(Order)
    
    if order_id:
        query = query.filter(Order.order_id == order_id)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    if email:
        query = query.filter(Order.email == email)
    if created_date:
        created_at_date = datetime.strptime(created_date, "%Y-%m-%d")
        query = query.filter(Order.created_at >= created_at_date)

    orders = query.all()
    return orders

# 注文詳細取得
@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return order

# 注文アイテム詳細取得
@router.get("/orders/detail/{order_detail_id}")
async def get_order_detail(order_detail_id: int, db: Session = Depends(get_db)):
    order_item = db.query(OrderItem).filter(OrderItem.order_item_id == order_detail_id).first()
    if not order_item:
        raise HTTPException(status_code=404, detail="注文詳細が見つかりません")
    return order_item

@router.post("/orders/edit")
async def handle_order_edit_webhook(request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    # HMAC署名の検証
    if not await verify_webhook(request, SHOPIFY_SECRET):
        logging.error("無効なHMAC署名：リクエストが拒否されました")
        raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        # リクエストデータを取得
        payload = await request.json()
        logging.info(f"受信した編集注文データ: {payload}")

        order_edit_data = payload.get("order_edit", {})
        order_id = order_edit_data.get("order_id")  # 注文IDを取得

        if not order_id:
            logging.error("注文IDが見つかりません")
            raise HTTPException(status_code=400, detail="注文IDが見つかりません")

        # データベースから注文を取得
        db_order = db.query(Order).filter(Order.order_id == str(order_id)).first()
        if not db_order:
            logging.error(f"注文ID {order_id} に関連する注文が見つかりません")
            raise HTTPException(status_code=404, detail="注文が見つかりません")

        # 注文の情報を更新
        # ここで必要に応じてdb_orderのフィールドを更新
        if 'staff_note' in order_edit_data:
            db_order.staff_note = order_edit_data['staff_note']  # スタッフノートを更新

        # line_itemsやdiscountsなど、必要に応じてさらに更新を行う
        if "line_items" in order_edit_data:
            line_items = order_edit_data["line_items"]
            # 追加と削除の処理をここに追加することができます

        db.commit()  # 更新をデータベースにコミット
        logging.info(f"注文ID {order_id} の注文が正常に更新されました")
        return {"message": "注文が正常に更新されました"}

    except Exception as e:
        logging.error(f"注文の更新中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="注文の更新中にエラーが発生しました。")


# 製品API

# 製品一覧
@router.get("/products/")

async def list_products(product_id: str = None, name: str = None, db: Session = Depends(get_db)):
    query = db.query(Product)

    if product_id:
        query = query.filter(Product.product_id == product_id)
    if name:
        query = query.filter(Product.name.contains(name))  # 名前に基づくフィルタリング

    products = query.all()
    return products



# 商品を作成するエンドポイント
@router.post("/products/create")
async def create_product(product_data: dict, request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    # HMAC署名の確認
    if not await verify_webhook(request, SHOPIFY_SECRET):
        logging.error("無効なHMAC署名: リクエストが拒否されました")
        raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        name = product_data.get("title")
        prompt = product_data.get("body_html", "")
        medias = product_data.get("images")
        product_id = product_data.get("id")

        image_urls = [img['src'] for img in medias] if medias else []
        image_paths = download_images_and_combine(image_urls, product_id)

        
        # 必要なフィールドの確認
        if not name or not product_id:
            logging.error("製品データが見つかりません: titleまたはproduct_idが不足しています。")
            raise HTTPException(status_code=400, detail="必要な製品データが不足しています。")

        # 製品のインスタンス作成
        new_product = Product(
            name=name,
            prompt=prompt,
            bmg=image_paths,
            product_id=product_id
        )

       # Define the path to 'merge.jpg' instead of 'original.jpg'
        # merge_image_path = Path(image_paths[1])  # Ensure this path references 'merge.jpg'

        # Read 'merge.jpg' as binary data
        # with merge_image_path.open("rb") as image_file:
        #     image_data = BytesIO(image_file.read())
        #     upload_file = UploadFile(filename=merge_image_path.name, file=image_data)  

        #     # Trigger video generation with error handling
        #     try:
        #         await create_video(product_id=product_id, file=upload_file, prompt=prompt)  # Pass the prompt here
                
        #     except Exception as e:
        #         logging.error(f"動画生成中にエラーが発生しました: {e}")
        #         raise HTTPException(status_code=500, detail="動画生成に失敗しました")

        # データベースに保存
        db.add(new_product)
        db.commit()
        db.refresh(new_product)

        return {"message": "製品が正常に追加されました", "product_id": new_product.product_id}
    except Exception as e:
        logging.error(f"製品の追加中にエラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="製品の追加中にエラーが発生しました")



# 製品更新
@router.put("/products/{id}")
async def update_product(id: int, product: ProductCreate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="製品が見つかりません")
    
    # 製品のフィールドを更新
    db_product.product_id = product.product_id
    db_product.name = product.name
    db_product.prompt = product.prompt
    db_product.bmg = product.bmg
    db.commit()
    
    return {"message": "製品が正常に更新されました", "product": db_product}
