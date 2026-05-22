#!/usr/bin/env python3
"""
sync_cohort.py — Butterfly Effect cohort onboarding bootstrap.

v1 SKELETON: --dry-run only (default). --execute is not yet wired.

Reads ERA's Cohort Roster sheet, mints an ephemeral participant keypair per
pending row, derives the canonical pk-hash, decides single vs two-event path
based on graduation_date, and prints the planned action as JSON.

No data is written. No HTTP calls are made. Safe to run unlimited times.

See ../SCHEMA.md for the full column glossary and ../PROPOSAL.md §7 for the
operational contract.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import gspread
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dateutil import parser as dateutil_parser
from google.oauth2.service_account import Credentials

ERA_SHEET_ID_DEFAULT = "1pApVCRqsDw9AjPUTc3fMUfMh-8H4Ne1HYuQ_d6xItog"
COHORT_TAB_DEFAULT = "Cohort Roster"
PROGRAM_SLUG = "butterfly-effect"
PROFILE_URL_TEMPLATE = (
    "https://truesight.me/programs/butterfly-effect/credentials/#{pk_hash}"
)

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def derive_pk_hash(public_key_b64: str) -> str:
    """
    Canonical pk-hash derivation. Must match the GAS implementation at
    tokenomics/google_app_scripts/tdg_credentialing/practice_event_processing.gs::deriveSlug()
    and the browser-side derivation in capoeira/assets/js/practice-event-submit.js.

    Formula: pk- + first 12 chars of base64url(SHA-256(base64-decoded pubkey bytes))
    """
    pubkey_bytes = base64.b64decode(public_key_b64)
    digest = hashlib.sha256(pubkey_bytes).digest()
    b64url = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pk-{b64url[:12]}"


def mint_keypair() -> tuple[str, bytes]:
    """
    Generate an RSA-2048 keypair. Returns (public_key_b64_spki, private_key_pem_bytes).
    The caller MUST NOT persist private_key_pem_bytes. Per PROPOSAL.md §2.7,
    participant private keys are ephemeral.
    """
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_der = priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(pub_der).decode("ascii"), priv_pem


def open_sheet(sheet_id: str, tab_name: str):
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        sys.exit(
            "ERROR: GOOGLE_APPLICATION_CREDENTIALS env var not set.\n"
            "       export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/../google_credentials.json"
        )
    if not Path(creds_path).is_file():
        sys.exit(f"ERROR: credentials file not found: {creds_path}")
    creds = Credentials.from_service_account_file(creds_path, scopes=SHEETS_SCOPES)
    gc = gspread.authorize(creds)
    book = gc.open_by_key(sheet_id)
    return book.worksheet(tab_name)


def plan_row(row_index: int, row: dict) -> dict:
    """Compute what would happen for one row in --dry-run mode."""
    name = (row.get("Name") or "").strip()
    school = (row.get("School") or "").strip()
    learner_type = (row.get("Learner Type") or "").strip().lower()
    graduation_date = str(row.get("Graduation Date") or "").strip()
    status = str(row.get("status") or "").strip().lower()
    existing_tx_id = str(row.get("attestation_tx_id") or "").strip()

    if status == "processed" and existing_tx_id:
        return {"row": row_index, "action": "skip", "reason": "already processed"}

    if not name:
        return {"row": row_index, "action": "skip", "reason": "empty Name column"}

    is_alumni = None
    graduation_iso = None
    if graduation_date:
        try:
            grad = dateutil_parser.parse(graduation_date, dayfirst=True).date()
            graduation_iso = grad.isoformat()
            today = datetime.now(timezone.utc).date()
            is_alumni = grad <= today
        except (ValueError, TypeError, dateutil_parser.ParserError):
            pass  # unparseable; flag for review

    public_key_b64, _priv_pem = mint_keypair()
    pk_hash = derive_pk_hash(public_key_b64)
    # _priv_pem goes out of scope when this function returns — Python GC reclaims it.
    # Per PROPOSAL.md §2.7, no persistence.

    return {
        "row": row_index,
        "action": "create",
        "name": name,
        "school": school,
        "learner_type": learner_type,
        "graduation_date_raw": graduation_date,
        "graduation_date_iso": graduation_iso,
        "is_alumni": is_alumni,
        "event_path": (
            "single-attestation"
            if is_alumni
            else ("two-event" if is_alumni is False else "needs-review-unparseable-date")
        ),
        "pk_hash": pk_hash,
        "public_key_b64_preview": public_key_b64[:32] + "..." + public_key_b64[-16:],
        "profile_url": PROFILE_URL_TEMPLATE.format(pk_hash=pk_hash),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Butterfly Effect cohort sync (v1 skeleton — --dry-run only)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(default) Walk pending rows and print planned actions; no writes.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="(NOT IMPLEMENTED in v1 skeleton) Apply changes — sign + POST + back-fill.",
    )
    parser.add_argument(
        "--row",
        type=int,
        default=None,
        help="Process a single row (1-indexed, header excluded).",
    )
    parser.add_argument(
        "--rebuild-row",
        type=int,
        default=None,
        help="Force re-process even if status==processed.",
    )
    parser.add_argument(
        "--sheet-id",
        default=os.environ.get("ERA_SHEET_ID", ERA_SHEET_ID_DEFAULT),
    )
    parser.add_argument(
        "--tab",
        default=os.environ.get("ERA_SHEET_TAB", COHORT_TAB_DEFAULT),
    )
    args = parser.parse_args()

    if args.execute:
        sys.exit(
            "ERROR: --execute is not implemented in the v1 skeleton.\n"
            "       This skeleton ships Phase 2 only — sheet read + payload planning.\n"
            "       Phase 3 PR will wire Edgar submission + sheet write-back."
        )

    print(
        f"Connecting to sheet {args.sheet_id} / tab '{args.tab}' "
        f"as service account...",
        file=sys.stderr,
    )
    ws = open_sheet(args.sheet_id, args.tab)
    records = ws.get_all_records()
    print(f"  → {len(records)} data rows present", file=sys.stderr)

    if args.row is not None:
        target_indices = [args.row]
    elif args.rebuild_row is not None:
        target_indices = [args.rebuild_row]
    else:
        target_indices = list(range(1, len(records) + 1))

    plans = []
    for idx in target_indices:
        if idx < 1 or idx > len(records):
            print(
                f"WARN: row {idx} out of range (sheet has {len(records)} data rows)",
                file=sys.stderr,
            )
            continue
        plan = plan_row(idx, records[idx - 1])
        plans.append(plan)
        print(json.dumps(plan, indent=2))

    create_count = sum(1 for p in plans if p["action"] == "create")
    skip_count = sum(1 for p in plans if p["action"] == "skip")
    needs_review = sum(
        1 for p in plans if p.get("event_path") == "needs-review-unparseable-date"
    )
    print(
        f"\nSummary: {create_count} would-create, {skip_count} skipped, "
        f"{needs_review} need review (unparseable Graduation Date), "
        f"{len(plans)} total",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
