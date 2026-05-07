import os
from fastapi import APIRouter, HTTPException

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
_APP_ROOT = os.path.join(_PROJECT_ROOT, "app")


def make_router() -> APIRouter:
    r = APIRouter(prefix="/api", tags=["source"])

    @r.get("/source")
    def get_source(file: str):
        if not file.endswith(".py") or ".." in file:
            raise HTTPException(status_code=403, detail="Only .py files in app/ are accessible")
        abs_path = os.path.normpath(os.path.join(_PROJECT_ROOT, file))
        if not abs_path.startswith(_APP_ROOT) or not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="File not found")
        try:
            return {"file": file, "content": open(abs_path, encoding="utf-8").read()}
        except OSError as exc:
            raise HTTPException(status_code=404, detail="File not found") from exc

    return r
