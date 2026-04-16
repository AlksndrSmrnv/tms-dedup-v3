"""Russian text normalization: lemmatization + stopword removal + caching."""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Optional

import regex as re

from tms_dedup.lexicon import extract_transfer_types, yo_to_e
from tms_dedup.stopwords import STOPWORDS

_ANALYZER = None
_ANALYZER_LOCK = threading.Lock()

_TOKEN_RE = re.compile(r"[\p{L}\p{N}]+(?:[\-][\p{L}\p{N}]+)*", flags=re.UNICODE)


def _get_analyzer():
    global _ANALYZER
    if _ANALYZER is None:
        with _ANALYZER_LOCK:
            if _ANALYZER is None:
                import pymorphy3

                _ANALYZER = pymorphy3.MorphAnalyzer()
    return _ANALYZER


class Lemmatizer:
    """Thin lemmatization wrapper with a disk-backed per-token cache."""

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path
        self._cache: dict[str, str] = {}
        if cache_path and cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def lemma(self, token: str) -> str:
        cached = self._cache.get(token)
        if cached is not None:
            return cached
        morph = _get_analyzer()
        parses = morph.parse(token)
        form = parses[0].normal_form if parses else token
        self._cache[token] = form
        return form

    def save(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        # write deterministically
        items = dict(sorted(self._cache.items()))
        self.cache_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


def tokenize(text: str) -> list[str]:
    text = yo_to_e(text.lower())
    return [m.group(0) for m in _TOKEN_RE.finditer(text)]


def normalize_to_lemmas(text: str, lemmatizer: Lemmatizer) -> list[str]:
    """Return lemmatized tokens with stopwords/digits/length<2 removed."""
    lemmas: list[str] = []
    for tok in tokenize(text):
        if tok in STOPWORDS:
            continue
        if tok.isdigit():
            continue
        if len(tok) < 2:
            continue
        lemma = lemmatizer.lemma(tok)
        if lemma in STOPWORDS:
            continue
        if len(lemma) < 2:
            continue
        lemmas.append(lemma)
    return lemmas


def normalized_text_for_matching(text: str, lemmatizer: Lemmatizer) -> str:
    """Lemmatized text used for both transfer-type extraction and TF-IDF."""
    return " ".join(normalize_to_lemmas(text, lemmatizer))


def strip_transfer_type_tokens(lemmas: list[str]) -> list[str]:
    """Drop tokens that contribute to the transfer-type signal.

    We detect transfer types on the joined lemma string (so multi-word
    phrases match), then strip the component lemmas so they don't double-count
    in the similarity score.
    """
    joined = " ".join(lemmas)
    found = extract_transfer_types(joined)
    if not found:
        return lemmas
    # Build a set of component lemma words that participate in any detected type.
    from tms_dedup.lexicon import TRANSFER_TYPES

    component_words: set[str] = set()
    single_word_re = re.compile(r"[\p{L}\p{N}]+")
    for tok in found:
        for pat in TRANSFER_TYPES[tok]:
            for w in single_word_re.findall(pat):
                component_words.add(w.lower())
    # Drop lemmas that are substrings of any component stem (component patterns
    # use suffix wildcards like `карт\w*`, so compare by stem prefix).
    result: list[str] = []
    for lem in lemmas:
        if any(lem.startswith(w) or w.startswith(lem) for w in component_words if len(w) >= 3):
            continue
        result.append(lem)
    return result
