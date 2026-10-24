from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, ForeignKey, JSON, ARRAY
from sqlalchemy.orm import relationship

from models.base import Base


class BuyItem(Base):
    __tablename__ = "buyItem"

    id = Column(Integer, primary_key=True)
    buy_id = Column(Integer, ForeignKey("buys.id", ondelete="CASCADE"), nullable=False)
    buy = relationship(
        "Buy",
        back_populates="buy_items"
    )
    item_ids = Column(ARRAY(Integer), nullable=False)
    review = relationship(
        "Review",
        back_populates="buy_item",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def __repr__(self):
        return f"BuyItem ID:{self.id}"


class BuyItemDTO(BaseModel):
    id: int | None = None
    buy_id: int | None = None
    item_ids: list[int] | None = None


class BuyItemAdmin(ModelView, model=BuyItem):
    name = "Chi tiết đơn"
    name_plural = "Chi tiết đơn hàng (Buy Items)"
    icon = "fa-solid fa-receipt"
    column_labels = {
        "id": "Mã ID",
        "buy": "Thuộc đơn hàng",
        "item_ids": "Danh sách mã sản phẩm",
        "review": "Đánh giá từ khách"
    }
    column_exclude_list = [BuyItem.buy_id]
    can_create = False
    can_delete = False
    can_edit = False
    can_export = False
