// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

import { BaseFeeVault_Uncategorized_Test } from "test/L2/BaseFeeVault.t.sol";
import { IFeeVault } from "interfaces/L2/IFeeVault.sol";
import { Types } from "src/libraries/Types.sol";

contract H2ZeroThresholdRecipient {
    IFeeVault public immutable vault;
    uint256 public callbacks;
    uint256 public nestedSuccesses;
    uint256 public nestedFailures;
    uint256 public maxReentries;
    bool public recycleFunds;

    constructor(IFeeVault _vault, uint256 _maxReentries, bool _recycleFunds) {
        vault = _vault;
        maxReentries = _maxReentries;
        recycleFunds = _recycleFunds;
    }

    receive() external payable {
        callbacks++;
        if (callbacks > maxReentries) return;
        if (recycleFunds && msg.value > 0) {
            (bool sent,) = address(vault).call{ value: msg.value }("");
            require(sent, "refund failed");
        }
        try vault.withdraw() returns (uint256) {
            nestedSuccesses++;
        } catch {
            nestedFailures++;
        }
    }
}

/// @notice H2: bounded zero-threshold reentry and recycled-funds accounting.
/// @dev Uses the Base test harness; no public chain or live funds.
contract FeeVaultH2_Test is BaseFeeVault_Uncategorized_Test {
    function _configure(address _recipient, uint256 _minimum) internal {
        vm.startPrank(proxyAdminOwner);
        feeVault.setRecipient(_recipient);
        feeVault.setWithdrawalNetwork(Types.WithdrawalNetwork.L2);
        feeVault.setMinWithdrawalAmount(_minimum);
        vm.stopPrank();
    }

    function test_H2_zeroThresholdEmptyVaultAllowsZeroValueReentry() public {
        H2ZeroThresholdRecipient receiver = new H2ZeroThresholdRecipient(feeVault, 3, false);
        _configure(address(receiver), 0);
        vm.deal(address(feeVault), 0);
        uint256 beforeProcessed = feeVault.totalProcessed();

        uint256 paid = feeVault.withdraw();

        assertEq(paid, 0);
        assertEq(receiver.callbacks(), 4, "unexpected callback count");
        assertEq(receiver.nestedSuccesses(), 3, "zero value reentries blocked");
        assertEq(receiver.nestedFailures(), 0);
        assertEq(feeVault.totalProcessed(), beforeProcessed, "zero transfers changed accounting");
        assertEq(address(feeVault).balance, 0);
    }

    function test_H2_positiveThresholdBlocksEmptyVaultReentry() public {
        H2ZeroThresholdRecipient receiver = new H2ZeroThresholdRecipient(feeVault, 1, false);
        _configure(address(receiver), 1);
        vm.deal(address(feeVault), 1 ether);
        uint256 beforeProcessed = feeVault.totalProcessed();

        uint256 paid = feeVault.withdraw();

        assertEq(paid, 1 ether);
        assertEq(receiver.callbacks(), 1);
        assertEq(receiver.nestedSuccesses(), 0);
        assertEq(receiver.nestedFailures(), 1);
        assertEq(feeVault.totalProcessed(), beforeProcessed + 1 ether);
        assertEq(address(receiver).balance, 1 ether);
    }

    function test_H2_recycledEthCountsMultipleWithdrawalsButNoExtraFunds() public {
        H2ZeroThresholdRecipient receiver = new H2ZeroThresholdRecipient(feeVault, 1, true);
        _configure(address(receiver), 0);
        vm.deal(address(feeVault), 1 ether);
        uint256 beforeProcessed = feeVault.totalProcessed();

        uint256 paid = feeVault.withdraw();

        assertEq(paid, 1 ether);
        assertEq(receiver.callbacks(), 2);
        assertEq(receiver.nestedSuccesses(), 1);
        assertEq(receiver.nestedFailures(), 0);
        assertEq(address(receiver).balance, 1 ether, "recipient extracted extra funds");
        assertEq(address(feeVault).balance, 0);
        // The same ETH is withdrawn twice after being returned to the vault.
        // This is processed-volume accounting, not evidence of a net loss.
        assertEq(feeVault.totalProcessed(), beforeProcessed + 2 ether);
    }
}
