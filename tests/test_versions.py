from forest_bot.application.ingest.versions import (
    containment,
    content_grams,
    find_versions,
    topic_words,
)
from forest_bot.domain import Document

DUES = (
    "Членські внески рукавички Під дубом\n\n"
    "Кожен дорослий звір здає 4 жолуді на місяць до 10 числа. Внески приймає скарбник Кабан "
    "у кошик біля входу. Замість 4 жолудів можна віддати 2 лісові горіхи. Хто не встиг "
    "до 10 числа, здає до кінця місяця вдвічі більше."
)
ROTA = (
    "Чергування в рукавичці Під дубом\n\n"
    "Щоранку черговий підмітає вхід і приносить воду зі струмка. Черга йде за віком, від "
    "найстаршого до наймолодшого. Хто захворів, міняється з сусідом і каже про це голові."
)


def _document(filename: str, text: str) -> Document:
    return Document(source_filename=filename, full_text=text)


def test_topic_words_drop_places_version_marks_and_boilerplate():
    assert topic_words("Членські внески рукавички Під дубом (2026).pdf") == {"член", "внес"}
    assert topic_words("внески_під_дубом.docx") == {"внес"}
    assert topic_words("Небезпеки поруч із рукавичкою У соснах.txt") == {"небе"}
    assert topic_words("Грибний путівник хвойного лісу.pdf") == {"гриб", "путі"}
    assert topic_words("Статут ОСМД нова редакція v2.docx") == {"стат", "осмд"}
    # «коли» says nothing about the topic: these two would otherwise share it.
    assert topic_words("Коли падають жолуді й горіхи.pdf") == {"пада", "жолу", "горі"}
    assert topic_words("Броди і коли бобри відкривають греблю.pdf") == {"брод", "відк"}


def test_names_phones_and_scanners_give_say_nothing():
    for name in ("IMG_2041.pdf", "Скан 12.10.2026.pdf", "Документ (1).docx", "scan_0012.pdf"):
        assert topic_words(name) == set(), name


def test_containment_is_relative_to_the_smaller_set():
    assert containment({"внес"}, {"член", "внес"}) == 1.0
    assert containment({"a", "b"}, {"b", "c"}) == 0.5
    assert containment(set(), {"a"}) == 0.0


def test_a_short_text_grown_into_a_guide_is_fully_contained():
    paragraph = DUES.split("\n\n")[1]
    guide = "\n\n".join([ROTA, paragraph, ROTA.upper(), "Ще багато нових порад про ліс."])
    assert containment(content_grams(paragraph), content_grams(guide)) == 1.0


def test_new_dues_are_found_by_name_or_by_content():
    current = [
        _document("Членські внески рукавички Під дубом.pdf", DUES),
        _document("Чергування в рукавичці Під дубом.pdf", ROTA),
    ]
    new_numbers = DUES.replace("4 жолуді", "5 жолудів").replace("10 числа", "12 числа")

    by_name = find_versions(_document("Внески на зиму.docx", "Інший текст зовсім."), current)
    by_content = find_versions(_document("IMG_2041.pdf", new_numbers), current)

    assert [m.document for m in by_name] == [current[0]]
    assert [m.document for m in by_content] == [current[0]]
    assert by_content[0].content_score > 0.5


def test_a_new_topic_at_the_same_place_is_not_a_version():
    current = [
        _document("Членські внески рукавички Під дубом.pdf", DUES),
        _document("Чергування в рукавичці Під дубом.pdf", ROTA),
    ]
    draft = _document(
        "Стежки до сусідів від рукавички Під дубом.txt",
        "Стежка до ліщини йде повз старий пень, а до верби — вздовж струмка.",
    )
    assert find_versions(draft, current) == []
