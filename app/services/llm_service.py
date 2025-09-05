# app/services/llm_service.py
import os
from typing import List, Tuple

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

from app.services.git_service import (
    list_all_text_files,
    read_all_text_files,
    strip_fences,
)

# ------------ Model ------------
MODEL_NAME = "gpt-4o-mini"

# Load .env (nearest found)
load_dotenv(find_dotenv(), override=True)

# ------------ OpenAI client ------------
def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or export it.")
    return OpenAI(api_key=api_key)

def _chat(system: str, user: str) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

# ------------ Prompt templates ------------
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

# Single reflection+revision call:
# If the diff is acceptable, return EXACTLY "NO_CHANGE" (or "OK").
# Otherwise, return ONLY a corrected raw unified diff (no commentary).
REFLECT_SYSTEM = """You are a senior engineer validating a unified diff.

Return rules (MUST follow):
- If the provided diff is valid and suitably addresses the user's goal, return EXACTLY:
NO_CHANGE
  (You may also return OK; both mean keep the original.)
- Otherwise, return ONLY a corrected raw unified diff that fixes problems and better satisfies the goal.
- Absolutely no code fences, no prose, no extra text beyond either 'NO_CHANGE'/'OK' or the raw diff.
"""

REFLECT_USER = """User goal:
{user_prompt}

Repo file list:
{file_list}

Proposed diff:
{primary_diff}
"""

# ------------ Helpers ------------
def _build_context(repo_path: str, user_prompt: str) -> Tuple[str, str]:
    files = list_all_text_files(repo_path, max_files=2000, max_size_kb=1024)
    file_list = "\n".join(f"- {p}" for p in files) if files else "(no text files found)"
    blobs: List[str] = []
    for rel, text in read_all_text_files(repo_path, files, per_file_char_cap=200_000):
        blobs.append(f"\n===== {rel} =====\n{text}")
    file_blobs = "\n".join(blobs) if blobs else "(no contents)"
    return file_list, file_blobs

def _ensure_raw_diff(s: str) -> str:
    s = strip_fences(s)
    lines = s.splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("diff --git "):
        i += 1
    return "\n".join(lines[i:]).strip()

def _looks_like_diff(diff_text: str) -> bool:
    return (
        bool(diff_text)
        and diff_text.startswith("diff --git ")
        and ("--- " in diff_text)
        and ("+++ " in diff_text)
        and ("@@ " in diff_text)
    )

# ------------ Public API (exactly 2 LLM calls) ------------
def generate_diff_with_reflection(repo_path: str, user_prompt: str) -> str:
    """
    Two-call workflow:
      1) Generate a diff from full repo context.
      2) Reflection: returns 'NO_CHANGE'/'OK' (keep primary) OR a corrected raw diff.
    """
    # Build context once
    file_list, file_blobs = _build_context(repo_path, user_prompt)

    # === Call 1: Primary generation ===
    user_gen = GEN_PROMPT.format(
        user_prompt=user_prompt,
        file_list=file_list,
        file_blobs=file_blobs,
    )
    primary = _ensure_raw_diff(_chat(SYSTEM_RULES, user_gen))

    # === Call 2: Reflection (NO_CHANGE/OK or corrected diff) ===
    reflect_resp = _chat(
        REFLECT_SYSTEM,
        REFLECT_USER.format(
            user_prompt=user_prompt,
            file_list=file_list,
            primary_diff=primary[:250_000],  # keep payload reasonable
        ),
    ).strip()

    upper = reflect_resp.upper()
    if upper in ("NO_CHANGE", "OK"):
        # keep original result (even if it's imperfect, by spec)
        return primary

    # Otherwise reflection returned a diff — prefer it if it looks valid
    revised = _ensure_raw_diff(reflect_resp)
    if _looks_like_diff(revised):
        return revised

    # Fallbacks
    if _looks_like_diff(primary):
        return primary
    return revised or primary
