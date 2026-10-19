# Forest Advice Bot

A Telegram bot for the forest's mittens («рукавички»). Animals send it documents with
advice; other animals ask questions in plain text and get an answer built from those
documents, with every statement marked by its source: the document, the place it applies
to and, for documents sent by animals, who sent it and when.

Python 3.14, PostgreSQL + pgvector, a local embedding model and the Groq API (free tier).
The bot speaks Ukrainian.

- [Quick start](#quick-start)
- [Using the bot](#using-the-bot)
- [How it works](#how-it-works): [adding a document](#adding-a-document), [answering a question](#answering-a-question)
- [Monthly cost](#monthly-cost)
- [Project structure](#project-structure)
- [Development](#development)
- [Known limitations](#known-limitations)

## Quick start

You need Docker, a bot token from [@BotFather](https://t.me/BotFather) and a
[Groq API key](https://console.groq.com/keys) (free).

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, GROQ_API_KEY and TELEGRAM_BOT_TOKEN
docker compose up
```

- **Build:** the image downloads the Forest Archive
  ([Лісовий архів](https://drive.google.com/drive/folders/1b_hEjnkQfP8ZVP-OEbnYWqoGSFwXMAP3),
  78 files) from Google Drive. Docker reuses this step, so each machine downloads it once.
- **First start:** the database schema is created, the embedding model (~1 GB) is downloaded
  into a volume, and the 78 archive documents are read and placed on the forest map. That
  is 78 LLM calls under Groq's free-tier rate limit: allow a few minutes before the bot
  answers. The log shows each document as it is placed.
- **Later starts** take seconds: the archive is already loaded.

Tokens are read from `.env` when the container starts and are never part of the image.
Documents and users live in the `pgdata` volume; `docker compose down -v` deletes them.

## Using the bot

**Adding a document.** Send a PDF, DOCX or TXT file (scans are fine).

1. On your first upload the bot asks your name: other animals see it next to your advice.
2. The bot reads the file and suggests the place it is written for: a mitten, a part of the
   forest or the whole forest. Confirm it or pick another with the buttons.
3. If a document at that place looks like an earlier version of yours, the bot asks
   whether yours replaces it. The replaced one stops being used, and its author is told.

**Asking a question.** Write it as a message, e.g. «Скільки внесок під дубом і до якого
числа?». If the question names no place, the bot asks which one with buttons. The answer
comes as a reply to your question:

```
Скільки внесок під дубом і до якого числа?

4 жолуді з дорослого звіра на місяць, до 10 числа, Кабанові в кошик біля входу [1].
Замість 4 жолудів можна віддати 2 лісові горіхи [1].

Джерела:
[1] «Членські внески рукавички Під дубом», 🧤 Під дубом — Лісовий архів
```

A document sent by an animal shows its author and date instead: `— Білка, 12.10.2026`.

## How it works

The forest map lives in [`forest_map.toml`](forest_map.toml). Advice applies at one of
three levels: the whole forest, a part of the forest, or one mitten.

| Mitten | Part(s) of the forest |
|---|---|
| Під ялиною, У соснах, Біля мурашника | Хвойний ліс |
| Під дубом, У ліщині | Листяний ліс |
| Під вербою | Листяний ліс **and** Біля річки |
| Біля бобрової греблі | Біля річки |
| На узліссі | none (only whole-forest advice and its own) |

Every document and every question is treated as **untrusted data**: anyone can upload, so
a document may contain text such as "ignore previous instructions". The safeguards are
noted at the steps where they apply.

### Adding a document

[`ingest.py`](forest_bot/application/ingest/ingest.py) tells the whole story, one function
per decision the author makes.

1. **Read** ([`extractors/`](forest_bot/application/ingest/extractors/),
   [`transform.py`](forest_bot/application/ingest/transform.py)). The format is detected
   from the file's content, not its extension. Size limits apply to the file, to unpacked
   DOCX archives (against zip bombs), to the PDF page count and to the extracted text.
   PDF pages without a text layer go through Tesseract OCR: each page is rendered at
   300 DPI and binarized at three thresholds, and the most confident reading wins. A page
   below 60% mean word confidence is rejected rather than stored as garbage. The text is
   then normalized (Unicode cleanup, PDF lines rejoined into paragraphs). The title is the
   file name: the first line of a scan is often OCR noise.
2. **Exact copy?** The hash of the normalized text is compared with the *current*
   documents. If the same text is already in use, the bot says where. If only the file
   name differs, it asks which name to keep.
3. **Draft and place.** The text is stored as a `pending` draft, which is never used in
   answers. An LLM suggests the place it is written for
   ([`classify.py`](forest_bot/application/ingest/classify.py)): the document goes into
   the prompt inside a delimited block, and the reply is constrained by a strict JSON
   schema to a place id from the map or null, so it cannot be anything else. The author
   confirms or picks another place. A document always has exactly one place.
4. **New version?** ([`versions.py`](forest_bot/application/ingest/versions.py))
   Telegram gives a re-sent document no stable id, so a new version is recognized by what
   it shares with the old one, comparing **only with the current documents at the same
   place**. Documents that look alike (the same template for different mittens) always sit
   at different places; within one place they are easy to tell apart. Two signals, either
   one is enough to ask:
   - *File name:* its topic words, with place names, version marks («2026», «v2»), small
     words and boilerplate («рукавичка», «IMG», «Скан») dropped and every word cut to a
     4-letter stem. Ask when a third of them are shared.
   - *Content:* word 3-grams (each word cut to 5 letters, tolerant of OCR noise). Ask when
     30% are shared.

   Both use containment (`|A ∩ B| / min(|A|, |B|)`), so a version that adds or drops a
   part still matches. The thresholds lean towards asking: a false alarm costs one button
   press, a missed version leaves outdated advice in answers. Measured on the 78 archive
   documents against 1,100 realistic new versions (changed numbers, renamed files, real
   re-scans, added sections, half rewritten): every version is caught except 2 that are
   half rewritten *and* renamed to junk such as «IMG_2041». Uploading 52 of the documents
   one by one on top of the other 26, in 200 random orders, never triggers a needless
   question.
   Embeddings were tried and dropped: the charters of two different mittens are 0.96
   cosine-similar.
5. **Activate** ([`embed.py`](forest_bot/application/ingest/embed.py),
   [`store.py`](forest_bot/application/ingest/store.py)). A document that fits the
   embedding model (512 tokens) is one chunk: every archive document does (161–336
   tokens). A longer one is split by paragraphs, lines, then sentences, with 10% overlap,
   and every piece starts with the title. The chunks are embedded with
   `intfloat/multilingual-e5-base`, run locally because Groq has no embeddings API. Then
   one transaction makes the draft `active`, the replaced version `superseded` and stores
   the chunks, so answers never see both versions or neither. The database re-checks
   everything at that moment: the draft must still be a draft (a double-tapped button does
   nothing twice), no current document may have the same text (a unique index), and the
   replaced version must still be current. If another animal changed the documents
   meanwhile, the bot asks to send the file again.

**The Forest Archive** goes through the same steps without an author
([`pipelines/ingest.py`](pipelines/ingest.py)): the LLM's place is final, and a document
it cannot place stays out of answers until the next start tries again. The archive is
loaded on every start of the container. A file loaded before is skipped by its name before
it is read, so only the first start does real work. A replaced archive document never
comes back.

### Answering a question

[`answer.py`](forest_bot/application/answer/answer.py) tells the story.

1. **Place** ([`classify.py`](forest_bot/application/answer/classify.py)). An LLM finds
   the place the question is about, in the animal's own words («біля сосон» is the mitten
   «У соснах»), constrained to a place id from the map or null. A question that names no
   place, a place not on the map, or several places gets the place buttons. The bot never
   guesses a mitten.
2. **Which advice applies.** For a mitten: the mitten, its part(s) and the whole forest.
   For a part: the part and the whole forest. For the whole forest: whole-forest documents
   only. Mitten advice is never used for a question about a part.
3. **Search** ([`search.py`](forest_bot/application/answer/search.py)). Separately for
   each of those places, over current documents only: the 3 closest chunks per place, so a
   relevant mitten document is never crowded out by broader ones. The place filter does
   most of the work. PostgreSQL first selects the place's documents through an ordinary
   index, then computes exact cosine distances to their chunks. There is no approximate
   vector index (HNSW) on purpose: it finds the nearest chunks of the whole forest first and
   filters by place after, so it can return fewer than asked from one place. Each search
   covers at most a few hundred chunks, which takes well under a millisecond. On 28
   realistic questions with the right place, the expected document was found every time,
   even with 1 chunk per place.
4. **Answer** ([`generate.py`](forest_bot/application/answer/generate.py)). An LLM answers
   from the documents found, which go into the prompt as delimited data, most specific
   place first. The rules in its prompt: **the most specific place wins** (mitten, then
   part, then whole forest), with broader advice only as a supplement; conflicting advice
   from two parts at the same level (as at «Під вербою») is given side by side; if the
   documents do not answer the question, it says so instead of answering from general
   knowledge. Every sentence ends with its document's mark, `[n]`.
5. **Sources** are rendered by code from the database, never by the model: title, place
   and, for documents sent by animals, the author's name and date. Marks pointing to
   documents the model was not given are dropped. An answer without marks lists every
   document it was given, so an answer never comes without sources.

The model has no tools and no side effects: it only reads text and returns text. At worst
a malicious document produces a wrong answer that names its author.

## Monthly cost

Three things cost money: the LLM calls, a server, and storage. Telegram is free.

### LLM (Groq)

The bot calls the LLM in three places. Tokens below are counted from the bot's real prompts;
an average document is **~250 tokens** (the 78 archive documents: 212–421). The model,
`openai/gpt-oss-120b`, costs **$0.15 per million input tokens** and **$0.60 per million
output tokens** ([price](https://console.groq.com/docs/model/openai/gpt-oss-120b), October
2026). Output tokens include the model's short reasoning and are estimates.

| Call | Input tokens | Output tokens | Cost |
|---|---|---|---|
| **Place of an uploaded document** | 630 (instructions + map) + 250 (the document) ≈ 900 | ~100 | $0.0002 |
| **Place of a question** | 540 (instructions + map) + 25 (the question) ≈ 570 | ~100 | $0.0001 |
| **Answer** | 315 (instructions) + 25 (the question) + 9 documents × ~265 ≈ 2,700 | ~400 | $0.0006 |

The answer gets up to 3 documents for each place whose advice applies: a question about a
mitten covers the mitten, its part and the whole forest, so up to 9 documents (12 at «Під
вербою», which lies in two parts).

- **A question** = place + answer ≈ 3,300 input + 500 output tokens ≈ **$0.0008**.
- **An upload** ≈ **$0.0002**.
- **Loading the archive** (once): 78 uploads ≈ $0.02.

So a month costs about **questions per day × 30 × $0.0008**: 100 questions a day ≈ $2.40,
1,000 a day ≈ $24. Uploads are negligible next to that.

**Groq's free tier costs nothing** and is limited by rate, not by budget. For this model a
free key gets 1,000 requests a day and 8,000 tokens a minute (as reported by the API's
`x-ratelimit-*` headers). A question is 2 requests and ~3,800 tokens, so the free tier
handles about **500 questions a day, at most 2 a minute**. When more come at once, the
client waits and retries. A bigger forest needs Groq's pay-as-you-go plan, priced as above.

### Hosting

One small VPS running the same `docker compose up`. The bot uses long polling, so it
needs no domain, public address or HTTPS. Size it for memory: the bot peaks at 1.4 GB with
the embedding model loaded, and PostgreSQL and OCR need room next to it, so take **2 vCPUs
and 4 GB of RAM**. Any provider will do; their prices for that size, as listed on their
pricing pages in October 2026 (without VAT):

| Provider | Plan | A month |
|---|---|---|
| [OVHcloud](https://www.ovhcloud.com/en/vps/) | VPS-1: 2 vCores, 4 GB | from $4.54 |
| [Contabo](https://contabo.com/en/vps/) | Cloud VPS 4: 4 vCPU, 8 GB | €4.40 with a 24-month term, €6.60 without |
| [Hostinger](https://www.hostinger.com/vps-hosting) | KVM 2: 2 vCPU, 8 GB | $8.79 at first, $14.99 on renewal |
| [Hetzner](https://www.hetzner.com/cloud/regular-performance/) | CPX22: 2 vCPU, 4 GB | €19.99 |
| [DigitalOcean](https://www.digitalocean.com/pricing/droplets) | Basic: 2 vCPU, 4 GB | $24 |
| [Akamai (Linode)](https://www.akamai.com/cloud/pricing/cpu) | Shared 4 GB: 2 vCPU | $24 |

So **about €5–25 a month**. The cheapest offers ask for a long term paid upfront; the big
cloud providers bill by the hour and add backups, snapshots and an API.

### Storage

A document takes about 9 KB in the database: its text and embedding. The uploaded files
themselves are not kept. 10,000 documents would take about 90 MB, so the VPS disk is plenty
and storage costs nothing extra.

### Total

| | A month |
|---|---|
| VPS (2 vCPU, 4 GB) | €5–25, depending on the provider |
| LLM on the free tier (up to ~500 questions a day) | $0 |
| LLM on pay-as-you-go | ~$0.0008 per question: $2.40 for 100 a day |
| Storage | $0 |

## Project structure

```
forest_bot/                 the application: everything except Telegram
  settings.py               every setting, from environment variables
  domain/                   database models, enums, the forest map (forest_map.py)
  application/
    ingest/                 a file → advice used in answers
      ingest.py             the story: upload_document → find_earlier_versions → activate;
                            seed_document for archive files
      extractors/           one reader per format (txt, docx, pdf) and ocr.py for scans
      transform.py          text cleanup, title, content hash
      classify.py           the LLM suggests the document's place
      versions.py           new-version detection (file-name words, content 3-grams)
      embed.py              chunks and their embeddings
      store.py              the documents table: drafts, current documents, replacing
    answer/                 a question → an answer with its sources
      answer.py             the story: find_place → answer_question
      classify.py           the LLM finds the question's place
      search.py             the closest chunks at each place whose advice applies
      generate.py           the LLM answer with [n] marks; cite() checks the marks
    place_classifier.py     shared by both classify.py: map in the prompt, strict schema
    users.py                animals' names
    startup.py              logging and startup checks (Tesseract, Groq key, model)
  infrastructure/           database engine, embedding model, Groq client
bot/                        the Telegram bot (aiogram)
  __main__.py               python -m bot: routers and long polling
  upload.py                 files: name → place buttons → new-version buttons → activate
  questions.py              questions: place buttons if needed → answer with sources
  keyboards.py, texts.py    the buttons, and everything the bot says
pipelines/
  ingest.py                 loads the Forest Archive into the database
  download_archive.py       downloads the archive from Google Drive (used by the build)
migrations/                 Alembic schema migrations
tests/                      pytest, fully offline
forest_map.toml             the forest map
Dockerfile, compose.yml     the shipped bot
compose.dev.yml             the database alone, for development
```

`forest_bot` knows nothing about Telegram: the bot and the pipelines are two consumers of
it. The application is async (Telegram, Groq and PostgreSQL are all network I/O); parsing
and embedding are CPU-bound and run in a worker thread so the bot keeps answering others.

## Development

You need Docker, [uv](https://docs.astral.sh/uv/) and
[Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) with Ukrainian
language data (`ukr`) on PATH.

```bash
cp .env.example .env
docker compose -f compose.dev.yml up -d   # PostgreSQL + pgvector alone, on 127.0.0.1:15432
uv sync
uv run alembic upgrade head
uv run python -m pipelines.ingest         # loads ARCHIVE_DIR (default: data/archive)
uv run python -m bot
uv run pytest                             # offline: no database, LLM, Tesseract or data files
```

`compose.dev.yml` is a separate Compose project with its own database, so development never
touches the data of `docker compose up`. Only one program may poll a bot token at a time.

To get the archive locally:
`uv run python -m pipelines.download_archive 1b_hEjnkQfP8ZVP-OEbnYWqoGSFwXMAP3 data/all`.
For testing uploads it helps to load only part of it (`data/archive`) and send the rest
through the bot.

After changing a model in `forest_bot/domain/`:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

### Settings

Everything is in [`settings.py`](forest_bot/settings.py) and can be set in `.env`. The
main ones:

| Variable | Default | |
|---|---|---|
| `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY` | | required |
| `POSTGRES_PASSWORD` | | required; also `POSTGRES_USER`, `_DB`, `_HOST`, `_PORT` |
| `LLM_MODEL` | `openai/gpt-oss-120b` | any Groq chat model |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | `intfloat/multilingual-e5-base`, `768` | a change needs a migration and re-embedding |
| `ANSWER_CHUNKS_PER_PLACE` | `3` | chunks found per place for an answer |
| `ARCHIVE_DIR` | `data/archive` (`/app/archive` in Docker) | the archive to load |
| `LOG_LEVEL` | `INFO` | |

## Known limitations

- **OCR** misreads one digit in the 19 archive scans: «до 5 числа» becomes «до 9 числа» in
  «Членські внески рукавички У ліщині» (measured with Tesseract 5.5.3; the Docker image
  has Debian's 5.5.0).
- **Free-tier rate limits:** the first start takes minutes, and at busy times answers
  wait for Groq (the client retries with backoff).
- **The archive download** uses Google Drive's public web pages, not its documented API, so
  a change at Google can break the build.
- **No deleting or withdrawing documents** for now: a document can only be replaced by a
  newer version. Withdrawing would not bring back the previous version, so animals are
  never left with outdated advice.
- **A renamed and rewritten** new version is not recognized as one; it is added next to
  the old one.
- **Changing the forest map** means editing `forest_map.toml` and restarting the bot.
- **Name registration** is kept in memory: files sent before giving a name are lost if the
  bot restarts in between.
