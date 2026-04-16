"""Russian stopwords + domain-specific noise words for the TMS test model.

Deliberately static (no nltk download) — keeps runs hermetic.
"""

from __future__ import annotations

# Base Russian stopwords (subset of NLTK's ru list, with duplicates removed).
RUSSIAN_BASE: set[str] = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "её", "мне", "было", "вот", "от", "меня", "ещё",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь",
    "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя",
    "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже",
    "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому",
    "этого", "какой", "совсем", "ним", "здесь", "этом", "один", "почти", "мой",
    "тем", "чтобы", "нее", "сейчас", "были", "куда", "зачем", "всех", "никогда",
    "можно", "при", "наконец", "два", "об", "другой", "хоть", "после", "над",
    "больше", "тот", "через", "эти", "нас", "про", "всего", "них", "какая",
    "много", "разве", "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой",
    "перед", "иногда", "лучше", "чуть", "том", "нельзя", "такой", "им", "более",
    "всегда", "конечно", "всю", "между",
}

# English fillers that sometimes appear in mixed test names.
ENGLISH_BASE: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "to",
    "of", "in", "on", "at", "for", "by", "with", "from", "as", "and", "or",
    "if", "when", "then", "this", "that", "these", "those", "it", "its",
}

# Domain-specific noise in test titles.
DOMAIN_NOISE: set[str] = {
    "тест", "тесты", "проверка", "проверки", "проверить", "проверяется",
    "кейс", "кейсы", "case", "tc", "tests",
    "сценарий", "сценарии", "scenario",
    "пользователь", "пользователи", "клиент", "клиенты", "user",
    "приложение", "приложении", "app",
}

STOPWORDS: frozenset[str] = frozenset(RUSSIAN_BASE | ENGLISH_BASE | DOMAIN_NOISE)


def stopwords_hash() -> str:
    import hashlib

    h = hashlib.sha256()
    for w in sorted(STOPWORDS):
        h.update(w.encode())
    return h.hexdigest()[:16]
