from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/dashboard", tags=["dashboard-ui"])


@router.get("", response_class=RedirectResponse)
async def dashboard_index() -> RedirectResponse:
    """Redirect to the default key management portal."""
    return RedirectResponse(url="/dashboard/keys", status_code=307)


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request) -> HTMLResponse:
    """API Key management developer portal."""
    return templates.TemplateResponse(request=request, name="keys.html")


@router.get("/usage", response_class=HTMLResponse)
async def usage_page(request: Request) -> HTMLResponse:
    """Live usage, latency, and telemetry dashboard."""
    return templates.TemplateResponse(request=request, name="usage.html")


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request) -> HTMLResponse:
    """Interactive client SDK documentation and code samples."""
    return templates.TemplateResponse(request=request, name="docs.html")
