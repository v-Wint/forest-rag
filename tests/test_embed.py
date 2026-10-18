from forest_bot.application.ingest.embed import split_document


def count_words(text: str) -> int:
    return len(text.split())


def test_text_that_fits_is_not_split():
    text = "Правила толоки\n\nПрибираємо ліс щосуботи."
    assert split_document(text, "Правила толоки", count_words, max_tokens=50, overlap=0.1) == [text]


def test_long_text_is_split_into_pieces_that_fit():
    title = "Статут ОСМД"
    paragraphs = [f"Пункт {i}. " + "слово " * 15 for i in range(10)]
    text = title + "\n\n" + "\n\n".join(paragraphs)

    pieces = split_document(text, title, count_words, max_tokens=40, overlap=0.1)

    assert len(pieces) > 1
    assert all(count_words(p) <= 40 for p in pieces)
    assert all(p.startswith(title) for p in pieces)
    assert not pieces[0].startswith(f"{title}\n\n{title}")  # the first piece already has it
    for i in range(10):
        assert any(f"Пункт {i}." in p for p in pieces)


def test_paragraph_longer_than_the_model_is_split_by_sentences():
    title = "Карта"
    text = title + "\n\n" + " ".join(f"Речення {i} про ліс." for i in range(30))

    pieces = split_document(text, title, count_words, max_tokens=20, overlap=0.1)

    assert all(count_words(p) <= 20 for p in pieces)
    assert all(p.startswith(f"{title}\n\nРечення") for p in pieces)  # no title-only piece
    assert all(p.endswith(".") for p in pieces)  # cut between sentences
