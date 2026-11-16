import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import aiofiles  # type: ignore[import-untyped]
from fastapi import UploadFile

from obliq_api.config import get_settings
from obliq_api.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError, ValidationError

settings = get_settings()

# Magic bytes for common document types
MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"RIFF", "image/webp"),  # simplified
]

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/gif",
    "image/bmp",
    "image/webp",
}


def detect_mime(header: bytes) -> str | None:
    for sig, mime in MAGIC_SIGNATURES:
        if header.startswith(sig):
            return mime
    return None


@asynccontextmanager
async def save_upload_temporarily(
    upload: UploadFile,
    *,
    max_size: int | None = None,
) -> AsyncIterator[Path]:
    """Stream upload to a temp file, validate, and guarantee deletion."""
    max_bytes = max_size or settings.max_upload_size_bytes
    tmp_path: Path | None = None

    try:
        # Read a small header for magic-byte detection
        header = await upload.read(16)
        await upload.seek(0)

        mime = detect_mime(header)
        if mime is None or mime not in ALLOWED_MIME:
            raise UnsupportedMediaTypeError(
                f"Unsupported or unrecognised file type (detected: {mime})"
            )

        suffix = Path(upload.filename or "upload").suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)

        size = 0
        async with aiofiles.open(tmp_path, "wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)  # 1 MiB
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise PayloadTooLargeError(
                        f"File exceeds maximum size of {settings.max_upload_size_mb} MB"
                    )
                await out.write(chunk)

        if size == 0:
            raise ValidationError("Uploaded file is empty")

        yield tmp_path
    finally:
        if tmp_path and tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()
