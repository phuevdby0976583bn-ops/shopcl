# -*- coding: utf-8 -*-
"""
modules/pow_challenge_engine.py
Nghiên cứu & mô phỏng cơ chế Proof of Work (PoW) & Dynamic Cryptographic Challenge:
1. Sinh bài toán tính toán mật mã (Client Puzzle / Hashcash) có TTL ngắn.
2. Bộ giải nghiệm (Solver) tốn tài nguyên CPU thực tế để triệt tiêu spam đa luồng.
3. Bộ thẩm định (Verifier) kiểm tra độ khó (Difficulty) và chống phát lại (Replay Protection).
"""

import hashlib
import os
import secrets
import time
from typing import Dict, Any, Optional, Tuple


class PoWChallengeEngine:
    """Bộ máy sinh và thẩm định thử thách tính toán Proof of Work (Dynamic Client Puzzle)."""

    def __init__(self, default_difficulty: int = 4, ttl_seconds: int = 20):
        self.default_difficulty = default_difficulty  # Số ký tự 0 hex yêu cầu ở đầu hash
        self.ttl = ttl_seconds
        # Lưu cache challenge đã cấp: {challenge_id: {"salt": str, "difficulty": int, "expire_at": float, "used": bool}}
        self._active_challenges: Dict[str, Dict[str, Any]] = {}

    def generate_challenge(self, action_name: str = "reg_account", difficulty: Optional[int] = None) -> Dict[str, Any]:
        """Server sinh thử thách PoW gửi kèm cho client."""
        diff = difficulty or self.default_difficulty
        challenge_id = f"pow_{action_name}_{secrets.token_hex(8)}"
        salt = secrets.token_hex(16)
        now = time.time()

        # Dọn dẹp thử thách hết hạn
        self._active_challenges = {k: v for k, v in self._active_challenges.items() if v["expire_at"] > now}

        self._active_challenges[challenge_id] = {
            "salt": salt,
            "difficulty": diff,
            "expire_at": now + self.ttl,
            "used": False
        }

        return {
            "challenge_id": challenge_id,
            "algorithm": "SHA256_HASHCASH",
            "salt": salt,
            "difficulty": diff,
            "target_prefix": "0" * diff,
            "ttl_seconds": self.ttl,
            "timestamp": int(now)
        }

    @staticmethod
    def solve_challenge(challenge_info: Dict[str, Any], max_iterations: int = 2000000) -> Dict[str, Any]:
        """
        Client giải thử thách PoW: Tìm số nonce sao cho SHA256(challenge_id + salt + str(nonce))
        bắt đầu bằng đúng target_prefix.
        """
        challenge_id = challenge_info["challenge_id"]
        salt = challenge_info["salt"]
        target = challenge_info["target_prefix"]

        start_time = time.time()
        nonce = 0
        computed_hash = ""

        prefix_bytes = f"{challenge_id}:{salt}:".encode("ascii")

        while nonce < max_iterations:
            h = hashlib.sha256(prefix_bytes + str(nonce).encode("ascii")).hexdigest()
            if h.startswith(target):
                computed_hash = h
                break
            nonce += 1

        elapsed = round(time.time() - start_time, 4)
        return {
            "challenge_id": challenge_id,
            "nonce": nonce,
            "result_hash": computed_hash,
            "elapsed_seconds": elapsed,
            "iterations_count": nonce,
            "solved": computed_hash.startswith(target)
        }

    def verify_solution(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Server thẩm định nghiệm PoW do client gửi lên."""
        cid = solution.get("challenge_id", "")
        now = time.time()

        if cid not in self._active_challenges:
            return {"valid": False, "reason": "CHALLENGE_NOT_FOUND_OR_EXPIRED", "risk_score": 0.85}

        item = self._active_challenges[cid]
        if item["used"]:
            return {"valid": False, "reason": "CHALLENGE_REPLAYED", "risk_score": 0.95}

        if now > item["expire_at"]:
            return {"valid": False, "reason": "CHALLENGE_TIMEOUT", "risk_score": 0.70}

        salt = item["salt"]
        diff = item["difficulty"]
        target = "0" * diff
        nonce = solution.get("nonce", 0)

        # Tính toán lại hash độc lập
        verify_data = f"{cid}:{salt}:{nonce}".encode("ascii")
        actual_hash = hashlib.sha256(verify_data).hexdigest()

        if not actual_hash.startswith(target):
            return {"valid": False, "reason": "INVALID_POW_PROOF", "risk_score": 1.0}

        # Đánh dấu đã tiêu thụ
        item["used"] = True

        return {
            "valid": True,
            "reason": "POW_PASSED",
            "difficulty": diff,
            "actual_hash": actual_hash,
            "risk_score": 0.0
        }
