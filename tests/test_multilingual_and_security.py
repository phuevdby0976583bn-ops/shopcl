# -*- coding: utf-8 -*-
import pytest
from enums.language import Language
from services.i18n_messages import (
    get_wallet_text,
    get_deposit_method_selection,
    get_out_of_stock_text,
    get_select_quantity_text,
    get_all_qty_label,
    get_instant_buy_confirm_text,
    get_search_prompt_caption,
    get_search_results_text,
)


def test_all_8_languages_wallet():
    for lang in Language:
        text, btns = get_wallet_text(lang, "testuser", 12345678, 10.0, 50.0, 15.0)
        assert len(text) > 20
        assert "testuser" in text
        assert "12345678" in text
        assert "bank" in btns and "binance" in btns and "onchain" in btns


def test_all_8_languages_deposit_methods():
    for lang in Language:
        text, btns = get_deposit_method_selection(lang)
        assert len(text) > 30
        assert "binance" in btns and "bank" in btns and "onchain" in btns


def test_all_8_languages_out_of_stock():
    for lang in Language:
        text = get_out_of_stock_text(lang, "Facebook", "Clone 2FA")
        assert "Facebook" in text
        assert "Clone 2FA" in text
        assert len(text) > 30


def test_all_8_languages_select_quantity():
    for lang in Language:
        text = get_select_quantity_text(lang, "Facebook", "Clone 2FA", 0.5, "USDT", "Desc text", 100)
        assert "Facebook" in text
        assert "Clone 2FA" in text
        assert "100" in text
        assert len(text) > 30


def test_all_8_languages_qty_labels():
    for lang in Language:
        label = get_all_qty_label(lang, 45)
        assert "45" in label
        assert len(label) >= 7


def test_all_8_languages_instant_buy_confirmation():
    for lang in Language:
        msg_ok, labels_ok = get_instant_buy_confirm_text(
            lang, "Category A", "Sub A", 0.5, 2, 1.0, "$", 10.0, True, 0.0
        )
        assert len(msg_ok) > 50
        assert "Category A" in msg_ok
        assert "Sub A" in msg_ok
        assert "buy" in labels_ok and "back_qty" in labels_ok and "cancel" in labels_ok

        msg_no, labels_no = get_instant_buy_confirm_text(
            lang, "Category B", "Sub B", 2.0, 10, 20.0, "$", 5.0, False, 15.0
        )
        assert len(msg_no) > 50
        assert "binance" in labels_no and "bank" in labels_no and "crypto" in labels_no


def test_all_8_languages_search():
    for lang in Language:
        prompt = get_search_prompt_caption(lang)
        assert len(prompt) > 20

        msg_found, btn_found = get_search_results_text(lang, "clone", found=True)
        assert "clone" in msg_found
        assert len(btn_found) > 3

        msg_not_found, btn_not_found = get_search_results_text(lang, "notfound", found=False)
        assert "notfound" in msg_not_found
        assert len(btn_not_found) > 3


def test_sqladmin_actions_dropdown_attribute():
    with open("templates/sqladmin/list.html", "r", encoding="utf-8") as f:
        content = f.read()
    assert 'data-custom-dropdown="actions"' in content
    assert 'data-custom-dropdown="export"' in content
    assert "overflow: visible !important;" in content
