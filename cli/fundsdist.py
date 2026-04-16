#!/usr/bin/env python3
"""fundsdist — Funds Distribution CLI tool."""

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Transfer:
    recipient: str
    address: str
    amount: str


@dataclass
class DistributionFile:
    network: str
    token: str
    note: str
    transfers: list[Transfer] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> DistributionFile:
    """Parse a distribution CSV file and return a DistributionFile."""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    if len(rows) < 3:
        raise ValueError(f"CSV must have at least 3 header rows, found {len(rows)}.")

    network = rows[0][0].strip()
    token   = rows[1][0].strip()
    note    = rows[2][0].strip()

    transfers = []
    for lineno, row in enumerate(rows[3:], start=4):
        if not any(cell.strip() for cell in row):
            continue  # skip blank lines
        if len(row) < 3:
            raise ValueError(
                f"Line {lineno}: expected 3 columns (recipient, address, amount), "
                f"got {len(row)}: {row}"
            )
        transfers.append(Transfer(
            recipient=row[0].strip(),
            address=row[1].strip(),
            amount=row[2].strip(),
        ))

    return DistributionFile(network=network, token=token, note=note, transfers=transfers)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def dump_distribution(dist: DistributionFile) -> None:
    """Pretty-print the contents of a distribution file."""
    print()
    print("=" * 60)
    print("  Distribution file contents")
    print("=" * 60)
    print(f"  Network : {dist.network}")
    print(f"  Token   : {dist.token}")
    print(f"  Note    : {dist.note}")
    print(f"  Entries : {len(dist.transfers)}")
    print("-" * 60)

    if not dist.transfers:
        print("  (no transfer rows)")
    else:
        # Column widths
        w_rec  = max(len("Recipient"), max(len(t.recipient) for t in dist.transfers))
        w_addr = max(len("Address"),   max(len(t.address)   for t in dist.transfers))
        w_amt  = max(len("Amount"),    max(len(t.amount)    for t in dist.transfers))

        header = (
            f"  {'Recipient':<{w_rec}}  {'Address':<{w_addr}}  {'Amount':>{w_amt}}"
        )
        print(header)
        print(f"  {'-'*w_rec}  {'-'*w_addr}  {'-'*w_amt}")

        for t in dist.transfers:
            print(f"  {t.recipient:<{w_rec}}  {t.address:<{w_addr}}  {t.amount:>{w_amt}}")

    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------

def action_load_csv() -> None:
    """Option 1 — load and dump a CSV file."""
    raw = input("Enter path to CSV file: ").strip()
    if not raw:
        print("No path entered.")
        return

    path = Path(raw).expanduser()
    if not path.exists():
        print(f"File not found: {path}")
        return
    if not path.is_file():
        print(f"Not a file: {path}")
        return

    try:
        dist = load_csv(path)
    except (ValueError, IndexError, csv.Error) as exc:
        print(f"Error reading CSV: {exc}")
        return

    dump_distribution(dist)


def action_help() -> None:
    """Option 9 — print help text."""
    print("""
fundsdist — Funds Distribution CLI
===================================

MENU OPTIONS
  1  Load CSV file
       Prompts for a file path, parses the distribution CSV, and
       displays the interpreted contents.

  9  Help
       Show this help text.

  0  Quit
       Exit the program.

CSV FILE FORMAT
  The CSV file must contain the following rows:

  Row 0 : Network name          (column 0)
  Row 1 : Token symbol/name     (column 0)
  Row 2 : Transfer note/memo    (column 0)
  Row 3+ : One transfer per row
            column 0 — Recipient name / label
            column 1 — Wallet address
            column 2 — Amount to transfer

  Example:
    Ethereum
    USDC
    Q1 2025 grants
    Alice,0xABC...123,1000
    Bob,0xDEF...456,2500
""")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

MENU = """
=============================
  fundsdist — Main Menu
=============================
  1  Load CSV file
  9  Help
  0  Quit
-----------------------------
Choice: """


def main() -> None:
    print("fundsdist  —  Funds Distribution Tool")

    while True:
        choice = input(MENU).strip()

        if choice == "1":
            action_load_csv()
        elif choice == "9":
            action_help()
        elif choice in ("0", "q", "quit", "exit"):
            print("Goodbye.")
            sys.exit(0)
        else:
            print(f"Unknown option: '{choice}'. Enter 1, 9, or 0.")


if __name__ == "__main__":
    main()
