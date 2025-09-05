# app/services/supabase_service.py
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(override=False)

_SUPABASE_CLIENT: Optional[Client] = None

def get_client() -> Client:
    global _SUPABASE_CLIENT
    if _SUPABASE_CLIENT is None:
        url = "https://njkcrjfpmjrvpxugylfi.supabase.co"
        key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5qa2NyamZwbWpydnB4dWd5bGZpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NzAzMDc3NiwiZXhwIjoyMDcyNjA2Nzc2fQ.L-q7pWZweM581JuvtdLVs7575Vidvzp01kQS4G8vMiU"
        _SUPABASE_CLIENT = create_client(url, key)
    return _SUPABASE_CLIENT

def log_run(
    repo_url: str,
    prompt: str,
    status: str,
    diff: Optional[str] = None,
    error: Optional[str] = None,
    model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Fire-and-forget logging. Never raises.
    """
    try:
        payload: Dict[str, Any] = {
            "repo_url": repo_url,
            "prompt": prompt,
            "status": status,            # 'ok' | 'error'
            "diff": diff,
            "error": error,
            "model": model,
            "latency_ms": latency_ms,
            "meta": extra or {},
        }
        # Trim extremely large diffs to keep rows insertable
        if payload.get("diff") and len(payload["diff"]) > 900_000:
            payload["diff"] = payload["diff"][:900_000]

        get_client().table("tinygen_runs").insert(payload).execute()
    except Exception as e:
        # Don’t crash the request if logging fails.
        print(f"[supabase] log_run failed: {e}")