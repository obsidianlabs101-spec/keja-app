import os
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException

from starlette.status import HTTP_400_BAD_REQUEST

from app.core.dependencies import get_current_user
from app.services.watermark_service import watermark_image, watermark_video
from app.services.avatar_service import normalize_avatar_image
from app.services import storage_service
from app.services import media_validation

router = APIRouter(prefix="/media", tags=["media"])

# SECURITY: a small per-request cap independent of any client-declared
# Content-Length, enforced while streaming (see the chunked read loop
# below) so a caller can't upload an effectively unbounded file and
# exhaust disk space. Adjust if legitimate clips need to be larger.
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

STATIC_DIR = "static"
AVATARS_DIR = os.path.join(STATIC_DIR, "avatars")
POSTERS_DIR = os.path.join(STATIC_DIR, "posters")
CLIPS_DIR = os.path.join(STATIC_DIR, "clips")
DOCUMENTS_DIR = os.path.join(STATIC_DIR, "documents")

_ALLOWED_TYPES = ("avatar", "poster", "clip", "document", "duplicate_guard")


def _ensure_dirs() -> None:
    os.makedirs(AVATARS_DIR, exist_ok=True)
    os.makedirs(POSTERS_DIR, exist_ok=True)
    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)


def _safe_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    ext = (ext or "").lower()
    # Allow only a small set of common extensions; fallback to .bin
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".pdf"}
    return ext if ext in allowed else ".bin"


def _watermark_and_reupload_clip_in_background(local_path: str, storage_filename: str) -> None:
    """Runs AFTER the upload response has already been sent to the browser
    (see BackgroundTasks below) — this is what makes clip uploads fast
    despite ffmpeg watermarking being slow on a free-tier CPU. The raw
    clip is already live and playable at its public URL by the time this
    even starts; this just quietly re-uploads the watermarked version
    over the same filename a bit later (Supabase upsert), so the URL
    never changes and nothing the frontend already has needs updating.
    Best-effort end to end: any failure here just means that one clip
    stays unwatermarked — it never un-publishes or breaks the post.
    """
    try:
        watermark_video(local_path)
        storage_service.upload_clip(local_path, storage_filename)
    except Exception as e:
        print(f"⚠️ Background clip watermark/re-upload failed for {storage_filename}: {e}")
    finally:
        try:
            os.remove(local_path)
        except Exception:
            pass


@router.post("/upload")
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    file_type: str = Form(...),
    current_user=Depends(get_current_user),
):
    # SECURITY: this endpoint previously had no authentication at all —
    # anyone, logged in or not, could upload files to be served publicly
    # from this server. Requiring a valid user session at minimum ties
    # every upload to an accountable identity and stops anonymous/bulk
    # abuse (storage exhaustion, hosting unrelated content on this domain).
    _ensure_dirs()

    file_type = (file_type or "").strip().lower()
    if file_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid file_type '{file_type}'. Expected one of: {', '.join(_ALLOWED_TYPES)}",
        )

    ext = _safe_extension(file.filename)
    filename = f"{uuid.uuid4().hex}{ext}"

    if file_type == "avatar":
        target_dir = AVATARS_DIR
    elif file_type == "duplicate_guard":
        # Reuses the avatars directory/bucket purely for storage — never
        # linked from anywhere public. See User.duplicate_guard_photo_url
        # for the actual access-gating (roulette deck + Live Gate only).
        target_dir = AVATARS_DIR
    elif file_type == "poster":
        target_dir = POSTERS_DIR
    elif file_type == "document":
        target_dir = DOCUMENTS_DIR
    else:  # clip
        target_dir = CLIPS_DIR

    target_path = os.path.join(target_dir, filename)

    total_bytes = 0
    try:
        with open(target_path, "wb") as f:
            if file_type == "clip":
                chunk_size = 1024 * 1024  # 1MB
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > _MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="File too large")
                    f.write(chunk)
            else:
                # images are typically smaller; still read in chunks for safety
                while True:
                    chunk = await file.read(1024 * 256)  # 256KB
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > _MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="File too large")
                    f.write(chunk)

        print(f"✅ Uploaded {total_bytes} bytes to {target_path}")

        if total_bytes == 0:
            # Remove the empty file
            try:
                os.remove(target_path)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

    except HTTPException:
        # Bug fix: this used to be caught by the broad `except Exception`
        # below and re-wrapped into a generic 500, which threw away the
        # real status code (e.g. 400 "empty file", 413 "too large") and
        # replaced it with a misleading "Upload failed: 400: ..." 500.
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except Exception:
            pass
        raise
    except Exception as e:
        print(f"❌ Upload error: {e}")
        # Clean up partial file
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        await file.close()

    # Content validation — the extension check earlier only ever looked at
    # the FILENAME, and when it didn't recognize the extension it didn't
    # reject the upload, it just silently renamed it to ".bin" and stored
    # it anyway. This is what actually opens the bytes now sitting on disk
    # and confirms they're a genuine image/video/PDF, not an arbitrary
    # file that happened to be renamed to look like one. Runs before any
    # watermarking/storage-upload work, so a rejected file never gets
    # processed or published anywhere.
    if file_type == "document":
        # Documents accept EITHER an image or a PDF (see host.html's
        # accept="image/*,application/pdf"), which opens a narrower but
        # real mismatch the single-validator types below don't have: the
        # file's extension came from the ORIGINAL filename, decided
        # before any content was even read — someone uploading a genuine
        # JPEG named "id.pdf" passes validation (it really is a valid
        # image) but would otherwise stay saved and served as if it were
        # a PDF. Detecting the actual kind and renaming to match keeps
        # what's served accurate to what's really in the file, not just
        # to what the uploader's filename happened to claim.
        kind = media_validation.detect_document_kind(target_path)
        if kind is None:
            try:
                os.remove(target_path)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="That doesn't look like a valid document file.")
        correct_ext = ".pdf" if kind == "pdf" else (media_validation.detect_image_extension(target_path) or ext)
        if correct_ext != ext:
            new_filename = f"{os.path.splitext(filename)[0]}{correct_ext}"
            new_path = os.path.join(target_dir, new_filename)
            os.rename(target_path, new_path)
            filename, target_path, ext = new_filename, new_path, correct_ext
    else:
        validators = {
            "avatar": media_validation.is_valid_image,
            "duplicate_guard": media_validation.is_valid_image,
            "poster": media_validation.is_valid_image,
            "clip": media_validation.is_valid_video,
        }
        validator = validators.get(file_type)
        if validator and not validator(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
            kind = "video" if file_type == "clip" else "image"
            raise HTTPException(status_code=400, detail=f"That doesn't look like a valid {kind} file.")

    # Server-side backstop: guarantee every avatar is a real, decodable,
    # square JPEG regardless of what actually arrived — see
    # avatar_service.normalize_avatar_image's docstring for why this is
    # what stops a bypass of the frontend crop UI from reintroducing the
    # broken-image-in-comments bug. Best-effort: if this can't run for any
    # reason, the original upload (which already succeeded above) is kept
    # as-is rather than failing the whole request.
    if file_type == "avatar":
        normalized_path = normalize_avatar_image(target_path)
        if normalized_path and normalized_path != target_path:
            filename = os.path.basename(normalized_path)
            target_path = normalized_path

    # Watermark public-facing media only — posters and clips are what
    # actually get shared/downloaded off-platform (WhatsApp status, TikTok
    # reposts, etc), so those are what should carry the BASH mark with
    # them like a TikTok watermark. Avatars and verification documents are
    # never watermarked.
    #
    # Posters (images, Pillow, no ffmpeg): fast enough to do synchronously
    # here — best-effort, if this fails the plain upload already succeeded
    # above and is kept as-is rather than failing the whole request over
    # an optional branding step.
    #
    # Clips (video, ffmpeg): deliberately NOT done here anymore. Full
    # re-encoding via ffmpeg on Render's free-tier 0.1-CPU instance could
    # take 20-40+ seconds — long enough that it was stalling the entire
    # upload request, blocking the frontend's caption prompt from ever
    # appearing. Clips now get uploaded to Supabase raw/unwatermarked
    # immediately below, and watermarking happens afterward as a
    # BackgroundTask (see _watermark_and_reupload_clip_in_background) —
    # the clip is already live and playable by the time that even starts,
    # and the watermarked version quietly replaces it a bit later at the
    # same URL.
    if file_type == "poster":
        try:
            watermark_image(target_path)
        except Exception as e:
            print(f"⚠️ Poster watermark skipped: {e}")

    # Posters, avatars, and clips all get uploaded to Supabase Storage
    # (see storage_service.py docstring for why: Render's disk is
    # ephemeral and gets wiped on every redeploy/restart — this was
    # silently destroying event posters, profile pictures, and clips
    # over time). Documents stay on local disk for now — lower risk,
    # rarely re-fetched after initial admin review.
    #
    # Posters/avatars upload synchronously here (Pillow is fast, no
    # ffmpeg involved) — no need for the background-task pattern clips
    # use below, that was specifically to avoid blocking on slow ffmpeg
    # watermarking.
    #
    # Best-effort throughout: if Supabase is unreachable for any reason
    # (misconfiguration, network blip, outage), falls back to the local
    # /static/ URL that already works today rather than failing the
    # whole upload.
    if file_type in ("poster", "avatar", "duplicate_guard"):
        try:
            uploader = storage_service.upload_poster if file_type == "poster" else storage_service.upload_avatar
            public_url = uploader(target_path, filename)
            try:
                os.remove(target_path)
            except Exception:
                pass
            return {"url": public_url}
        except Exception as e:
            print(f"⚠️ Supabase Storage upload failed for {file_type}, serving from local disk instead: {e}")

    if file_type == "clip":
        try:
            public_url = storage_service.upload_clip(target_path, filename)
            # Watermarking happens after the response is sent — see the
            # function's own docstring for why. The raw file is kept
            # around (not deleted here) so the background task still has
            # something to read; it deletes it once it's done with it.
            background_tasks.add_task(
                _watermark_and_reupload_clip_in_background, target_path, filename
            )
            return {"url": public_url}
        except Exception as e:
            print(f"⚠️ Supabase Storage upload failed, serving from local disk instead: {e}")

    rel_url = f"/static/{file_type}s/{filename}"
    return {"url": rel_url}