import json

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Path, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependecies.get_db_sessions import get_postgres
from app.core.database import bucket
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files Testing"])
file_manager = FileService()


@router.get("/dev", description="Health check endpoint for Files routes")
async def get_dev_route():
    return JSONResponse(status_code=200, content={"msg": "this route is working...."})


@router.post("/uploadfile/{user_id}", description="Upload a file for a given user and store it")
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
