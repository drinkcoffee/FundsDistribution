// SPDX-License-Identifier: MIT
pragma solidity ^0.8.22;

import {Test} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

import {FundsDistributor} from "../src/FundsDistributor.sol";

contract MockERC20 is ERC20 {
    constructor(string memory name_, string memory symbol_) ERC20(name_, symbol_) {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract FundsDistributorTest is Test {
    /// @dev Mirrors `FundsDistributor` events for `vm.expectEmit` topic/data checks.
    event TokenAdded(address indexed token);
    event TokenRemoved(address indexed token);
    event Distributed(address indexed token, uint256 totalAmount, uint256 recipientCount);

    FundsDistributor internal impl;
    FundsDistributor internal distributor;

    address internal admin = address(0xA11);
    address internal upgrader = address(0xA22);
    address internal distributorWallet = address(0xA33);
    address internal outsider = address(0xB00);

    function setUp() public {
        impl = new FundsDistributor();
        bytes memory init =
            abi.encodeCall(FundsDistributor.initialize, (admin, upgrader, distributorWallet));
        distributor = FundsDistributor(address(new ERC1967Proxy(address(impl), init)));
    }

    function test_Initialize_GrantsRoles() public view {
        assertTrue(distributor.hasRole(distributor.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(distributor.hasRole(distributor.UPGRADE_ROLE(), upgrader));
        assertTrue(distributor.hasRole(distributor.DISTRIBUTE_ROLE(), distributorWallet));
    }

    function test_Initialize_RevertsWhenDefaultAdminZero() public {
        FundsDistributor freshImpl = new FundsDistributor();
        bytes memory init = abi.encodeCall(FundsDistributor.initialize, (address(0), upgrader, distributorWallet));
        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        new ERC1967Proxy(address(freshImpl), init);
    }

    function test_Initialize_RevertsWhenUpgraderZero() public {
        FundsDistributor freshImpl = new FundsDistributor();
        bytes memory init = abi.encodeCall(FundsDistributor.initialize, (admin, address(0), distributorWallet));
        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        new ERC1967Proxy(address(freshImpl), init);
    }

    function test_Initialize_RevertsWhenDistributorZero() public {
        FundsDistributor freshImpl = new FundsDistributor();
        bytes memory init = abi.encodeCall(FundsDistributor.initialize, (admin, upgrader, address(0)));
        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        new ERC1967Proxy(address(freshImpl), init);
    }

    function test_Initialize_CannotRunTwice() public {
        vm.expectRevert(Initializable.InvalidInitialization.selector);
        distributor.initialize(admin, upgrader, distributorWallet);
    }

    function test_AddToken_ApprovesWhenNameMatches() public {
        MockERC20 token = new MockERC20("Test Coin", "TC");
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Test Coin", address(token));
        assertTrue(distributor.approvedToken(address(token)));
    }

    function test_AddToken_RevertsWhenNameMismatch() public {
        MockERC20 token = new MockERC20("Test Coin", "TC");
        vm.expectRevert(
            abi.encodeWithSelector(FundsDistributor.TokenNameMismatch.selector, "Wrong Name", "Test Coin")
        );
        vm.prank(admin);
        distributor.addToken("Wrong Name", address(token));
    }

    function test_AddToken_RevertsWhenTokenZero() public {
        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        vm.prank(admin);
        distributor.addToken("x", address(0));
    }

    function test_AddToken_RevertsWhenNotAdmin() public {
        MockERC20 token = new MockERC20("Test Coin", "TC");
        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControl.AccessControlUnauthorizedAccount.selector,
                outsider,
                distributor.DEFAULT_ADMIN_ROLE()
            )
        );
        vm.prank(outsider);
        distributor.addToken("Test Coin", address(token));
    }

    function test_RemoveToken_ClearsApproval() public {
        MockERC20 token = new MockERC20("Test Coin", "TC");
        vm.startPrank(admin);
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        distributor.addToken("Test Coin", address(token));
        assertTrue(distributor.approvedToken(address(token)));
        vm.expectEmit(true, false, false, false, address(distributor));
        emit TokenRemoved(address(token));
        distributor.removeToken(address(token));
        vm.stopPrank();
        assertFalse(distributor.approvedToken(address(token)));
    }

    function test_RemoveToken_RevertsWhenTokenZero() public {
        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        vm.prank(admin);
        distributor.removeToken(address(0));
    }

    function test_Distribute_TransfersFromCallerToRecipients() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        address alice = address(0xA1);
        address bob = address(0xA2);

        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        uint256 amount = 300e18;
        token.mint(distributorWallet, amount);
        vm.prank(distributorWallet);
        token.approve(address(distributor), amount);

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](2);
        recipients[0] = FundsDistributor.Recipient({addr: alice, amount: 100e18});
        recipients[1] = FundsDistributor.Recipient({addr: bob, amount: 200e18});

        vm.expectEmit(true, false, false, true, address(distributor));
        emit Distributed(address(token), 300e18, 2);
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);

        assertEq(token.balanceOf(alice), 100e18);
        assertEq(token.balanceOf(bob), 200e18);
        assertEq(token.balanceOf(distributorWallet), 0);
    }

    function test_Distribute_RevertsWhenTokenNotApproved() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0xC0), amount: 1});

        vm.expectRevert(FundsDistributor.TokenNotApproved.selector);
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);
    }

    function test_Distribute_RevertsWhenRecipientZero() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0), amount: 1e18});

        vm.expectRevert(FundsDistributor.ZeroAddress.selector);
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);
    }

    function test_Distribute_RevertsWhenAmountZero() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0xC0), amount: 0});

        vm.expectRevert(FundsDistributor.ZeroAmount.selector);
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);
    }

    function test_Distribute_RevertsWhenCallerLacksDistributeRole() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0xC0), amount: 1e18});

        vm.expectRevert(
            abi.encodeWithSelector(
                IAccessControl.AccessControlUnauthorizedAccount.selector,
                outsider,
                distributor.DISTRIBUTE_ROLE()
            )
        );
        vm.prank(outsider);
        distributor.distribute(address(token), recipients);
    }

    function test_Distribute_RevertsWhenIncorrectAllowance() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        vm.expectEmit(true, false, false, true, address(distributor));
        emit TokenAdded(address(token));
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        token.mint(distributorWallet, 100e18);
        vm.prank(distributorWallet);
        token.approve(address(distributor), 50e18);

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0xC0), amount: 100e18});

        vm.expectRevert(
            abi.encodeWithSelector(FundsDistributor.IncorrectAllowance.selector, uint256(50e18), uint256(100e18))
        );
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);
    }

    function test_Distribute_RevertsWhenInsufficientBalance() public {
        MockERC20 token = new MockERC20("Pay Token", "PAY");
        vm.prank(admin);
        distributor.addToken("Pay Token", address(token));

        // Approve the full amount but only mint half.
        token.mint(distributorWallet, 50e18);
        vm.prank(distributorWallet);
        token.approve(address(distributor), 100e18);

        FundsDistributor.Recipient[] memory recipients = new FundsDistributor.Recipient[](1);
        recipients[0] = FundsDistributor.Recipient({addr: address(0xC0), amount: 100e18});

        vm.expectRevert(
            abi.encodeWithSelector(FundsDistributor.InsufficientBalance.selector, uint256(50e18), uint256(100e18))
        );
        vm.prank(distributorWallet);
        distributor.distribute(address(token), recipients);
    }

    function test_GetApprovedTokens_ReturnsEmptyInitially() public view {
        assertEq(distributor.getApprovedTokens().length, 0);
    }

    function test_GetApprovedTokens_ReflectsAddAndRemove() public {
        MockERC20 tokenA = new MockERC20("Token A", "A");
        MockERC20 tokenB = new MockERC20("Token B", "B");
        MockERC20 tokenC = new MockERC20("Token C", "C");

        vm.startPrank(admin);
        distributor.addToken("Token A", address(tokenA));
        distributor.addToken("Token B", address(tokenB));
        distributor.addToken("Token C", address(tokenC));

        address[] memory tokens = distributor.getApprovedTokens();
        assertEq(tokens.length, 3);
        assertEq(tokens[0], address(tokenA));
        assertEq(tokens[1], address(tokenB));
        assertEq(tokens[2], address(tokenC));

        // Remove the middle token; order changes (swap-and-pop moves C into B's slot).
        distributor.removeToken(address(tokenB));
        vm.stopPrank();

        tokens = distributor.getApprovedTokens();
        assertEq(tokens.length, 2);
        assertTrue(tokens[0] == address(tokenA) || tokens[0] == address(tokenC));
        assertTrue(tokens[1] == address(tokenA) || tokens[1] == address(tokenC));
        assertFalse(distributor.approvedToken(address(tokenB)));
    }
}
