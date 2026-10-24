import pytest
from wtforms import TextAreaField
from models.item import Item, ItemAdmin
from processing.api_items import BulkUploadRequest


def test_item_admin_has_textarea():
    assert "private_data" in ItemAdmin.form_overrides
    assert ItemAdmin.form_overrides["private_data"] is TextAreaField
    assert "rows" in ItemAdmin.form_widget_args["private_data"]
    assert ItemAdmin.form_widget_args["private_data"]["rows"] >= 10


def test_bulk_upload_request_model():
    req = BulkUploadRequest(
        category_name="Facebook Clone",
        subcategory_name="Clone US 2FA",
        price=0.25,
        items=[
            "100082728282|Pass123|2FACODE",
            "100082728283|Pass456|2FACODE"
        ],
        check_live=True,
        delete_die=True
    )
    assert req.category_name == "Facebook Clone"
    assert len(req.items) == 2
    assert req.price == 0.25
    assert req.check_live is True
