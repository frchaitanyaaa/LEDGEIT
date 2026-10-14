"""Blockchain access for anchoring and verification (web3.py), plus an in-memory chain for tests."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from ..core.config import REPO_ROOT, get_settings

ABI_FILE = REPO_ROOT / "contracts" / "abi" / "LedgeitAnchor.json"
EXPLORERS = {80002: "https://amoy.polygonscan.com"}
NETWORKS = {"local": ("hardhat-local", 31337, "localhost"), "amoy": ("polygon-amoy", 80002, "amoy")}


@dataclass
class TxResult:
    tx_hash: str
    block_number: int
    block_timestamp: datetime
    gas_used: int
    effective_gas_price_wei: int

    @property
    def fee_native(self) -> Decimal:
        return Decimal(self.gas_used * self.effective_gas_price_wei) / Decimal(10**18)


@dataclass
class OnchainAnchor:
    timestamp: datetime
    block_number: int
    leaf_count: int
    risk_level: int


class AlreadyAnchored(Exception):
    pass


class ChainClient(Protocol):
    network: str
    chain_id: int
    contract_address: str

    def anchor(self, root_hex: str, batch_id: int, leaf_count: int, risk_level: int) -> TxResult: ...
    def get_anchor(self, root_hex: str) -> OnchainAnchor | None: ...
    def find_anchor_tx(self, root_hex: str) -> TxResult | None: ...
    def explorer_tx_url(self, tx_hash: str) -> str | None: ...


def _abi() -> dict:
    return json.loads(ABI_FILE.read_text())


class Web3Chain:
    def __init__(self, rpc_url: str, private_key: str, contract_address: str, network: str, chain_id: int):
        from eth_account import Account
        from web3 import Web3

        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
        self.account = Account.from_key(private_key) if private_key else None
        self.network, self.chain_id = network, chain_id
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=_abi()["abi"])
        self._lock = threading.Lock()

    @staticmethod
    def deploy(rpc_url: str, private_key: str) -> str:
        from eth_account import Account
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        acct = Account.from_key(private_key)
        art = _abi()
        c = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
        tx = c.constructor().build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address, "pending"),
            "chainId": w3.eth.chain_id,
        })
        h = w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
        return r.contractAddress

    def _tx_result(self, receipt) -> TxResult:
        block = self.w3.eth.get_block(receipt.blockNumber)
        return TxResult(
            tx_hash="0x" + bytes(receipt.transactionHash).hex().removeprefix("0x"),
            block_number=receipt.blockNumber,
            block_timestamp=datetime.fromtimestamp(block.timestamp, timezone.utc),
            gas_used=receipt.gasUsed,
            effective_gas_price_wei=int(receipt.get("effectiveGasPrice", 0) or 0),
        )

    def anchor(self, root_hex: str, batch_id: int, leaf_count: int, risk_level: int) -> TxResult:
        if not self.account:
            raise RuntimeError("ANCHOR_PRIVATE_KEY not configured")
        if self.get_anchor(root_hex):
            raise AlreadyAnchored(root_hex)
        with self._lock:
            fn = self.contract.functions.anchor(bytes.fromhex(root_hex), batch_id, leaf_count, risk_level)
            tx = fn.build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address, "pending"),
                "chainId": self.chain_id,
            })
            h = self.w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if receipt.status != 1:
            raise RuntimeError(f"anchor tx reverted: {h.hex()}")
        return self._tx_result(receipt)

    def get_anchor(self, root_hex: str) -> OnchainAnchor | None:
        ts, bn, leaves, risk = self.contract.functions.anchors(bytes.fromhex(root_hex)).call()
        if ts == 0:
            return None
        return OnchainAnchor(datetime.fromtimestamp(ts, timezone.utc), bn, leaves, risk)

    def find_anchor_tx(self, root_hex: str) -> TxResult | None:
        a = self.get_anchor(root_hex)
        if not a:
            return None
        logs = self.contract.events.RootAnchored().get_logs(
            from_block=a.block_number, to_block=a.block_number, argument_filters={"root": bytes.fromhex(root_hex)})
        if not logs:
            return None
        return self._tx_result(self.w3.eth.get_transaction_receipt(logs[0].transactionHash))

    def explorer_tx_url(self, tx_hash: str) -> str | None:
        base = EXPLORERS.get(self.chain_id)
        return f"{base}/tx/{tx_hash}" if base else None

    def anchor_count(self) -> int:
        return int(self.contract.functions.anchorCount().call())


class MemoryChain:
    """Deterministic in-memory stand-in for the contract (tests, CHAIN=memory)."""

    network, chain_id, contract_address = "memory", 1337, "0x" + "11" * 20

    def __init__(self) -> None:
        self.anchors: dict[str, tuple[OnchainAnchor, TxResult]] = {}
        self.block = 100
        self.fail_next = 0

    def anchor(self, root_hex: str, batch_id: int, leaf_count: int, risk_level: int) -> TxResult:
        if self.fail_next:
            self.fail_next -= 1
            raise RuntimeError("simulated RPC failure")
        if root_hex in self.anchors:
            raise AlreadyAnchored(root_hex)
        self.block += 1
        now = datetime.now(timezone.utc)
        tx = TxResult("0x" + format(self.block, "064x"), self.block, now, 71869, 30 * 10**9)
        self.anchors[root_hex] = (OnchainAnchor(now, self.block, leaf_count, risk_level), tx)
        return tx

    def get_anchor(self, root_hex: str) -> OnchainAnchor | None:
        a = self.anchors.get(root_hex)
        return a[0] if a else None

    def find_anchor_tx(self, root_hex: str) -> TxResult | None:
        a = self.anchors.get(root_hex)
        return a[1] if a else None

    def explorer_tx_url(self, tx_hash: str) -> str | None:
        return None

    def anchor_count(self) -> int:
        return len(self.anchors)


_override: ChainClient | None = None


def set_chain(c: ChainClient | None) -> None:
    """Inject a chain client (tests)."""
    global _override
    _override = c
    get_chain.cache_clear()


def deployment_file(network_key: str) -> Path:
    return get_settings().deployments_dir / f"{network_key}.json"


def resolve_contract_address(chain: str) -> str | None:
    s = get_settings()
    if s.contract_address:
        return s.contract_address
    f = deployment_file(NETWORKS[chain][2])
    if f.exists():
        return json.loads(f.read_text())["address"]
    return None


@lru_cache
def get_chain() -> ChainClient | None:
    if _override is not None:
        return _override
    s = get_settings()
    if s.chain not in NETWORKS:
        return None
    network, chain_id, _ = NETWORKS[s.chain]
    addr = resolve_contract_address(s.chain)
    if not addr:
        return None
    rpc = s.rpc_url_local if s.chain == "local" else s.rpc_url_amoy
    return Web3Chain(rpc, s.anchor_private_key, addr, network, chain_id)


def ensure_local_deployment(wait_seconds: int = 60) -> str:
    """For CHAIN=local: deploy the contract to the Hardhat node if no deployment is recorded."""
    s = get_settings()
    addr = resolve_contract_address("local")
    from web3 import Web3

    deadline = time.time() + wait_seconds
    w3 = Web3(Web3.HTTPProvider(s.rpc_url_local))
    while not w3.is_connected():
        if time.time() > deadline:
            raise RuntimeError(f"Hardhat node not reachable at {s.rpc_url_local}")
        time.sleep(1)
    if addr and w3.eth.get_code(Web3.to_checksum_address(addr)) not in (b"", b"\x00"):
        return addr
    addr = Web3Chain.deploy(s.rpc_url_local, s.anchor_private_key)
    f = deployment_file("localhost")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"network": "localhost", "chainId": 31337, "address": addr,
                             "deployedAt": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n")
    get_chain.cache_clear()
    return addr
