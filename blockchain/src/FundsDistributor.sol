// SPDX-License-Identifier: MIT
pragma solidity ^0.8.22;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {ReentrancyGuardTransient} from "@openzeppelin/contracts/utils/ReentrancyGuardTransient.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title FundsDistributor
 * @notice Pull-based ERC20 distributor behind a UUPS proxy: an admin allowlists tokens by name, and an operator
 *         pulls tokens from their own balance to many recipients in one transaction.
 * @dev Deploy the implementation once, then deploy an {ERC1967Proxy} with `initialize` calldata. Roles:
 *      `DEFAULT_ADMIN_ROLE` (OpenZeppelin) for token list and role admin; `UPGRADE_ROLE` for UUPS upgrades;
 *      `DISTRIBUTE_ROLE` for `distribute`. Token allowlist is separate from ERC20 `approve`: callers must
 *      approve this contract for at least the sum of recipient amounts before `distribute`.
 */
contract FundsDistributor is Initializable, AccessControlUpgradeable, ReentrancyGuardTransient, UUPSUpgradeable {
    using SafeERC20 for IERC20;

    /// @notice Thrown when an address parameter must be non-zero.
    error ZeroAddress();
    /// @notice Thrown when a recipient amount must be non-zero.
    error ZeroAmount();
    /// @notice Thrown when operating on a token that is not in the allowlist.
    error TokenNotApproved();
    /// @notice Thrown when `addToken` is called for a token that is already allowlisted.
    error TokenAlreadyApproved();
    /// @notice Thrown when `distribute` is called with an empty recipients array.
    error NoRecipients();
    /// @notice Thrown when the caller's ERC20 allowance for this contract is not equal to the sum of recipient amounts.
    /// @param approvedAmount Current `allowance(msg.sender, address(this))` on the token.
    /// @param requiredAmount Sum of all `recipients[i].amount` values.
    error IncorrectAllowance(uint256 approvedAmount, uint256 requiredAmount);
    /// @notice Thrown when the caller's ERC20 balance is less than the sum of recipient amounts.
    /// @param balance Current `balanceOf(msg.sender)` on the token.
    /// @param requiredAmount Sum of all `recipients[i].amount` values.
    error InsufficientBalance(uint256 balance, uint256 requiredAmount);
    /// @notice Thrown when the supplied name does not match `IERC20Metadata(token).name()`.
    error TokenNameMismatch(string tokenName, string nameFromContract);
    /// @notice Thrown when `msg.value` does not equal the sum of recipient amounts in `distributeEth`.
    /// @param sentAmount `msg.value` supplied by the caller.
    /// @param requiredAmount Sum of all `recipients[i].amount` values.
    error IncorrectEthValue(uint256 sentAmount, uint256 requiredAmount);
    /// @notice Thrown when a native ETH transfer to a recipient fails in `distributeEth`.
    /// @param recipient Address that rejected or failed to receive ETH.
    error EthTransferFailed(address recipient);
    /// @notice Thrown when `upgradeStorage` is called on a version that requires no storage migration.
    error DoNotNeedToUpgradeStorage();

    /// @notice Emitted after a token is allowlisted.
    event TokenAdded(address indexed token);
    /// @notice Emitted after a token is removed from the allowlist.
    event TokenRemoved(address indexed token);
    /// @notice Emitted after a successful `distribute` (all transfers completed).
    event Distributed(address indexed token, uint256 totalAmount, uint256 recipientCount);


    /// @notice Role allowed to authorize UUPS implementation upgrades.
    bytes32 public constant UPGRADE_ROLE = keccak256("UPGRADE_ROLE");
    /// @notice Role allowed to invoke `distribute`.
    bytes32 public constant DISTRIBUTE_ROLE = keccak256("DISTRIBUTE_ROLE");

    /// @notice Storage version set by the initial deployment.
    uint256 public constant VERSION1 = 1;


    /// @notice Single transfer leg: destination address and amount of token units.
    struct Recipient {
        address addr;
        uint256 amount;
    }

    /// @notice Storage layout version; set to {VERSION1} at initialization and updated by future `upgradeStorage` calls.
    uint256 public version;

    /// @notice Whether `distribute` may be used for this ERC20 contract address.
    mapping(address => bool) public approvedToken;
    /// @dev Ordered list of approved token addresses; kept in sync with `approvedToken`.
    address[] private _approvedTokens;
    /// @dev 0-based index of each token in `_approvedTokens`; valid only when `approvedToken[token]` is true.
    mapping(address => uint256) private _tokenIndex;


    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    /**
     * @notice One-time setup for the proxy instance; grants roles and initializes `AccessControl`.
     * @param _defaultAdmin Account receiving `DEFAULT_ADMIN_ROLE` (token list, role administration).
     * @param _upgrader Account receiving `UPGRADE_ROLE` for UUPS upgrades.
     * @param _distributor Account receiving `DISTRIBUTE_ROLE` to call `distribute`.
     * @dev Reverts with {ZeroAddress} if any argument is `address(0)`. Callable only once (initializer).
     */
    function initialize(address _defaultAdmin, address _upgrader, address _distributor) external initializer {
        if (_defaultAdmin == address(0) || _upgrader == address(0) || _distributor == address(0)) {
            revert ZeroAddress();
        }

        __AccessControl_init();

        version = VERSION1;

        _grantRole(DEFAULT_ADMIN_ROLE, _defaultAdmin);
        _grantRole(UPGRADE_ROLE, _upgrader);
        _grantRole(DISTRIBUTE_ROLE, _distributor);
    }

    /**
     * @notice Allow list a token for `distribute`. Token myst support `name()` function.
     * @param tokenName Expected token name; must equal `IERC20Metadata(token).name()` (byte-for-byte string match via hash).
     * @param token ERC20 contract address.
     * @dev Caller must hold `DEFAULT_ADMIN_ROLE`. 
     */
    function addToken(string calldata tokenName, address token) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(token != address(0), ZeroAddress());
        string memory nameFromContract = IERC20Metadata(token).name();
        if (keccak256(bytes(tokenName)) != keccak256(bytes(nameFromContract))) {
            revert TokenNameMismatch(tokenName, nameFromContract);
        }
        _addToken(token);
    }

    /**
     * @notice Allow list a token for `distribute`.
     * @param token ERC20 contract address.
     * @dev Caller must hold `DEFAULT_ADMIN_ROLE`.
     */
    function addToken(address token) public onlyRole(DEFAULT_ADMIN_ROLE) {
        require(token != address(0), ZeroAddress());
        _addToken(token);
    }

    /**
     * @notice Removes a token from the allowlist so `distribute` cannot use it until re-added.
     * @param token ERC20 contract address to remove.
     * @dev Caller must hold `DEFAULT_ADMIN_ROLE`. 
     */
    function removeToken(address token) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (token == address(0)) {
            revert ZeroAddress();
        }
        if (!approvedToken[token]) {
            revert TokenNotApproved();
        }
        approvedToken[token] = false;

        // Swap the token with the last element then pop, preserving a packed array.
        uint256 idx = _tokenIndex[token];
        uint256 last = _approvedTokens.length - 1;
        if (idx != last) {
            address lastToken = _approvedTokens[last];
            _approvedTokens[idx] = lastToken;
            _tokenIndex[lastToken] = idx;
        }
        _approvedTokens.pop();
        delete _tokenIndex[token];

        emit TokenRemoved(token);
    }

    /**
     * @notice Transfers `token` from `msg.sender` to each recipient using `transferFrom`, in one transaction.
     * @param token Allowlisted ERC20 to distribute.
     * @param recipients Destinations and amounts; amounts are summed and compared to `msg.sender`'s allowance for this contract.
     * @dev Caller must hold `DISTRIBUTE_ROLE`. `msg.sender` must have approved this contract for at exactly the sum of amounts.
     *      Reverts if the token is not allowlisted, recipients is empty, any recipient address is zero, any amount is zero,
     *      allowance is insufficient, or any `safeTransferFrom` fails. Emits {Distributed} after all legs succeed.
     */
    function distribute(address token, Recipient[] calldata recipients) external onlyRole(DISTRIBUTE_ROLE) nonReentrant {
        if (recipients.length == 0) {
            revert NoRecipients();
        }
        if (!approvedToken[token]) {
            revert TokenNotApproved();
        }

        IERC20 erc20 = IERC20(token);
        uint256 totalAmount;
        uint256 recipientCount = recipients.length;
        for (uint256 i = 0; i < recipientCount; i++) {
            Recipient calldata r = recipients[i];
            if (r.addr == address(0)) {
                revert ZeroAddress();
            }
            if (r.amount == 0) {
                revert ZeroAmount();
            }
            totalAmount += r.amount;
        }

        uint256 approvedAmount = erc20.allowance(msg.sender, address(this));
        if (approvedAmount != totalAmount) {
            revert IncorrectAllowance(approvedAmount, totalAmount);
        }
        uint256 balance = erc20.balanceOf(msg.sender);
        if (balance < totalAmount) {
            revert InsufficientBalance(balance, totalAmount);
        }

        for (uint256 i = 0; i < recipientCount; i++) {
            Recipient calldata r = recipients[i];
            erc20.safeTransferFrom(msg.sender, r.addr, r.amount);
        }
        emit Distributed(token, totalAmount, recipientCount);
    }

    /**
     * @notice Sends ETH supplied as `msg.value` to each recipient in one transaction.
     * @param recipients Destinations and amounts in wei; amounts must sum exactly to `msg.value`.
     * @dev Caller must hold `DISTRIBUTE_ROLE`. Reverts if recipients is empty, any address is zero, any amount is zero,
     *      `msg.value` does not equal the total, or any ETH transfer fails. Emits {Distributed} with `token = address(0)`.
     */
    function distributeEth(Recipient[] calldata recipients) external payable onlyRole(DISTRIBUTE_ROLE) nonReentrant {
        if (recipients.length == 0) {
            revert NoRecipients();
        }

        uint256 totalAmount;
        uint256 recipientCount = recipients.length;
        for (uint256 i = 0; i < recipientCount; i++) {
            Recipient calldata r = recipients[i];
            if (r.addr == address(0)) {
                revert ZeroAddress();
            }
            if (r.amount == 0) {
                revert ZeroAmount();
            }
            totalAmount += r.amount;
        }

        if (msg.value != totalAmount) {
            revert IncorrectEthValue(msg.value, totalAmount);
        }

        for (uint256 i = 0; i < recipientCount; i++) {
            Recipient calldata r = recipients[i];
            (bool success,) = r.addr.call{value: r.amount}("");
            if (!success) {
                revert EthTransferFailed(r.addr);
            }
        }
        emit Distributed(address(0), totalAmount, recipientCount);
    }

    /**
     * @notice Called after a UUPS upgrade to migrate storage to a new layout.
     * @dev Always reverts with {DoNotNeedToUpgradeStorage} on VERSION1; future implementations will perform
     *      the required migration and update {version}.
     */
    function upgradeStorage(bytes memory /* data */) external pure {
        revert DoNotNeedToUpgradeStorage();
    }

    /**
     * @notice Allowlists a token for `distribute` after verifying its ERC20 metadata name.
     * @param token ERC20 contract address (must implement `name()`).
     * @dev Caller must hold `DEFAULT_ADMIN_ROLE`. Reverts {ZeroAddress}, {TokenAlreadyApproved}, {TokenNameMismatch}, or access errors.
     */
    function _addToken(address token) internal {
        require(!approvedToken[token], TokenAlreadyApproved());
        _tokenIndex[token] = _approvedTokens.length;
        _approvedTokens.push(token);
        approvedToken[token] = true;
        emit TokenAdded(token);
    }


    /**
     * @notice Returns all currently allowlisted token addresses.
     * @return tokens Array of approved ERC20 contract addresses.
     */
    function getApprovedTokens() external view returns (address[] memory tokens) {
        return _approvedTokens;
    }

    /**
     * @notice UUPS hook: only `UPGRADE_ROLE` may set a new implementation.
     * @param newImplementation Address of the new implementation contract (unused here; enforced by `UUPSUpgradeable`).
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyRole(UPGRADE_ROLE) {}
}
