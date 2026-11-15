"""OCR engine wrapper.

In production this wraps the real `obliq-ocr` package (parse_document / save_result).
For local development / CI a deterministic stub is used when the package
is not available.

obliq_ocr.parse_document returns a ParseResult whose .to_dict() shape is:
{
    "source": str,
    "device": str,
    "pages": [
        {
            "page": int,           # 1-based
            "method": str,         # "text_layer" | "ocr" | "blank"
            "reason": str,
            "text": str,
            "n_chars": int,
            "confidence": float | None,
            "seconds": float,
        },
        ...
    ]
}

We normalise that into the internal protocol shape:
{
    "page_count": int,
    "pages": [
        {
            "page_number": int,
            "text": str | None,
            "confidence": float | None,
            "method": str,
            "reason": str,
            "n_chars": int,
            "seconds": float,
            "status": "ok" | "blank" | "low_confidence",
        },
        ...
    ],
    "status": "succeeded" | "partial" | "failed",
    "processing_time_ms": int,
    "device": str,
    "source": str,
}
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing
import time
from pathlib import Path
from typing import Any

from obliq_api.config import get_settings
from obliq_api.protocols import OCREngine

settings = get_settings()

LOW_CONFIDENCE_THRESHOLD = 0.5

# Use 'spawn' explicitly on all platforms so worker processes are clean.
# On Windows this is the default; on Linux/macOS it avoids fork-related
# issues with asyncio event loops inside the parent process.
_mp_context = multiprocessing.get_context("spawn")

_process_pool: concurrent.futures.ProcessPoolExecutor | None = None


def _get_process_pool() -> concurrent.futures.ProcessPoolExecutor:
    global _process_pool
    if _process_pool is None:
        _process_pool = concurrent.futures.ProcessPoolExecutor(
            max_workers=2,
            mp_context=_mp_context,
        )
    return _process_pool


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _page_status(method: str, confidence: float | None) -> str:
    """Map obliq_ocr method/confidence to our internal page status."""
    if method == "blank":
        return "blank"
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        return "low_confidence"
    return "ok"


def _normalise_result(raw: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    """Convert obliq_ocr.ParseResult.to_dict() into the internal protocol shape."""
    raw_pages: list[dict[str, Any]] = raw.get("pages", [])
    pages = []
    any_low_conf = False

    for p in raw_pages:
        method: str = p.get("method", "ocr")
        confidence: float | None = p.get("confidence")
        status = _page_status(method, confidence)
        if status == "low_confidence":
            any_low_conf = True
        pages.append(
            {
                "page_number": p["page"],
                "text": p.get("text") or None,
                "confidence": confidence,
                "method": method,
                "reason": p.get("reason", ""),
                "n_chars": p.get("n_chars", 0),
                "seconds": p.get("seconds", 0.0),
                "status": status,
                "bounding_boxes": None,
                "error": None,
            }
        )

    overall = "partial" if any_low_conf else "succeeded"
    return {
        "page_count": len(pages),
        "pages": pages,
        "status": overall,
        "processing_time_ms": elapsed_ms,
        "device": raw.get("device", "unknown"),
        "source": raw.get("source", ""),
    }


# ---------------------------------------------------------------------------
# Engine classes
# ---------------------------------------------------------------------------

class StubOCREngine:
    """Deterministic stub used when obliq-ocr is not installed."""

    async def extract(
        self,
        file_path: str,
        *,
        max_pages: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        path = Path(file_path)
        size = path.stat().st_size if path.exists() else 0
        page_count = max(1, min(size // 50_000, max_pages or settings.max_pages_per_job))

        await asyncio.sleep(0.05 * page_count)  # simulate work

        pages = []
        for i in range(page_count):
            pages.append(
                {
                    "page_number": i + 1,
                    "text": f"[stub] Page {i + 1} content extracted from {path.name}",
                    "confidence": 0.92,
                    "method": "text_layer",
                    "reason": "stub",
                    "n_chars": 50,
                    "seconds": 0.05,
                    "status": "ok",
                    "bounding_boxes": None,
                    "error": None,
                }
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "page_count": page_count,
            "pages": pages,
            "status": "succeeded",
            "processing_time_ms": elapsed_ms,
            "device": "stub",
            "source": Path(file_path).name,
        }

    async def health_check(self) -> bool:
        return True


class ObliqOCREngine:
    """Real engine backed by the obliq-ocr package (parse_document).

    OCR is CPU-bound. We run it in a ProcessPoolExecutor so the work
    happens in a separate OS process and the asyncio event loop is fully
    free to serve other requests (polls, health checks, etc.) while OCR
    is running.
    """

    def __init__(self) -> None:
        # Verify the package is importable before accepting any jobs.
        try:
            import obliq_ocr  # type: ignore[import-untyped]  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "obliq-ocr package is not installed. "
                "Run `pip install obliq-ocr` or use StubOCREngine for development."
            ) from exc

    async def extract(
        self,
        file_path: str,
        *,
        max_pages: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Run parse_document in a worker process, keeping the event loop free."""
        from obliq_api.worker.ocr_worker import run_ocr

        loop = asyncio.get_running_loop()
        start = time.perf_counter()

        pool = _get_process_pool()
        raw = await loop.run_in_executor(pool, run_ocr, file_path)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _normalise_result(raw, elapsed_ms)

    async def health_check(self) -> bool:
        return True


def create_ocr_engine() -> OCREngine:
    """Return the real engine if obliq-ocr is installed, otherwise the stub."""
    try:
        return ObliqOCREngine()
    except RuntimeError:
        return StubOCREngine()
