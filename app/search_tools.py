import os
import re
from typing import Optional

_CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".rs",
              ".cpp", ".c", ".h", ".cs", ".swift", ".kt", ".php", ".sh"}
_DOC_EXTS  = {".md", ".rst", ".txt", ".adoc", ".mdx"}
_DESIGN_PATTERN = re.compile(r"design|spec|diagram|arch|figma|wireframe|mockup", re.I)


def classify_file(path: str) -> str:
    _, ext = os.path.splitext(path)
    if ext.lower() in _CODE_EXTS:
        return "code"
    if ext.lower() in _DOC_EXTS:
        return "doc"
    if _DESIGN_PATTERN.search(path):
        return "design"
    return "doc"


def _github_blob_url(source: str, file_path: str) -> Optional[str]:
    if not source.startswith("https://github.com/"):
        return None
    base = source.rstrip("/")
    if base.endswith(".git"):
        base = base[:-4]
    return f"{base}/blob/main/{file_path}"


def _ddg_search(query: str, max_results: int = 3) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        return results or []
    except Exception:
        return []


def find_refs(
    related_files: list[str],
    source: str,
    repo_name: str,
) -> list[dict]:
    """
    Build suggested_change_refs for the given related_files.
    GitHub sources: construct blob URL directly.
    Local sources: DuckDuckGo search for relevant docs.
    All errors are caught; returns partial results or [].
    """
    refs = []
    is_github = source.startswith("https://github.com/")

    for file_path in related_files:
        ref_type = classify_file(file_path)
        try:
            if is_github:
                url = _github_blob_url(source, file_path)
                if url:
                    refs.append({
                        "file": file_path,
                        "ref_type": ref_type,
                        "ref_url": url,
                        "title": file_path,
                    })
            else:
                if ref_type == "code":
                    query = f"{repo_name} {file_path} implementation reference"
                else:
                    query = f"{repo_name} {file_path} documentation"
                results = _ddg_search(query, max_results=1)
                if results:
                    r = results[0]
                    refs.append({
                        "file": file_path,
                        "ref_type": ref_type,
                        "ref_url": r.get("href", ""),
                        "title": r.get("title", file_path),
                    })
        except Exception:
            continue

    return refs
