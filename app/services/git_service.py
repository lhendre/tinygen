# app/services/git_service.py
import os
import pathlib
from typing import List, Tuple

import git  # GitPython


def clone_repo(repo_url: str, target_dir: str) -> str:
    """
    Clone repo into target_dir/repo and return that path.
    """
    repo_path = os.path.join(target_dir, "repo")
    git.Repo.clone_from(repo_url, repo_path)
    return repo_path


# We’ll treat these as “texty” by extension. If something slips through,
# we still decode with errors="replace" so the model gets *something*.
TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".md", ".toml", ".ini",
    ".yml", ".yaml",
    ".sh", ".bash", ".zsh",
    ".env", ".cfg", ".txt",
    ".css", ".scss", ".less",
    ".html", ".htm",
    ".mjs", ".cjs",
    ".csv", ".tsv"
}


def list_all_text_files(repo_path: str, max_files: int = 2000, max_size_kb: int = 1024) -> List[str]:
    """
    Return up to max_files relative paths of candidate text files, each <= max_size_kb.
    We assume small repos, so defaults are generous but bounded.
    """
    root = pathlib.Path(repo_path)
    files: List[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        # skip hidden/VC dirs
        if any(seg.startswith(".git") for seg in rel.split(os.sep)):
            continue
        try:
            size_ok = p.stat().st_size <= max_size_kb * 1024
        except Exception:
            size_ok = False
        if size_ok and (p.suffix.lower() in TEXT_EXTS or p.suffix == "" or _looks_text(p)):
            files.append(rel)
        if len(files) >= max_files:
            break
    return files


def _looks_text(path: pathlib.Path) -> bool:
    """
    Heuristic: try to read a small prefix as utf-8.
    """
    try:
        with path.open("rb") as fh:
            chunk = fh.read(2048)
        chunk.decode("utf-8")
        return True
    except Exception:
        return False


def read_all_text_files(repo_path: str, paths: List[str], per_file_char_cap: int = 200_000) -> List[Tuple[str, str]]:
    """
    Read all given files (assumed small). Each file is read fully up to per_file_char_cap.
    Returns list of (relative_path, text).
    """
    root = pathlib.Path(repo_path)
    out: List[Tuple[str, str]] = []

    for rel in paths:
        p = root / rel
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            # last resort: try binary->utf8 replacement
            try:
                with p.open("rb") as fh:
                    text = fh.read().decode("utf-8", errors="replace")
            except Exception:
                continue
        if len(text) > per_file_char_cap:
            text = text[:per_file_char_cap]
        out.append((rel, text))

    return out


def strip_fences(s: str) -> str:
    """
    Remove triple-backtick fences if present.
    """
    s = s.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s
