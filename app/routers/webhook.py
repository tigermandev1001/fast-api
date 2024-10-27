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
@router.post("/webhook/orders")
async def handle_order_webhook(request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    # HMAC署名の検証
    # if not await verify_webhook(request, SHOPIFY_SECRET):
    #     logging.error("無効なHMAC署名: リクエスト拒否")
    #     raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        # リクエストデータを取得
        payload = await request.json()
        logging.info(f"受信した注文データ: {payload}")

        if request.headers.get("X-Shopify-Topic") == "orders/create":
            # 注文の詳細を抽出
            order_id = payload["id"]
            customer_id = payload["customer"]["id"]
            email = payload["customer"]["email"]
            created_at = datetime.strptime(payload["created_at"], "%Y-%m-%dT%H:%M:%S%z")

            # 注文をデータベースに追加
            db_order = Order(order_id=str(order_id), created_at=created_at, customer_id=str(customer_id), email=email)
            db.add(db_order)
            db.commit()
            logging.info(f"注文 {order_id} がデータベースに保存されました")

            # 注文アイテムをデータベースに追加
            for item in payload["line_items"]:
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

# 注文アイテム詳細更新
@router.put("/orders/detail/{id}")
async def update_order_detail(id: int, order_item: OrderItemUpdate, db: Session = Depends(get_db)):
    db_order_item = db.query(OrderItem).filter(OrderItem.order_item_id == id).first()
    if not db_order_item:
        raise HTTPException(status_code=404, detail="注文詳細が見つかりません")
    
    # 注文アイテムのフィールドを更新
    db_order_item.product_id = order_item.product_id
    db_order_item.branch_no = order_item.branch_no
    db_order_item.status = order_item.status
    db.commit()
    
    return {"message": "注文詳細が正常に更新されました", "order_item": db_order_item}

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

# 製品追加
@router.post("/products/")
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(**product.dict())  # Create an instance of the SQLAlchemy model
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return {"message": "製品が正常に追加されました", "product": new_product}

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
