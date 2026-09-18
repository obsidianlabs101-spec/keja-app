"""
app/services/media_validation.py

Confirms an uploaded file's actual CONTENT matches what it's claimed to be
— not just its filename. media.py's _safe_extension() only ever looked at
the filename's extension, and when that didn't match anything expected it
didn't reject the file, it just renamed it to ".bin" and accepted it
anyway. That meant literally any file — a PDF, a zip, an executable —
could be renamed to look like an image or video and would be stored and
served publicly from this server without ever being opened or checked.

Three checks, one per media family actually accepted by media.py:
  - is_valid_image(): Pillow, a guaranteed pip dependency (see
    requirements.txt) — always available, so this is a hard, reliable
    gate. Used for avatar/poster/duplicate_guard uploads.
  - is_valid_video(): ffmpeg/ffprobe is a SYSTEM dependency that may not
    be installed on every server (watermark_service.py already treats it
    the same way — every call checks for the binary first and degrades
    gracefully rather than assuming it's there). A binary file-signature
    check runs first regardless (dependency-free, always available) and
    catches the overwhelming majority of "renamed some other file type"
    attempts on its own; ffprobe, when present, adds a second, stronger
    pass that confirms a genuinely decodable video stream exists.
  - is_valid_pdf(): a plain magic-byte check — PDFs always start with the
    literal bytes "%PDF-", no library needed.
  - is_valid_document(): images and PDFs are both legitimate ID/business
    registration uploads (see host.html's accept="image/*,application/pdf"
    on those fields) — true if either check passes.

Every function is a simple, fast, local check on the file already sitting
on disk — no network calls, safe to run synchronously on the upload path
before any watermarking/storage-upload work begins.
"""
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Common video container signatures, checked directly against the first
# bytes of the file — dependency-free, so this always runs regardless of
# whether ffprobe happens to be installed on this server.
_MP4_FAMILY_BOX = b"ftyp"          # MP4/MOV/M4V (ISO base media): 'ftyp' box at offset 4
_WEBM_MKV_HEADER = b"\x1a\x45\xdf\xa3"  # WebM/Matroska: EBML header at offset 0
_RIFF_HEADER = b"RIFF"             # AVI: 'RIFF' at offset 0, 'AVI ' at offset 8
_AVI_TAG = b"AVI "

_PDF_HEADER = b"%PDF-"


def is_valid_image(path: str) -> bool:
    """True if Pillow can actually open and structurally verify the file
    as an image. Image.verify() is the standard, lightweight Pillow check
    for "is this really a decodable image" — it doesn't do a full pixel
    decode, but it does parse the real file structure, which is exactly
    what catches a renamed non-image file (verify() raises on those).

    NOTE for callers: verify() leaves the Image object unusable for
    anything further (a documented Pillow quirk) — this function only
    ever uses it for the yes/no check and discards the object, so later
    code that needs to actually open the file again (watermark_image,
    normalize_avatar_image) is unaffected; they open it fresh.
    """
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception as e:
        logger.info("is_valid_image: rejected %s (%s)", path, e)
        return False


def _sniff_video_container(path: str) -> bool:
    """Dependency-free binary signature check — always runs, regardless
    of whether ffprobe is installed. Reliably distinguishes real video
    containers from an arbitrary renamed file; it does not confirm the
    stream inside actually decodes (that's what ffprobe below is for,
    when available)."""
    try:
        with open(path, "rb") as f:
            header = f.read(64)
    except Exception:
        return False
    if len(header) < 12:
        return False
    if header[4:8] == _MP4_FAMILY_BOX:
        return True
    if header[0:4] == _WEBM_MKV_HEADER:
        return True
    if header[0:4] == _RIFF_HEADER and header[8:12] == _AVI_TAG:
        return True
    return False


def _ffprobe_confirms_video_stream(path: str):
    """Returns True/False if ffprobe is installed and could check the
    file; returns None if ffprobe isn't available on this server, so the
    caller knows to fall back to the signature check alone instead of
    treating "couldn't check" as "check failed". Same defensive pattern
    watermark_service.py already uses for this exact binary."""
    if not shutil.which("ffprobe"):
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and "video" in result.stdout
    except Exception as e:
        logger.info("ffprobe check failed for %s (%s) — treating as unavailable", path, e)
        return None


def is_valid_video(path: str) -> bool:
    """Signature check first (always runs); ffprobe adds a second,
    stronger pass only when the binary is actually installed on this
    server. A file that fails the signature check is rejected outright —
    no legitimate video file lacks a recognizable container header, so
    this never produces a false rejection of a real upload."""
    if not _sniff_video_container(path):
        return False
    ffprobe_result = _ffprobe_confirms_video_stream(path)
    if ffprobe_result is False:
        # ffprobe was available, ran, and found no real video stream —
        # trust that over the signature check (a container header alone
        # doesn't guarantee what's inside it is playable).
        return False
    return True


def is_valid_pdf(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(len(_PDF_HEADER))
        return header == _PDF_HEADER
    except Exception:
        return False


def is_valid_document(path: str) -> bool:
    """Government ID / business registration uploads accept either an
    image or a PDF (see host.html's accept="image/*,application/pdf") —
    valid if it's genuinely either one."""
    return is_valid_image(path) or is_valid_pdf(path)


def detect_document_kind(path: str):
    """Like is_valid_document, but tells the caller WHICH of the two
    valid kinds this actually is ("pdf" or "image"), or None if it's
    neither. media.py uses this to catch a real mismatch: the file's
    extension (and therefore the Content-Type a browser will be told to
    expect) comes from whatever the ORIGINAL filename claimed — decided
    before any of these checks ever run. Someone uploading a genuine JPEG
    named "id.pdf" passes is_valid_document() (it really is a valid
    image) while still being saved and served as if it were a PDF. Not a
    malicious-content risk on its own, but exactly the kind of
    claimed-type-vs-actual-content mismatch that MIME-confusion attacks
    rely on, and it also just breaks the file for whoever opens it
    expecting a PDF. Checked in this order because a real PDF's bytes
    never happen to also decode as an image, so there's no ambiguity to
    worry about between the two branches.
    """
    if is_valid_pdf(path):
        return "pdf"
    if is_valid_image(path):
        return "image"
    return None


_PILLOW_FORMAT_TO_EXT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "GIF": ".gif",
    "WEBP": ".webp",
}


def detect_image_extension(path: str):
    """The correct file extension (".jpg", ".png", etc) for the image
    ACTUALLY sitting at `path`, read from Pillow's own format detection —
    not guessed from a filename. Used alongside detect_document_kind() to
    fix a mismatched extension (see that function's docstring) with the
    right one instead of a generic placeholder. Returns None if Pillow
    can't identify a supported format (shouldn't happen for anything that
    already passed is_valid_image(), but this is a plain lookup, not
    worth raising over)."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            return _PILLOW_FORMAT_TO_EXT.get(img.format)
    except Exception:
        return None