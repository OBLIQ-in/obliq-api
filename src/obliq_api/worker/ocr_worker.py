"""Isolated OCR worker module.

This module contains ONLY the worker function that runs inside the
ProcessPoolExecutor child process. It must NOT import anything from
obliq_api at module level, because on Windows multiprocessing uses
'spawn' — every worker process re-imports this module from scratch,
and importing obliq_api triggers pydantic-settings which tries to read
.env and validate all settings, which fails in the worker environment.

Keep this file dependency-free at the module level.
"""

from __future__ import annotations


def run_ocr(file_path: str) -> dict:
    """
    Entry point for the worker process.
    Imports obliq_ocr here (inside the function) so it only loads in the
    worker, not in the main process at import time.
    """
    from obliq_ocr import parse_document  # type: ignore[import-untyped]
    result = parse_document(file_path, verbose=False)
    return result.to_dict()
