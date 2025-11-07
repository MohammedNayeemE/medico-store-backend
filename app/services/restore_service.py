import os
import shutil
import subprocess
import tarfile
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.backup_models import Backup, Restore


class RestoreService:
    RESTORE_DIR = settings.RESTORE_DIR  # e.g., /var/tmp/epharmacy_restore

    @classmethod
    async def restore_backup(
        cls, db: AsyncSession, backup_id: int, restored_by: str = "system"
    ):
        """
        Perform a restore from an existing backup and log the process in the restores table.
        """
        # 1️⃣ Validate the backup
        backup = await db.get(Backup, backup_id)
        if not backup or backup.status != "success":
            raise ValueError("Backup not found or failed — cannot restore.")

        # 2️⃣ Create a new restore log entry
        restore = Restore(
            backup_id=backup_id,
            status="running",
            restored_by=restored_by,
            environment="production",  # can make this dynamic later
        )
        db.add(restore)
        await db.commit()
        await db.refresh(restore)

        os.makedirs(cls.RESTORE_DIR, exist_ok=True)
        tar_path = backup.artifact_path

        postgres_dump = None
        mongo_dump = None

        try:
            # 3️⃣ Extract the backup tar.gz
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(cls.RESTORE_DIR)

            # 4️⃣ Locate dump files
            for root, _, files in os.walk(cls.RESTORE_DIR):
                for f in files:
                    if f.startswith("postgres_") and f.endswith(".dump"):
                        postgres_dump = os.path.join(root, f)
                    elif f.startswith("mongo_") and f.endswith(".archive.gz"):
                        mongo_dump = os.path.join(root, f)

            # 5️⃣ Restore PostgreSQL
            if postgres_dump:
                print(f"[RestoreService] Restoring PostgreSQL from {postgres_dump}...")
                env = os.environ.copy()
                if getattr(settings, "POSTGRES_PASSWORD", None):
                    env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

                subprocess.run(
                    [
                        "pg_restore",
                        "-h",
                        settings.POSTGRES_HOST,
                        "-U",
                        settings.POSTGRES_USER,
                        "-d",
                        settings.POSTGRES_DB,
                        "--clean",
                        "--if-exists",
                        postgres_dump,
                    ],
                    check=True,
                    env=env,
                )

            # 6️⃣ Restore MongoDB (includes GridFS)
            if mongo_dump:
                print(f"[RestoreService] Restoring MongoDB from {mongo_dump}...")
                subprocess.run(
                    [
                        "mongorestore",
                        f"--uri={settings.MONGO_URI}",
                        f"--archive={mongo_dump}",
                        "--gzip",
                        "--drop",
                    ],
                    check=True,
                )

            # 7️⃣ Update restore record → success
            restore.status = "success"
            restore.finished_at = datetime.now()
            await db.commit()

        except subprocess.CalledProcessError as e:
            # CLI command (pg_restore/mongorestore) failed
            restore.status = "failed"
            restore.error_message = f"Restore command failed: {str(e)}"
            restore.finished_at = datetime.now()
            await db.commit()
            raise RuntimeError(f"Restore failed: {e}")

        except Exception as e:
            # General failure
            restore.status = "failed"
            restore.error_message = str(e)
            restore.finished_at = datetime.now()
            await db.commit()
            raise

        finally:
            # 8️⃣ Cleanup temporary restore directory
            try:
                shutil.rmtree(cls.RESTORE_DIR)
            except Exception as cleanup_err:
                print(f"[RestoreService] Warning: cleanup failed - {cleanup_err}")

        # 9️⃣ Return structured response
        return {
            "status": restore.status,
            "restored_at": (
                restore.finished_at.isoformat() if restore.finished_at else None
            ),
            "restore_id": restore.id,
            "details": {
                "postgres_restored": bool(postgres_dump),
                "mongo_restored": bool(mongo_dump),
                "backup_id": backup_id,
                "restored_by": restored_by,
            },
        }
