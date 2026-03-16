"""
MRA Backend — Local Setup Script
=================================
Run this once to set up the backend on a new machine.

Usage:
    python setup.py

What it does:
    1. Creates a Python virtual environment (if not present)
    2. Installs dependencies from requirements.txt
    3. Creates .env from .env.example (if not present) and prompts for DB password
    4. Creates the PostgreSQL database 'mra_db' (if not present)
    5. Runs Alembic migrations to create all tables
    6. Seeds agent + topic mapping data
"""

import os
import sys
import subprocess
import shutil
import platform

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, "venv")
IS_WINDOWS = platform.system() == "Windows"
PYTHON_VENV = os.path.join(VENV_DIR, "Scripts" if IS_WINDOWS else "bin", "python")
PIP_VENV = os.path.join(VENV_DIR, "Scripts" if IS_WINDOWS else "bin", "pip")


def print_step(n, msg):
    print(f"\n{'='*60}")
    print(f"  Step {n}: {msg}")
    print(f"{'='*60}")


def run(cmd, cwd=ROOT, env=None, check=True):
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=cwd, shell=True, env=merged_env)
    if check and result.returncode != 0:
        print(f"\n❌ Command failed: {cmd}")
        sys.exit(1)
    return result


def step1_venv():
    print_step(1, "Virtual Environment")
    if os.path.exists(PYTHON_VENV):
        print("  ✓ Virtual environment already exists — skipping")
        return

    print("  Creating virtual environment...")
    run(f'"{sys.executable}" -m venv venv')
    print("  ✓ Virtual environment created at ./venv")


def step2_deps():
    print_step(2, "Install Dependencies")
    print("  Installing packages from requirements.txt...")
    run(f'"{PIP_VENV}" install -r requirements.txt')
    print("  ✓ All dependencies installed")


def step3_env():
    print_step(3, "Environment Configuration")
    env_path = os.path.join(ROOT, ".env")
    example_path = os.path.join(ROOT, ".env.example")

    if os.path.exists(env_path):
        print("  ✓ .env file already exists — skipping")
        # Read and return the DATABASE_URL
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    return line.strip().split("=", 1)[1]
        return None

    if not os.path.exists(example_path):
        print("  ❌ .env.example not found!")
        sys.exit(1)

    print("  Creating .env from .env.example...")
    print()
    db_user = input("  PostgreSQL username [postgres]: ").strip() or "postgres"
    db_pass = input("  PostgreSQL password: ").strip()
    db_host = input("  PostgreSQL host [localhost]: ").strip() or "localhost"
    db_port = input("  PostgreSQL port [5432]: ").strip() or "5432"
    db_name = input("  Database name [mra_db]: ").strip() or "mra_db"

    if not db_pass:
        print("  ❌ Password cannot be empty!")
        sys.exit(1)

    db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    with open(example_path, "r") as f:
        content = f.read()

    content = content.replace(
        "DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/mra_db",
        f"DATABASE_URL={db_url}",
    )

    with open(env_path, "w") as f:
        f.write(content)

    print(f"  ✓ .env created with DATABASE_URL → {db_host}:{db_port}/{db_name}")
    return db_url


def step4_create_db(db_url: str):
    print_step(4, "Create Database")
    if not db_url:
        print("  ⚠ Could not parse DATABASE_URL — skipping DB creation")
        print("  → Please create the database manually:")
        print("    CREATE DATABASE mra_db;")
        return

    # Parse the URL to get connection details
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    try:
        parts = db_url.replace("postgresql+asyncpg://", "")
        user_pass, host_db = parts.split("@", 1)
        user, password = user_pass.split(":", 1)
        host_port, db_name = host_db.split("/", 1)
        host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "5432")
    except Exception:
        print("  ⚠ Could not parse DATABASE_URL — skipping DB creation")
        return

    print(f"  Connecting to PostgreSQL at {host}:{port}...")

    script = f"""
import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(
            user="{user}", password="{password}",
            host="{host}", port={port}, database="postgres"
        )
        row = await conn.fetchrow("SELECT 1 FROM pg_database WHERE datname = $1", "{db_name}")
        if row:
            print("  ✓ Database '{db_name}' already exists — skipping")
        else:
            await conn.execute("CREATE DATABASE {db_name}")
            print("  ✓ Database '{db_name}' created!")
        await conn.close()
    except Exception as e:
        print(f"  ❌ Failed to connect to PostgreSQL: {{e}}")
        print("  → Make sure PostgreSQL is running and credentials are correct")
        raise SystemExit(1)

asyncio.run(main())
"""
    result = subprocess.run(
        [PYTHON_VENV, "-c", script],
        cwd=ROOT,
    )
    if result.returncode != 0:
        sys.exit(1)


def step5_migrate():
    print_step(5, "Run Database Migrations")
    print("  Running alembic upgrade head...")
    alembic_bin = os.path.join(VENV_DIR, "Scripts" if IS_WINDOWS else "bin", "alembic")
    if os.path.exists(alembic_bin):
        run(f'"{alembic_bin}" upgrade head')
    else:
        run(f'"{PYTHON_VENV}" -m alembic upgrade head')
    print("  ✓ All migrations applied")


def step6_seed():
    print_step(6, "Seed Data (Agents + Topic Mappings)")
    print("  Running seed script...")
    run(f'"{PYTHON_VENV}" -m app.seed')
    print("  ✓ Seed data loaded")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           MRA Backend — Local Setup Script              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Platform : {platform.system()} {platform.release()}")
    print(f"  Python   : {sys.version.split()[0]}")
    print(f"  Root     : {ROOT}")

    # Check Python version
    if sys.version_info < (3, 11):
        print("\n  ⚠ Python 3.11+ is recommended. You have", sys.version.split()[0])

    step1_venv()
    step2_deps()
    db_url = step3_env()
    step4_create_db(db_url)
    step5_migrate()
    step6_seed()

    print("\n" + "=" * 60)
    print("  ✅ Setup complete!")
    print("=" * 60)
    print()
    print("  To start the backend server:")
    print()
    if IS_WINDOWS:
        print("    .\\venv\\Scripts\\activate")
    else:
        print("    source venv/bin/activate")
    print("    uvicorn app.main:app --reload --port 8000")
    print()
    print("  API will be available at: http://localhost:8000")
    print("  API docs at:              http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
