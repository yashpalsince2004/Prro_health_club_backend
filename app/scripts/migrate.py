"""
Run Alembic migrations programmatically.
Called by Railway's deploy command before starting the server.
"""
import subprocess
import sys
from loguru import logger

def run_migrations():
    logger.info("Running Alembic migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        logger.error(f"Migration failed: {result.stderr}")
        sys.exit(1)
    logger.info(f"Migration output: {result.stdout}")
    logger.info("Migrations complete.")

if __name__ == "__main__":
    run_migrations()
