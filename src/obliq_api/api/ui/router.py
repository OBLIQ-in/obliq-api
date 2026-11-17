from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from obliq_api.api.ui.templates import DOCS_PAGE_HTML, KEYS_PAGE_HTML, USAGE_PAGE_HTML

router = APIRouter(prefix="/dashboard", tags=["dashboard-ui"])


@router.get("", response_class=RedirectResponse)
async def dashboard_index() -> RedirectResponse:
    """Redirect to the default key management portal."""
    return RedirectResponse(url="/dashboard/keys", status_code=307)


@router.get("/keys", response_class=HTMLResponse)
async def keys_page() -> HTMLResponse:
    """API Key management developer portal."""
    return HTMLResponse(content=KEYS_PAGE_HTML)


@router.get("/usage", response_class=HTMLResponse)
async def usage_page() -> HTMLResponse:
    """Live usage, latency, and telemetry dashboard."""
    return HTMLResponse(content=USAGE_PAGE_HTML)


@router.get("/docs", response_class=HTMLResponse)
async def docs_page() -> HTMLResponse:
    """Interactive client SDK documentation and code samples."""
    return HTMLResponse(content=DOCS_PAGE_HTML)
