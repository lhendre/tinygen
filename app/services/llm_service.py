# app/services/llm_service.py
import os
from typing import List, Tuple

from dotenv import load_dotenv,find_dotenv
from openai import OpenAI

from app.services.git_service import (
    list_all_text_files,
    read_all_text_files,
    strip_fences,
)

MODEL_NAME = "gpt-4o-mini"  # expose for logging


# Load .env if present
load_dotenv(find_dotenv(), override=True)

# ---------- OpenAI client ----------

def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or export it.")
    return OpenAI(api_key=api_key)

def _chat(system: str, user: str) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL_NAME,   # <— use the constant
        temperature=0.0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

# ---------- Prompt templates ----------

SYSTEM_RULES = """You are a meticulous software engineer that outputs VALID UNIX unified diffs only.

Output requirements (STRICT):
- Output RAW unified diff only. NO code fences. NO prose or explanations.
- The FIRST non-empty line MUST start with: diff --git
- Use canonical headers:
  diff --git a/path/file.ext b/path/file.ext
  --- a/path/file.ext
  +++ b/path/file.ext
- Include @@ hunk headers with correct unchanged context lines.
- When creating new files, use '/dev/null' as the old path.
- Do NOT include any text before or after the diff. No leading/trailing fences or commentary.
"""

GEN_PROMPT = """Goal (user prompt):
{user_prompt}

Repository file tree:
{file_list}

Full file contents (for ALL files listed, truncated only if extremely large):
{file_blobs}

Task:
Generate the unified diff that implements the goal in THIS repository.
Follow SYSTEM RULES strictly. Output ONLY the raw unified diff.
"""

# ---------- Helpers ----------

def _build_context(repo_path: str, user_prompt: str) -> Tuple[str, str]:
    """
    Build a full repo snapshot: list + full contents for all text files (assume small repos).
    Returns (file_list, file_blobs).
    """
    files = list_all_text_files(repo_path, max_files=2000, max_size_kb=1024)
    file_list = "\n".join(f"- {p}" for p in files) if files else "(no text files found)"

    blobs: List[str] = []
    for rel, text in read_all_text_files(repo_path, files, per_file_char_cap=200_000):
        blobs.append(f"\n===== {rel} =====\n{text}")
    file_blobs = "\n".join(blobs) if blobs else "(no contents)"

    return file_list, file_blobs


def _ensure_raw_diff(s: str) -> str:
    """
    Strip code fences and any preface before the first 'diff --git' header.
    """
    s = strip_fences(s)
    lines = s.splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("diff --git "):
        i += 1
    return "\n".join(lines[i:]).strip()

# ---------- Public API ----------

def generate_diff_with_reflection(repo_path: str, user_prompt: str) -> str:
    """
    Generate and return a unified diff string based on the FULL repo context + prompt.
    (No applying, no reflection, no planning — just pass everything to the model.)
    """
    file_list, file_blobs = _build_context(repo_path, user_prompt)
    user = GEN_PROMPT.format(
        user_prompt=user_prompt,
        file_list=file_list,
        file_blobs=file_blobs,
    )
    diff = _chat(SYSTEM_RULES, user)
    return _ensure_raw_diff(diff)
