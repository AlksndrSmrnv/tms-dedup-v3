from tms_dedup import config
from tms_dedup.candidates import _block_key, _top_pairs_within_block


def _make(id_, name, tts=(), section="Feat / A"):
    return {
        "id": id_,
        "name": name,
        "section": section,
        "section_category": "feature" if not tts else "transfer-type",
        "name_lemmas": name.lower().split(),
        "name_lemma_text": name.lower(),
        "stripped_name": name.lower(),
        "transfer_type_set": list(tts),
        "feature_block_key": section.split(" / ")[-1].lower(),
    }


def test_block_key_differs_across_transfer_types():
    a = _make("A", "перевод", tts=["phone"])
    b = _make("B", "перевод", tts=["card"])
    assert _block_key(a) != _block_key(b)


def test_block_key_equal_for_same_set():
    a = _make("A", "x", tts=["phone", "sbp"])
    b = _make("B", "y", tts=["sbp", "phone"])  # order-independent
    assert _block_key(a) == _block_key(b)


def test_identical_names_score_high():
    block = [
        _make("A", "успешный перевод на своего получателя", tts=["phone"]),
        _make("B", "успешный перевод на своего получателя", tts=["phone"]),
    ]
    pairs = _top_pairs_within_block(block, lower=config.LOWER_THRESHOLD, upper=config.UPPER_THRESHOLD, top_k=5)
    assert len(pairs) == 1
    assert pairs[0]["score"] >= 0.99
    assert pairs[0]["tier"] == "high_confidence"


def test_unrelated_names_not_paired():
    block = [
        _make("A", "перевод с карты на карту внутри банка", tts=["c2c"]),
        _make("B", "смена пароля в личном кабинете", tts=["c2c"]),
    ]
    pairs = _top_pairs_within_block(block, lower=config.LOWER_THRESHOLD, upper=config.UPPER_THRESHOLD, top_k=5)
    assert pairs == []


def test_top_k_cap():
    block = [
        _make("A", "быстрый перевод успешный", tts=["phone"]),
        _make("B", "быстрый перевод успешно", tts=["phone"]),
        _make("C", "перевод быстрый успешный", tts=["phone"]),
        _make("D", "успешный быстрый перевод выполнен", tts=["phone"]),
        _make("E", "успешно быстрый перевод", tts=["phone"]),
        _make("F", "перевод быстро и успешно", tts=["phone"]),
        _make("G", "быстро перевод ок", tts=["phone"]),
    ]
    pairs = _top_pairs_within_block(block, lower=0.4, upper=0.9, top_k=2)
    # Per-row top-K: the final union can have at most n*top_k unique pairs.
    n = len(block)
    assert len(pairs) <= n * 2
    # And must be strictly less than full cartesian (n*(n-1)/2 = 21), proving the cap bit.
    assert len(pairs) < n * (n - 1) // 2
