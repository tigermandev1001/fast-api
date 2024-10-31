from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order, OrderItem, Product
from pydantic import BaseModel
from datetime import datetime
import hmac
import base64
import logging
import json
import re
from app.routers.photo import combine_images_endpoint
from app.auth import get_current_user

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

async def verify_webhook(request: Request, secret: str) -> bool:
    """Verify Shopify HMAC signature."""
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if hmac_header is None:
        return False

    body = await request.body()
    calculated_hmac = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, digestmod="sha256").digest()
    ).decode("utf-8")
    return hmac.compare_digest(hmac_header, calculated_hmac)

@router.post("/orders")
async def handle_order_webhook(request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    if not await verify_webhook(request, SHOPIFY_SECRET):
        logging.error("無効なHMAC署名: リクエスト拒否")
        raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        payload = await request.json()
        if request.headers.get("X-Shopify-Topic") == "orders/create":
            await process_order(payload, db)
            return {"message": "注文が受信され、処理されました。"}
    except Exception as e:
        logging.error(f"注文処理中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=400, detail="注文の処理中にエラーが発生しました。")

async def process_order(payload: dict, db: Session):
    """Process incoming order and save it to the database."""
    order_id = payload["id"]
    customer_info = payload.get("customer", {})
    customer_id = customer_info.get("id")
    email = customer_info.get("email")
    created_at = datetime.strptime(payload["created_at"], "%Y-%m-%dT%H:%M:%S%z")

    if customer_id is None:
        logging.warning(f"注文 {order_id} に顧客データがありません。注文の作成をスキップします。")
        return

    db_order = Order(order_id=str(order_id), created_at=created_at, customer_id=str(customer_id), email=email)
    db.add(db_order)
    await process_order_items(payload.get("line_items", []), order_id, db)
    db.commit()
    logging.info(f"注文 {order_id} がデータベースに保存されました")

async def process_order_items(line_items: list, order_id: str, db: Session):
    """Process each line item of the order."""
    for item in line_items:
        product_id = item["product_id"]
        order_item = OrderItem(order_item_id=item["id"], order_id=str(order_id), product_id=product_id, branch_no=0, status=1)
        db.add(order_item)

        original_url = next((prop["value"] for prop in item.get("properties", []) if prop["name"] == "画像アップロード"), None)
        if original_url:
            image_url = await filter_image_url(original_url)
            await combine_images_endpoint(image_url, order_id, product_id)
            logging.info(f"受信した注文データ: {image_url}, 注文ID: {order_id}, 商品ID: {product_id}")

    db.commit()
    logging.info(f"注文アイテムがデータベースに保存されました (注文ID: {order_id})")

async def filter_image_url(original_url: str) -> str:
    """Extract and return the new image URL."""
    match = re.search(r'ph_image=([^&]+)', original_url)
    if match:
        image_id = match.group(1)
        return f"https://uploadly-files.com/{image_id}.jpg"
    else:
        raise ValueError("ph_imageがURLに含まれていません")

@router.get("/orders")
async def list_orders(order_id: str = None, customer_id: str = None, email: str = None, created_date: str = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """List all orders with optional filters."""
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

    return query.all()

@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Retrieve a specific order by order ID."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return order

@router.get("/orders/detail/{order_detail_id}")
async def get_order_detail(order_detail_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Retrieve order item details."""
    order_item = db.query(OrderItem).filter(OrderItem.order_item_id == order_detail_id).first()
    if not order_item:
        raise HTTPException(status_code=404, detail="注文詳細が見つかりません")
    return order_item

@router.post("/orders/edit")
async def handle_order_edit_webhook(request: Request, db: Session = Depends(get_db)):
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    if not await verify_webhook(request, SHOPIFY_SECRET):
        logging.error("無効なHMAC署名：リクエストが拒否されました")
        raise HTTPException(status_code=403, detail="無効なHMAC署名")

    try:
        payload = await request.json()
        order_edit_data = payload.get("order_edit", {})
        order_id = order_edit_data.get("order_id")

        if not order_id:
            raise HTTPException(status_code=400, detail="注文IDが見つかりません")

        db_order = db.query(Order).filter(Order.order_id == str(order_id)).first()
        if not db_order:
            raise HTTPException(status_code=404, detail="注文が見つかりません")

        if 'staff_note' in order_edit_data:
            db_order.staff_note = order_edit_data['staff_note']

        # Further updates can be handled here

        db.commit()
        logging.info(f"注文ID {order_id} の注文が正常に更新されました")
        return {"message": "注文が正常に更新されました"}
    except Exception as e:
        logging.error(f"注文の更新中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="注文の更新中にエラーが発生しました。")

@router.get("/products")
async def list_products(product_id: str = None, name: str = None, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """List all products with optional filters."""
    query = db.query(Product)

    if product_id:
        query = query.filter(Product.product_id == product_id)
    if name:
        query = query.filter(Product.name.contains(name))

    return query.all()

@router.post("/products")
async def create_product(product_data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Create a new product."""
    try:
        name = product_data.get("name")
        prompt = product_data.get("prompt")
        bgm = product_data.get("bgm")
        product_id = product_data.get("product_id")

        if not name or not product_id:
            raise HTTPException(status_code=400, detail="必要な製品データが欠けています。")

        # Validate JSON format for bgm
        
        # Check if the product already exists
        existing_product = db.query(Product).filter(Product.product_id == product_id).first()
        if existing_product:
            raise HTTPException(status_code=400, detail="この商品IDはすでに登録されています。")

        new_product = Product(name=name, prompt=prompt, bmg=bgm, product_id=product_id)
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        return {"message": "製品が正常に追加されました", "product_id": new_product.product_id}
    except Exception as e:
        logging.error(f"製品の作成中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="製品の作成中にエラーが発生しました。")
    
@router.put("/products/{product_id}")
async def update_product(product_id: str, product_data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Update an existing product."""
    try:
        existing_product = db.query(Product).filter(Product.product_id == product_id).first()
        if not existing_product:
            raise HTTPException(status_code=404, detail="商品が見つかりません。")

        # 更新したいフィールドを取得
        name = product_data.get("name", existing_product.name)
        prompt = product_data.get("prompt", existing_product.prompt)
        bgm = product_data.get("bgm", existing_product.bmg)

        # JSON形式の検証
        if bgm:
            try:
                bgm_data = json.loads(bgm)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="bgmフィールドが有効なJSON形式ではありません。")
            existing_product.bmg = json.dumps(bgm_data)

        existing_product.name = name
        existing_product.prompt = prompt

        db.commit()
        return {"message": "製品が正常に更新されました", "product_id": existing_product.product_id}
    except Exception as e:
        logging.error(f"製品の更新中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="製品の更新中にエラーが発生しました。")
    
@router.put("/products/{product_id}")
async def update_product(product_id: str, product_data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Update an existing product."""
    try:
        existing_product = db.query(Product).filter(Product.product_id == product_id).first()
        if not existing_product:
            raise HTTPException(status_code=404, detail="商品が見つかりません。")

        # 更新したいフィールドを取得
        name = product_data.get("name", existing_product.name)
        prompt = product_data.get("prompt", existing_product.prompt)
        bgm = product_data.get("bgm", existing_product.bmg)

        # JSON形式の検証
        if bgm:
            try:
                bgm_data = json.loads(bgm)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="bgmフィールドが有効なJSON形式ではありません。")
            existing_product.bmg = json.dumps(bgm_data)

        existing_product.name = name
        existing_product.prompt = prompt

        db.commit()
        return {"message": "製品が正常に更新されました", "product_id": existing_product.product_id}
    except Exception as e:
        logging.error(f"製品の更新中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="製品の更新中にエラーが発生しました。")

@router.delete("/products/{product_id}")
async def delete_product(product_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Delete a product."""
    try:
        existing_product = db.query(Product).filter(Product.product_id == product_id).first()
        if not existing_product:
            raise HTTPException(status_code=404, detail="商品が見つかりません。")

        db.delete(existing_product)
        db.commit()
        return {"message": "製品が正常に削除されました", "product_id": product_id}
    except Exception as e:
        logging.error(f"製品の削除中にエラーが発生しました: {str(e)}")
        raise HTTPException(status_code=500, detail="製品の削除中にエラーが発生しました。")
