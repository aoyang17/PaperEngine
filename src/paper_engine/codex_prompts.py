from __future__ import annotations

from typing import Any


def oa_fallback_prompt(candidate: dict[str, Any]) -> str:
    return f"""Find open-access metadata/PDF evidence for this paper.

Candidate:
{candidate}

Allowed sources: arXiv, DOI landing page, publisher official page, OpenAlex, Crossref, Semantic Scholar, author/project page when clearly linked, official open-access PDF.
Forbidden sources: Sci-Hub, random file mirrors, unverified PDFs, LLM-memory-only BibTeX.

Return only JSON with:
status: found|not_found|needs_manual
source_urls: list[str]
metadata: object
pdf_url: string|null
confidence: high|medium|low
notes: string
"""


def parse_fallback_result(data: dict[str, Any]) -> dict[str, Any]:
    status = data.get("status")
    if status not in {"found", "not_found", "needs_manual"}:
        raise ValueError(f"invalid fallback status: {status}")
    if data.get("confidence") not in {"high", "medium", "low"}:
        raise ValueError(f"invalid confidence: {data.get('confidence')}")
    return data

