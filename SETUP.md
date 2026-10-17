# Run TraceFront

**You need:**
- Node.js 18.17 or newer
- Python 3.11 or newer
- For LinuxONE, the SSH key file `linuxone-teammate`

Run every command in **PowerShell** from the repository root, unless a step says `cd`.

## 1. Connect to LinuxONE

The backend API, the ML models and the database all run on the server. This step connects your computer to them.

1. Save the key as `%USERPROFILE%\.ssh\linuxone-teammate`. Ask a teammate for it.
2. Open the tunnel, and leave this terminal open:

   ```powershell
   .\backend\demo-tunnel.ps1
   ```

   - http://localhost:8000 now reaches the server's backend API.
   - http://localhost:8100 now reaches the server's ML service.
   - The server's database is used automatically.

3. Check that it works, in a new terminal:

   ```powershell
   python -B backend\preflight.py
   ```

   It should end with `ready: durable backend, all five pathogen models and explanations`.

## 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

- `npm install` is only needed the first time, when there is no `node_modules` folder yet.
- Open http://localhost:3000.
- If the dev server prints `localhost:3001`, another frontend is holding port 3000. Stop it with Ctrl+C in its terminal, then run `npm run dev` again.

## 3. Backend on your own machine

You only need this to change backend code. For the demo, step 1 already gives you the server's backend.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Set-Content .env "DATABASE_URL=sqlite:///./tracefront.db"
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

- The first four lines are only needed the first time.
- Open http://localhost:8000/docs to check it's running.
- Your local backend now uses port 8000, so open the tunnel with the server's backend on another port. You still get the server's ML service on 8100:

  ```powershell
  .\backend\demo-tunnel.ps1 -BackendPort 18000
  ```

- To run the tests:

  ```powershell
  .\.venv\Scripts\python -B -m unittest app.test_system
  ```

## 4. Ship code to LinuxONE

Commit first, then:

```powershell
.\backend\deploy.ps1
```

## If something goes wrong

| Problem | Fix |
|---|---|
| "Cannot reach the backend API at http://localhost:8000" | The tunnel isn't running. Run step 1 again. |
| "Cannot reach the service at http://localhost:18000" | You're on an old frontend build. Stop it and run `npm run dev`. |
| `Permission denied (publickey)` | The key is missing, or you ran it from Git Bash. Use PowerShell. |
| PowerShell won't run `.ps1` files | Use `powershell -ExecutionPolicy Bypass -File .\backend\demo-tunnel.ps1` |
| Port 8000 or 8100 already in use | Stop the local backend or ML service first, or use `-BackendPort 18000` as in step 3. |

To stop anything, press Ctrl+C in its terminal.
