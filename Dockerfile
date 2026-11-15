FROM python:3.11-slim

# Install system dependencies required by PyMuPDF and ONNX/OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user (UID 1000 required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR $HOME/app

# Copy project definition and source code
COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
COPY --chown=user alembic ./alembic
COPY --chown=user alembic.ini ./

# Install application and production dependencies
RUN pip install --no-cache-dir .

# Hugging Face Spaces standard port (also configurable via PORT environment variable)
EXPOSE 7860

# Run FastAPI app via uvicorn
CMD ["uvicorn", "obliq_api.main:app", "--host", "0.0.0.0", "--port", "7860"]
