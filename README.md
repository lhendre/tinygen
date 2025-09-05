
# TinyGen II

TinyGen is a toy service inspired by Codegen:

- Clones a small public GitHub repo  
- Takes a free-form prompt  
- Returns a **unified diff** describing the changes  

Built with **FastAPI**, **Uvicorn**, and **OpenAI**.  
Bonus: can log all inputs/outputs to **Supabase**.

---

## 🚀 Local Setup (Mac)

### Prereqs
- macOS with [Homebrew](https://brew.sh/)
- Python 3.11+ (3.12 recommended)
- Git
- OpenAI API key

Install system deps:

```bash
brew install python@3.12 git
```

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/tinygen2.git
cd tinygen2
```

### 2. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install requirements

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. Configure environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
# Optional Supabase logging:
# SUPABASE_URL=https://<project-ref>.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
```
Currently are Supabase information is hardcoded in for the purpose of the demo, you can optionally add in your own in the file or move it to the .env variable.  These will cease to work after 9/5/2025
### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:  
👉 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📡 Public Demo (EC2)

This project is temporarily deployed at:

👉 **http://ec2-54-91-119-244.compute-1.amazonaws.com:8000/docs**

> Note: this runs on plain HTTP for demo purposes (no HTTPS).  
> Logs are written to `/tmp/tinygen.log` on the host.

---

## 🔌 API Endpoints

### `POST /generate-diff`

Takes JSON body:

```json
{
  "repoUrl": "https://github.com/jayhack/llm.sh",
  "prompt": "# The program doesn't output anything in windows 10\n(base) C:\\Users\\off99\\Documents\\Code\\>llm list files in current dir; windows\n/ Querying GPT-3200\n───────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n       │ File: temp.sh\n───────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n   1   │\n   2   │ dir\n   3   │ ```\n───────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────\n>> Do you want to run this program? [Y/n] y\n\nRunning...\n\n\n(base) C:\\Users\\off99\\Documents\\Code\\>\nNotice that there is no output. Is this supposed to work on Windows also?\nAlso it might be great if the script detects which OS or shell I'm using and try to use the appropriate command e.g. dir instead of ls because I don't want to be adding windows after every prompt."
}
```

Returns:

```json
{
  "diff": "diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py\n@@ -19,7 +19,10 @@\n-    os.system('bash temp.sh')\n+    if os.name == 'nt':\n+        os.system('powershell.exe .\\\\temp.sh')\n+    else:\n+        os.system('bash temp.sh')"
}
```

### `POST /generate-diff/raw`

- Query param: `?repoUrl=<github-url>`
- Body: raw prompt text

### `GET /health`

Health check → `{ "ok": true }`

---

## 🗄️ (Optional) Supabase Logging

If you configure Supabase, all runs (repo, prompt, diff, status) are logged into a `tinygen_runs` table.

Setup:

1. In Supabase SQL Editor, create the table (see `/app/services/supabase_service.py` for schema).
2. Add env vars to `.env`:

   ```bash
   SUPABASE_URL=...
   SUPABASE_SERVICE_ROLE_KEY=...
   ```

3. Restart the app. Use `/debug/supabase/status` to verify.

---

## ⚠️ Notes

- This is **not production hardened**. Uvicorn is exposed directly in the demo.
- HTTPS requires a reverse proxy (Caddy/Nginx) + a custom domain.
- The service is designed for **small repos** (for demo purposes).  
- Keep your OpenAI + Supabase keys secret — don’t commit `.env`as we do in this demo.
