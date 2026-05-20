# Spend Management App

**Development Environment Setup**

Session Date: May 15, 2026

---

## 1. Project Overview

This document captures all setup steps completed during the first development session for the Spend Management application — a full-stack financial management platform built from scratch.

### 1.1 Architecture Decisions

The following stack was agreed upon after discussion:

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + Vite + Tailwind CSS | Component-based UI, fast dev server, utility styling |
| Backend API | FastAPI (Python) | Python-native for analytics, modern async framework |
| Database | MySQL 8 (Docker) | Relational data model suits financial data |
| Cache + Jobs | Redis + Celery | Background jobs for forecasting and reports |
| Package mgr (FE) | npm | Standard for JavaScript/Node ecosystem |
| Package mgr (BE) | uv | Fast modern Python package manager |
| Containers | Docker + Compose | Consistent local and production environments |
| Version control | Git + GitHub | Source control and remote backup |

### 1.2 Project Folder Structure

The project lives at `~/spend-management/` with the following top-level structure:

```
spend-management/
  client/          React + Vite frontend (npm)
  server/          FastAPI backend (uv/Python)
  infra/           Docker Compose + Nginx config
  .github/         CI/CD workflows (GitHub Actions)
  Makefile         Dev workflow shortcuts
  .gitignore       Git ignore rules
  README.md        Project documentation
```

---

## 2. Prerequisites Installed

The following tools were installed on the Mac (Apple Silicon / arm64) using Homebrew:

| Item | Status | Details |
|---|---|---|
| Homebrew 5.1.11 | Done | Mac package manager |
| Node.js v26.0.0 | Done | JavaScript runtime + Vite build tool |
| npm 11.12.1 | Done | Node package manager |
| Python 3.14.5 | Done | Backend language |
| uv 0.11.14 | Done | Python package manager |
| Git 2.50.1 | Done | Version control |
| Docker Desktop 29.4.3 | Done | Container runtime |
| VS Code 1.120.0 | Done | Code editor |
| MySQL Workbench | Done | Database GUI client |

### 2.1 Installation Commands

**Homebrew**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv zsh)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv zsh)"
```

**Core tools**

```bash
brew install node git
brew install --cask docker visual-studio-code mysqlworkbench
```

**Python + uv**

```bash
brew install python
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

## 3. Frontend Setup (`client/`)

### 3.1 Scaffold React + Vite Project

```bash
cd ~/spend-management/client
npm create vite@latest . -- --template react
```

### 3.2 Install Dependencies

```bash
npm install axios react-router-dom recharts
npm install -D tailwindcss @tailwindcss/vite
```

### 3.3 Configure Tailwind CSS v4

Tailwind v4 uses a Vite plugin — no `tailwind.config.js` needed. Update `vite.config.js`:

```js
import tailwindcss from '@tailwindcss/vite'
plugins: [react(), tailwindcss()]
```

Replace contents of `src/index.css` with:

```css
@import "tailwindcss";
```

### 3.4 Configure Vite Proxy

Added API proxy in `vite.config.js` so frontend calls to `/api` route to the backend:

```js
server: { proxy: { '/api': 'http://localhost:8000' } }
```

### 3.5 Start Frontend Dev Server

```bash
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## 4. Backend Setup (`server/`)

### 4.1 Initialize Python Project

```bash
cd ~/spend-management/server
uv init
uv python pin 3.14
```

### 4.2 Install Python Dependencies

```bash
uv add fastapi uvicorn sqlalchemy pydantic-settings python-jose passlib bcrypt celery redis pandas numpy scikit-learn python-multipart pymysql
```

### 4.3 Create FastAPI Entry Point

Created `server/src/main.py` with CORS middleware configured to allow the frontend origin:

```bash
uv run uvicorn src.main:app --reload --port 8000
```

- Backend runs at: `http://localhost:8000`
- Swagger API docs at: `http://localhost:8000/docs`

### 4.4 Backend Folder Structure

```
server/src/
  api/         Route handlers (dashboard, spend, planning, forecast, reporting, approvals, auth)
  models/      SQLAlchemy ORM models (transaction, budget, vendor, approval, user)
  schemas/     Pydantic request/response shapes
  services/    Business logic (forecast_engine, anomaly_detector, budget_service, etc.)
  workers/     Celery background tasks (report, email, forecast workers)
  db/          Database session and base
  core/        Config, security, dependency injection
  main.py      FastAPI app entry point
```

---

## 5. Database + Cache Setup

### 5.1 Docker Compose Configuration

Created `infra/docker-compose.yml` with MySQL 8 and Redis 7 services:

| Setting | Value |
|---|---|
| MySQL image | mysql:8 |
| MySQL container | spend-db |
| MySQL port | 3306 |
| Database name | spend_management |
| DB username | spend_user |
| DB password | spend_pass |
| Redis image | redis:7-alpine |
| Redis container | spend-redis |
| Redis port | 6379 |

### 5.2 Start Containers

```bash
cd ~/spend-management/infra
docker compose up -d
```

### 5.3 MySQL Workbench Connection

Connected MySQL Workbench to the Docker container with these settings:

| Field | Value |
|---|---|
| Connection name | spend-management |
| Hostname | 127.0.0.1 |
| Port | 3306 |
| Username | spend_user |
| Password | spend_pass |
| Default schema | spend_management |

> **Note:** MySQL Workbench shows a version warning (8.4.9 vs supported 8.0) — click **Continue Anyway**. Everything works correctly.

---

## 6. Git + GitHub Setup

### 6.1 Configure Git Identity

```bash
git config --global user.name "radhanatarajan"
git config --global user.email "radhanatarajan@yahoo.com"
```

### 6.2 Initialize Repository and First Commit

```bash
cd ~/spend-management
git init
git add .
git commit -m "initial setup: React + Vite + Tailwind frontend, FastAPI backend"
```

### 6.3 Push to GitHub

Created a private repository at `github.com/radhanatarajan/spend-management`, then:

```bash
git remote add origin https://github.com/radhanatarajan/spend-management.git
git branch -M main
git push -u origin main
```

> **Note:** A Personal Access Token (classic) with `repo` scope was used as the Git password. GitHub no longer accepts account passwords for CLI operations.

---

## 7. Dev Workflow Shortcuts (Makefile)

Added a `Makefile` at the project root with shortcuts for daily development:

| Command | What it does |
|---|---|
| `make dev-db` | Starts MySQL + Redis containers via Docker Compose |
| `make dev-api` | Starts FastAPI backend on port 8000 with hot reload |
| `make dev-client` | Starts React frontend on port 5173 with hot reload |
| `make stop` | Stops all Docker containers |

### 7.1 Daily Startup Order

1. Start Docker Desktop (from Applications) — wait for engine to start
2. Run: `make dev-db`  (starts MySQL + Redis)
3. Run: `make dev-api`  (in a new terminal tab)
4. Run: `make dev-client`  (in a new terminal tab)

---

## 8. Running Services Summary

| Item | Status | Details |
|---|---|---|
| React frontend | Running | http://localhost:5173 |
| FastAPI backend | Running | http://localhost:8000 |
| Swagger API docs | Running | http://localhost:8000/docs |
| MySQL database | Running | localhost:3306 (Docker) |
| Redis cache | Running | localhost:6379 (Docker) |
| GitHub repository | Connected | github.com/radhanatarajan/spend-management |

---

## 9. What's Next

The development environment is fully set up. The following steps are planned for the next session:

- Install VS Code extensions (Python, Pylance, Ruff, ESLint, Prettier, Tailwind IntelliSense, Docker, GitLens)
- Connect FastAPI to MySQL using SQLAlchemy + PyMySQL
- Create database models: User, Transaction, Budget, Vendor, Approval
- Build first API routes: authentication (login/token) and dashboard data
- Wire frontend to backend — first real data flowing end to end
- Set up Celery workers for background jobs
