# Setup and run (Docker)

Runs the whole project locally: web app, API, AI inspector, anchor worker, local blockchain, database and the simulated camera.

## Before you start
- Install **Git** and **Docker Desktop**, then start Docker Desktop and wait until it says "Engine running".
- Free ports: 5173 (web), 8000 (API), 8001 (AI), 8545 (blockchain), 5432 (database). A local PostgreSQL on 5432 can clash with the Docker one, so stop it if you have one.
- Use **PowerShell**. The commands below are written for it.

## 1. Get the code
```
git clone https://github.com/frchaitanyaaa/LEDGEIT.git
cd LEDGEIT
git checkout ishan
```
`main` has no code yet. The working code is on the `ishan` branch (it also contains Aryan's and the original MVP commits). Make sure the `infra/docker-compose.yml` fix that removes MinIO is pushed to that branch, or the stack will not start.

## 2. Configure
```
copy .env.example .env
$C = "docker compose -f infra/docker-compose.yml"
```
The `$C` shortcut is used in every command below. Set it again in each new PowerShell window.

## 3. Start everything
```
Invoke-Expression "$C up -d --build"
Invoke-Expression "$C ps"
```
The first build takes several minutes. Every service should show `Up`.

## 4. Load demo data (plant, lines, devices, users, models)
```
Invoke-Expression "$C exec api python -m ledgeit_api.db.seed"
```

## 5. Copy the tamper-lab scripts into the API container
Needed for the attack demo, and again after any rebuild.
```
Invoke-Expression "$C cp scripts api:/app/scripts"
```

## 6. Start the simulated camera
```
Invoke-Expression "$C --profile demo up -d edge-simulator"
```
It sends one inspection per second. Wait about a minute so records get anchored.

## 7. Open the app
http://localhost:5173

| User | Role |
|---|---|
| `qe@ledgeit.dev` | Quality Engineer |
| `qm@ledgeit.dev` | Quality Manager (sees Reports and Economics) |
| `auditor@ledgeit.dev` | Auditor |
| `operator@ledgeit.dev` | Operator |
| `admin@ledgeit.dev` | Admin |

Password for all: `ledgeit123`

The demo walkthrough is in [guide.md](guide.md).

## Useful commands
| Task | Command |
|---|---|
| Stop the camera | `Invoke-Expression "$C stop edge-simulator"` |
| Watch API logs | `Invoke-Expression "$C logs api --tail 40"` |
| Run one attack | `Invoke-Expression "$C exec api python /app/scripts/tamper-lab/tamper_lab.py edit-decision INS-<code>"` |
| Stop everything (keep data) | `Invoke-Expression "$C down"` |
| **Reset to clean data** (wipes everything) | `Invoke-Expression "$C down -v"`, then repeat steps 3 to 6 |

Attacks available in the tamper lab: `edit-decision`, `swap-image`, `delete-event`, `smart-insider`.

If you run these in Git Bash instead of PowerShell, prefix with `MSYS_NO_PATHCONV=1` or it rewrites the `/app/...` paths.

## Troubleshooting
- **Image pull error:** check Docker Desktop is running and you are online.
- **Port already in use:** stop the program using that port, then run `up -d` again.
- **A service keeps restarting:** run the logs command for that service (`logs <service> --tail 40`) and send the output to the team.
- **Dashboard shows lots of `DUPLICATE_EVIDENCE` alerts:** the simulator re-sent frames from an earlier run. Reset to clean data (see above) and start the simulator once.

## Optional: use the real YOLO model instead of the placeholder
1. Train it with `services/ai-inspector/training/colab_train.ipynb` on Google Colab.
2. Copy the downloaded `.pt` files and `manifest.json` into `services/ai-inspector/models/` (never commit the `.pt` files).
3. Set `MODEL_BACKEND=yolo` in `.env`, then run `Invoke-Expression "$C up -d --build ai-inspector"`.

Untested: switching to YOLO has not been run end to end yet.
