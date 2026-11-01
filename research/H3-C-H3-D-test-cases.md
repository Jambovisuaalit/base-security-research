# H3-C and H3-D — local fork acceptance cases

Status: SPECIFIED / NOT EXECUTED. No vulnerability confirmed.

Pinned Base block: 53374803. Local RPC only: http://127.0.0.1:8545.

## H3-C: bridge revert atomicity

Use a snapshot of the pinned fork. On the **local fork only**, replace the L2StandardBridge runtime at 0x4200000000000000000000000000000000000010 with an unconditional revert stub. Advance local time beyond the FeeDisburser interval, then call `disburseFees()` with a fixed gas limit so a reverted transaction is mined. Assert receipt status 0, unchanged `lastDisbursementTime`, unchanged vault `totalProcessed`, unchanged FeeDisburser balance, and unchanged Sequencer/L1 vault balances. Permit only separately measured L2 gas-fee accrual in BaseFeeVault. Restore snapshot.

## H3-D1: no eligible vault

Restore pristine snapshot. Set all three main vault balances and FeeDisburser balance to zero **locally only**. Advance local time past interval. Call `disburseFees()`. Assert receipt status 1, exactly one `NoFeesCollected` event, unchanged lastDisbursementTime and `totalProcessed`, and zero FeeDisburser balance. Restore snapshot.

## H3-D2: exactly one eligible vault

Restore pristine snapshot. Set SequencerFeeVault balance to 3 ETH, BaseFeeVault and L1FeeVault balances to zero, and FeeDisburser balance to zero **locally only**. Advance local time. Call `disburseFees()`. Assert receipt status 1, exactly one FeeDisburser `FeesReceived` event from SequencerFeeVault for 3 ETH, exactly 3 ETH increase in its `totalProcessed`, unchanged other vault counters, one L2StandardBridge `ETHBridgeInitiated` for 3 ETH, correct configured L1 wallet recipient, and FeeDisburser balance zero. Restore snapshot.

## Guardrails

No mainnet writes. Synthetic bridge code and synthetic balances must be labelled; these are fault-injection tests, not actual mainnet conditions. Capture receipts, state deltas, emitted logs, pinned block hash, and assertions in GitHub Actions artifacts. An L2 bridge initiation does not verify final L1 settlement.
