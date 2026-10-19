"""Download the Forest Archive, a public Google Drive folder, into a local folder.

The Docker build runs it, so the image carries the archive and pipelines.ingest seeds the
database from settings.archive_dir. Standard library only, and no settings: it runs in a
build stage before the app is installed and without a .env.

No API key: the folder's embedded view lists its files, and a public file downloads by id.
Both are Drive's web pages, not its documented API, so a change at Google can break this.

python -m pipelines.download_archive FOLDER_ID OUT_DIR
"""

import argparse
import html
import re
import urllib.request
from pathlib import Path

FOLDER_URL = "https://drive.google.com/embeddedfolderview?id={}"
FILE_URL = "https://drive.usercontent.google.com/download?id={}&export=download"

_ENTRY = re.compile(r'id="entry-([\w-]+)".*?class="flip-entry-title">([^<]+)<', re.DOTALL)


def download_archive(folder_id: str, out_dir: Path) -> list[Path]:
    files = list_folder(folder_id)
    if not files:
        raise RuntimeError(f"no files listed in Drive folder {folder_id}: not public?")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for file_id, name in files:
        path = out_dir / name
        path.write_bytes(download_file(file_id))
        print(f"downloaded {name}")
        paths.append(path)
    return paths


def list_folder(folder_id: str) -> list[tuple[str, str]]:
    """(file id, file name) of every file in the folder."""
    page = _get(FOLDER_URL.format(folder_id)).decode()
    return [(file_id, html.unescape(name)) for file_id, name in _ENTRY.findall(page)]


def download_file(file_id: str) -> bytes:
    data = _get(FILE_URL.format(file_id))
    # A file that is not public, or too big to skip the virus scan, gets a web page instead.
    if data.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        raise RuntimeError(f"Drive sent a web page instead of file {file_id}")
    return data


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a public Google Drive folder.")
    parser.add_argument("folder_id")
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    paths = download_archive(args.folder_id, args.out_dir)
    print(f"done: {len(paths)} files in {args.out_dir}")
