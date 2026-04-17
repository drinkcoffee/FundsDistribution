#!/usr/bin/env python3
"""fundsdist — Funds Distribution CLI tool."""

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from web3 import Web3

from fireblocks import FireblocksClient
from networks import FUNDS_DISTRIBUTOR_ABI, NETWORKS, Network


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
            continue
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
        w_rec  = max(len("Recipient"), max(len(t.recipient) for t in dist.transfers))
        w_addr = max(len("Address"),   max(len(t.address)   for t in dist.transfers))
        w_amt  = max(len("Amount"),    max(len(t.amount)    for t in dist.transfers))

        print(f"  {'Recipient':<{w_rec}}  {'Address':<{w_addr}}  {'Amount':>{w_amt}}")
        print(f"  {'-'*w_rec}  {'-'*w_addr}  {'-'*w_amt}")
        for t in dist.transfers:
            print(f"  {t.recipient:<{w_rec}}  {t.address:<{w_addr}}  {t.amount:>{w_amt}}")

    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Core logic (no interactive I/O — called from both CLI and menu paths)
# ---------------------------------------------------------------------------

def _dump_networks() -> None:
    for network in NETWORKS.values():
        print(f"\n  {network.name}")
        print(f"    RPC URL    : {network.rpc_url}")
        print(f"    Distributor: {network.distributor_address}")
        print(f"    FB asset   : {network.fireblocks_asset_id}")
        print(f"    Tokens:")
        if network.token_addresses:
            for symbol, addr in network.token_addresses.items():
                print(f"      {symbol:<10}  {addr}")
        else:
            print(f"      (none)")
    print()


def _get_approved_tokens(network: Network) -> None:
    w3 = Web3(Web3.HTTPProvider(network.rpc_url))
    if not w3.is_connected():
        print(f"Could not connect to {network.rpc_url}")
        return

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(network.distributor_address),
        abi=FUNDS_DISTRIBUTOR_ABI,
    )
    try:
        addresses = contract.functions.getApprovedTokens().call()
    except Exception as exc:
        print(f"Contract call failed: {exc}")
        return

    print(f"\nApproved tokens on {network.name} ({len(addresses)} total):")
    if not addresses:
        print("  (none)")
    else:
        address_to_symbol = {v.lower(): k for k, v in network.token_addresses.items()}
        for addr in addresses:
            symbol = address_to_symbol.get(addr.lower(), "unknown")
            print(f"  {symbol:<10}  {addr}")
    print()


def _fireblocks_submit(network: Network, calldata: str, note: str) -> None:
    vault_id = os.environ.get("FIREBLOCKS_VAULT_ID")
    if not vault_id:
        print("FIREBLOCKS_VAULT_ID environment variable is not set.")
        return
    try:
        client = FireblocksClient.from_env()
        tx = client.submit_contract_call(
            vault_id=vault_id,
            asset_id=network.fireblocks_asset_id,
            to_address=network.distributor_address,
            calldata=calldata,
            note=note,
        )
    except EnvironmentError as exc:
        print(f"Configuration error: {exc}")
        return
    except Exception as exc:
        print(f"Fireblocks request failed: {exc}")
        return
    print(f"\nTransaction submitted.")
    print(f"  ID     : {tx.transaction_id}")
    print(f"  Status : {tx.status}")
    print()


def _add_token(network: Network, token_address: str, symbol: str, confirm: bool = True) -> None:
    w3 = Web3()
    contract = w3.eth.contract(abi=FUNDS_DISTRIBUTOR_ABI)
    try:
        calldata = contract.encode_abi("addToken", args=[Web3.to_checksum_address(token_address)])
    except Exception as exc:
        print(f"Failed to encode calldata: {exc}")
        return

    note = f"Add token {symbol} ({token_address}) to FundsDistributor on {network.name}"

    print(f"\n  Network     : {network.name}")
    print(f"  Contract    : {network.distributor_address}")
    print(f"  Token       : {symbol} ({token_address})")
    print(f"  Note        : {note}")

    if confirm:
        if input("\nSubmit to Fireblocks? (yes/no): ").strip().lower() not in ("yes", "y"):
            print("Cancelled.")
            return

    _fireblocks_submit(network, calldata, note)


def _remove_token(network: Network, token_address: str, symbol: str, confirm: bool = True) -> None:
    w3 = Web3()
    contract = w3.eth.contract(abi=FUNDS_DISTRIBUTOR_ABI)
    try:
        calldata = contract.encode_abi("removeToken", args=[Web3.to_checksum_address(token_address)])
    except Exception as exc:
        print(f"Failed to encode calldata: {exc}")
        return

    note = f"Remove token {symbol} ({token_address}) from FundsDistributor on {network.name}"

    print(f"\n  Network     : {network.name}")
    print(f"  Contract    : {network.distributor_address}")
    print(f"  Token       : {symbol} ({token_address})")
    print(f"  Note        : {note}")

    if confirm:
        if input("\nSubmit to Fireblocks? (yes/no): ").strip().lower() not in ("yes", "y"):
            print("Cancelled.")
            return

    _fireblocks_submit(network, calldata, note)


# ---------------------------------------------------------------------------
# Interactive menu helpers
# ---------------------------------------------------------------------------

def _select_network() -> Network | None:
    network_names = list(NETWORKS.keys())
    print("\nAvailable networks:")
    for i, name in enumerate(network_names, start=1):
        print(f"  {i}  {name}")
    raw = input("Select network (number): ").strip()
    try:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(network_names):
            raise ValueError
    except ValueError:
        print("Invalid selection.")
        return None
    return NETWORKS[network_names[idx]]


# ---------------------------------------------------------------------------
# Interactive admin sub-menu
# ---------------------------------------------------------------------------

ADMIN_MENU = """
-----------------------------
  Admin
-----------------------------
  1  List approved tokens
  2  Add token
  3  Remove token
  4  Networks
  0  Back
-----------------------------
Choice: """


def admin_list() -> None:
    network = _select_network()
    if network is None:
        return
    _get_approved_tokens(network)


def admin_add() -> None:
    network = _select_network()
    if network is None:
        return

    known = list(network.token_addresses.items())
    print("\nKnown tokens on this network:")
    for i, (symbol, addr) in enumerate(known, start=1):
        print(f"  {i}  {symbol:<10}  {addr}")
    print(f"  {len(known) + 1}  Enter a custom address")

    raw = input("Select token (number): ").strip()
    try:
        choice = int(raw) - 1
        if choice < 0 or choice > len(known):
            raise ValueError
    except ValueError:
        print("Invalid selection.")
        return

    if choice < len(known):
        symbol, token_address = known[choice]
    else:
        token_address = input("Token address: ").strip()
        if not token_address:
            print("No address entered.")
            return
        symbol = token_address

    _add_token(network, token_address, symbol)


def admin_remove() -> None:
    network = _select_network()
    if network is None:
        return

    w3 = Web3(Web3.HTTPProvider(network.rpc_url))
    if not w3.is_connected():
        print(f"Could not connect to {network.rpc_url}")
        return

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(network.distributor_address),
        abi=FUNDS_DISTRIBUTOR_ABI,
    )
    try:
        addresses = contract.functions.getApprovedTokens().call()
    except Exception as exc:
        print(f"Contract call failed: {exc}")
        return

    if not addresses:
        print("No approved tokens on this network.")
        return

    address_to_symbol = {v.lower(): k for k, v in network.token_addresses.items()}
    print("\nCurrently approved tokens:")
    for i, addr in enumerate(addresses, start=1):
        symbol = address_to_symbol.get(addr.lower(), "unknown")
        print(f"  {i}  {symbol:<10}  {addr}")

    raw = input("Select token to remove (number): ").strip()
    try:
        choice = int(raw) - 1
        if choice < 0 or choice >= len(addresses):
            raise ValueError
    except ValueError:
        print("Invalid selection.")
        return

    token_address = addresses[choice]
    symbol = address_to_symbol.get(token_address.lower(), "unknown")
    _remove_token(network, token_address, symbol)


def menu_admin() -> None:
    while True:
        choice = input(ADMIN_MENU).strip()
        if choice == "1":
            admin_list()
        elif choice == "2":
            admin_add()
        elif choice == "3":
            admin_remove()
        elif choice == "4":
            _dump_networks()
        elif choice in ("0", "b", "back"):
            return
        else:
            print(f"Unknown option: '{choice}'. Enter 1-4 or 0.")


# ---------------------------------------------------------------------------
# Interactive dist sub-menu
# ---------------------------------------------------------------------------

DIST_MENU = """
-----------------------------
  Dist
-----------------------------
  1  Check CSV file
  0  Back
-----------------------------
Choice: """


def dist_check() -> None:
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


def menu_dist() -> None:
    while True:
        choice = input(DIST_MENU).strip()
        if choice == "1":
            dist_check()
        elif choice in ("0", "b", "back"):
            return
        else:
            print(f"Unknown option: '{choice}'. Enter 1 or 0.")


# ---------------------------------------------------------------------------
# CLI subcommand handlers
# ---------------------------------------------------------------------------

def _resolve_network(name: str) -> Network | None:
    network = NETWORKS.get(name)
    if network is None:
        print(f"Unknown network '{name}'. Available: {', '.join(NETWORKS)}")
    return network


def _resolve_token_for_add(network: Network, token_arg: str) -> tuple[str, str] | None:
    if token_arg in network.token_addresses:
        return token_arg, network.token_addresses[token_arg]
    if token_arg.startswith("0x"):
        return token_arg, token_arg
    print(
        f"Token '{token_arg}' is not a known symbol on {network.name} and does not look like "
        f"an address. Known symbols: {', '.join(network.token_addresses)}"
    )
    return None


def _resolve_token_for_remove(network: Network, token_arg: str) -> tuple[str, str] | None:
    if token_arg in network.token_addresses:
        return token_arg, network.token_addresses[token_arg]
    if token_arg.startswith("0x"):
        address_to_symbol = {v.lower(): k for k, v in network.token_addresses.items()}
        symbol = address_to_symbol.get(token_arg.lower(), "unknown")
        return symbol, token_arg
    print(
        f"Token '{token_arg}' is not a known symbol on {network.name} and does not look like "
        f"an address. Known symbols: {', '.join(network.token_addresses)}"
    )
    return None


def cmd_admin_networks(_args: argparse.Namespace) -> None:
    _dump_networks()


def cmd_admin_list(args: argparse.Namespace) -> None:
    network = _resolve_network(args.network)
    if network is None:
        sys.exit(1)
    _get_approved_tokens(network)


def cmd_admin_add(args: argparse.Namespace) -> None:
    network = _resolve_network(args.network)
    if network is None:
        sys.exit(1)
    resolved = _resolve_token_for_add(network, args.token)
    if resolved is None:
        sys.exit(1)
    symbol, token_address = resolved
    _add_token(network, token_address, symbol, confirm=not args.yes)


def cmd_admin_remove(args: argparse.Namespace) -> None:
    network = _resolve_network(args.network)
    if network is None:
        sys.exit(1)
    resolved = _resolve_token_for_remove(network, args.token)
    if resolved is None:
        sys.exit(1)
    symbol, token_address = resolved
    _remove_token(network, token_address, symbol, confirm=not args.yes)


def cmd_dist_check(args: argparse.Namespace) -> None:
    path = Path(args.file).expanduser()
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    try:
        dist = load_csv(path)
    except (ValueError, IndexError, csv.Error) as exc:
        print(f"Error reading CSV: {exc}")
        sys.exit(1)
    dump_distribution(dist)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fundsdist",
        description="Funds Distribution CLI — run without arguments for interactive mode.",
    )
    group_sub = parser.add_subparsers(dest="group", metavar="GROUP")

    # --- admin ---
    admin = group_sub.add_parser("admin", help="Manage the FundsDistributor token allowlist.")
    admin_sub = admin.add_subparsers(dest="command", metavar="COMMAND")

    admin_sub.add_parser("networks", help="List all configured networks and their tokens.")

    p = admin_sub.add_parser("list", help="List tokens approved on the FundsDistributor contract.")
    p.add_argument("--network", required=True, metavar="NAME",
                   help=f"Network name. Available: {', '.join(NETWORKS)}")

    p = admin_sub.add_parser("add", help="Submit an addToken transaction via Fireblocks.")
    p.add_argument("--network", required=True, metavar="NAME",
                   help=f"Network name. Available: {', '.join(NETWORKS)}")
    p.add_argument("--token", required=True, metavar="SYMBOL_OR_ADDRESS",
                   help="Token symbol (e.g. USDC) or contract address.")
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")

    p = admin_sub.add_parser("remove", help="Submit a removeToken transaction via Fireblocks.")
    p.add_argument("--network", required=True, metavar="NAME",
                   help=f"Network name. Available: {', '.join(NETWORKS)}")
    p.add_argument("--token", required=True, metavar="SYMBOL_OR_ADDRESS",
                   help="Token symbol (e.g. USDC) or contract address.")
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")

    # --- dist ---
    dist = group_sub.add_parser("dist", help="Distribution file operations.")
    dist_sub = dist.add_subparsers(dest="command", metavar="COMMAND")

    p = dist_sub.add_parser("check", help="Parse and display a distribution CSV file.")
    p.add_argument("file", help="Path to the CSV file.")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MAIN_MENU = """
=============================
  fundsdist — Main Menu
=============================
  1  Admin
  2  Dist
  9  Help
  0  Quit
-----------------------------
Choice: """

_CLI_DISPATCH = {
    ("admin", "networks"): cmd_admin_networks,
    ("admin", "list"):     cmd_admin_list,
    ("admin", "add"):      cmd_admin_add,
    ("admin", "remove"):   cmd_admin_remove,
    ("dist",  "check"):    cmd_dist_check,
}


def _print_help() -> None:
    print("""
fundsdist — Funds Distribution CLI
===================================

INTERACTIVE MENU
  1  Admin  →  list / add / remove approved tokens
  2  Dist   →  check a distribution CSV file

COMMAND-LINE USAGE
  fundsdist admin networks
  fundsdist admin list   --network NAME
  fundsdist admin add    --network NAME --token SYMBOL_OR_ADDRESS [--yes]
  fundsdist admin remove --network NAME --token SYMBOL_OR_ADDRESS [--yes]
  fundsdist dist  check  <file>

Run any subcommand with --help for full argument details.
""")


def main() -> None:
    if len(sys.argv) > 1:
        parser = _build_parser()
        args = parser.parse_args()
        handler = _CLI_DISPATCH.get((args.group, getattr(args, "command", None)))
        if handler is None:
            # Group given but no subcommand — print that group's help.
            parser.parse_args([args.group, "--help"])
        handler(args)
        return

    print("fundsdist  —  Funds Distribution Tool")
    while True:
        choice = input(MAIN_MENU).strip()
        if choice == "1":
            menu_admin()
        elif choice == "2":
            menu_dist()
        elif choice == "9":
            _print_help()
        elif choice in ("0", "q", "quit", "exit"):
            print("Goodbye.")
            sys.exit(0)
        else:
            print(f"Unknown option: '{choice}'. Enter 1, 2, 9, or 0.")


if __name__ == "__main__":
    main()
