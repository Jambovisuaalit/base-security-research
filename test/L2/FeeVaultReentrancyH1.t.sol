// SPDX-License-Identifier: MIT
pragma solidity 0.8.15;

import { BaseFeeVault_Uncategorized_Test } from "test/L2/BaseFeeVault.t.sol";
import { IFeeVault } from "interfaces/L2/IFeeVault.sol";
import { Types } from "src/libraries/Types.sol";

/// @notice Test-only recipient; no mainnet interaction.
contract H1ReenteringFeeRecipient {
    IFeeVault public immutable vault;
    bool public attempted;
    bool public succeeded;
    bool public reverted;

    constructor(IFeeVault _vault) {
        vault = _vault;
    }

    receive() external payable {
        if (!attempted) {
            attempted = true;
            try vault.withdraw() returns (uint256) {
                succeeded = true;
            } catch {
                reverted = true;
            }
        }
    }
}

contract FeeVaultReentrancyH1_Test is BaseFeeVault_Uncategorized_Test {
    function test_H1_reentrantWithdrawalCannotDoubleCount() public {
        H1ReenteringFeeRecipient receiver = new H1ReenteringFeeRecipient(feeVault);

        vm.startPrank(proxyAdminOwner);
        feeVault.setRecipient(address(receiver));
        feeVault.setWithdrawalNetwork(Types.WithdrawalNetwork.L2);
        feeVault.setMinWithdrawalAmount(1);
        vm.stopPrank();

        uint256 amount = 1 ether;
        uint256 beforeProcessed = feeVault.totalProcessed();
        vm.deal(address(feeVault), amount);

        uint256 paid = feeVault.withdraw();
        assertEq(paid, amount, "outer withdrawal incorrect");
        assertTrue(receiver.attempted(), "reentry not attempted");
        assertFalse(receiver.succeeded(), "unexpected reentry success");
        assertTrue(receiver.reverted(), "reentry should revert");
        assertEq(address(receiver).balance, amount, "recipient balance incorrect");
        assertEq(address(feeVault).balance, 0, "vault not emptied");
        assertEq(feeVault.totalProcessed(), beforeProcessed + amount, "accounting mismatch");
    }
}
