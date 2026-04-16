from tms_dedup.normalize import (
    Lemmatizer,
    normalize_to_lemmas,
    strip_transfer_type_tokens,
    tokenize,
)


def test_tokenize_basic():
    toks = tokenize("Перевод по номеру телефона: 1000 руб.")
    assert "перевод" in toks
    assert "телефона" in toks
    assert ":" not in toks
    assert "1000" in toks  # filtered later, but tokenize returns it


def test_lemmatization_and_stopwords():
    lm = Lemmatizer()
    lemmas = normalize_to_lemmas("Переводы тестового пользователя на карту", lm)
    # "тестового" -> "тестовый" might or might not appear depending on stopword match.
    # What matters: "переводы" -> "перевод", stopwords/domain-noise dropped.
    assert "перевод" in lemmas
    assert "карта" in lemmas
    assert "пользователь" not in lemmas  # domain noise


def test_strip_transfer_type_tokens_phone():
    lm = Lemmatizer()
    lemmas = normalize_to_lemmas("Перевод по номеру телефона другу", lm)
    stripped = strip_transfer_type_tokens(lemmas)
    assert "телефон" not in " ".join(stripped)
    # Residual meaningful content should remain.
    assert stripped, "stripped name should not be empty for this input"


def test_digit_and_short_tokens_dropped():
    lm = Lemmatizer()
    lemmas = normalize_to_lemmas("Test 1 a ok 1000", lm)
    assert all(len(tok) >= 2 for tok in lemmas)
    assert not any(tok.isdigit() for tok in lemmas)
