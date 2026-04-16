# FundsDistribution

A CLI tool for distributing tokens to multiple wallet addresses from a simple CSV file.

## Repository layout

```
FundsDistribution/
├── cli/
│   ├── fundsdist.py      # Main CLI script
│   ├── requirements.txt  # Python dependencies
│   └── setup_venv.sh     # One-shot virtual environment bootstrap
├── blockchain/           # On-chain contracts / integration code
└── scripts/              # Operational scripts
```

## Requirements

- Python 3.10 or later
- macOS, Linux, or WSL

## Setup

```bash
cd cli
./setup_venv.sh
```

This creates a `.venv` virtual environment and installs all dependencies. You only need to run it once.

To activate the environment in subsequent sessions:

```bash
source cli/.venv/bin/activate
```

## Running the tool

```bash
cd cli
source .venv/bin/activate
python fundsdist.py
```

The tool starts with an interactive menu:

```
=============================
  fundsdist — Main Menu
=============================
  1  Load CSV file
  9  Help
  0  Quit
-----------------------------
Choice:
```

## Menu options

| Option | Description |
|--------|-------------|
| `1` | Load a distribution CSV file and display its interpreted contents |
| `9` | Show in-tool help |
| `0` | Quit (`q`, `quit`, and `exit` also work) |

## CSV file format

Each distribution is described by a single CSV file with the following structure:

| Row | Column 0 | Column 1 | Column 2 |
|-----|----------|----------|----------|
| 0 | Network name | — | — |
| 1 | Token symbol or name | — | — |
| 2 | Transfer note / memo | — | — |
| 3+ | Recipient label | Wallet address | Amount |

- Blank rows in the transfer section are ignored.
- Column values are trimmed of leading/trailing whitespace.

### Example CSV

```
Ethereum
USDC
Q1 2025 grants
Alice,0xABCDEF1234567890ABCDEF1234567890ABCDEF12,1000
Bob,0xDEF4561234567890DEF4561234567890DEF45612,2500
Carol,0x1234567890ABCDEF1234567890ABCDEF12345678,500
```

### Example output

```
============================================================
  Distribution file contents
============================================================
  Network : Ethereum
  Token   : USDC
  Note    : Q1 2025 grants
  Entries : 3
------------------------------------------------------------
  Recipient  Address                                     Amount
  ---------  ------------------------------------------  ------
  Alice      0xABCDEF1234567890ABCDEF1234567890ABCDEF12    1000
  Bob        0xDEF4561234567890DEF4561234567890DEF45612    2500
  Carol      0x1234567890ABCDEF1234567890ABCDEF12345678     500
============================================================
```
