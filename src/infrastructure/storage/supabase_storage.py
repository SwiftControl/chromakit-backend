from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from supabase import Client
except Exception:  # pragma: no cover
    Client = object  # type: ignore


@dataclass
class StorageResult:
    path: str
    width: int
    height: int
    content_type: str
    size: int


class SupabaseStorage:
    """Storage adapter for Supabase Storage with a local fake fallback."""

    def __init__(self, client: Client | None) -> None:
        self.client = client
        self.bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "images")
        self.disabled = os.getenv("SUPABASE_DISABLED", "0") == "1"
        self.local_dir = Path(os.getenv("SUPABASE_STORAGE_LOCAL_DIR", ".local_storage"))
        if self.disabled:
            self.local_dir.mkdir(parents=True, exist_ok=True)

    def _encode_image(self, array: np.ndarray, ext: str) -> tuple[bytes, str]:
        arr = np.clip(array, 0.0, 1.0).astype(np.float32)
        if arr.ndim == 2:
            mode = "L"
            pil_arr = (arr * 255.0).astype("uint8")
        else:
            mode = "RGB"
            pil_arr = (arr[..., :3] * 255.0).astype("uint8")
        img = Image.fromarray(pil_arr, mode=mode)
        from io import BytesIO

        buf = BytesIO()
        fmt = "PNG" if ext.lower() == "png" else "JPEG"
        if fmt == "JPEG" and mode == "L":
            img = img.convert("L")
        img.save(buf, format=fmt, quality=95)
        content_type = f"image/{'png' if fmt == 'PNG' else 'jpeg'}"
        return buf.getvalue(), content_type

    def upload_numpy(self, user_id: str, array: np.ndarray, ext: str = "png") -> StorageResult:
        ext = ext.lower().lstrip(".")
        image_bytes, content_type = self._encode_image(array, ext)
        height, width = array.shape[:2]
        file_name = f"{uuid.uuid4()}.{ext}"
        storage_path = f"{user_id}/{file_name}"
        if self.disabled or self.client is None:
            # local fake storage
            full_path = self.local_dir / storage_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(image_bytes)
            return StorageResult(path=str(storage_path), width=width, height=height, content_type=content_type, size=len(image_bytes))
        # real upload
        try:  # pragma: no cover - network
            self.client.storage.from_(self.bucket).upload(  # type: ignore[attr-defined]
                path=storage_path,
                file=image_bytes,
                file_options={"content-type": content_type},
                upsert=False,
            )
            return StorageResult(path=storage_path, width=width, height=height, content_type=content_type, size=len(image_bytes))
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Storage upload failed: {exc}")

    def download_to_numpy(self, path: str) -> np.ndarray:
        data = self.download_bytes(path)
        from io import BytesIO

        img = Image.open(BytesIO(data)).convert("RGB")
        arr = np.asarray(img).astype(np.float32) / 255.0
        return arr

    def download_bytes(self, path: str) -> bytes:
        if self.disabled or self.client is None:
            full_path = self.local_dir / path
            return full_path.read_bytes()
        # pragma: no cover - network
        return self.client.storage.from_(self.bucket).download(path)  # type: ignore[attr-defined]

    def delete(self, path: str) -> None:
        if self.disabled or self.client is None:
            full_path = self.local_dir / path
            if full_path.exists():
                full_path.unlink()
            return
        try:  # pragma: no cover - network
            self.client.storage.from_(self.bucket).remove([path])  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError(f"Storage delete failed: {exc}")
