# H3 — FeeDisburser and ETH fee-routing research plan

Status: **OPEN / HYPOTHESES ONLY**. No vulnerability confirmed. Date: 2026-11-01.

## Ground truth
Pinned Base mainnet block: **53,374,803**. FeeDisburser proxy: `0x09C7bAD99688a55a2e83644BFAed09e62bDcCcBA`; implementation: `0x72984fef9c2123ebb66912ceab9e47c5e9b738e6`. Main vaults: Sequencer `0x4200000000000000000000000000000000000011`, Base `0x4200000000000000000000000000000000000019`, L1 `0x420000000000000000000000000000000000001a`. L2StandardBridge predeploy: `0x4200000000000000000000000000000000000010`.

Verified FeeDisburser source (BaseScan/Etherscan, chain 8453): `disburseFees()` checks `block.timestamp >= lastDisbursementTime + FEE_DISBURSEMENT_INTERVAL`; calls three vaults; records `feeBalance = address(this).balance`; returns with `NoFeesCollected` if zero; otherwise updates timestamp and calls `bridgeETHTo{value: address(this).balance}(L1_WALLET, 35000, bytes(""))`. Each vault is checked for L2 withdrawal and matching recipient before calling `withdraw()` if its balance meets minimum. `receive()` only emits `FeesReceived`.

## Evidence to collect (read-only; all at same block)
- `L1_WALLET()(address)`, `FEE_DISBURSEMENT_INTERVAL()(uint256)`, `lastDisbursementTime()(uint256)`, `netFeeRevenue()(uint256)` (deprecated, never use as financial truth), `version()(string)`.
- FeeDisburser balance; three vault balances and minima; L2StandardBridge code, EIP-1967 implementation slot and verified source.
- Record implementation addresses, proxy admins, block hash, and readout artifact. Validate getters and signatures against verified ABI.

## Hypotheses and tests
### H3-A — interval and caller boundary
- Local fork: before interval, `disburseFees()` must revert `IntervalNotReached` and preserve all relevant balances/storage.
- At/after interval, a normal unprivileged caller can execute it (permissionless by design). Two calls within one interval must not double-disburse.
- If the zero-fees path leaves the timestamp unchanged, document whether repeated calls cause any actual adverse effect; do not label gas cost or event spam as vulnerability without impact.

### H3-B — conservation of ETH
- Record vault balances, FeeDisburser balance, bridge balance, relevant L2ToL1MessagePasser state/events and emitted `FeesDisbursed` before/after.
- Assert vault withdrawal deltas equal FeeDisburser `FeesReceived` events, allowing for new L2 fee accrual in BaseFeeVault.
- Assert amount sent to bridge matches the FeeDisburser balance immediately before bridge call; assert only the configured `L1_WALLET` is the target.
- Distinguish L2 bridge initiation from completed L1 settlement: **do not claim L1 receipt from an L2-only fork**.

### H3-C — bridge failure / atomicity
- Local isolated tests with a reverting bridge stub or mock (explicitly labelled synthetic), checking whether entire disbursement rolls back including vault withdrawals and timestamp.
- On unmodified fork, test only legitimate paths. Do not mutate mainnet.

### H3-D — zero fees / threshold edge cases
- All vaults below threshold, FeeDisburser empty: expect `NoFeesCollected` and no bridge.
- One vault above threshold and others below: expect only eligible vault withdrawal.
- Clearly distinguish synthetic balance manipulation from deployed mainnet configuration.

## Execution guardrails
- Never broadcast transactions to Base mainnet.
- Use `anvil --fork-url https://mainnet.base.org --fork-block-number 53374803` and send only to `http://127.0.0.1:8545`.
- Assert receipt status before accounting assertions; avoid `vault balance == 0` because transaction fees accrue.
- Save complete receipts, events, pinned block, implementation metadata, and assertion results as GitHub Actions artifacts.
- Any bounty candidate requires a permissionless exploit and independently reproduced economic impact.

## Exit criteria
PASS: all actual fork invariants hold and no permissionless redirection/double-withdrawal identified -> **NO-GO**.
ESCALATE: reproducible permissionless deviation with quantified asset impact, independently validated, without privileged assumptions -> investigate eligibility before any report.

## Prior evidence
- [H2-C closure](H2-C-closure-2026-11-01.md)
- [Mainnet read-only audit](https://github.com/Jambovisuaalit/base-security-research/actions/runs/41311869150)
- [H2-C local fork PASS](https://github.com/Jambovisuaalit/base-security-research/actions/runs/41314291412)
