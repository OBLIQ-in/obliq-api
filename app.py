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
import uvicorn

from obliq_api.main import create_app

# ZeroGPU compatibility: satisfy Hugging Face ZeroGPU startup validator
try:
    import spaces

    @spaces.GPU
    def _zerogpu_runner(text: str = "") -> str:
        """Registered GPU function required by Hugging Face ZeroGPU supervisor."""
        return text
except ImportError:
    def _zerogpu_runner(text: str = "") -> str:
        return text

# Initialize core FastAPI backend
fastapi_app = create_app()

# Create status overview dashboard for browser visitors
with gr.Blocks(title="Obliq OCR API") as demo:
    gr.Markdown(
        """
        # 🚀 Obliq API Service
        **High-performance Multi-Tenant Asynchronous OCR & Document Engine**

        ---

        ### 📡 Service Health & Endpoints
        - **Health Probe:** [`/health`](/health)
        - **Readiness Probe:** [`/ready`](/ready)
        - **Interactive OpenAPI Docs:** [`/docs`](/docs)
        - **ReDoc Specification:** [`/redoc`](/redoc)

        ### 🔐 Core API Routes (v1)
        - `POST /v1/jobs` — Upload & process documents (PDF, PNG, JPEG, TIFF)
        - `GET /v1/jobs/{id}` — Poll job processing status
        - `GET /v1/jobs/{id}/result` — Retrieve structured OCR text & page data
        - `GET /v1/dashboard/summary` — Developer usage & credit balance
        """
    )

    # Wire the @spaces.GPU function to a hidden event listener for ZeroGPU startup detection
    _dummy_btn = gr.Button("ZeroGPU Check", visible=False)
    _dummy_out = gr.Textbox(visible=False)
    _dummy_btn.click(fn=_zerogpu_runner, inputs=[], outputs=_dummy_out)

# Mount Gradio onto the root of FastAPI
# All custom FastAPI routes (/health, /ready, /v1/*, /docs) take precedence,
# while browser visitors hitting the root URL see the interactive status dashboard!
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
