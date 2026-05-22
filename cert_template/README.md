# cert_template/

Visual assets for the Butterfly Effect completion certificate PDF.

| File | Purpose |
|---|---|
| `cert_config.json` | Overlay field positions (where the recipient name + date + QR code land on the base PDF), font references, color. Schema documented inline. |
| `cert_template.pdf` | Base certificate PDF — the unedited design Bilal provided. Names, dates, QR are overlaid at render time using coordinates from `cert_config.json`. |
| `logo.png` | Butterfly Effect program logo. Used as the centre logo on the QR code that points at each participant's profile page. |
| `fonts/EBGaramond-Italic-VariableFont_wght.ttf` | The italic display face used for the recipient name and date overlays. |

## How these get used

1. **Central rendering** — `lineage-engine/scripts/build_cv_cache.py` (the GitHub Action in `lineage-credentials`) fetches these via the URLs in `../config.json::cert_template.base_url + cert_template.*` whenever a credential is rendered for this program.
2. **Per-program QR** — `logo.png` becomes the centre logo of the per-program QR (`_cache/cv/<slug>__butterfly-effect.qr.png`).
3. **PDF overlay** — `cert_overlay.py` in lineage-engine reads `cert_config.json`, opens `cert_template.pdf` as the base, applies overlays, embeds the QR.

## Editing the cert design

Update the file(s) here, commit, push. Next time a credential renders (push to `lineage-credentials/programs/butterfly-effect/...`), the build picks up the new template.

If the recipient name overflows or the QR placement looks off, edit the `overlay_fields` coordinates in `cert_config.json` — no code change needed.

## Cross-references

- `../config.json` — exposes the stable URLs the central handler fetches these from.
- `../SCHEMA.md` — the `Config URL` field on each `[CREDENTIALING ATTESTATION EVENT]` points at the program config that resolves to these assets.
- Originally vendored at `lineage-engine/scripts/program_assets/butterfly-effect/` per `CREDENTIALING_PROGRAM_PAGES.md §15.3`. Migrated here 2026-05-22 so program-specific assets live with the program.
