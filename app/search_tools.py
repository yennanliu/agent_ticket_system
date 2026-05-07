import os
import re
from typing import Optional

_CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".rs",
              ".cpp", ".c", ".h", ".cs", ".swift", ".kt", ".php", ".sh"}
_DOC_EXTS  = {".md", ".rst", ".txt", ".adoc", ".mdx"}
_DESIGN_PATTERN = re.compile(r"design|spec|diagram|arch|figma|wireframe|mockup", re.I)
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
_SNIPPET_BYTES = 500


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


def _walk_file_tree(abs_source: str) -> list[str]:
    """Return relative paths of all non-skipped files under abs_source."""
    paths: list[str] = []
    for root, dirs, files in os.walk(abs_source):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            paths.append(os.path.relpath(fpath, abs_source))
    return paths


def _path_similarity(query: str, candidate: str) -> float:
    """Jaccard similarity on lowercase path tokens (split on /._-)."""
    tokens = lambda s: set(re.split(r"[/._\-]", s.lower())) - {""}
    q, c = tokens(query), tokens(candidate)
    if not q or not c:
        return 0.0
    return len(q & c) / len(q | c)


def _local_ref(file_path: str, abs_source: str, ref_type: str) -> Optional[dict]:
    """
    Resolve file_path against the local repo. Tries exact match first,
    then falls back to highest Jaccard-similarity file in the tree.
    Returns None if nothing plausible is found.
    """
    exact = os.path.join(abs_source, file_path)
    if os.path.isfile(exact):
        matched = file_path
    else:
        tree = _walk_file_tree(abs_source)
        if not tree:
            return None
        matched = max(tree, key=lambda p: _path_similarity(file_path, p))
        if _path_similarity(file_path, matched) == 0.0:
            return None

    abs_file = os.path.join(abs_source, matched)
    snippet = ""
    try:
        with open(abs_file, encoding="utf-8", errors="ignore") as fh:
            snippet = fh.read(_SNIPPET_BYTES)
    except OSError:
        pass

    return {
        "file": matched,
        "ref_type": ref_type,
        "ref_url": f"file://{abs_file}",
        "title": matched,
        "snippet": snippet,
    }


def find_refs(
    related_files: list[str],
    source: str,
    repo_name: str,
) -> list[dict]:
    """
    Build suggested_change_refs for the given related_files.
    GitHub sources: construct blob URL directly.
    Local sources: resolve against the local file tree using path similarity.
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
                ref = _local_ref(file_path, os.path.abspath(source), ref_type)
                if ref:
                    refs.append(ref)
        except Exception:
            continue

    return refs
