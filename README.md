# ChromaKit Backend

FastAPI backend for academic image processing using NumPy (no OpenCV), Clean Architecture, and Supabase for auth, database, and storage.

Everything (code, comments, endpoints, docs) is in English as required.

## Tech Stack
- Python 3.11+
- FastAPI, Uvicorn
- NumPy for processing; Pillow for image I/O; Matplotlib optional
- Pydantic v2
- Supabase (auth, database, storage) via supabase-py v2
- Quality: Ruff and Black
- Tests: Pytest (+ asyncio, coverage)
- Package manager: uv (fast Python package installer and resolver)

## Project Structure (Clean Architecture)
```
chromakit-backend/
├── src/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── main.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Run it in 2 minutes (recommended: uv)

Prerequisites:
- Python 3.11+ available on PATH (3.11 recommended)
- uv installed (one-time)

Install uv:
- macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Setup and run:
```bash
# 1) Create a local virtualenv for the project (uses .venv)
uv venv --python 3.11

# 2) Activate the venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
# .venv\Scripts\Activate.ps1

# 3) Install dependencies (app + dev tools declared in pyproject)
uv sync --extra dev

# 4) Create your environment file
cp .env.example .env
# For local runs without a Supabase instance, keep: SUPABASE_DISABLED=1
# Files will be written under .local_storage/ and tables are emulated in-memory.

# 5) Run the API
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
# Open http://127.0.0.1:8000/docs
```

Smoke test:
```bash
# Health
curl http://127.0.0.1:8000/health
# -> {"status":"healthy"}
```

Auth header while SUPABASE_DISABLED=1:
- Any token value is accepted; use: `Authorization: Bearer test-token`

Upload a sample image and list images:
```bash
# Create a 4x4 PNG in Python (optional) and upload via curl
python - <<'PY'
from PIL import Image
img = Image.new('RGB', (4,4), color=(128,64,32))
img.save('sample.png')
PY

# Upload
curl -X POST \
  -H 'Authorization: Bearer test-token' \
  -F 'file=@sample.png;type=image/png' \
  http://127.0.0.1:8000/images/upload

# List
curl -H 'Authorization: Bearer test-token' http://127.0.0.1:8000/images
```

Run a processing operation (brightness) and check history:
```bash
# Replace IMG_ID with the id returned by the upload step
IMG_ID=img_1
curl -X POST \
  -H 'Authorization: Bearer test-token' \
  -H 'Content-Type: application/json' \
  -d '{"image_id": "'$IMG_ID'", "factor": 1.5}' \
  http://127.0.0.1:8000/processing/brightness

# The response will include a URL to access the processed image
# Response: {"id": "img_2", "url": "https://...", "operation": "brightness", ...}

# History
curl -H 'Authorization: Bearer test-token' http://127.0.0.1:8000/history
```

Notes:
- Local storage path when `SUPABASE_DISABLED=1`: `.local_storage/{user_id}/{uuid}.{ext}`
- To clean local files, stop the server and remove `.local_storage/`.
- When connecting to a real Supabase project, set SUPABASE_URL, SUPABASE_ANON_KEY and set `SUPABASE_DISABLED=0`.

---

## Alternative setup without uv
If you prefer using the standard Python tooling:
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Environment variables
Copy `.env.example` to `.env` and adjust:
```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_STORAGE_BUCKET=images
SUPABASE_DISABLED=1
SUPABASE_STORAGE_LOCAL_DIR=.local_storage
```

With `SUPABASE_DISABLED=1`:
- Auth is bypassed (any Bearer token accepted) for local dev.
- Storage writes to `.local_storage/` and database tables are emulated in-memory.

---

## Tests, Lint, and Formatting
```bash
# Unit + integration tests
uv run pytest -q

# Coverage (terminal)
uv run pytest --cov=src --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run black .
```

---

## API Overview

**📖 Complete API Documentation**: See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for comprehensive endpoint reference, TypeScript types, and usage examples.

### Core Endpoints

**Authentication**:
- `POST /auth/validate` - Validate JWT token
- `GET /auth/me` - Get current user profile
- `PATCH /auth/profile` - Update user profile

**Image Management**:
- `POST /images/upload` - Upload new image
- `GET /images` - List user's images (paginated)
- `GET /images/{image_id}` - Get image metadata
- `GET /images/{image_id}/download` - Download image file
- `DELETE /images/{image_id}` - Delete image

**Image Processing** (all return processed image URLs):
- `POST /processing/brightness` - Adjust brightness
- `POST /processing/contrast` - Adjust contrast (logarithmic/exponential)
- `POST /processing/negative` - Create negative/inverted image
- `POST /processing/grayscale` - Convert to grayscale (3 methods)
- `POST /processing/binarize` - Convert to binary (black/white)
- `POST /processing/rotate` - Rotate image
- `POST /processing/crop` - Crop rectangular region
- `POST /processing/translate` - Move image position
- `POST /processing/reduce-resolution` - Reduce image size
- `POST /processing/enlarge-region` - Zoom specific region
- `POST /processing/merge` - Merge two images with transparency
- `POST /processing/channel` - Manipulate RGB/CMY channels
- `GET /processing/{image_id}/histogram` - Calculate color histogram

**Processing History**:
- `GET /history` - List processing operations (paginated)
- `GET /history/{history_id}` - Get specific operation details
- `DELETE /history/{history_id}` - Delete history record

### Key Features
- ✅ All image processing happens in Python backend (NumPy-based)
- ✅ All processing endpoints return URLs to processed images
- ✅ Automatic processing history tracking
- ✅ User-scoped access control
- ✅ Comprehensive error handling
- ✅ OpenAPI/Swagger documentation at `/docs`

**Data Model**:
- Images: `{user_id}/{uuid}.{ext}` in Supabase Storage (or `.local_storage/` locally)
- Database tables: `profiles`, `images`, `edit_history`

---

## 🚀 Deployment

### Docker Deployment (Recommended)

Build and run with Docker:
```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Digital Ocean One-Click Deployment

Deploy to Digital Ocean droplet with automated setup:

```bash
# 1. SSH into your Ubuntu 22.04 droplet
ssh root@your_droplet_ip

# 2. Run automated setup script
curl -fsSL https://raw.githubusercontent.com/SwiftControl/chromakit-backend/main/scripts/setup-droplet.sh | bash

# 3. Configure environment and deploy
cd /opt/chromakit-backend
cp .env.example .env
# Edit .env with your Supabase credentials
docker-compose -f docker-compose.prod.yml up -d

# 4. Optional: Setup SSL
./scripts/setup-ssl.sh your-domain.com
```

### GitHub Actions CI/CD

Automated deployment on push to main/develop branches:

1. **Configure Repository Secrets:**
   - `PRODUCTION_HOST`: Your droplet IP
   - `PRODUCTION_USER`: SSH username (usually `root`)
   - `PRODUCTION_SSH_KEY`: Private SSH key
   - `PRODUCTION_PORT`: SSH port (usually `22`)

2. **Deployment Flow:**
   - Push to `main` → Production deployment
   - Push to `develop` → Staging deployment
   - Pull requests → Run tests only

### Architecture

```
Internet → Nginx (SSL, Rate Limiting) → FastAPI Backend → Supabase
```

**Features:**
- 🔒 SSL termination with Let's Encrypt
- 🛡️ Rate limiting and security headers
- 📊 Health checks and monitoring
- 🔄 Automatic deployments
- 📝 Structured logging
- 🐳 Container orchestration

### Quick Links

- 📖 **[Complete Deployment Guide](docs/deployment.md)**
- ⚡ **[Quick Start Guide](docs/quick-start.md)**
- 🔧 **[Configuration Examples](docs/)**

---

## Troubleshooting
- "ModuleNotFoundError: No module named 'src'" when running pytest: the test suite already configures the path; ensure you run tests from the project root with `uv run pytest` (or `pytest`) while the venv is active.
- If `uv` warns about `VIRTUAL_ENV` mismatch, prefer `uv sync` and `uv run` from the project root with the `.venv` created above.
- Pillow deprecation warnings about `mode` are harmless for now.
- **Deployment issues**: Check the [deployment troubleshooting guide](docs/deployment.md#troubleshooting)
