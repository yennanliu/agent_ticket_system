import os
from typing import Optional
from github import Github

_SKIP_DIRS = {".git", "node_modules", "__pycache__", "output", ".venv", "dist", "build"}
_SOURCE_EXTS = {".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".sh"}
_MAX_BYTES = 50_000


def read_repo(source: str) -> dict:
    """Auto-detect local path vs GitHub URL and return RepoContext."""
    if source.startswith("http://") or source.startswith("https://"):
        return _read_github(source)
    return _read_local(source)


def _read_local(path: str) -> dict:
    abs_path = os.path.abspath(path)
    name = os.path.basename(abs_path)
    file_tree: list[str] = []
    file_contents_parts: list[str] = []
    readme = ""
    total_bytes = 0

    for root, dirs, files in os.walk(abs_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, abs_path)
            _, ext = os.path.splitext(fname)
            if ext.lower() not in _SOURCE_EXTS:
                continue
            file_tree.append(rel)
            if total_bytes >= _MAX_BYTES:
                continue
            try:
                content = open(fpath, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if fname.lower() == "readme.md" and not readme:
                readme = content
            chunk = f"### {rel}\n{content}\n\n"
            chunk_bytes = len(chunk.encode())
            if total_bytes + chunk_bytes > _MAX_BYTES:
                remaining = _MAX_BYTES - total_bytes
                chunk = chunk.encode()[:remaining].decode("utf-8", errors="ignore")
                file_contents_parts.append(chunk)
                total_bytes = _MAX_BYTES
                break
            file_contents_parts.append(chunk)
            total_bytes += chunk_bytes

    return {
        "name": name,
        "file_tree": file_tree,
        "readme": readme,
        "file_contents": "".join(file_contents_parts),
    }


def _read_github(url: str) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token) if token else Github()

    # Parse owner/repo from URL
    parts = url.rstrip("/").split("/")
    repo_id = f"{parts[-2]}/{parts[-1]}"
    repo = g.get_repo(repo_id)

    readme = ""
    try:
        readme = repo.get_readme().decoded_content.decode("utf-8", errors="ignore")
    except Exception:
        pass

    file_tree: list[str] = []
    file_contents_parts: list[str] = []
    total_bytes = 0

    try:
        contents = repo.get_contents("")
        for item in contents:
            if item.type == "file":
                file_tree.append(item.path)
    except Exception:
        pass

    issues_text = ""
    try:
        issues = list(repo.get_issues(state="open"))[:20]
        issues_text = "\n".join(f"#{i.number}: {i.title}" for i in issues)
    except Exception:
        pass

    if issues_text:
        file_contents_parts.append(f"### Open Issues\n{issues_text}\n\n")

    return {
        "name": repo.name,
        "file_tree": file_tree,
        "readme": readme,
        "file_contents": "".join(file_contents_parts),
    }
