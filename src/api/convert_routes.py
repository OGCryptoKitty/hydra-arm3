"""
HYDRA — Format conversion endpoints.

HTML to Markdown, JSON to CSV, CSV to JSON.
Pay-per-call via x402 on Base L2.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup, NavigableString
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

convert_router = APIRouter(tags=["Conversion"])

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"User-Agent": "HYDRA-Convert/1.0 (x402; +https://hydra-api-nlnj.onrender.com)"},
        )
    return _http_client


def _table_to_md(table) -> str:
    rows = table.find_all("tr")
    if not rows:
        return ""
    md_rows = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text(strip=True).replace("|", "\\|") for c in cells]
        md_rows.append("| " + " | ".join(cell_texts) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n" + "\n".join(md_rows) + "\n"


def _process_element(element) -> str:
    if isinstance(element, NavigableString):
        text = str(element)
        if not text.strip():
            return " " if text else ""
        return text

    if element.name is None:
        return ""

    children_text = "".join(_process_element(c) for c in element.children)

    tag = element.name
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        return f"\n\n{'#' * level} {children_text.strip()}\n\n"
    if tag == "p":
        return f"\n\n{children_text.strip()}\n\n"
    if tag == "a":
        href = element.get("href", "")
        text = children_text.strip()
        if href and text:
            return f"[{text}]({href})"
        return text
    if tag in ("strong", "b"):
        return f"**{children_text.strip()}**"
    if tag in ("em", "i"):
        return f"*{children_text.strip()}*"
    if tag == "code":
        if element.parent and element.parent.name == "pre":
            return children_text
        return f"`{children_text.strip()}`"
    if tag == "pre":
        lang = ""
        code_el = element.find("code")
        if code_el and code_el.get("class"):
            for cls in code_el["class"]:
                if cls.startswith("language-"):
                    lang = cls[9:]
                    break
        return f"\n\n```{lang}\n{children_text.strip()}\n```\n\n"
    if tag == "ul":
        items = []
        for li in element.find_all("li", recursive=False):
            items.append(f"- {_process_element(li).strip()}")
        return "\n\n" + "\n".join(items) + "\n\n"
    if tag == "ol":
        items = []
        for i, li in enumerate(element.find_all("li", recursive=False), 1):
            items.append(f"{i}. {_process_element(li).strip()}")
        return "\n\n" + "\n".join(items) + "\n\n"
    if tag == "blockquote":
        lines = children_text.strip().split("\n")
        return "\n\n" + "\n".join(f"> {line}" for line in lines) + "\n\n"
    if tag == "img":
        alt = element.get("alt", "")
        src = element.get("src", "")
        return f"![{alt}]({src})"
    if tag == "br":
        return "\n"
    if tag == "hr":
        return "\n\n---\n\n"
    if tag == "table":
        return _table_to_md(element)
    if tag in ("script", "style", "nav", "footer", "aside", "noscript", "iframe", "svg"):
        return ""
    return children_text


def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()
    result = _process_element(soup)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


class Html2MdRequest(BaseModel):
    html: str = Field(default=None, description="Raw HTML string to convert")
    url: str = Field(default=None, description="URL to fetch and convert to markdown")
    max_length: int = Field(default=20000, ge=100, le=100000)


@convert_router.post("/v1/convert/html2md", tags=["Conversion"])
async def convert_html2md(req: Html2MdRequest):
    """
    Convert HTML to clean Markdown. Accepts raw HTML or a URL.
    Preserves headings, lists, links, code blocks, tables. $0.005 USDC.
    """
    start = time.monotonic()

    if not req.html and not req.url:
        return JSONResponse(status_code=422, content={"error": "Provide 'html' or 'url'"})

    source_url = req.url
    html = req.html

    if req.url and not req.html:
        client = await _get_client()
        try:
            resp = await client.get(req.url)
            resp.raise_for_status()
            html = resp.text
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            return JSONResponse(status_code=422, content={
                "error": "Failed to fetch URL",
                "detail": str(type(e).__name__),
            })

    markdown = _html_to_markdown(html)
    truncated = len(markdown) > req.max_length
    if truncated:
        markdown = markdown[:req.max_length]

    return {
        "markdown": markdown,
        "length": len(markdown),
        "truncated": truncated,
        "source_url": source_url,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


class Json2CsvRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Array of JSON objects", min_length=1, max_length=10000)
    delimiter: str = Field(default=",", max_length=1)


@convert_router.post("/v1/convert/json2csv", tags=["Conversion"])
async def convert_json2csv(req: Json2CsvRequest):
    """
    Convert a JSON array of objects to CSV. Returns CSV text with
    headers derived from object keys. $0.003 USDC.
    """
    start = time.monotonic()

    all_keys: list[str] = []
    seen: set[str] = set()
    for row in req.data:
        for k in row:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=all_keys, delimiter=req.delimiter, extrasaction="ignore")
    writer.writeheader()
    for row in req.data:
        writer.writerow(row)

    csv_text = output.getvalue()
    return {
        "csv": csv_text,
        "rows": len(req.data),
        "columns": len(all_keys),
        "headers": all_keys,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }


class Csv2JsonRequest(BaseModel):
    csv_text: str = Field(..., description="CSV text with header row", alias="csv")
    delimiter: str = Field(default=",", max_length=1)


@convert_router.post("/v1/convert/csv2json", tags=["Conversion"])
async def convert_csv2json(req: Csv2JsonRequest):
    """
    Convert CSV text to a JSON array of objects. First row is treated
    as column headers. $0.003 USDC.
    """
    start = time.monotonic()

    reader = csv.DictReader(io.StringIO(req.csv_text), delimiter=req.delimiter)
    rows = list(reader)

    return {
        "data": rows,
        "rows": len(rows),
        "columns": len(reader.fieldnames or []),
        "headers": list(reader.fieldnames or []),
        "elapsed_ms": round((time.monotonic() - start) * 1000),
    }
