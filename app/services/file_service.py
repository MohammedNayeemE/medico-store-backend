import io
import zipfile
from typing import Dict, List

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import bucket
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
)
from app.models.user_management_models import FileAsset, User


class FileService:
    def __init__(self) -> None:
        pass

    async def UPLOAD_SINGLE_FILE(
        self,
        bucket: AsyncIOMotorGridFSBucket,
        db: AsyncSession,
        file: UploadFile,
        user_id: int,
    ):
        try:
            result = await db.execute(select(User).filter(User.user_id == user_id))
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise NotFoundException("user-id not found")
            grid_file_id = await bucket.upload_from_stream(
                file.filename, file.file, metadata={"content_type": file.content_type}
            )
            file_url: str = str(grid_file_id)
            asset = FileAsset(
                file_name=file.filename,
                file_url=file_url,
                file_type=file.content_type,
                uploaded_by=user_obj.user_id,
                size_bytes=file.size,
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)
            return {
                "asset_id": asset.asset_id,
                "file_id": file_url,
                "file_name": asset.file_name,
                "content_type": asset.file_type,
            }
        except NotFoundException:
            raise
        except Exception as e:
            print(f"[upload_single_file]: {e}")
            raise InternalServerErrorException(
                "internal server error : [upload_single_file]"
            )

    async def UPLOAD_MULTIPLE_FILES(
        self,
        bucket: AsyncIOMotorGridFSBucket,
        files: List[UploadFile],
        db: AsyncSession,
        user_id: int,
    ):
        try:
            if len(files) > 5:
                raise BadRequestException(
                    "u can upload only 5 files at a time my nigga"
                )
            result = await db.execute(select(User).filter(User.user_id == user_id))
            user_obj = result.scalar_one_or_none()
            if not user_obj:
                raise NotFoundException("user id not found")
            data: List[Dict[str, str]] = []
            for file in files:
                grid_file_id = await bucket.upload_from_stream(
                    file.filename,
                    file.file,
                    metadata={"content_type": file.content_type},
                )
                file_url: str = str(grid_file_id)
                asset = FileAsset(
                    file_name=file.filename,
                    file_url=file_url,
                    file_type=file.content_type,
                    uploaded_by=user_obj.user_id,
                    size_bytes=file.size,
                )
                db.add(asset)
                await db.flush()
                data.append({"asset_id": str(asset.asset_id), "file_id": file_url})
            await db.commit()
            return {"data": data}
        except (BadRequestException, NotFoundException) as e:
            raise
        except Exception as e:
            print("-------------------")
            print(f"upload_multiple_files: {e}")
            await db.rollback()
            raise InternalServerErrorException(
                "internal server error : [upload_multiple_files]"
            )

    async def DOWNLOAD_SINGLE_FILE(
        self, bucket: AsyncIOMotorGridFSBucket, file_id: str
    ):
        try:
            grid_out = await bucket.open_download_stream(ObjectId(file_id))
            return StreamingResponse(
                grid_out,
                media_type=grid_out.metadata.get(
                    "content_type", "application/octet-stream"
                ),
            )
        except Exception as e:
            print("-------------------------")
            print(f"[download_single_file] : {e}")
            raise InternalServerErrorException(
                "internal server error : [download_single_file]"
            )

    async def DOWNLOAD_MULTIPLE_FILES(
        self,
        bucket: AsyncIOMotorGridFSBucket,
        file_ids: List[str],
    ):
        try:
            if not file_ids:
                raise BadRequestException("No file IDs provided")
            memory_file = io.BytesIO()
            zip_buffer = zipfile.ZipFile(
                memory_file, mode="w", compression=zipfile.ZIP_DEFLATED
            )
            for file_id in file_ids:
                try:
                    grid_out = await bucket.open_download_stream(ObjectId(file_id))
                    file_bytes = await grid_out.read()
                    filename = grid_out.filename or f"{file_id}.bin"
                    zip_buffer.writestr(filename, file_bytes)
                except Exception as e:
                    print(f"[download_multiple_files: skipped] {file_id} -> {e}")
                    continue
            zip_buffer.close()
            memory_file.seek(0)
            return StreamingResponse(
                memory_file,
                media_type="application/zip",
                headers={
                    "Content-Disposition": "attachment; filename=downloaded_files.zip"
                },
            )
        except BadRequestException:
            raise
        except Exception as e:
            print("-------------------")
            print(f"[download_multiple_files]: {e}")
            raise InternalServerErrorException(
                "internal server error : [download_multiple_files]"
            )

    async def GET_FILE_BY_ASSET_ID(
        self, asset_id: int, db: AsyncSession, bucket: AsyncIOMotorGridFSBucket
    ):
        try:
            result = await db.execute(
                select(FileAsset).filter(FileAsset.asset_id == asset_id)
            )
            asset_obj = result.scalar_one_or_none()
            if not asset_obj:
                raise NotFoundException("file not found")
            grid_out = await bucket.open_download_stream(ObjectId(asset_obj.file_url))
            return StreamingResponse(
                grid_out,
                media_type=grid_out.metadata.get(
                    "content_type", "application/octet-stream"
                ),
                headers={
                    "Content-Disposition": f'inline; filename="{asset_obj.file_name}"'
                },
            )
        except NotFoundException:
            raise
        except Exception as e:
            print("=============================")
            print(f"[get_file_by_asset_id]: {e}")
            raise InternalServerErrorException("Internal server error")

    async def GET_PRESCRIPTION(
        self,
        asset_id: int,
        db: AsyncSession,
        bucket: AsyncIOMotorGridFSBucket,
        current_user: User,
    ):
        try:
            result = await db.execute(
                select(FileAsset).filter(FileAsset.asset_id == asset_id)
            )
            asset_obj = result.scalar_one_or_none()
            if not asset_obj:
                raise NotFoundException("File not Found")
            if (
                current_user.role_id != 1
                and asset_obj.uploaded_by != current_user.user_id
            ):
                raise ForbiddenException("Forbidden")
            grid_out = await bucket.open_download_stream(ObjectId(asset_obj.file_url))
            return StreamingResponse(
                grid_out,
                media_type=grid_out.metadata.get(
                    "content_type", "application/octet-stream"
                ),
                headers={
                    "Content-Disposition": f'inline; filename="{asset_obj.file_name}"'
                },
            )
        except NotFoundException:
            raise
        except Exception as e:
            pass
