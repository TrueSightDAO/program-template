# scripts/

Operational scripts for spinning up + iterating on a cohort-credentialing program.

## `create_roster_sheet.py` — bootstrap the program's Google Sheet

Run this **once** during setup to create your program's Cohort Roster sheet with the canonical column schema, formatting, and sharing baked in. No manual sheet construction needed.

```bash
pip install -r requirements.txt

# OAuth setup (one time): download client_secret.json from
# console.cloud.google.com → APIs & Services → Credentials → Create OAuth client ID
# (Desktop app type). Save it somewhere local and point an env var at it:
export GOOGLE_OAUTH_CLIENT_SECRET_JSON=$HOME/client_secret.json

python3 create_roster_sheet.py \
  --title "Your Program Cohort Roster 2026" \
  --admin admin1@example.com \
  --admin admin2@example.com
```

What it does:

- Creates a fresh Google Sheet with `Cohort Roster` + `Audit Trail` tabs
- Writes all 16 source/audit column headers (Cohort Roster) + 9 audit headers (Audit Trail) from SCHEMA.md
- Applies frozen header rows, bold dark-teal header band, alternating row banding, conditional formatting on `status` (green/yellow/red)
- Shares with the tokenomics SA as Editor (so the central handler can back-fill)
- Shares with each `--admin` email as Editor (= the trust circle for the program)
- Prints the new spreadsheet URL on stdout

Auth modes:

- **OAuth (preferred)** — uses your Google account; sheet ends up owned by you. Set `GOOGLE_OAUTH_CLIENT_SECRET_JSON`. Token cached at `~/.config/truesight/create_roster_sheet_token.json` after first run.
- **Service account** — set `GOOGLE_APPLICATION_CREDENTIALS`. Currently blocked by Google's "service accounts can't create files outside a shared drive" rule — the call returns 403 unless the SA is added as a member of a shared drive and you specify that parent. Most operators will find OAuth simpler.

**For LLM-assisted setup:** an LLM agent that has read access to this repo can read the script, install the deps in the operator's environment, and invoke it after the operator provides their OAuth client secret. No manual sheet creation required.

## `sync_cohort.py`

**v1 status:** SKELETON. Implements `--dry-run` (default). `--execute` exits with an error; Phase 3 PR will wire Edgar submission + sheet write-back.

### What the dry-run does

For each pending row in the ERA Cohort Roster sheet:

1. Connects to the Google Sheet via the service account (`butterfly-effect-club@get-data-io.iam.gserviceaccount.com`)
2. Skips rows where `status == processed` AND `attestation_tx_id` is present
3. For every row that needs work:
   - Mints an RSA-2048 keypair in-process (private half is garbage-collected immediately)
   - Derives the canonical `pk-<hash>` slug using `pk-` + first 12 chars of `base64url(SHA-256(decoded pubkey bytes))`
   - Decides the event path: `single-attestation` (alumni, grad date ≤ today) or `two-event` (live cohort, grad date > today)
   - Prints the planned action as JSON
4. Prints a summary count

No data is written. No HTTP calls are made. Safe to run unlimited times.

### Local prerequisites

1. Python 3.10+
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Service-account credentials at `../google_credentials.json` (gitignored). Verify the service account has:
   - **Editor** on ERA Cohort Roster sheet (`1pApVCRqsDw9...`) — granted 2026-05-22 ✓
   - **Viewer** on Main Ledger (`1GE7PUq-...`) — needed to look up Bilal's lineage pubkey + admin pubkeys. **TODO: grant this.**
4. Set the env var:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/../google_credentials.json
   ```

### Usage

```bash
# Dry-run all rows (default)
python3 sync_cohort.py --dry-run

# Dry-run a single row (1-indexed, header excluded)
python3 sync_cohort.py --dry-run --row 5

# Custom sheet ID / tab name (uses ERA defaults if omitted)
python3 sync_cohort.py --dry-run --sheet-id <ID> --tab "Cohort Roster"
```

### What's not implemented yet

`--execute` will eventually:

1. Look up Bilal's registered pubkey from Main Ledger Contributors Digital Signatures
2. Sign each event payload with ERA's lineage private key (loaded from `$ERA_LINEAGE_KEY_PATH`, never committed)
3. POST to Edgar's `/dao/submit_contribution`
4. Capture the `Request Transaction ID` from the response
5. Back-fill audit columns on the Cohort Roster row
6. Append an entry to the `Audit Trail` tab

The skeleton stops short of that to keep the v1 scaffold side-effect-free.

## CI

The same script runs via `.github/workflows/sync_cohort.yml`:

- **Daily cron** (03:00 UTC) — currently dry-run only
- **`workflow_dispatch`** — manual button on Actions page, supports `--row N`

Service-account credentials in CI come from the `GOOGLE_CREDENTIALS_JSON_B64` repo secret (base64-encoded service-account JSON, decoded into `/tmp/creds.json` at job start).
