# obliq-api

A high-performance FastAPI microservice wrapping the [obliq-ocr](https://pypi.org/project/obliq-ocr/) engine, built to process mixed-format tax documents, invoices, and challans uniformly across distributed enterprise services.

## Overview

`obliq-api` exposes the page-aware extraction power of `obliq-ocr` as an asynchronous HTTP REST interface. It automatically handles text-layer vs. scanned page routing, executes OCR pipelines via ONNX Runtime, and streams structured JSON payloads back to consumer microservices without blocking the main application thread.

## Key Features

- **Asynchronous Endpoints**: Non-blocking request handling optimized for high-concurrency document ingestion.
- **Universal Payload Contract**: Standardized request/response wrappers matching the `obliq-ocr` schema.
- **Multi-Environment Runtime**: Containerized out-of-the-box with support for CPU and GPU execution contexts.
- **Health & Readiness Probes**: Built-in endpoints for Kubernetes liveness, readiness, and latency tracking.

## API Endpoints

### 1. Health Check
* **Endpoint**: `GET /health`
* **Description**: Returns the runtime status and loaded device context (CPU/CUDA).

### 2. Parse Document
* **Endpoint**: `POST /api/v1/parse`
* **Content-Type**: `multipart/form-data`
* **Parameters**: 
  * `file`: PDF or supported image file (`.pdf`, `.png`, `.jpg`)
  * `force_device` (optional): Override execution backend (`cpu` or `cuda`)
* **Response**: Full structured JSON output containing page-level breakdown, confidence scores, extraction methods, and raw text.

## Quickstart (Local Development)

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Docker and Docker Compose (optional for containerized runs)

### Installation

1. Clone the repository and navigate into the directory:
   ```bash
   git clone https://github.com/OBLIQ-in/obliq-api.git
   cd obliq-api
