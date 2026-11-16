# Design

Derived from the built UI in `web/src/styles.css`. Operate-mode product surface: a reviewer works through three screens and needs to trust each number.

## Scene
A claims analyst at a desk in daylight, comparing a policy document with what the tool extracted, then checking a payout line by line. Hence a light ground, quiet chrome and dense, legible tables. A hiring engineer sees the same screens.

## Colour (restrained: tinted neutrals plus one accent)
- Ground `#f1f4f4`, surface `#ffffff`, second neutral `#e8eded`, lines `#d3dcdf`.
- Ink `#111d25`, secondary `#3f4e58`, muted `#596873` (all at least 4.5:1 on the ground).
- Accent petrol `#0b5f66` (dark `#064349`, tint `#d9eaec`): primary buttons, current step, applied rule nodes, the insurer-pays bar. Nothing else is accent-coloured.
- Semantic: review amber (`#fcf0d0` / `#6d4300`) for values needing a human; red (`#962a1b`) for reductions and rejection; green only for "quote found".

## Type
- Source Serif 4 for headings, the quote block and the payout figure; Public Sans for UI, body and data. Both self-hosted through Fontsource.
- All money uses tabular lining figures. Indian digit grouping via `Intl.NumberFormat("en-IN")` on decimal strings.
- Fixed rem scale, no fluid type: 0.8125 / 0.875 / 0.9375 / 1 / 1.125 / 1.375 / 2.25 / 3.5.

## Components
- Ledger rows (coverage): one row per field, whole row is a button that expands the source inline. Flagged rows carry a tinted ground and a "Review" chip with an icon; colour is never the only signal.
- Audit trail (payout): vertical rail, numbered nodes, rule text, and right-aligned before to after amounts with the delta. Steps with no effect are muted and can be hidden.
- Forms: 44px controls, visible labels, live Indian-grouped preview under each money field, errors under the field.
- Buttons: one primary (petrol), one secondary (outlined), one quiet. Same shape and height everywhere.
- States present: loading skeletons, empty, error alert, disabled, focus ring (2px petrol), hover, reduced motion.

## Not used
No emoji, no gradient blobs, no icon-card grids, no modals, no decorative motion.
