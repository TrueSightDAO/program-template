# program-template — TrueSight DAO cohort-credentialing template

Fork this repo to launch a new **cohort-credentialing program** under the TrueSight DAO infrastructure. Within ~30 minutes you can have:

- A roster sheet with audit columns + Audit Trail tab
- An admin console at `https://<your-program>.truesight.me/`
- Public credential pages at `https://truesight.me/programs/<your-slug>/credentials/#<pk_hash>`
- End-to-end attestation pipeline (browser-signed → Edgar → central GAS → lineage-credentials → rendered PDF)

**Working reference implementation:** [`TrueSightDAO/butterfly-effect-club`](https://github.com/TrueSightDAO/butterfly-effect-club) (ERA Professionals × TrueSight DAO, 97 alumni). Read its `PROPOSAL.md` for the full architecture decisions.

**Canonical playbook:** [`agentic_ai_context/CREDENTIALING_COHORT_PROGRAM_ONBOARDING.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/CREDENTIALING_COHORT_PROGRAM_ONBOARDING.md)

---

## What you do (6 operator steps)

### 1. Fork this repo

```
gh repo fork TrueSightDAO/program-template --clone --remote=false --org=TrueSightDAO --fork-name=<your-program>-club
```

Rename the fork to match your program slug (e.g. `swe-apprentice-club`, `yoga-iyengar-club`). The slug should be **lowercase, hyphen-separated, ASCII, ≤32 chars** — it gets etched into printed certificate QR codes per `CREDENTIALING_PROGRAM_PAGES.md §3`.

### 2. Edit `config.json`

Replace every `TODO-your-program-slug` / `TODO Your Program` with your actual values. The `_note` and `_routing_note` fields are operator hints — keep or remove as you prefer.

### 3. Replace `cert_template/`

Drop in your program's certificate PDF, logo, and font files. Update `cert_template/cert_config.json` overlay coordinates so the recipient name + date land in the right place on your design.

If you don't have a custom design yet, the placeholder files in this template render a generic certificate that's usable for testing.

### 4. Set up your Google Sheet

Create a fresh Google Sheet with two tabs (`Cohort Roster` + `Audit Trail`) and these exact column headers in row 1:

**`Cohort Roster` tab — row 1:**

```
Name	School	Learner Type	Graduation Date	public_key	pk_hash	attestation_tx_id	qualification_tx_id	profile_url	credential_pdf_url	certificate_url	status	processed_at	github_commit_sha	notes	public_listable_override
```

**`Audit Trail` tab — row 1:**

```
processed_at	name	action	github_commit_sha	profile_url	credential_pdf_url	certificate_url	error_message	triggered_by
```

Optional polish — match what `butterfly-effect-club` does: freeze row 1, bold the header band, add alternating row banding, conditional-format the `status` column (green=processed / yellow=pending / red=failed). All cosmetic — the back-end works without them.

**Then share** the sheet with:
- **`butterfly-effect-club@get-data-io.iam.gserviceaccount.com`** (the tokenomics SA) as **Editor** — this is what allows the central handler to back-fill audit columns
- Each person who should be able to attest cohort completions, as **Editor**. Sheet editors = trust circle.

### 5. PR to truesight_me_beta

Add a manifest at `truesight_me_beta/programs/<your-slug>/manifest.json` extending the existing manifest schema with these credentialing fields:

```json
{
  "program_mode": "cohort_credentialing",
  "roster_sheet_url": "https://docs.google.com/spreadsheets/d/<your-sheet-id>/edit",
  "roster_tab": "Cohort Roster",
  "audit_trail_tab": "Audit Trail",
  "admin_panel_url": "https://<your-program>.truesight.me/",
  "program_repo": "https://github.com/TrueSightDAO/<your-program>-club",
  "tokenomics_admin_endpoint": "https://script.google.com/macros/s/AKfycbytzZtEhKEHCmxoSbhQXrg5Clc7imS24BFT134nu9yN4QvMCuQfhzEHgbuT8PRYcxgtGQ/exec"
}
```

(Reuse the existing `tokenomics_admin_endpoint` URL — it's a single central GAS that handles all programs.)

After merge, sync to `truesight_me_prod` per `MEMORY:feedback_truesight_me_cname_divergence` (preserve `CNAME` while syncing).

### 6. Configure DNS + GitHub Pages

- DNS: add CNAME record `<your-program>.truesight.me` → `truesightdao.github.io` (Route 53 in the TRUESIGHT_DAO_AUTOPILOT AWS account if truesight.me)
- GitHub Pages: in your repo's Settings → Pages, set source to `main` branch root, custom domain `<your-program>.truesight.me`. Enforce HTTPS once cert provisions

---

## End result

Once steps 1–6 are done:

1. Open `https://<your-program>.truesight.me/` → embedded `create_signature.html` flow asks for your email
2. Verify your email → admin recognizes you (your email is a sheet editor)
3. Attestation queue loads from your roster's pending rows
4. Click Attest on a row → public credential page renders at `truesight.me/programs/<your-slug>/credentials/#<pk_hash>` within ~60s

Any new sheet editor you add becomes an admin on next sign-in. No per-program GAS deployment or backend ever needed.

---

## Files in this template

| File | Purpose | What to edit |
|---|---|---|
| `config.json` | Program identity + asset paths | Slug, display name, sheet URLs |
| `index.html` | Admin console (boots from config.json) | Usually nothing — auto-rebrands from config |
| `CNAME` | GitHub Pages custom domain | Your subdomain |
| `cert_template/` | Certificate PDF + logo + fonts | Replace with your design |
| `SCHEMA.md` | Sheet column glossary + event field reference | Update sheet URL only |
| `scripts/sync_cohort.py` | Dev-side `--dry-run` tool | Usually nothing — works against any roster sheet that follows the standard layout |
| `PROPOSAL.md` | Architecture record from butterfly-effect-club | Keep as reference, or replace with your own |
| `.github/workflows/sync_cohort.yml` | Daily cron dry-run + manual workflow_dispatch | Usually nothing |

---

## Architecture references

- [`PROPOSAL.md`](PROPOSAL.md) — full v4 architecture decisions (originally from butterfly-effect-club; describes the central-tokenomics-GAS + self-describing-events model your fork inherits)
- [`SCHEMA.md`](SCHEMA.md) — sheet column convention + `[CREDENTIALING ATTESTATION EVENT]` payload spec
- [`agentic_ai_context/CREDENTIALING_COHORT_PROGRAM_ONBOARDING.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/CREDENTIALING_COHORT_PROGRAM_ONBOARDING.md) — canonical playbook
- [`agentic_ai_context/CREDENTIALING_PLATFORM.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/CREDENTIALING_PLATFORM.md) — broader credentialing data model (also covers practitioner activity-tracking mode like capoeira)
- [`agentic_ai_context/CREDENTIALING_PROGRAM_PAGES.md`](https://github.com/TrueSightDAO/agentic_ai_context/blob/main/CREDENTIALING_PROGRAM_PAGES.md) — `truesight.me/programs/<slug>/` URL/page convention
