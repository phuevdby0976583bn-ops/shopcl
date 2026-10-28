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


def test_bulk_upload_request_with_media_id():
    req = BulkUploadRequest(
        media_id="0AgACAgUAAxUAAWrdTEFel8nwqyfqdm-JW5tDEZQ-AAJmE2sbA8fhVvptkVWyk7XSAQADAgADYwADPQQ",
        items=[
            "100082728282|Pass123|c_user=100082728282; xs=123;"
        ]
    )
    assert req.media_id.startswith("0AgACAg")
    assert len(req.items) == 1
    assert req.check_live is None


def test_bulk_upload_admin_view_in_bot():
    with open("bot.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "admin.add_base_view(BulkUploadAdminView)" in content


@pytest.mark.asyncio
async def test_multipart_size_limit_exceeds_1024kb():
    """Kiem tra upload tai khoan vuot qua 1024KB khong bi loi 400 Part exceeded maximum size of 1024KB."""
    import utils.multipart_fix  # noqa: F401
    from starlette.requests import Request

    boundary = "boundary_test_multipart_exceeded_check"
    line = b"10008892182|Pass123|2FA_CODE|mail@domain.com|mailpass
"
    large_payload = line * 50000  # ~2.7 MB, vuot xa nguong 1024KB (1MB)
    assert len(large_payload) > 1024 * 1024

    body = (
        f"--{boundary}
".encode() +
        b'Content-Disposition: form-data; name="private_data"

' +
        large_payload +
        b"
" +
        f"--{boundary}
".encode() +
        b'Content-Disposition: form-data; name="price"

0.25
' +
        f"--{boundary}--
".encode()
    )

    sent = False
    async def mock_receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "app": True,
        "headers": [
            (b"content-type", f"multipart/form-data; boundary={boundary}".encode()),
            (b"content-length", str(len(body)).encode()),
        ]
    }

    req = Request(scope, receive=mock_receive)
    form = await req.form()
    assert "private_data" in form
    assert len(form["private_data"]) == len(large_payload)
    assert form["price"] == "0.25"
