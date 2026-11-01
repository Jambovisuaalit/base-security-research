# H3-A / H3-B fork validation — PASS (2026-11-01)

**Status:** H3-A and H3-B tested scenarios **PASS**; H3 overall remains **OPEN** for H3-C/H3-D and L1 settlement verification. No demonstrated vulnerability or bounty candidate.

## Reproduction
- Repository: `Jambovisuaalit/base-security-research`
- Test script: [scripts/h3_fork_validate.py](../scripts/h3_fork_validate.py)
- Workflow: [.github/workflows/h3-a-h3-b-fork.yml](../.github/workflows/h3-a-h3-b-fork.yml)
- [Successful GitHub Actions run #41316121377](https://github.com/Jambovisuaalit/base-security-research/actions/runs/41316121377)
- [Evidence ZIP artifact #13087501250](https://github.com/Jambovisuaalit/base-security-research/actions/runs/41316121377/artifacts/13087501250)
- Artifact SHA-256: `b545316d63d5f3bf532962d0be494aa8be7354ceee77629ded6c40c5d9522838`
- Commit tested: `e45699bd6f2bbb253d10365e7fd5c51b1e1f30f8`.
- Chain 8453, Base mainnet fork pinned at block `53374803`, hash `0x2026ed0fd54db46322e1c9a4db49b299603093cc4e7c601f57a73e20772c19cf`.
- **All transactions were LOCAL Anvil fork transactions; no live Base transaction was sent.**

## H3-A — withdrawal interval
- `FEE_DISBURSEMENT_INTERVAL`: `86400` seconds.
- `lastDisbursementTime` before: `1793446545`.
- Local fork test timestamp: `1793538955`.
- First unprivileged `disburseFees()` transaction succeeded.
- Immediate second `eth_call` reverted, consistent with interval enforcement.
- Note: second attempt was a read-only `eth_call` at current block, not a second mined transaction.

## H3-B — conservation and recipient routing
- Initial FeeDisburser balance: **0 wei**.
- SequencerFeeVault collected: **10,769,752,562,918,694,317 wei**.
- BaseFeeVault collected: **5,458,957,002,828,359,002 wei**.
- L1FeeVault: below minimum; not withdrawn.
- Total `FeesDisbursed` event: **16,228,709,565,747,053,319 wei**.
- `ETHBridgeInitiated` value: **16,228,709,565,747,053,319 wei**.
- Configured `L1_WALLET` and bridge event recipient: `0x23B597f33f6f2621F77DA117523Dffd634cDf4ea`.
- FeeDisburser post-transaction balance: **0 wei**.
- For participating vaults, `totalProcessed` increments matched collected amounts exactly.

## Limits and decision
- The validation checks one unmodified pinned deployment state and one locally advanced timestamp; it is not an exhaustive security proof.
- L2 bridge initiation is **not** evidence of L1 finalized receipt.
- The interval test does not establish impossibility of other authorization or reentrancy paths.
- **H3-A and H3-B: PASS / NO-GO bounty report based on tested scenarios.**
- **H3 overall: OPEN**, with H3-C (atomicity and revert behavior) and H3-D (empty/threshold cases) still unverified.

## Next actions
1. Implement H3-C synthetic reverting-bridge atomicity tests with explicit synthetic labels; verify vault balance and timestamp rollback.
2. Implement H3-D no-fees and one-vault-eligible cases on local forks only.
3. If L1 settlement is in scope, separately verify the corresponding real historic bridge finalization with L1 evidence; never infer it from local L2 fork logs.
