# Visual Card

Use visual cards to explain the figures and tables that materially help understand the paper.

## Priority

Prefer:

1. Method/system overview figure.
2. Task/data definition figure.
3. Main result figure or table.
4. Key ablation, failure case, or limitation visual.
5. Survey taxonomy or timeline figure.

## Card Contract

Each `visual_cards` item must include:

- `label`: paper label such as `Figure 1` or `Table 1`;
- `kind`: `method_overview`, `main_result`, `ablation`, `dataset`, `limitation`, or similar;
- `page`;
- `image_path` or `placeholder_reason`;
- `source_caption`;
- `placement_section`: where the visual should be embedded in the final note, such as `method_understanding`, `evaluation`, or `limitations`;
- `placed_near`: source block ID where it is most useful;
- `reading_note`: what the reader should inspect and what conclusion it supports;
- `crop_status`: `tight_crop`, `full_page_approximate`, `placeholder`, or `missing`;
- `source_refs`.

If the available image is a full page, set `crop_status` to `full_page_approximate`. Do not pretend it is a tight crop. If an important visual cannot be shown, use `placeholder_reason` and explain the limitation in `extraction_notes.visual_crop_limitations`.

Before writing a card, verify that the figure/table label, caption, page number, and `image_path` point to the same visual evidence. A sentence that mentions "Figure 2" is not enough evidence for the image page; inspect the contact sheet or page image containing the actual caption/visual. If you only have a full-page image, describe it as a page view containing the figure/table, not as a tight crop.

The note renderer shows every card in the Visual Cards overview and also embeds it near `placement_section`. Use that field to put method diagrams next to method explanation, result tables next to evaluation, and limitation/failure visuals next to limitations.
