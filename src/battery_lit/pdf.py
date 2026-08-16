from __future__ import annotations

import shutil
from pathlib import Path

import requests


def is_pdf(path: Path) -> bool:
    return path.exists() and path.is_file() and path.read_bytes()[:5] == b"%PDF-"


def copy_pdf(src: str | Path, dst: Path) -> None:
    src_path = Path(src).expanduser()
    if not is_pdf(src_path):
        raise ValueError(f"not a valid PDF: {src_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst)


def arxiv_pdf_url(arxiv_id: str) -> str:
    clean = arxiv_id.replace("arXiv:", "").strip()
    return f"https://arxiv.org/pdf/{clean}.pdf"


def download_pdf(url: str, dst: Path, timeout: int = 60) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "battery-lit-v2/0.1"})
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    dst.write_bytes(response.content)
    if not is_pdf(dst):
        dst.unlink(missing_ok=True)
        raise ValueError(f"download did not produce a PDF ({content_type}): {url}")

