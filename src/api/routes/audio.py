import asyncio
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from src.api.dependencies import get_current_user
from src.api.models.response_models import apiResponse
from src.core.db.db_schemas import APIKey, AudioAsset
from src.core.logger import logger
from src.services.storage import s3_audio
from src.services.storage.audio_transcode import (
    AudioDecodeError,
    AudioTooLong,
    transcode_to_wav,
)

router = APIRouter()


def serialize_asset(asset: AudioAsset) -> dict:
    """Public representation: includes the stored s3_url, never the raw S3 key."""
    return asset.model_dump(exclude={"id", "s3_key"})


async def find_owned_audio(audio_id: str, current_user: APIKey) -> AudioAsset:
    """Return the caller's active audio asset or raise 404."""
    asset = await AudioAsset.find_one(
        AudioAsset.audio_id == audio_id,
        AudioAsset.created_by_email == current_user.user_email,
        AudioAsset.is_active == True,
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Audio asset not found")
    return asset


# Upload a new audio asset into the library
@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    audio_name: str = Form(...),
    transcript: str = Form(...),
    current_user: APIKey = Depends(get_current_user),
):
    logger.info(f"Received audio upload: {audio_name}")
    raw = await file.read()

    # Accept any format; normalize to WAV 48kHz mono (PyAV, in-process) and enforce the 30s cap.
    try:
        wav_bytes, duration = await asyncio.to_thread(transcode_to_wav, raw)
    except AudioTooLong:
        raise HTTPException(status_code=400, detail="Audio must be 30 seconds or shorter")
    except AudioDecodeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audio_id = str(uuid.uuid4())
    key = await asyncio.to_thread(s3_audio.upload, audio_id, wav_bytes)

    asset = AudioAsset(
        audio_id=audio_id,
        audio_name=audio_name,
        transcript=transcript,
        s3_key=key,
        s3_url=s3_audio.public_url(key),
        duration_seconds=duration,
        filename=file.filename,
        created_by_email=current_user.user_email,
    )
    await asset.insert()

    logger.info(f"Audio asset created: {audio_id}")
    return apiResponse(
        success=True,
        message="Audio uploaded successfully",
        data={"audio_id": audio_id, "duration_seconds": duration, "url": asset.s3_url},
    )


# List the caller's audio assets
@router.get("/list")
async def list_audio(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: APIKey = Depends(get_current_user),
):
    query = AudioAsset.find(
        AudioAsset.created_by_email == current_user.user_email,
        AudioAsset.is_active == True,
    )
    total = await query.count()
    assets = await query.sort("-created_at").skip((page - 1) * limit).limit(limit).to_list()

    return apiResponse(
        success=True,
        message="Audio assets retrieved successfully",
        data={
            "audios": [serialize_asset(a) for a in assets],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            },
        },
    )


# Get one audio asset
@router.get("/{audio_id}")
async def get_audio(audio_id: str, current_user: APIKey = Depends(get_current_user)):
    asset = await find_owned_audio(audio_id, current_user)
    return apiResponse(
        success=True,
        message="Audio asset retrieved successfully",
        data=serialize_asset(asset),
    )


# Soft-delete an audio asset (assistants referencing it fall back to the model greeting)
@router.delete("/{audio_id}")
async def delete_audio(audio_id: str, current_user: APIKey = Depends(get_current_user)):
    asset = await find_owned_audio(audio_id, current_user)
    asset.is_active = False
    await asset.save()
    logger.info(f"Audio asset soft-deleted: {audio_id}")
    return apiResponse(
        success=True,
        message="Audio asset deleted successfully",
        data={"audio_id": audio_id},
    )
