# Source Map

Build `papers/<bibkey>/source_map.json` before writing `deep_read.json`.

The source map is a compact evidence map, not a full translation. Record only the blocks that the deep-reading report relies on.

## Block IDs

- `S001`, `S002`, ... for body text.
- `C001`, `C002`, ... for captions.
- `F001`, `F002`, ... for figure evidence.
- `T001`, `T002`, ... for table evidence.
- `M001`, `M002`, ... for math formula evidence, including vision-transcribed equations from `math_pages`.
- `E001`, `E002`, ... for external availability evidence.

Each block must include page, section, `section_id`, `paragraph_ids`, type, `source_kind`, source text, confidence, and optional notes.

`source_kind` must be one of:

- `body_text`
- `caption`
- `figure`
- `table`
- `equation`
- `algorithm`
- `metadata`
- `external`

For `body_text` and `caption`, do not leave `paragraph_ids` empty. Use IDs from `paper_index.json`.

Use `equation` for cleaned formula blocks that the report explains. If the formula comes from `math_index.json` or `formula_vision.json`, include `image_path`, `backend`, and `latex` when available; set confidence honestly. Use `body_text` with type `theorem`, `definition`, `principle`, `method_family`, or `timeline_milestone` when the source is prose but the report depends on that specific mathematical or survey structure.

Use `source_kind: "external"` only for external pages opened during the availability search. External blocks should use `page: 0`, `section: "External availability"`, and `section_id: "external_availability"`; `paragraph_ids` may be empty. Record the external page title, URL, access date, and search query or lookup path in `notes`. Keep `source_text` to the specific availability evidence from the opened page, not a search-result snippet.

## Selection Rules

Cover at least:

- abstract or contribution block;
- introduction gap block;
- core method/theory block;
- key equation/theorem/definition block when a theory lens is active;
- method-family or timeline-milestone blocks when a survey lens is active;
- algorithm or derivation block when relevant;
- experiment setup block;
- main result block;
- limitation/future-work block;
- visual/caption block for each visual card.
- external availability block for each opened external source used to support code, data, or model availability.

Do not cite evidence that is absent from `source_map.json`. Do not use source IDs as decoration; every ID must point to a real source block.
