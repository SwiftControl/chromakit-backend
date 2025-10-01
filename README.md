# ChromaKit Backend

FastAPI backend for academic image processing using NumPy (no OpenCV), Clean Architecture, and Supabase for auth, database, and storage.

Everything (code, comments, endpoints, docs) is in English as required.

## Tech Stack
- Python 3.11+
- FastAPI, Uvicorn
- NumPy for processing; Matplotlib optional for histogram plotting; Pillow for image I/O only
- Pydantic v2
- Supabase (auth, database, storage) via supabase-py v2
- Quality: Ruff and Black
- Tests: Pytest, pytest-asyncio, pytest-cov
- Package manager: uv (you can also use pip locally)

## Project Structure (Clean Architecture)
```
chromakit-backend/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── image.py
│   │   │   ├── profile.py
│   │   │   └── edit_history.py
│   │   └── services/
│   │       └── processing_service.py
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── upload_image.py
│   │   │   └── ... (one use-case per operation)
│   │   └── dtos/
│   │       ├── image_dto.py
│   │       └── history_dto.py
│   ├── infrastructure/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── image_routes.py
│   │   │   │   ├── processing_routes.py
│   │   │   │   ├── auth_routes.py
│   │   │   │   └── history_routes.py
│   │   │   ├── dependencies.py
│   │   │   └── middlewares.py
│   │   ├── database/
│   │   │   ├── supabase_client.py
│   │   │   └── repositories/
│   │   │       ├── image_repository.py
│   │   │       ├── history_repository.py
│   │   │       └── profile_repository.py
│   │   └── storage/
│   │       └── supabase_storage.py
│   └── main.py
├── tests/
│   ├── unit/
│   │   └── test_processing_service.py
│   ├── integration/
│   │   └── test_api_endpoints.py
│   └── conftest.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── ruff.toml
└── README.md
```

## Environment
Copy .env.example to .env and fill in values. For local tests you can leave SUPABASE_DISABLED=1 to use a built-in fake Supabase adapter.

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=
SUPABASE_STORAGE_BUCKET=images
SUPABASE_DISABLED=1
SUPABASE_STORAGE_LOCAL_DIR=.local_storage
```

## Quickstart (uv)
- Requires Python 3.11+.
- On zsh, quote extras like ".[dev]" to avoid globbing.

```
# create and activate a project-local venv with Python 3.11+
uv venv --python 3.11
source .venv/bin/activate

# install app + dev tools (pytest, ruff, black)
uv pip install -e ".[dev]"

# run the API (from project root)
uv run uvicorn src.main:app --reload
# open http://127.0.0.1:8000/docs

# run tests
uv run pytest -q
```

## Quickstart (pip)
```
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
uvicorn src.main:app --reload
# run tests
pytest -q
```

## Tests & Coverage
- Unit tests cover image processing logic (NumPy-only).
- Integration tests exercise auth validation, upload/list, histogram, and a processing flow with history.
- Target coverage: 80%+

## API Overview
All image management and processing endpoints require a valid Supabase access token via Authorization: Bearer <token>. For local testing with SUPABASE_DISABLED=1, any token value is accepted and a fake user is injected.

Implemented endpoints (high-level):
- POST /auth/validate
- POST /images/upload
- GET /images
- GET /images/{image_id}
- DELETE /images/{image_id}
- POST /processing/{operation}
- GET /history
- GET /history/{history_id}

Notes:
- Images are stored in Supabase Storage bucket "images" at path {user_id}/{uuid}.{ext}.
- Database tables expected: profiles, images, edit_history.

## Development Notes
- Code style enforced by Black and Ruff.
- All processing operations accept and return normalized NumPy arrays in range [0, 1].
- Pillow is used only for file I/O; processing is NumPy-only.
- The fake Supabase adapter stores files under .local_storage and keeps table rows in memory for tests.
