import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_migrations_apply_and_match_models(tmp_path):
    db = tmp_path / "migrate.db"
    up = _alembic(db, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    # No drift: the ORM models and the migration history describe the same schema.
    check = _alembic(db, "check")
    assert check.returncode == 0, check.stdout + check.stderr
    down = _alembic(db, "downgrade", "base")
    assert down.returncode == 0, down.stderr
