Check and start all local development components for the spend-management project. Work through each step in order and report status clearly.

## Step 1 — Docker Desktop

Run: `docker info 2>/dev/null | head -1`

- If Docker is not running (command fails or returns error), tell the user to open Docker Desktop and wait for it to start, then stop — nothing else can proceed without Docker.
- If Docker is running, note it as ✓ and continue.

## Step 2 — MySQL Container (port 3306)

Run: `docker ps --format "{{.Names}}\t{{.Status}}" 2>/dev/null`

- If a container named `spend-db` (or similar spend-management DB container) is listed with status `Up`, note it as ✓.
- If not running, start it: `cd /Users/radhanatarajan/spend-management && make dev-db`
  - Wait for the command to complete, then re-run `docker ps` to confirm the container is Up.

## Step 3 — FastAPI Server (port 8000)

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs`

- If response is `200`, the API is already running — note it as ✓.
- If not reachable, start it in the background:
  `cd /Users/radhanatarajan/spend-management && make dev-api > /tmp/spend-api.log 2>&1 &`
  Wait 5 seconds, then re-check the curl. If still not up, show the last 20 lines of `/tmp/spend-api.log` to help debug.

## Step 4 — Vite Client (port 5173)

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173`

- If response is `200`, the client is already running — note it as ✓.
- If not reachable, start it in the background:
  `cd /Users/radhanatarajan/spend-management && make dev-client > /tmp/spend-client.log 2>&1 &`
  Wait 5 seconds, then re-check the curl. If still not up, show the last 20 lines of `/tmp/spend-client.log` to help debug.

## Step 5 — Final Summary

Print a status table:

| Component       | Status | URL                          |
|-----------------|--------|------------------------------|
| Docker Desktop  | ✓ / ✗  |                              |
| MySQL (Docker)  | ✓ / ✗  | localhost:3306                |
| FastAPI API     | ✓ / ✗  | http://localhost:8000/docs   |
| Vite Client     | ✓ / ✗  | http://localhost:5173        |

If all green: tell the user the stack is ready and they can open http://localhost:5173.
If anything is red: tell the user exactly what failed and what to do next.
