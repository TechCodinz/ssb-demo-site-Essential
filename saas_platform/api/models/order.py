from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON
from api.database import Base
from datetime import datetime

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    plan = Column(String)
    email = Column(String, index=True)
    tx_hash = Column(String, unique=True, index=True)
    expected_amount = Column(Float)
    status = Column(String, default="pending")  # pending, completed, failed, underpaid
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    note = Column(String, nullable=True)
    license_key = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
