#!/usr/bin/env python3
"""
create_roster_sheet.py — bootstrap a new Cohort Roster Google Sheet from SCHEMA.md.

Creates a fresh Google Sheet with:
- `Cohort Roster` tab — 16 columns matching SCHEMA.md §5 (source + audit)
- `Audit Trail` tab — 9 columns matching SCHEMA.md §5.3
- Frozen header rows, bold header band, alternating row banding,
  conditional formatting on the `status` column (green/yellow/red)
- Shared with the tokenomics SA as Editor (so the central handler can write back)
- Shared with each admin email you pass in as Editor (= the trust circle)

Auth: OAuth as the operator (preferred — sheet is owned by you, not a SA).
A consent screen opens on first run and the token is cached locally.

Service-account auth is also supported via $GOOGLE_APPLICATION_CREDENTIALS
but is currently blocked by Google for arbitrary file creation outside
shared drives — see scripts/README.md for details.

Usage:
  pip install -r requirements.txt
  python3 create_roster_sheet.py \\
    --title "Foo Cohort Roster 2026" \\
    --admin bilal@example.com \\
    --admin sheeran@example.com \\
    [--tokenomics-sa butterfly-effect-club@get-data-io.iam.gserviceaccount.com]

Outputs the new spreadsheet URL on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import gspread
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as SACredentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

DEFAULT_TOKENOMICS_SA = 'butterfly-effect-club@get-data-io.iam.gserviceaccount.com'

ROSTER_HEADERS = [
    'Name', 'School', 'Learner Type', 'Graduation Date',
    'public_key', 'pk_hash', 'attestation_tx_id', 'qualification_tx_id',
    'profile_url', 'credential_pdf_url', 'certificate_url',
    'status', 'processed_at', 'github_commit_sha', 'notes',
    'public_listable_override',
]

AUDIT_HEADERS = [
    'processed_at', 'name', 'action', 'github_commit_sha',
    'profile_url', 'credential_pdf_url', 'certificate_url',
    'error_message', 'triggered_by',
]


def get_credentials():
    """Prefer the OAuth flow (operator account); fall back to SA if explicitly set."""
    sa_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_path and Path(sa_path).is_file():
        print(f'Using service account at {sa_path}', file=sys.stderr)
        return SACredentials.from_service_account_file(sa_path, scopes=SCOPES)

    # OAuth flow — uses the operator's Google account
    token_path = Path.home() / '.config' / 'truesight' / 'create_roster_sheet_token.json'
    if token_path.is_file():
        try:
            creds = UserCredentials.from_authorized_user_file(str(token_path), SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                return creds
        except Exception as e:
            print(f'Cached token invalid ({e}) — re-authorizing', file=sys.stderr)

    client_secret_env = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET_JSON')
    if not client_secret_env:
        sys.exit(
            'ERROR: OAuth setup required.\n'
            '  Option A (recommended for one-off setup): set\n'
            '    GOOGLE_OAUTH_CLIENT_SECRET_JSON=<path-to-client-secret.json>\n'
            '  Download client_secret.json from console.cloud.google.com → APIs → Credentials\n'
            '  (Desktop app OAuth client; see scripts/README.md for full setup).\n\n'
            '  Option B: set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON,\n'
            '  but the SA must have Drive create permission in a shared drive — most SAs\n'
            '  do not, so you will see 403 on file creation.'
        )

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_env, SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f'Token cached at {token_path}', file=sys.stderr)
    return creds


def build_formatting_requests(roster_sid: int, audit_sid: int) -> list[dict]:
    """Header band + alternating rows + conditional formatting on status column."""
    return [
        # Cohort Roster header band
        {'repeatCell': {
            'range': {'sheetId': roster_sid, 'startRowIndex': 0, 'endRowIndex': 1},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.18, 'green': 0.27, 'blue': 0.31},
                'horizontalAlignment': 'CENTER',
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'wrapStrategy': 'WRAP',
            }},
            'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment,textFormat,wrapStrategy)',
        }},
        {'autoResizeDimensions': {'dimensions': {
            'sheetId': roster_sid, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': len(ROSTER_HEADERS),
        }}},
        {'addBanding': {'bandedRange': {
            'range': {'sheetId': roster_sid, 'startRowIndex': 0, 'endColumnIndex': len(ROSTER_HEADERS)},
            'rowProperties': {
                'headerColor': {'red': 0.18, 'green': 0.27, 'blue': 0.31},
                'firstBandColor': {'red': 1, 'green': 1, 'blue': 1},
                'secondBandColor': {'red': 0.96, 'green': 0.96, 'blue': 0.94},
            },
        }}},
        # Conditional formatting on status column (col L, index 11)
        {'addConditionalFormatRule': {'rule': {
            'ranges': [{'sheetId': roster_sid, 'startRowIndex': 1, 'startColumnIndex': 11, 'endColumnIndex': 12}],
            'booleanRule': {
                'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'processed'}]},
                'format': {'backgroundColor': {'red': 0.78, 'green': 0.91, 'blue': 0.78}, 'textFormat': {'bold': True}},
            },
        }, 'index': 0}},
        {'addConditionalFormatRule': {'rule': {
            'ranges': [{'sheetId': roster_sid, 'startRowIndex': 1, 'startColumnIndex': 11, 'endColumnIndex': 12}],
            'booleanRule': {
                'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'failed'}]},
                'format': {'backgroundColor': {'red': 0.96, 'green': 0.78, 'blue': 0.78}, 'textFormat': {'bold': True}},
            },
        }, 'index': 1}},
        {'addConditionalFormatRule': {'rule': {
            'ranges': [{'sheetId': roster_sid, 'startRowIndex': 1, 'startColumnIndex': 11, 'endColumnIndex': 12}],
            'booleanRule': {
                'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': 'pending'}]},
                'format': {'backgroundColor': {'red': 1, 'green': 0.95, 'blue': 0.80}},
            },
        }, 'index': 2}},
        # Audit Trail formatting
        {'repeatCell': {
            'range': {'sheetId': audit_sid, 'startRowIndex': 0, 'endRowIndex': 1},
            'cell': {'userEnteredFormat': {
                'backgroundColor': {'red': 0.18, 'green': 0.27, 'blue': 0.31},
                'horizontalAlignment': 'CENTER',
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
            }},
            'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)',
        }},
        {'autoResizeDimensions': {'dimensions': {
            'sheetId': audit_sid, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': len(AUDIT_HEADERS),
        }}},
        {'addBanding': {'bandedRange': {
            'range': {'sheetId': audit_sid, 'startRowIndex': 0, 'endColumnIndex': len(AUDIT_HEADERS)},
            'rowProperties': {
                'headerColor': {'red': 0.18, 'green': 0.27, 'blue': 0.31},
                'firstBandColor': {'red': 1, 'green': 1, 'blue': 1},
                'secondBandColor': {'red': 0.96, 'green': 0.96, 'blue': 0.94},
            },
        }}},
    ]


def main():
    parser = argparse.ArgumentParser(
        description='Create a new Cohort Roster Google Sheet with schema-conforming columns + formatting.'
    )
    parser.add_argument('--title', required=True, help='Spreadsheet title (e.g. "Yoga Lineage Cohort Roster 2026")')
    parser.add_argument('--admin', action='append', default=[],
                        help='Email to add as Editor (= trust circle for the program). Repeatable.')
    parser.add_argument('--tokenomics-sa', default=DEFAULT_TOKENOMICS_SA,
                        help=f'Service account email for the central handler to write back. Default: {DEFAULT_TOKENOMICS_SA}')
    parser.add_argument('--public-read', action='store_true',
                        help='Also grant anyone-with-link Reader access (use for the program-template sample sheet).')
    args = parser.parse_args()

    creds = get_credentials()
    sheets = build('sheets', 'v4', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)

    # 1. Create the spreadsheet with both tabs
    ss = sheets.spreadsheets().create(body={
        'properties': {'title': args.title},
        'sheets': [
            {'properties': {'title': 'Cohort Roster', 'gridProperties': {
                'frozenRowCount': 1, 'rowCount': 200, 'columnCount': len(ROSTER_HEADERS),
            }}},
            {'properties': {'title': 'Audit Trail', 'gridProperties': {
                'frozenRowCount': 1, 'rowCount': 1000, 'columnCount': len(AUDIT_HEADERS),
            }}},
        ],
    }, fields='spreadsheetId,spreadsheetUrl,sheets(properties(sheetId,title))').execute()
    ss_id = ss['spreadsheetId']
    url = ss['spreadsheetUrl']
    roster_sid = next(s['properties']['sheetId'] for s in ss['sheets'] if s['properties']['title'] == 'Cohort Roster')
    audit_sid = next(s['properties']['sheetId'] for s in ss['sheets'] if s['properties']['title'] == 'Audit Trail')
    print(f'Created sheet: {url}', file=sys.stderr)

    # 2. Write headers
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=ss_id,
        body={'valueInputOption': 'RAW', 'data': [
            {'range': "'Cohort Roster'!A1", 'values': [ROSTER_HEADERS]},
            {'range': "'Audit Trail'!A1", 'values': [AUDIT_HEADERS]},
        ]},
    ).execute()
    print('Headers written', file=sys.stderr)

    # 3. Apply formatting
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={'requests': build_formatting_requests(roster_sid, audit_sid)},
    ).execute()
    print('Formatting applied', file=sys.stderr)

    # 4. Share
    if args.tokenomics_sa:
        drive.permissions().create(fileId=ss_id, body={
            'type': 'user', 'role': 'writer', 'emailAddress': args.tokenomics_sa,
        }, sendNotificationEmail=False).execute()
        print(f'Shared with tokenomics SA: {args.tokenomics_sa}', file=sys.stderr)
    for email in args.admin:
        drive.permissions().create(fileId=ss_id, body={
            'type': 'user', 'role': 'writer', 'emailAddress': email,
        }, sendNotificationEmail=False).execute()
        print(f'Shared with admin: {email}', file=sys.stderr)
    if args.public_read:
        drive.permissions().create(fileId=ss_id, body={'type': 'anyone', 'role': 'reader'},
                                    sendNotificationEmail=False).execute()
        print('Shared anyone-with-link as Reader', file=sys.stderr)

    print(url)


if __name__ == '__main__':
    main()
