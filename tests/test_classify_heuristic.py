from tms_dedup.classify_heuristic import classify_one
from tms_dedup.normalize import Lemmatizer


def _classify(path: str) -> dict:
    return classify_one(path, Lemmatizer())


def test_phone_sbp_is_transfer_type():
    r = _classify("Переводы / По номеру телефона / СБП")
    assert r["category"] == "transfer-type"
    assert "phone" in r["transfer_types"]
    assert "sbp" in r["transfer_types"]


def test_card_is_transfer_type():
    r = _classify("Переводы / На карту / Внутрибанковский")
    assert r["category"] == "transfer-type"
    assert "card" in r["transfer_types"]
    assert "internal" in r["transfer_types"]


def test_limits_is_feature():
    r = _classify("Общее / Лимиты и комиссии")
    assert r["category"] == "feature"
    assert not r["transfer_types"]


def test_mixed_transfer_and_feature():
    r = _classify("Переводы / СБП / Лимиты")
    assert r["category"] == "mixed"
    assert "sbp" in r["transfer_types"]


def test_unknown_ambiguous():
    r = _classify("Общее / Разное")
    assert r["category"] == "unknown"
    assert r["confidence"] == 0.0
