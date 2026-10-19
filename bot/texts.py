"""Everything the bot says, in one place."""

from forest_bot.application.answer import Answer
from forest_bot.application.ingest import FailureReason
from forest_bot.domain import CurrentDocument, ScopeLevel
from forest_bot.domain.forest_map import Place

START = (
    "Привіт! Я лісовий порадник.\n\n"
    "📄 Надішли документ (PDF, DOCX або TXT), і я додам його до спільного архіву порад.\n"
    "❓ Напиши питання, і я відповім за документами з архіву."
)

ASK_NAME = (
    "Перш ніж додати документ, скажи, як тебе звати? "
    "Це ім'я побачать інші звірі поруч із твоїми порадами."
)
BAD_NAME = "Ім'я має бути від 1 до {max} символів. Спробуй ще раз."
REGISTERED = "Приємно познайомитись, {name}!"
QUEUED = "Додам і цей документ, щойно познайомимося."

READING = "Читаю «{filename}»…"
ALREADY_CURRENT = "Цей документ уже є в порадах: «{title}» для «{place}»."
ASK_RENAME = (
    "Цей документ уже є в порадах: «{title}» для «{place}», але у файлі з іншою назвою.\n\n"
    "Яку назву файлу залишити?"
)
RENAMED = "Готово, тепер файл «{title}» називається «{filename}»."
NAME_KEPT = "Добре, назву файлу не змінюю."
RENAME_STALE = (
    "Цей документ щойно замінили новішим варіантом. Надішли файл ще раз, і я перевірю знову."
)
ASK_PLACE = (
    "«{title}»\n\nДля якого місця ця порада? Думаю, для «{place}». Підтверди або обери інше."
)
ASK_PLACE_UNCLEAR = "«{title}»\n\nНе можу зрозуміти, для якого місця ця порада. Обери, будь ласка."

ASK_REPLACE_ONE = (
    "Для «{place}» уже є схожий документ:\n{documents}\n\n"
    "Цей документ — його новий варіант? Тоді старий я більше не використовуватиму."
)
ASK_REPLACE_MANY = (
    "Для «{place}» уже є схожі документи:\n{documents}\n\n"
    "Цей документ — новий варіант одного з них? Тоді старий я більше не використовуватиму."
)
REPLACE_ONE_BUTTON = "🔁 Так, замінити"
REPLACE_NTH_BUTTON = "🔁 Замінює {n}"
SEPARATE_BUTTON = "➕ Ні, це окремий документ"
ARCHIVE = "Лісовий архів"

ADDING = "Додаю…"
PLACED = "Готово! «{title}» додано до порад для «{place}»."
REPLACED = "Готово! «{title}» тепер замість «{old}» у порадах для «{place}»."
YOURS_REPLACED = "Твій документ «{old}» для «{place}» замінено новішим варіантом: «{title}»."
ALREADY_ADDED = "Такий самий документ щойно додав інший звір, тож він уже є в порадах."
DOCUMENTS_CHANGED = (
    "Документи для «{place}» щойно змінилися. Надішли файл ще раз, і я перевірю знову."
)
NOT_YOURS = "Це вирішує лише той, хто надіслав документ."
UNKNOWN_PLACE = "Такого місця вже немає на мапі лісу. Надішли документ ще раз."

SEND_AS_FILE = "Фото я не читаю. Надішли документ файлом: PDF, DOCX або TXT."

THINKING = "Шукаю відповідь…"
ASK_QUESTION_PLACE = (
    "Для якого місця це питання? Обери рукавичку, частину лісу або весь ліс. "
    "Наступного разу можеш назвати місце в самому питанні."
)
QUESTION_TOO_LONG = "Питання задовге. Спробуй коротше, до {max} символів."
QUESTION_LOST = "Не бачу самого питання. Напиши його ще раз."
NO_ANSWER = "У порадах для «{place}» немає відповіді на це питання."
SOURCES = "Джерела:"

ERROR = "Щось пішло не так. Спробуй ще раз трохи згодом."

EXTRACTION_ERRORS = {
    FailureReason.UNSUPPORTED: "Я читаю лише PDF, DOCX і TXT. Збережи документ в одному з них.",
    FailureReason.TOO_LARGE: "Документ завеликий для мене. Надішли коротший.",
    FailureReason.CORRUPT: "Файл пошкоджений або захищений паролем, я не можу його відкрити.",
    FailureReason.EMPTY: "У файлі немає тексту.",
    FailureReason.UNREADABLE_SCAN: (
        "Не можу надійно прочитати цей скан. Надішли чіткіший скан або текстовий файл."
    ),
}

# Telegram allows 4096 characters a message and counts an emoji as two: leave room.
MAX_MESSAGE_CHARS = 4000

_LEVEL_ICONS = {ScopeLevel.FOREST: "🌳", ScopeLevel.PART: "🗺", ScopeLevel.MITTEN: "🧤"}


def place_label(place: Place) -> str:
    return f"{_LEVEL_ICONS[place.level]} {place.name}"


def ask_replace(place: Place, earlier: list[CurrentDocument]) -> str:
    """Numbered when there are several, matching the «Замінює N» buttons."""
    if len(earlier) == 1:
        documents = f"• {_describe(earlier[0])}"
        return ASK_REPLACE_ONE.format(place=place.name, documents=documents)
    documents = "\n".join(f"{n}. {_describe(d)}" for n, d in enumerate(earlier, start=1))
    return ASK_REPLACE_MANY.format(place=place.name, documents=documents)


def answer_messages(answer: Answer) -> list[str]:
    """The answer, then its sources numbered as the [n] marks in it, in as many messages
    as Telegram needs."""
    if answer.text is None:
        return [NO_ANSWER.format(place=answer.place.name)]
    sources = "\n".join(f"[{n}] {_source(d)}" for n, d in enumerate(answer.sources, start=1))
    return split_message(f"{answer.text}\n\n{SOURCES}\n{sources}")


def split_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Pieces of at most `limit` characters, cut at the last line break that fits; inside a
    line only when the line alone is longer."""
    pieces = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = limit
        pieces.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return [*pieces, text]


def _describe(document: CurrentDocument) -> str:
    return f"«{document.title}» — {_sent_by(document)}"


def _source(document: CurrentDocument) -> str:
    return f"«{document.title}», {place_label(document.place)} — {_sent_by(document)}"


def _sent_by(document: CurrentDocument) -> str:
    """Who sent it and when; the Forest Archive's documents have neither."""
    if document.author_name is None:
        return ARCHIVE
    return f"{document.author_name}, {document.uploaded_at:%d.%m.%Y}"
