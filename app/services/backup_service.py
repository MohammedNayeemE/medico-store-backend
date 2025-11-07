import datetime
import json
import os
import shutil
import subprocess

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.backup_models import Backup


class BackupService:
    BACKUP_DIR = settings.BACKUP_DIR

    @classmethod
    async def create_backup(
        cls, db: AsyncSession, backup_id: int, parts: list[str] | None
    ):
        backup = await db.get(Backup, backup_id)
        backup.status = "running"
        await db.commit()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(cls.BACKUP_DIR, f"backup_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # manifest tracks which components were backed up
            manifest = {
                "timestamp": timestamp,
                "parts": parts or ["postgres", "mongo"],
            }

            # --- PostgreSQL Backup ---
            if not parts or "postgres" in parts:
                pg_file = os.path.join(temp_dir, f"postgres_{timestamp}.dump")
                pg_cmd = [
                    "pg_dump",
                    "-h",
                    settings.POSTGRES_HOST,
                    "-U",
                    settings.POSTGRES_USER,
                    "-d",
                    settings.POSTGRES_DB,
                    "-F",
                    "c",
                    "-f",
                    pg_file,
                ]
                subprocess.run(pg_cmd, check=True)
                manifest["postgres"] = os.path.basename(pg_file)

            # --- MongoDB Backup (includes GridFS) ---
            if not parts or "mongo" in parts:
                mongo_file = os.path.join(temp_dir, f"mongo_{timestamp}.archive.gz")
                mongo_cmd = [
                    "mongodump",
                    f"--uri={settings.MONGO_URI}",  # ensure this is the correct URI
                    f"--archive={mongo_file}",
                    "--gzip",
                ]
                subprocess.run(mongo_cmd, check=True)
                manifest["mongo"] = os.path.basename(mongo_file)

            # --- Manifest file ---
            manifest_file = os.path.join(temp_dir, "manifest.json")
            with open(manifest_file, "w") as f:
                json.dump(manifest, f, indent=2)

            # --- Compress everything ---
            final_path = os.path.join(cls.BACKUP_DIR, f"backup_{timestamp}.tar.gz")
            shutil.make_archive(final_path.replace(".tar.gz", ""), "gztar", temp_dir)

            # --- Cleanup temporary files ---
            shutil.rmtree(temp_dir)

            # --- Update backup metadata ---
            backup.status = "success"
            backup.finished_at = datetime.datetime.now()
            backup.artifact_path = final_path
            backup.size_bytes = os.path.getsize(final_path)
            await db.commit()

        except Exception as e:
            backup.status = "failed"
            backup.error_message = str(e)
            await db.commit()
            raise e
