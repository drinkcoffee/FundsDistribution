# FundsDistributor (Foundry)

This package contains **FundsDistributor**, an upgradeable (UUPS) Solidity contract that distributes ERC20 tokens from a caller’s balance to many recipients in one transaction. Only allowlisted tokens may be used; admins manage the list and roles; operators with `DISTRIBUTE_ROLE` run distributions.

## Contract overview

- **Proxy pattern**: Deploy `FundsDistributor` as the implementation, then an `ERC1967Proxy` whose initializer calls `initialize(defaultAdmin, upgrader, distributor)`.
- **Roles** (OpenZeppelin `AccessControl`):
  - `DEFAULT_ADMIN_ROLE`: add/remove allowlisted tokens (`addToken` / `removeToken`), manage roles.
  - `UPGRADE_ROLE`: authorize UUPS upgrades (`upgradeToAndCall` / `upgradeTo` via OpenZeppelin).
  - `DISTRIBUTE_ROLE`: call `distribute`.
- **Token allowlist**: `addToken(string tokenName, address token)` checks `tokenName` against `IERC20Metadata(token).name()` before setting `approvedToken[token]`.
- **`distribute`**: For an allowlisted `token`, pulls `recipients[i].amount` from **`msg.sender`** to `recipients[i].addr` using `SafeERC20.safeTransferFrom`. Requires `msg.sender`’s allowance for **this contract** to be **at least** the sum of all amounts; otherwise reverts with `InsufficientAllowance(approvedAmount, requiredAmount)`. Emits `Distributed` on success.

Source: [`src/FundsDistributor.sol`](./src/FundsDistributor.sol).

## Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (`forge`, `cast`, optional `anvil`)

Dependencies are vendored under `lib/` (OpenZeppelin upgradeable stack, forge-std). If submodules are missing:

```shell
git submodule update --init --recursive
```

## Build

From this directory (`blockchain/`):

```shell
forge build
```

## Test

```shell
forge test -vvv
```

## Deploy

Copy `.env.example` to `.env` and set-up the following environment variables.

| Variable | Purpose |
|----------|---------|
| `DEPLOYER_ADDRESS` | Address passed into `initialize` for all three roles (adjust script if you need split roles). |
| `BLOCKSCOUT_APIKEY` | API key fragment for Blockscout verification URL. |
| `PRIVATE_KEY` | Used when `USE_LEDGER` is not `1`. |
| `USE_MAINNET` | `1` for Immutable mainnet RPC, else testnet. |
| `USE_LEDGER` | `1` to use Ledger (`LEDGER_HD_PATH` required). |
| `LEDGER_HD_PATH` | Path to key. For instance: `m/44'/60'/0'/0/0` |


The from `blockchain/` directory:

```shell
bash script/deploy.sh
```

# Deployments

| Contract           | Environment | Address                          |
|--------------------|-------------|----------------------------------|
| ERC1967 Proxy      | Testnet     | [0x2777dc1b338272d74715e6a42c06a2fbde00252b](https://explorer.testnet.immutable.com/address/0x2777dc1b338272d74715e6a42c06a2fbde00252b) |
| FundsDistributor   | Testnet     | [0x127b9c228d706ad17f77fc0cf229c35ed80e2e91](https://explorer.testnet.immutable.com/address/0x127b9c228d706ad17f77fc0cf229c35ed80e2e91) |
