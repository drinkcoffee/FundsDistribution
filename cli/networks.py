"""Network configurations for fundsdist."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    symbol: str


@dataclass(frozen=True)
class Network:
    name: str
    rpc_url: str
    distributor_address: str
    fireblocks_asset_id: str       # native gas token asset ID as labelled in Fireblocks
    token_addresses: dict[str, str]  # symbol -> contract address for this network
    token_fireblocks_asset_ids: dict[str, str]  # symbol -> Fireblocks asset ID for ERC-20 tokens

    def token_address(self, symbol: str) -> str:
        """Return the address for a token symbol on this network, raising KeyError if not found."""
        return self.token_addresses[symbol]


# ---------------------------------------------------------------------------
# FundsDistributor ABI (minimal — only the functions used by this CLI)
# ---------------------------------------------------------------------------

FUNDS_DISTRIBUTOR_ABI = [
    {
        "name": "getApprovedTokens",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "tokens", "type": "address[]"}],
    },
    {
        "name": "addToken",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [],
    },
    {
        "name": "removeToken",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [],
    },
]


# ---------------------------------------------------------------------------
# Global token definitions
# ---------------------------------------------------------------------------

USDC = Token(symbol="USDC")

TOKENS: dict[str, Token] = {
    USDC.symbol: USDC,
}


# ---------------------------------------------------------------------------
# Network definitions
# ---------------------------------------------------------------------------

IMMUTABLE_TESTNET = Network(
    name="Immutable_Testnet",
    rpc_url="https://rpc.testnet.immutable.com",
    distributor_address="0x2777dc1b338272d74715e6a42c06a2fbde00252b",
    fireblocks_asset_id="IMX_TEST",
    token_addresses={
        USDC.symbol: "0x3B2d8A1931736Fc321C24864BceEe981B11c3c57",
    },
    token_fireblocks_asset_ids={
        USDC.symbol: "USDC_IMX_TEST",
    },
)

ETHEREUM = Network(
    name="Ethereum",
    rpc_url="https://rpc.flashbots.net/fast",
    distributor_address="0x0000000000000000000000000000000000000000",
    fireblocks_asset_id="ETH",
    token_addresses={
        USDC.symbol: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    },
    token_fireblocks_asset_ids={
        USDC.symbol: "USDC",
    },
)

NETWORKS: dict[str, Network] = {
    IMMUTABLE_TESTNET.name: IMMUTABLE_TESTNET,
    ETHEREUM.name: ETHEREUM,
}
