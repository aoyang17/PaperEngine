# citation_guard

Verify paper/work-level identity, title, year, and venue against source evidence. DOI/arXiv are preferred, but OpenAlex Work ID, Semantic Scholar ID, DBLP key, or a verified publisher/work URL may identify papers that lack DOI/arXiv. ISSN/ISBN are venue/book identifiers only; keep them as metadata, but do not use them alone to pass citation guard. Reject unverified BibTeX. Unknown venue stays `unknown`. Final BibTeX must come from verified metadata, not LLM memory.
