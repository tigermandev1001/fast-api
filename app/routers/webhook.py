from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Order, OrderItem
from datetime import datetime
import json
import hmac
import base64

router = APIRouter()

# Function to verify the HMAC signature from Shopify
def verify_webhook(request: Request, secret: str):
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    calculated_hmac = base64.b64encode(hmac.new(secret.encode('utf-8'), request.body, digestmod='sha256').digest()).decode('utf-8')
    return hmac.compare_digest(hmac_header, calculated_hmac)

@router.get("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    # Replace with your Shopify app secret
    SHOPIFY_SECRET = "ad5e83aaaac2115d687a1beebe954affc2c6c7fe23c074771bbb869c119d6f70"

    # Verify the request
    if not verify_webhook(request, SHOPIFY_SECRET):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    try:
        # Parse the JSON body
        payload = await request.json()

        # Example: Handle a new order creation
        if request.headers.get("X-Shopify-Topic") == "orders/create":
            order_id = payload["id"]  # Shopify Order ID
            customer_id = payload["customer"]["id"]  # Shopify Customer ID
            email = payload["customer"]["email"]  # Customer email
            created_at = datetime.strptime(payload["created_at"], "%Y-%m-%dT%H:%M:%S%z")

            # Save the order to the database
            db_order = Order(order_id=str(order_id), created_at=created_at, customer_id=str(customer_id), email=email)
            db.add(db_order)
            db.commit()

            # Handle order items
            for item in payload["line_items"]:
                order_item = OrderItem(
                    order_item_id=item["id"],
                    order_id=str(order_id),
                    product_id=item["product_id"],
                    branch_no=0,  # Default value
                    status=1  # Example status
                )
                db.add(order_item)

            db.commit()
            return {"message": "Order received and processed."}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))