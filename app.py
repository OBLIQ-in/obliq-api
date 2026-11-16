"""Hugging Face Spaces Entrypoint.

Mounts the Obliq FastAPI application alongside a Gradio status overview interface.
Listens on port 7860 (Hugging Face Spaces default).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is on pythonpath in container
src_dir = str(Path(__file__).parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import gradio as gr
import spaces
import uvicorn

from obliq_api.main import create_app

@spaces.GPU
def _status_runner(text: str = "Ready") -> str:
    """Return operational status for browser visitors."""
    return f"Obliq API operational: {text}"

# Initialize core FastAPI backend
fastapi_app = create_app()

# Create status overview dashboard for browser visitors using gr.Interface
demo = gr.Interface(
    fn=_status_runner,
    inputs=gr.Textbox(label="Status Check", value="Ready"),
    outputs=gr.Textbox(label="System Status"),
    title="🚀 Obliq OCR API Service",
    description=(
        "**High-performance Multi-Tenant Asynchronous OCR & Document Engine**\n\n"
        "- **Health Probe:** `/health`\n"
        "- **Readiness Probe:** `/ready`\n"
        "- **Interactive OpenAPI Docs:** `/docs`\n"
        "- **Core Endpoints:** `/v1/jobs`, `/v1/orgs/me`, `/v1/dashboard/summary`"
    ),
)

# Mount Gradio onto the root of FastAPI
# All custom FastAPI routes (/health, /ready, /v1/*, /docs) take precedence,
# while browser visitors hitting the root URL see the interactive status dashboard.
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
