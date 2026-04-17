"""
HYDRA Arm 3 — Treasury Yield Manager

Programmatic DeFi yield generation on idle USDC via Aave V3 on Base L2.

When HYDRA's treasury balance exceeds the operating reserve, excess USDC
is deposited into Aave's USDC lending pool to earn yield (currently 5-12% APY).
Funds can be withdrawn instantly for remittance or operating expenses.

This implements the "compound revenue engine" capitalism model:
  API revenue → treasury → Aave yield → more treasury → more yield

Addresses (Base mainnet):
  USDC:           0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
  Aave Pool:      0xA238Dd80C259a72e81d7e4664a9801593F98d1c5
  aBaseUSDC:      0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB

Safety constraints:
  - Only deposits USDC (stablecoin, no impermanent loss risk)
  - Only uses Aave V3 (battle-tested, $14.6B TVL)
  - Maintains operating reserve ($500 USDC minimum never deposited)
  - Withdraws automatically when remittance is triggered
  - All operations are reversible (instant withdraw from Aave)
  - No leverage, no borrowing, no exotic strategies
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Optional

from web3 import Web3

logger = logging.getLogger("hydra.treasury_yield")

AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
AUSDC_ADDRESS = "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6

OPERATING_RESERVE = Decimal("500")
MIN_DEPOSIT = Decimal("50")

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]

AAVE_POOL_ABI = [
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "referralCode", "type": "uint16"},
        ],
        "name": "supply",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "to", "type": "address"},
        ],
        "name": "withdraw",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


class TreasuryYieldManager:
    """
    Manages USDC yield generation via Aave V3 on Base.

    Called by the automaton heartbeat to check if excess funds
    should be deposited or if funds need to be withdrawn.
    """

    def __init__(
        self,
        w3: Web3,
        wallet_address: str,
        private_key: str,
    ) -> None:
        self.w3 = w3
        self.wallet_address = Web3.to_checksum_address(wallet_address)
        self._private_key = private_key

        self.usdc = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI,
        )
        self.ausdc = w3.eth.contract(
            address=Web3.to_checksum_address(AUSDC_ADDRESS),
            abi=ERC20_ABI,
        )
        self.aave_pool = w3.eth.contract(
            address=Web3.to_checksum_address(AAVE_POOL_ADDRESS),
            abi=AAVE_POOL_ABI,
        )

        self._enabled = True
        self._total_deposited = Decimal("0")
        self._total_yield_earned = Decimal("0")

    def get_aave_balance(self) -> Decimal:
        """Get current aUSDC balance (USDC deposited + yield earned)."""
        try:
            raw = self.ausdc.functions.balanceOf(self.wallet_address).call()
            return Decimal(raw) / Decimal(10**USDC_DECIMALS)
        except Exception as exc:
            logger.warning("Failed to query aUSDC balance: %s", exc)
            return Decimal("0")

    def get_depositable_amount(self, wallet_balance: Decimal) -> Decimal:
        """
        Calculate how much USDC can be deposited while maintaining
        the operating reserve.
        """
        excess = wallet_balance - OPERATING_RESERVE
        if excess < MIN_DEPOSIT:
            return Decimal("0")
        return excess

    async def deposit_to_aave(self, amount: Decimal) -> Optional[str]:
        """
        Deposit USDC into Aave V3 lending pool.

        Returns the transaction hash on success, None on failure.
        """
        if amount < MIN_DEPOSIT:
            logger.info("Deposit amount $%s below minimum $%s — skipping", amount, MIN_DEPOSIT)
            return None

        amount_raw = int(amount * Decimal(10**USDC_DECIMALS))

        try:
            current_allowance = self.usdc.functions.allowance(
                self.wallet_address,
                Web3.to_checksum_address(AAVE_POOL_ADDRESS),
            ).call()

            if current_allowance < amount_raw:
                logger.info("Approving Aave pool to spend %s USDC...", amount)
                approve_tx = self.usdc.functions.approve(
                    Web3.to_checksum_address(AAVE_POOL_ADDRESS),
                    amount_raw,
                ).build_transaction({
                    "from": self.wallet_address,
                    "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
                    "gas": 100_000,
                    "maxFeePerGas": self.w3.eth.gas_price * 2,
                    "maxPriorityFeePerGas": self.w3.eth.gas_price,
                })
                signed = self.w3.eth.account.sign_transaction(approve_tx, self._private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
                receipt = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                )
                if receipt.status != 1:
                    logger.error("USDC approval failed")
                    return None
                logger.info("USDC approval confirmed: tx=%s", tx_hash.hex())

            supply_tx = self.aave_pool.functions.supply(
                Web3.to_checksum_address(USDC_ADDRESS),
                amount_raw,
                self.wallet_address,
                0,
            ).build_transaction({
                "from": self.wallet_address,
                "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
                "gas": 300_000,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.gas_price,
            })
            signed = self.w3.eth.account.sign_transaction(supply_tx, self._private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            )

            if receipt.status == 1:
                self._total_deposited += amount
                logger.info(
                    "AAVE DEPOSIT SUCCESS: $%s USDC → Aave lending pool (tx=%s). "
                    "Earning yield automatically.",
                    amount, tx_hash.hex(),
                )
                return tx_hash.hex()
            else:
                logger.error("Aave supply transaction reverted: tx=%s", tx_hash.hex())
                return None

        except Exception as exc:
            logger.error("Aave deposit failed: %s", exc)
            return None

    async def withdraw_from_aave(self, amount: Optional[Decimal] = None) -> Optional[str]:
        """
        Withdraw USDC from Aave V3 lending pool.

        If amount is None, withdraws everything (max uint256).
        Returns the transaction hash on success, None on failure.
        """
        if amount is not None:
            amount_raw = int(amount * Decimal(10**USDC_DECIMALS))
        else:
            amount_raw = 2**256 - 1  # type(uint256).max — withdraw all

        try:
            withdraw_tx = self.aave_pool.functions.withdraw(
                Web3.to_checksum_address(USDC_ADDRESS),
                amount_raw,
                self.wallet_address,
            ).build_transaction({
                "from": self.wallet_address,
                "nonce": self.w3.eth.get_transaction_count(self.wallet_address),
                "gas": 300_000,
                "maxFeePerGas": self.w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": self.w3.eth.gas_price,
            })
            signed = self.w3.eth.account.sign_transaction(withdraw_tx, self._private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            )

            if receipt.status == 1:
                logger.info(
                    "AAVE WITHDRAWAL SUCCESS: USDC withdrawn from Aave (tx=%s)",
                    tx_hash.hex(),
                )
                return tx_hash.hex()
            else:
                logger.error("Aave withdraw transaction reverted: tx=%s", tx_hash.hex())
                return None

        except Exception as exc:
            logger.error("Aave withdrawal failed: %s", exc)
            return None

    def get_yield_status(self) -> dict:
        """Return current yield status for monitoring."""
        aave_balance = self.get_aave_balance()
        yield_earned = max(Decimal("0"), aave_balance - self._total_deposited)
        self._total_yield_earned = yield_earned

        return {
            "aave_balance_usdc": str(aave_balance),
            "total_deposited_usdc": str(self._total_deposited),
            "yield_earned_usdc": str(yield_earned),
            "enabled": self._enabled,
            "protocol": "Aave V3",
            "network": "Base L2",
            "strategy": "USDC lending (no leverage, no IL risk)",
        }
