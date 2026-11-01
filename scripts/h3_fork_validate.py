#!/usr/bin/env python3
"""H3-A/H3-B read-only-source, LOCAL Anvil fork validation; never sends to public RPC."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

RPC = "http://127.0.0.1:8545"
BLOCK = 53374803
FEE = "0x09C7bAD99688a55a2e83644BFAed09e62bDcCcBA"
BRIDGE = "0x4200000000000000000000000000000000000010"
VAULTS = [
    "0x4200000000000000000000000000000000000011",
    "0x4200000000000000000000000000000000000019",
    "0x420000000000000000000000000000000000001a",
]
DEV_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
OUT = Path("evidence/h3")
OUT.mkdir(parents=True, exist_ok=True)

def rpc(method, params=None):
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params or []}).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = json.load(response)
    if "error" in data:
        raise RuntimeError(f"{method}: {data['error']}")
    return data["result"]

def cast(*args):
    return subprocess.check_output(["cast", *args, "--rpc-url", RPC], text=True).strip()

def getter(addr, sig):
    return cast("call", addr, sig).split()[0]

def bal(addr):
    return int(rpc("eth_getBalance", [addr, "latest"]), 16)

def topic(sig):
    return subprocess.check_output(["cast", "keccak", sig], text=True).strip().lower()

def check(cond, message):
    if not cond:
        raise AssertionError(message)

def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2) + "\n")

def main():
    check(int(rpc("eth_chainId"), 16) == 8453, "wrong chain")
    check(int(rpc("eth_blockNumber"), 16) == BLOCK, "wrong fork block")
    parent = rpc("eth_getBlockByNumber", ["latest", False])
    check(int(parent["number"], 16) == BLOCK, "unpinned fork")
    last = int(getter(FEE, "lastDisbursementTime()(uint256)"))
    interval = int(getter(FEE, "FEE_DISBURSEMENT_INTERVAL()(uint256)"))
    wallet = getter(FEE, "L1_WALLET()(address)")
    check(int(wallet, 16) != 0, "zero L1 wallet")
    check(interval >= 86400, "unexpected interval")
    minimum = {}
    before_vault = {}
    before_processed = {}
    for v in VAULTS:
        check(getter(v, "RECIPIENT()(address)").lower() == FEE.lower(), "vault recipient mismatch")
        check(int(getter(v, "WITHDRAWAL_NETWORK()(uint8)")) == 1, "vault network mismatch")
        minimum[v.lower()] = int(getter(v, "MIN_WITHDRAWAL_AMOUNT()(uint256)"))
        before_vault[v.lower()] = bal(v)
        before_processed[v.lower()] = int(getter(v, "totalProcessed()(uint256)"))
    initial_fee = bal(FEE)
    # Set local fork time to the first valid interval boundary; no public network writes.
    target = max(int(parent["timestamp"], 16) + 2, last + interval + 2)
    rpc("evm_setNextBlockTimestamp", [target])
    receipt = json.loads(cast("send", FEE, "disburseFees()", "--private-key", DEV_KEY, "--json"))
    dump("disburse-receipt.json", receipt)
    check(int(receipt["status"], 16) == 1, "disbursement transaction reverted")
    check(int(getter(FEE, "lastDisbursementTime()(uint256)")) == target, "timestamp not advanced")
    # A: a second immediate call must be blocked by the interval guard.
    call_data = subprocess.check_output(["cast", "calldata", "disburseFees()"], text=True).strip()
    second_reverted = False
    try:
        rpc("eth_call", [{"to": FEE, "data": call_data}, "latest"])
    except RuntimeError as exc:
        second_reverted = True
        (OUT / "second-call-revert.txt").write_text(str(exc) + "\n")
    check(second_reverted, "second call within interval unexpectedly succeeded")
    # B: event-based conservation and real accounting deltas, no reliance on vault balance == 0.
    received_topic = topic("FeesReceived(address,uint256)")
    disbursed_topic = topic("FeesDisbursed(uint256,uint256,uint256)")
    bridge_topic = topic("ETHBridgeInitiated(address,address,uint256,bytes)")
    received = {}
    disbursed = []
    bridge_events = []
    for log in receipt["logs"]:
        topics = [t.lower() for t in log["topics"]]
        if log["address"].lower() == FEE.lower() and topics[0] == received_topic:
            sender = "0x" + topics[1][-40:]
            received[sender] = received.get(sender, 0) + int(log["data"], 16)
        if log["address"].lower() == FEE.lower() and topics[0] == disbursed_topic:
            data = bytes.fromhex(log["data"][2:])
            check(len(data) >= 96, "short FeesDisbursed event")
            disbursed.append([int.from_bytes(data[i:i+32], "big") for i in (0,32,64)])
        if log["address"].lower() == BRIDGE.lower() and topics[0] == bridge_topic:
            bridge_events.append(log)
    eligible = {v.lower(): before_vault[v.lower()] for v in VAULTS if before_vault[v.lower()] >= minimum[v.lower()]}
    check(received == eligible, f"FeeDisburser receive mismatch: {received} != {eligible}")
    for v in VAULTS:
        key = v.lower()
        delta = int(getter(v, "totalProcessed()(uint256)")) - before_processed[key]
        check(delta == eligible.get(key, 0), f"processed mismatch for {v}: {delta}")
    expected = initial_fee + sum(eligible.values())
    check(len(disbursed) == 1, "expected one FeesDisbursed event")
    check(disbursed[0] == [target, 0, expected], f"FeesDisbursed mismatch: {disbursed}")
    check(bal(FEE) == 0, "FeeDisburser residual ETH after bridge")
    check(len(bridge_events) == 1, "expected exactly one ETHBridgeInitiated event")
    bridge_event = bridge_events[0]
    check(len(bridge_event["topics"]) >= 3, "bridge event missing indexed addresses")
    bridge_to = "0x" + bridge_event["topics"][2][-40:]
    check(bridge_to.lower() == wallet.lower(), "L1 bridge target mismatch")
    # ETHBridgeInitiated event data is ABI-encoded (uint256 amount, bytes extraData).
    amount = int(bridge_event["data"][2:66], 16)
    check(amount == expected, f"bridge event amount mismatch: {amount} != {expected}")
    result = {
        "status": "PASS", "scope": "LOCAL_ANVIL_ONLY", "pinned_block": BLOCK,
        "pinned_block_hash": parent["hash"], "test_timestamp": target,
        "interval_seconds": interval, "last_disbursement_before": last,
        "second_call_reverted": second_reverted, "l1_wallet": wallet,
        "initial_disburser_wei": initial_fee, "vault_withdrawals_wei": eligible,
        "fees_disbursed_wei": expected, "bridge_initiated_wei": amount,
        "bridge_target": bridge_to, "final_disburser_wei": bal(FEE),
        "caveat": "L2 bridge initiation only; L1 final settlement NOT verified",
    }
    dump("assertions.json", result)
    print("PASS H3-A/H3-B: " + json.dumps(result))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        (OUT / "failure.txt").write_text(f"{type(exc).__name__}: {exc}\n")
        raise
