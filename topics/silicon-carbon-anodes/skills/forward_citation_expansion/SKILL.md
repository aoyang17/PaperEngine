---
name: forward_citation_expansion
description: Use when the user asks to find newer papers that cite a seed paper, follow "cited by" links, expand a topic forward in time, find later work building on a paper, or collect future citations without scraping Google Scholar.
---

# forward_citation_expansion

Use this skill to collect papers that cite a named seed paper. This is the forward-looking counterpart to `skills/reference_expansion/SKILL.md`.

The purpose is to discover later papers, not to download PDFs directly. OpenAlex and Semantic Scholar are used as citation graph and metadata sources; PDF acquisition is handled later by `battery_lit acquire`.

## Inputs

Read only the named seed first. Do not read full `library.bib`, full `candidates.jsonl`, full paper directories, PDFs, sibling topics, or Google Scholar pages.

Useful commands:

- `battery_lit library find --root <topic> --query TEXT --json`
- `battery_lit candidates show --root <topic> CAND-ID --json`
- `battery_lit status --root <topic> --json`

Acceptable seed identifiers:

- bibkey
- candidate ID
- exact title
- DOI
- arXiv ID
- OpenAlex work ID
- Semantic Scholar paper ID

If the user gives only a Google Scholar citation URL, do not scrape or paginate Google Scholar. Ask for the paper title, DOI, arXiv ID, or bibkey. Google Scholar can be used manually by the user, but this skill must not automate it.

## Workflow

1. Resolve the seed paper from a CLI summary or user-provided identifier. Prefer DOI, arXiv ID, OpenAlex ID, or Semantic Scholar ID over title-only matching.
2. Run the bundled helper:

```bash
python3 skills/forward_citation_expansion/scripts/collect_citing_titles.py \
  --seed-title "<title>" \
  --seed-doi "<doi-if-known>" \
  --seed-arxiv "<arxiv-if-known>" \
  --limit 50 \
  --out-json reports/forward_citation_raw_<seed>.json \
  --out-tsv reports/forward_citation_titles_<seed>.tsv \
  --admitted-json reports/forward_citation_admitted_<seed>.json \
  --titles-out reports/selected_forward_citation_titles_<seed>.txt
```

Use `--only-acquirable` only when the user asks for papers that can likely be downloaded automatically. Otherwise keep important metadata-only citing papers visible for screening.

3. Inspect the TSV, topic preferences, and any hard user constraints. The candidate list is the admission gate: reject nonmatching years, domains, venues, or explicit exclusions before admission.
4. Add admitted records with the existing fixture path so arXiv/PDF metadata is preserved:

```bash
battery_lit collect --root <topic> \
  --fixture reports/forward_citation_admitted_<seed>.json \
  --target-new <N>
```

5. Run `battery_lit tool dedup --root <topic> --fix --json`.
6. If new candidates were added, follow `skills/candidate_scoring/SKILL.md` before reporting completion. Unscored candidates have `score: 0` and are not ranked.

## PDF Expectations

Do not treat OpenAlex as a PDF source. OpenAlex is good for finding citing works, but many OpenAlex records have no direct PDF URL even when the work is open elsewhere.

The helper enriches PDF acquisition signals in this order:

1. arXiv ID from Semantic Scholar, OpenAlex DOI, URL, or title metadata.
2. Direct PDF URLs from Semantic Scholar `openAccessPdf`.
3. Direct PDF URLs from OpenAlex `primary_location`, `best_oa_location`, and every `locations[*]`.
4. OpenAlex `open_access.oa_url` only when it looks like a direct PDF.

If a paper has an arXiv ID, the helper sets `pdf_url` to `https://arxiv.org/pdf/<arxiv_id>.pdf`. If no PDF signal exists, keep `pdf_url` empty and report the paper as `metadata_only`; do not invent PDF links.

## Output to User

Report:

- seed paper used
- OpenAlex citing count and Semantic Scholar citing count
- number of merged unique citing papers
- number marked `acquirable`
- number marked `metadata_only`
- number admitted to candidates
- whether dedup and scoring completed

Mention blockers explicitly: missing seed identifier, API rate limit, no citing papers found, or no candidates passing the user's hard constraints.
