from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, SmallInteger, JSON
from sqlalchemy.orm import relationship
from app.database import Base

class Order(Base):
    __tablename__ = 'order'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False)
    customer_id = Column(String(20), nullable=False)
    email = Column(String(200), nullable=False)
    
    items = relationship("OrderItem", back_populates="order")

class Photo(Base):
    __tablename__ = 'photo'
    id = Column(Integer, primary_key=True, index=True)
    photo_url = Column(String(255))
    user_id = Column(String(20))
    status = Column(String(20)) 


class OrderItem(Base):
    __tablename__ = 'order_item'

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(String(20), nullable=False)
    order_id = Column(String(20), ForeignKey('order.order_id'), nullable=False)
    product_id = Column(String(20), nullable=False)
    branch_no = Column(Integer, default=0)
    status = Column(SmallInteger, nullable=False)

    order = relationship("Order", back_populates="items")


class Product(Base):
    __tablename__ = 'product'

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    prompt = Column(JSON)
    bmg = Column(JSON)


class Service(Base):
    __tablename__ = 'service'

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(15), nullable=False)
    name = Column(String(40), nullable=False)


class Config(Base):
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(30), nullable=False)
    value = Column(String)
