// Copyright (c) Whatgame Studios 2026
// SPDX-License-Identifier: PROPRIETARY
pragma solidity ^0.8.26;

import "forge-std/Script.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {FundsDistributor} from "../src/FundsDistributor.sol";

contract FundsDistributorScript is Script {
    function deploy() public {
        address deployer = vm.envAddress("DEPLOYER_ADDRESS");
        address roleAdmin = deployer;
        address upgradeAdmin = deployer;
        address distributorAdmin = deployer;

        vm.broadcast();
        FundsDistributor impl = new FundsDistributor();
        bytes memory initData =
            abi.encodeWithSelector(FundsDistributor.initialize.selector, roleAdmin, upgradeAdmin, distributorAdmin);

        vm.broadcast();
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);

        console.log("Proxy address: ", address(proxy));
        console.log("Implementation address: ", address(impl));
    }
}
