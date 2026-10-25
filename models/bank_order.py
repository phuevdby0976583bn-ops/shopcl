from datetime import datetime
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from markupsafe import Markup

from models.base import Base


class BankDepositOrder(Base):
    __tablename__ = "bank_deposit_orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User")
    telegram_id = Column(BigInteger, nullable=False)
    bank_code = Column(String(32), default="BIDV")
    account_number = Column(String(64), default="8880117869")
    account_name = Column(String(128), default="")
    amount_vnd = Column(Float, default=0.0)
    amount_usd = Column(Float, default=0.0)
    memo = Column(String(128), nullable=False, index=True)
    transaction_id = Column(String(128), unique=True, nullable=True)
    status = Column(String(32), default="PENDING", index=True)
    chat_id = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"BankDepositOrder({self.bank_code}, {self.account_number}, {self.amount_vnd:,.0f}đ, {self.status})"


class BankDepositOrderAdmin(ModelView, model=BankDepositOrder):
    name = "Nạp Ngân Hàng (BIDV)"
    name_plural = "Nạp Ngân Hàng (BIDV)"
    icon = "fa-solid fa-building-columns"
    column_list = [
        "id",
        "telegram_id",
        "bank_code",
        "amount_vnd",
        "amount_usd",
        "memo",
        "transaction_id",
        "status",
        "created_at"
    ]
    column_labels = {
        "id": "ID",
        "user": "Khách hàng",
        "telegram_id": "Telegram ID",
        "bank_code": "Ngân hàng",
        "account_number": "Số TK nhận",
        "amount_vnd": "Tiền VNĐ",
        "amount_usd": "Quy đổi ($)",
        "memo": "Nội dung CK",
        "transaction_id": "Mã GD ThueApi",
        "status": "Trạng thái",
        "created_at": "Thời gian tạo"
    }
    column_formatters = {
        "amount_vnd": lambda m, a: Markup(f'<span class="badge bg-green text-green-fg font-monospace fs-6">💵 {float(m.amount_vnd or 0):,.0f} đ</span>'),
        "amount_usd": lambda m, a: Markup(f'<span class="badge bg-yellow text-yellow-fg font-monospace fs-6">+{float(m.amount_usd or 0):g} $</span>'),
        "status": lambda m, a: Markup(
            '<span class="badge bg-success">✅ THÀNH CÔNG</span>' if m.status == "COMPLETED"
            else '<span class="badge bg-warning text-dark">⏳ CHỜ THANH TOÁN</span>' if m.status == "PENDING"
            else f'<span class="badge bg-secondary">{m.status}</span>'
        )
    }
    column_sortable_list = ["id", "amount_vnd", "amount_usd", "status", "created_at"]
    column_searchable_list = ["memo", "transaction_id"]
    can_delete = True
    can_view_details = True
    can_edit = True
    can_create = False
    can_export = True

    async def delete_model(self, request, pk) -> None:
        from sqlalchemy import delete
        async with self.session_maker() as session:
            await session.execute(delete(BankDepositOrder).where(BankDepositOrder.id == int(pk)))
            await session.commit()
