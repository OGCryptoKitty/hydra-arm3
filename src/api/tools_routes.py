"""
HYDRA — Developer micro-tools.

Hash, encode/decode, diff, validate. Pure computation endpoints.
Pay-per-call via x402 on Base L2.
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
import re
import time
import urllib.parse

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

tools_router = APIRouter(tags=["Developer Tools"])


class HashRequest(BaseModel):
    text: str = Field(..., description="Text to hash", max_length=1_000_000)
    algorithm: str = Field(default="sha256", description="Hash algorithm: sha256, sha512, md5, sha1, sha3_256")


@tools_router.post("/v1/tools/hash", tags=["Developer Tools"])
async def tools_hash(req: HashRequest):
    """
    Hash text with SHA-256, SHA-512, MD5, SHA-1, or SHA3-256.
    Returns hex digest. $0.001 USDC.
    """
    algo = req.algorithm.lower().replace("-", "").replace("_", "")
    algo_map = {
        "sha256": "sha256",
        "sha512": "sha512",
        "md5": "md5",
        "sha1": "sha1",
        "sha3256": "sha3_256",
        "sha3512": "sha3_512",
    }

    if algo not in algo_map:
        return JSONResponse(status_code=422, content={
            "error": f"Unsupported algorithm: {req.algorithm}",
            "supported": list(algo_map.keys()),
        })

    h = hashlib.new(algo_map[algo])
    data = req.text.encode("utf-8")
    h.update(data)

    return {
        "algorithm": algo_map[algo],
        "hex": h.hexdigest(),
        "input_bytes": len(data),
    }


class EncodeRequest(BaseModel):
    text: str = Field(..., description="Text to encode or decode", max_length=1_000_000)
    operation: str = Field(..., description="Operation: base64_encode, base64_decode, url_encode, url_decode, hex_encode, hex_decode")


@tools_router.post("/v1/tools/encode", tags=["Developer Tools"])
async def tools_encode(req: EncodeRequest):
    """
    Encode or decode text. Supports Base64, URL encoding, and hex.
    $0.001 USDC.
    """
    op = req.operation.lower().replace("-", "_")

    try:
        if op == "base64_encode":
            result = base64.b64encode(req.text.encode("utf-8")).decode("ascii")
        elif op == "base64_decode":
            result = base64.b64decode(req.text).decode("utf-8")
        elif op == "url_encode":
            result = urllib.parse.quote(req.text, safe="")
        elif op == "url_decode":
            result = urllib.parse.unquote(req.text)
        elif op == "hex_encode":
            result = req.text.encode("utf-8").hex()
        elif op == "hex_decode":
            result = bytes.fromhex(req.text).decode("utf-8")
        else:
            return JSONResponse(status_code=422, content={
                "error": f"Unsupported operation: {req.operation}",
                "supported": ["base64_encode", "base64_decode", "url_encode", "url_decode", "hex_encode", "hex_decode"],
            })
    except Exception as e:
        return JSONResponse(status_code=422, content={
            "error": "Operation failed",
            "detail": str(e)[:200],
        })

    return {
        "operation": op,
        "result": result,
        "input_length": len(req.text),
        "output_length": len(result),
    }


class DiffRequest(BaseModel):
    text_a: str = Field(..., description="Original text", max_length=500_000)
    text_b: str = Field(..., description="Modified text", max_length=500_000)
    context_lines: int = Field(default=3, ge=0, le=20)


@tools_router.post("/v1/tools/diff", tags=["Developer Tools"])
async def tools_diff(req: DiffRequest):
    """
    Unified diff between two texts. Returns diff lines, change stats,
    and similarity ratio. $0.003 USDC.
    """
    lines_a = req.text_a.splitlines(keepends=True)
    lines_b = req.text_b.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        lines_a, lines_b, fromfile="a", tofile="b", n=req.context_lines,
    ))

    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    ratio = difflib.SequenceMatcher(None, req.text_a, req.text_b).ratio()

    return {
        "diff": "".join(diff_lines),
        "stats": {
            "lines_added": added,
            "lines_removed": removed,
            "lines_a": len(lines_a),
            "lines_b": len(lines_b),
            "similarity": round(ratio, 4),
        },
        "identical": req.text_a == req.text_b,
    }


class ValidateJsonRequest(BaseModel):
    text: str = Field(..., description="JSON string to validate", max_length=1_000_000)
    pretty: bool = Field(default=True, description="Return pretty-printed JSON if valid")


@tools_router.post("/v1/tools/validate/json", tags=["Developer Tools"])
async def tools_validate_json(req: ValidateJsonRequest):
    """
    Validate JSON syntax. Returns parsed structure info and optionally
    pretty-printed output. $0.001 USDC.
    """
    try:
        parsed = json.loads(req.text)
        result: dict = {
            "valid": True,
            "type": type(parsed).__name__,
        }
        if isinstance(parsed, list):
            result["length"] = len(parsed)
        elif isinstance(parsed, dict):
            result["keys"] = list(parsed.keys())[:50]
            result["key_count"] = len(parsed)

        if req.pretty:
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            result["pretty"] = pretty
            result["pretty_length"] = len(pretty)

        return result
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": str(e),
            "line": e.lineno,
            "column": e.colno,
            "position": e.pos,
        }


class ValidateEmailRequest(BaseModel):
    email: str = Field(..., description="Email address to validate", max_length=320)


@tools_router.post("/v1/tools/validate/email", tags=["Developer Tools"])
async def tools_validate_email(req: ValidateEmailRequest):
    """
    Email format validation with MX record check via DNS.
    Returns format validity and whether the domain accepts mail. $0.002 USDC.
    """
    start = time.monotonic()
    email = req.email.strip()

    email_re = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$")
    format_valid = bool(email_re.match(email))

    if not format_valid:
        return {
            "email": email,
            "format_valid": False,
            "mx_valid": None,
            "elapsed_ms": round((time.monotonic() - start) * 1000),
        }

    domain = email.split("@")[1]

    mx_valid = None
    mx_records = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://dns.google/resolve",
                params={"name": domain, "type": "MX"},
                headers={"Accept": "application/dns-json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for answer in data.get("Answer", []):
                    mx_records.append(answer.get("data", "").strip('"'))
                mx_valid = len(mx_records) > 0
    except httpx.RequestError:
        pass

    return {
        "email": email,
        "format_valid": True,
        "domain": domain,
        "mx_valid": mx_valid,
        "mx_records": mx_records if mx_records else None,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
