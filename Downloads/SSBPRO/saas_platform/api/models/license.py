from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON
from api.database import Base
from datetime import datetime

class License(Base):
    __tablename__ = "licenses"

    key = Column(String, primary_key=True, index=True)
    plan = Column(String)
    email = Column(String, index=True)
    hwid = Column(String, default="*")
    activated = Column(Boolean, default=False)
    expires = Column(DateTime)
    issued_at = Column(DateTime, default=datetime.utcnow)
    order_id = Column(String, ForeignKey("orders.order_id"), nullable=True)
    bound_devices = Column(JSON, default=list)
    cloud_session_id = Column(String, nullable=True)
    last_validated = Column(DateTime, nullable=True)
    regenerated_from = Column(String, nullable=True)
    regenerated_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
