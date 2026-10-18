"""Is an upload a new version of a current document? Telegram gives the same document no
stable id, so a version is recognized by what it shares with the old one: the topic words
of the file name, or the content. It is compared only with the current documents at the
same place; the author does not matter. The thresholds are measured in the README
(Likely new versions)."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath

from forest_bot.domain import Document
from forest_bot.domain.forest_map import forest_map
from forest_bot.settings import settings

# Letters and digits; underscores and punctuation separate words («внески_під_дубом»).
_WORD = re.compile(r"[^\W_]+")

# Small words that say nothing about the topic: prepositions (those of place names too) and
# question words («Коли падають жолуді», «Броди і коли бобри відкривають греблю»).
_SMALL_WORDS = frozenset(
    {"під", "біля", "над", "від", "для", "при", "наш", "наша", "чим", "коли", "куди", "чому"}
)
# 4-letter stems of boilerplate: «рукавичка» in any form, «поруч», names that scanners,
# phones and editors give files («IMG_2041», «Скан 12.10», «Документ (1)»).
_BOILERPLATE = frozenset(
    {"рука", "пору", "нашо", "img", "scan", "скан", "doc", "docu", "доку", "файл", "copy", "копі"}
)
# A version, not a topic: years and numbers, «v2», «нова редакція», «оновлено», «final».
_VERSION_MARK = re.compile(r"\d+|v\d+|нов\w*|онов\w*|редак\w*|змін\w*|final\w*|фінал\w*")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


# Place names in file names are inflected («хвойного лісу», «Під дубом»), so a word is a
# place word if it starts with the stem of a word in a place name.
_PLACE_STEMS = tuple(
    sorted(
        {
            word[:4]
            for place in forest_map.places.values()
            for word in _words(place.name)
            if len(word) >= 3 and word not in _SMALL_WORDS
        }
    )
)


@dataclass(frozen=True, slots=True)
class Match:
    document: Document
    name_score: float
    content_score: float


def find_versions(draft: Document, current: Sequence[Document]) -> list[Match]:
    """The current documents (at the draft's place) the draft may be a new version of,
    most similar first."""
    name, content = topic_words(draft.source_filename), content_grams(draft.full_text)
    matches = [
        Match(
            document,
            containment(name, topic_words(document.source_filename)),
            containment(content, content_grams(document.full_text)),
        )
        for document in current
    ]
    return sorted(
        (
            m
            for m in matches
            if m.name_score >= settings.version_name_threshold
            or m.content_score >= settings.version_content_threshold
        ),
        key=lambda m: max(m.name_score, m.content_score),
        reverse=True,
    )


def topic_words(filename: str) -> set[str]:
    """What a file name says the document is about, as 4-letter stems: «Членські внески
    рукавички Під дубом (2026).pdf» → {"член", "внес"}. A crude stem, but it makes
    «внески» and «внесків», «гриби» and «грибний» equal."""
    return {
        word[:4]
        for word in _words(PurePath(filename).stem)
        if len(word) >= 3
        and word not in _SMALL_WORDS
        and word[:4] not in _BOILERPLATE
        and not _VERSION_MARK.fullmatch(word)
        and not word.startswith(_PLACE_STEMS)
    }


def content_grams(text: str) -> set[tuple[str, ...]]:
    """Every three consecutive words, each cut to 5 letters. Long enough that an unrelated
    long guide does not contain them by chance; short enough to survive OCR noise."""
    stems = [word[:5] for word in _words(text)]
    return {tuple(stems[i : i + 3]) for i in range(len(stems) - 2)}


def containment[T](a: set[T], b: set[T]) -> float:
    """The share of the smaller set found in the other: a version that grew from one
    paragraph into a guide still contains all of the old one."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))
