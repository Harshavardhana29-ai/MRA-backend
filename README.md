# MRA Backend

FastAPI + PostgreSQL backend for the **Market Research Agent** application.

---

## Prerequisites

| Tool       | Version     | Notes                           |
|------------|-------------|---------------------------------|
| Python     | 3.11+       | 3.13 recommended                |
| PostgreSQL | 14+         | Must be running as a service    |
| Git        | any         | To clone the repo               |

---

## ⚡ Quick Setup (Automated)

```bash
# 1. Clone the repo and navigate to Backend
cd Backend

# 2. Run the setup script
python setup.py
```

The script will:
1. Create a virtual environment (`venv/`)
2. Install all Python dependencies
3. Prompt for your PostgreSQL credentials and create `.env`
4. Create the `mra_db` database
5. Run Alembic migrations (creates all tables)
6. Seed agent + topic mapping data

After setup, start the server:

```bash
# Windows
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# macOS / Linux
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

---

## 🛠️ Manual Setup (Step by Step)

### 1. Create virtual environment

```bash
python -m venv venv

# Activate it
# Windows:
.\venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
# Copy the example file
cp .env.example .env        # macOS/Linux
copy .env.example .env      # Windows
```

Edit `.env` and set your PostgreSQL password:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/mra_db
NEWS_AGENT_API_URL=https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask
CORS_ORIGINS=http://localhost:8080,http://localhost:5173,http://localhost:3000,http://localhost:8081
```

### 4. Create the database

Open `psql` or pgAdmin and run:

```sql
CREATE DATABASE mra_db;
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Seed data

```bash
python -m app.seed
```

### 7. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Endpoints

| Method | Endpoint                              | Description                  |
|--------|---------------------------------------|------------------------------|
| GET    | `/api/health`                         | Health check                 |
| GET    | `/api/data-sources`                   | List all data sources        |
| POST   | `/api/data-sources`                   | Create a data source         |
| PUT    | `/api/data-sources/{id}`              | Update a data source         |
| DELETE | `/api/data-sources/{id}`              | Delete a data source         |
| GET    | `/api/workflows`                      | List all workflows           |
| POST   | `/api/workflows`                      | Create a workflow            |
| GET    | `/api/workflows/{id}`                 | Get workflow details         |
| PUT    | `/api/workflows/{id}`                 | Update a workflow            |
| DELETE | `/api/workflows/{id}`                 | Soft-delete a workflow       |
| GET    | `/api/agents`                         | List all agents              |
| GET    | `/api/agents/by-topics?topics=...`    | Get agents for given topics  |
| GET    | `/api/agents/topic-mapping`           | Full topic → agents map      |
| POST   | `/api/runs`                           | Start a workflow run         |
| GET    | `/api/runs/{id}`                      | Get run status & report      |
| GET    | `/api/runs/{id}/logs`                 | Get run activity logs        |
| GET    | `/api/runs/stats`                     | Run statistics               |

Interactive API docs available at: **http://localhost:8000/docs**

---

## 📁 Project Structure

```
Backend/
├── setup.py              # Automated setup script
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .env                  # Your local env config (git-ignored)
├── alembic.ini           # Alembic configuration
├── alembic/              # Database migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── config.py         # Settings (reads from .env)
│   ├── database.py       # Async SQLAlchemy engine & session
│   ├── seed.py           # Seed data script
│   ├── models/           # SQLAlchemy ORM models
│   │   ├── agent.py      # Agent, AgentTopicMapping
│   │   ├── data_source.py# DataSource
│   │   ├── workflow.py   # Workflow, WorkflowDataSource, WorkflowAgent
│   │   └── run.py        # WorkflowRun, RunLog
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic layer
│   └── api/              # FastAPI route handlers
└── venv/                 # Virtual environment (git-ignored)
```

---

## 🔧 Environment Variables

| Variable           | Description                                      | Example                                                                 |
|--------------------|--------------------------------------------------|-------------------------------------------------------------------------|
| `DATABASE_URL`     | Async PostgreSQL connection string               | `postgresql+asyncpg://postgres:pass@localhost:5432/mra_db`              |
| `NEWS_AGENT_API_URL` | URL of the News Aggregator agent API           | `https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask`               |
| `CORS_ORIGINS`     | Comma-separated allowed frontend origins         | `http://localhost:8080,http://localhost:5173`                            |

---

## 🔄 Common Commands

```bash
# Start dev server
uvicorn app.main:app --reload --port 8000

# Create a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Apply migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Re-seed data
python -m app.seed
```

---

## ❓ Troubleshooting

| Problem                            | Solution                                                          |
|------------------------------------|-------------------------------------------------------------------|
| `Connection refused` on startup    | Make sure PostgreSQL service is running                            |
| `database "mra_db" does not exist` | Run `CREATE DATABASE mra_db;` in psql or use `setup.py`           |
| `ModuleNotFoundError`              | Activate the virtual environment first                            |
| CORS errors in browser             | Add your frontend URL to `CORS_ORIGINS` in `.env`                 |
| Agents not showing for a topic     | Check `agent_topic_mappings` table or re-run `python -m app.seed` |
