from tms_dedup.lexicon import count_feature_markers, extract_transfer_types, yo_to_e


def test_yo_normalization():
    assert yo_to_e("сч\u0451т") == "счет"
    assert yo_to_e("Ё") == "Е"


def test_phone_variants_match():
    assert "phone" in extract_transfer_types("перевод по номеру телефона другу")
    assert "phone" in extract_transfer_types("phone transfer")
    assert "phone" in extract_transfer_types("на телефон")


def test_sbp_word_boundary():
    assert "sbp" in extract_transfer_types("оплата через sbp")
    assert "sbp" not in extract_transfer_types("sbpanel диагностика")


def test_card_and_c2c():
    assert "card" in extract_transfer_types("перевод на карту другого банка")
    assert "c2c" in extract_transfer_types("c2c перевод")
    assert "c2c" in extract_transfer_types("с карты на карту")


def test_account_requisites():
    assert "account" in extract_transfer_types("перевод по реквизитам")
    assert "account" in extract_transfer_types("перевод на счет")
    assert "account" in extract_transfer_types("swift перевод")


def test_qr_short_token():
    assert "qr" in extract_transfer_types("оплата по qr")
    assert "qr" not in extract_transfer_types("qrtool integration")


def test_feature_markers():
    assert count_feature_markers("лимиты и комиссии") >= 2
    assert count_feature_markers("3ds подтверждение") >= 2
    assert count_feature_markers("быстрый перевод") == 0


def test_yo_replacement_in_extract():
    # ё-forms in the input should still match the е-normalized patterns.
    assert "account" in extract_transfer_types("перевод на счёт")
