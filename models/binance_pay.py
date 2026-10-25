from datetime import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base


class BinancePayOrder(Base):
    __tablename__ = "binance_pay_orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User")
    telegram_id = Column(BigInteger, nullable=False)
    memo = Column(String(64), nullable=False, index=True)
    amount = Column(Float, default=0.0)
    transaction_id = Column(String(128), unique=True, nullable=True)
    status = Column(String(32), default="PENDING", index=True)
    chat_id = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"BinancePayOrder({self.memo}, {self.amount} USDT, {self.status})"


class BinancePayOrderAdmin(ModelView, model=BinancePayOrder):
    name = "Đơn Binance Pay"
    name_plural = "Đơn Binance Pay"
    icon = "fa-brands fa-bitcoin"
    column_labels = {
        "id": "ID",
        "user": "Khách hàng",
        "telegram_id": "Telegram ID",
        "memo": "Mã Memo",
        "amount": "Số USDT ($)",
        "transaction_id": "Mã GD Binance",
        "status": "Trạng thái",
        "created_at": "Thời gian tạo",
        "updated_at": "Cập nhật lúc"
    }
    column_sortable_list = [BinancePayOrder.id, BinancePayOrder.amount, BinancePayOrder.status, BinancePayOrder.created_at]
    can_delete = True
    can_view_details = True
    can_edit = True
    can_create = False
    can_export = True
