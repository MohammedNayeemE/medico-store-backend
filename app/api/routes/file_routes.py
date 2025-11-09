import json
from typing import List

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Request,
    Security,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.auth import get_current_user
from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.models.user_management_models import FileAsset, User
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files Testing"])
file_manager = FileService()


@router.get("/dev", description="Health check endpoint for Files routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post(
    "/uploadfile/{user_id}", description="Upload a file for a given user and store it"
)
async def upload_file(
    user_id: int = Path(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await file_manager.UPLOAD_SINGLE_FILE(
        bucket=bucket, db=db, file=file, user_id=user_id
    )
    return result


@router.get("/downloadfile/{file_id}", description="Download/stream a file by its ID")
async def downloadfile(file_id: str):
    result = await file_manager.DOWNLOAD_SINGLE_FILE(bucket=bucket, file_id=file_id)
    return result


@router.post("/upload-multiple-files/{user_id}")
async def upload_multiple_files(
    user_id: int = Path(...),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_postgres),
):
    result = await file_manager.UPLOAD_MULTIPLE_FILES(
        bucket=bucket, db=db, files=files, user_id=user_id
    )
    return result


@router.post("/download-multiple-files")
async def download_multiple_files(
    file_ids: List[str],
    db: AsyncSession = Depends(get_postgres),
):
    result = await file_manager.DOWNLOAD_MULTIPLE_FILES(
        bucket=bucket, file_ids=file_ids
    )
    return result


@router.get("/assets/{asset_id}", description="Stream a file using asset_id")
async def get_file_by_asset_id(
    asset_id: int = Path(...), db: AsyncSession = Depends(get_postgres)
):
    result = await file_manager.GET_FILE_BY_ASSET_ID(
        asset_id=asset_id, db=db, bucket=bucket
    )
    return result


@router.get(
    "/assets/prescriptions/{asset_id}", description="Stream Prescription using asset_id"
)
async def get_prescription_by_asset_id(
    asset_id: int = Path(...),
    db: AsyncSession = Depends(get_postgres),
    current_user: User = Security(get_current_user, scopes=["prescription:read"]),
):
    result = await file_manager.GET_PRESCRIPTION(
        asset_id=asset_id, db=db, current_user=current_user, bucket=bucket
    )
    return result
