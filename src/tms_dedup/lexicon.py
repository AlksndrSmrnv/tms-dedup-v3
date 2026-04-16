"""Canonical transfer-type tokens and feature markers for the Russian banking domain.

Patterns are applied to a lemmatized + lowercased string where `ё` has been
normalized to `е`. Short acronym tokens use `\\b` word-boundaries to avoid
matching inside other words (e.g. `sbp` must not match `sbpanel`).
"""

from __future__ import annotations

import regex as re

# Each canonical token maps to a list of regex patterns.
# Patterns are tested against an already-lemmatized, lowercased, ё->е string.
TRANSFER_TYPES: dict[str, list[str]] = {
    "phone": [
        r"\bпо\s+номер\w*\s+телефон\w*",
        r"\bномер\w*\s+телефон\w*",
        r"\bна\s+телефон\w*",
        r"\bтелефон\w*",
        r"\bphone\b",
        r"\bmobile\b",
    ],
    "sbp": [
        r"\bсбп\b",
        r"\bсистем\w*\s+быстр\w*\s+платеж\w*",
        r"\bsbp\b",
        r"\bfps\b",
    ],
    "card": [
        r"\bна\s+карт\w*",
        r"\bпо\s+номер\w*\s+карт\w*",
        r"\bномер\w*\s+карт\w*",
        r"\bкарт\w*",
        r"\bcard\b",
        r"\bpan\b",
    ],
    "c2c": [
        r"\bc2c\b",
        r"\bкарт\w*[\s\-]+карт\w*",
        r"\bс\s+карт\w*\s+на\s+карт\w*",
        r"\bcard[\s\-]+to[\s\-]+card\b",
    ],
    "account": [
        r"\bпо\s+реквизит\w*",
        r"\bреквизит\w*",
        r"\bна\s+сч[её]т\b",
        r"\bсч[её]т\w*",
        r"\bбик\b",
        r"\bbic\b",
        r"\bрасч[её]тн\w*\s+сч[её]т\w*",
        r"\bр/с\b",
        r"\bswift\b",
        r"\baccount\b",
    ],
    "wallet": [
        r"\bкошел[её]к\w*",
        r"\bэлектронн\w*\s+кошел[её]к\w*",
        r"\bwallet\b",
        r"\bqiwi\b",
        r"\byoomoney\b",
        r"\bюmoney\b",
    ],
    "self": [
        r"\bмежду\s+свои\w*",
        r"\bсвои\s+сч[её]т\w*",
        r"\bперевод\s+себе\b",
        r"\bself[\s\-]+transfer\b",
        r"\bown\s+account\w*",
    ],
    "internal": [
        r"\bвнутрибанковск\w*",
        r"\bвнутри\s+банк\w*",
        r"\bвнутренн\w*\s+перевод\w*",
        r"\bintrabank\b",
    ],
    "external": [
        r"\bв\s+друг\w*\s+банк\w*",
        r"\bмежбанковск\w*",
        r"\binterbank\b",
    ],
    "international": [
        r"\bмеждународн\w*",
        r"\bза\s+рубеж\b",
        r"\bвалютн\w*\s+перевод\w*",
        r"\binternational\b",
        r"\bcurrency\s+transfer\b",
    ],
    "qr": [
        r"\bqr\b",
        r"\bпо\s+qr\b",
        r"\bqr[\s\-]+код\w*",
    ],
    "template": [
        r"\bпо\s+шаблон\w*",
        r"\bшаблон\w*",
        r"\btemplate\b",
    ],
    "recurring": [
        r"\bавтоплат[её]ж\w*",
        r"\bрегулярн\w*\s+перевод\w*",
        r"\brecurring\b",
        r"\bstanding\s+order\b",
    ],
}

# Feature markers: presence of any of these in a section path pushes the
# classification away from pure "transfer-type" and toward "feature" or "mixed".
FEATURE_MARKERS: list[str] = [
    r"\bлимит\w*",
    r"\bкомисс\w*",
    r"\bвалидац\w*",
    r"\bнегативн\w*",
    r"\bпозитивн\w*",
    r"\bnegative\b",
    r"\bpositive\b",
    r"\bсмоук\w*",
    r"\bsmoke\b",
    r"\bрегресс\w*",
    r"\bregression\b",
    r"\bfee\b",
    r"\bистори\w*",
    r"\bуведомлен\w*",
    r"\bpush\b",
    r"\bsms\b",
    r"\b3ds\b",
    r"\botp\b",
    r"\bподтвержд\w*",
    r"\bавторизац\w*",
    r"\bотмен\w*",
    r"\bвозврат\w*",
    r"\bповтор\w*",
    r"\bчерновик\w*",
    r"\bdraft\b",
    r"\bизбранн\w*",
    r"\bfavorit\w*",
    r"\bполучател\w*",
    r"\brecipient\w*",
    r"\bпоиск\w*",
    r"\bфильтр\w*",
]

# Precompiled for speed.
_TRANSFER_TYPE_RE: dict[str, list[re.Pattern[str]]] = {
    tok: [re.compile(p, flags=re.IGNORECASE | re.UNICODE) for p in patterns]
    for tok, patterns in TRANSFER_TYPES.items()
}

_FEATURE_MARKERS_RE: list[re.Pattern[str]] = [
    re.compile(p, flags=re.IGNORECASE | re.UNICODE) for p in FEATURE_MARKERS
]


def yo_to_e(text: str) -> str:
    return text.replace("ё", "е").replace("Ё", "Е")


def extract_transfer_types(lemmatized_lower: str) -> set[str]:
    """Return the set of canonical transfer-type tokens found in the text.

    The input is expected to be already lowercased, lemmatized, and ё-normalized.
    """
    text = yo_to_e(lemmatized_lower)
    found: set[str] = set()
    for token, patterns in _TRANSFER_TYPE_RE.items():
        for p in patterns:
            if p.search(text):
                found.add(token)
                break
    return found


def count_feature_markers(lemmatized_lower: str) -> int:
    text = yo_to_e(lemmatized_lower)
    return sum(1 for p in _FEATURE_MARKERS_RE if p.search(text))


def lexicon_hash() -> str:
    """Stable hash of the lexicon contents; used to invalidate stage caches."""
    import hashlib

    h = hashlib.sha256()
    for k in sorted(TRANSFER_TYPES):
        h.update(k.encode())
        for p in TRANSFER_TYPES[k]:
            h.update(p.encode())
    for p in FEATURE_MARKERS:
        h.update(p.encode())
    return h.hexdigest()[:16]
