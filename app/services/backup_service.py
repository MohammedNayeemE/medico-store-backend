import datetime
import json
import os
import shutil
import subprocess
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.backup_models import Backup


class BackupService:
    """
    Service class for managing database backups.
    
    Handles backup creation for PostgreSQL and MongoDB, backup restoration, and backup management.
    """
    BACKUP_DIR = settings.BACKUP_DIR

    @classmethod
    async def create_backup(
        cls,
        db: AsyncSession,
        backup_id: int,
        parts: Optional[List[str]] = None,
        postgres_tables: Optional[List[str]] = None,  # ⬅️ new argument
    ):
        """
        Create a backup of the database (PostgreSQL and/or MongoDB).
        
        Args:
            db: Database session
            backup_id: Backup record ID
            parts: List of parts to backup (e.g., ["postgres", "mongo"])
            postgres_tables: Optional list of specific PostgreSQL tables to backup
        
        Returns:
            Backup status and file paths
        """
        backup = await db.get(Backup, backup_id)
        backup.status = "running"
        await db.commit()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(cls.BACKUP_DIR, f"backup_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            manifest = {
                "timestamp": timestamp,
                "parts": parts or ["postgres", "mongo"],
            }

            # --- PostgreSQL Backup ---
            if not parts or "postgres" in parts:
                pg_file = os.path.join(temp_dir, f"postgres_{timestamp}.dump")

                # ✅ Selective table backup support
                if postgres_tables:
                    # Build command for selected tables
                    pg_cmd = [
                        "pg_dump",
                        "-h",
                        settings.POSTGRES_HOST,
                        "-U",
                        settings.POSTGRES_USER,
                        "-d",
                        settings.POSTGRES_DB,
                        "-F",
                        "c",  # custom format
                        "-f",
                        pg_file,
                    ]
                    # Add each table name individually
                    for table in postgres_tables:
                        pg_cmd.extend(["-t", table])
                else:
                    # Default full database dump
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
                manifest["postgres"] = {
                    "file": os.path.basename(pg_file),
                    "tables": postgres_tables or "ALL",
                }

            # --- MongoDB Backup ---
            if not parts or "mongo" in parts:
                mongo_file = os.path.join(temp_dir, f"mongo_{timestamp}.archive.gz")
                mongo_cmd = [
                    "mongodump",
                    f"--uri={settings.MONGO_URI}",
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

            # --- Cleanup ---
            shutil.rmtree(temp_dir)

            # --- Update metadata ---
            backup.status = "success"
            backup.finished_at = datetime.datetime.now()
            backup.artifact_path = final_path
            backup.size_bytes = os.path.getsize(final_path)
            await db.commit()

        except Exception as e:
            backup.status = "failed"
            backup.error_message = str(e)
            await db.commit()
            raise
