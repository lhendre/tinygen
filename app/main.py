import os
import shutil
import tempfile
import time

from fastapi import FastAPI, Body, Form
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env early
load_dotenv(override=False)

from app.services.git_service import clone_repo
from app.services.llm_service import generate_diff_with_reflection, MODEL_NAME
from app.services.supabase_service import log_run

app = FastAPI(title="TinyGen II")

class GenerateRequest(BaseModel):
    repoUrl: str
    prompt: str

@app.get("/health")
def health():
    return {"ok": True}

def _run_generation(repo_url: str, prompt: str):
    t0 = time.time()
    tempdir = tempfile.mkdtemp()
    try:
        repo_path = clone_repo(repo_url, tempdir)
        diff = generate_diff_with_reflection(repo_path, prompt)
        latency_ms = int((time.time() - t0) * 1000)
        # Log success to Supabase (non-blocking)
        log_run(repo_url, prompt, status="ok", diff=diff, model=MODEL_NAME, latency_ms=latency_ms)
        return {"diff": diff}
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        log_run(repo_url, prompt, status="error", error=str(e), model=MODEL_NAME, latency_ms=latency_ms)
        # Re-raise to return the 500 to the caller
        raise
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)

# JSON body (Pydantic)
@app.post("/generate-diff")
def generate_diff_json(body: GenerateRequest):
    return _run_generation(body.repoUrl, body.prompt)

# Form body (helpful in Swagger/Postman)
@app.post("/generate-diff/form")
def generate_diff_form(
    repoUrl: str = Form(...),
    prompt: str = Form(...)
):
    return _run_generation(repoUrl, prompt)

# Raw text body for prompt; repoUrl as query string
@app.post("/generate-diff/raw")
def generate_diff_raw(
    repoUrl: str,
    prompt: str = Body(..., media_type="text/plain"),
):
    return _run_generation(repoUrl, prompt)

