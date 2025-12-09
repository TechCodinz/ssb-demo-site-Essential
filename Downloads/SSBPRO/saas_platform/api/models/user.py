from sqlalchemy import Column, String, Boolean, DateTime
from api.database import Base
from datetime import datetime
import secrets

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(8))
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    plan = Column(String, default="cloud_sniper")
    verified = Column(Boolean, default=False)
    telegram_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
