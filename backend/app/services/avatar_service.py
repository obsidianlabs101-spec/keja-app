"""
app/services/avatar_service.py

The frontend now shows a proper crop grid before an avatar upload ever
leaves the browser (see profile.js's avatar-crop modal), so under normal
use every avatar arrives here already a clean square JPEG. This is the
server-side backstop for everything that path doesn't cover: an old
cached page still running the previous upload code, a direct API call
that skips the browser entirely, or a future caller that forgets this
step exists. Belt and suspenders — the crop UI is what actually fixes the
experience, this is what makes the fix hold even when something upstream
doesn't cooperate.

Same best-effort philosophy as watermark_service.py: Pillow is a normal
pip dependency and is expected to always be present, but if it somehow
isn't, this quietly leaves the original upload untouched rather than
failing the whole request over an optional hardening step.
"""
import logging
import os

logger = logging.getLogger(__name__)

AVATAR_TARGET_SIZE = 640  # px, square


def normalize_avatar_image(path: str):
    """Re-encodes the image at `path` into a guaranteed square JPEG:
    center-cropped to a 1:1 aspect ratio and resized to a fixed size,
    with EXIF rotation actually baked into the pixels (phone photos
    frequently carry orientation as metadata rather than physically
    rotating the image, which is why a portrait selfie could otherwise
    end up saved sideways).

    This is also what fixes the root cause of the "image error" bug in
    comments: an unrecognized source format (e.g. HEIC from an iPhone)
    used to get saved under a fallback ".bin" extension — a file browsers
    have no reason to try rendering as an image at all. Every avatar that
    goes through here comes out the other side as a normal, universally
    supported .jpg, independent of whatever format it arrived in.

    Returns the new file path (always ending in .jpg) on success, or None
    if normalization was skipped/failed — callers should keep using the
    original path unchanged in that case, exactly like watermark_image's
    best-effort contract.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow not installed — skipping avatar normalization for %s", path)
        return None

    new_path = os.path.splitext(path)[0] + ".jpg"

    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)  # bake in phone-camera rotation
            img = img.convert("RGB")  # drops alpha/palette modes JPEG can't hold

            width, height = img.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            img = img.crop((left, top, left + side, top + side))

            if side != AVATAR_TARGET_SIZE:
                resample = getattr(Image, "LANCZOS", None) or Image.ANTIALIAS
                img = img.resize((AVATAR_TARGET_SIZE, AVATAR_TARGET_SIZE), resample)

            img.save(new_path, "JPEG", quality=90)
    except Exception as e:
        logger.warning("Avatar normalization failed for %s: %s", path, e)
        return None

    if new_path != path:
        try:
            os.remove(path)
        except Exception:
            pass

    return new_path