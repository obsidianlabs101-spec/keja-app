"""
app/services/watermark_service.py

Stamps a small "BASH" watermark onto public-facing media (event posters and
video clips) at upload time — the same idea as TikTok burning its logo into
every video you download. This is what makes a clip still say "BASH" on it
after someone downloads it and reposts it on WhatsApp/TikTok/Instagram,
instead of the branding only existing on our own site.

Two independent paths:
  - Images (posters): pure Python via Pillow. Always available (it's a
    normal pip package), so this always runs for image uploads.
  - Video (clips): shells out to the `ffmpeg` binary, which is a system
    dependency, not a Python package — it may or may not be installed on
    any given server. Every call here checks for it first and simply skips
    watermarking (the plain upload still succeeds) if it isn't found,
    rather than ever letting a missing optional binary break an upload.

Both functions are deliberately best-effort: any failure is logged and
swallowed, never raised, because a broken watermark pass must never turn
into a failed media upload.
"""
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

WATERMARK_TEXT = "BASH"


def watermark_image(path: str) -> bool:
    """Stamps `path` (an image file, edited in place) with a semi-transparent
    BASH wordmark in the bottom-right corner. Returns True if it actually
    watermarked the file, False if it left it untouched (and logged why)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow not installed — skipping image watermark for %s", path)
        return False

    if path.lower().endswith(".gif"):
        # Animated GIFs would silently collapse to a single static frame if
        # run through the compositing below — not worth the trade-off for
        # a watermark, so leave them untouched.
        return False

    try:
        with Image.open(path) as base:
            base = base.convert("RGBA")
            w, h = base.size

            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            font_size = max(18, int(min(w, h) * 0.045))
            font = None
            for candidate in (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ):
                try:
                    font = ImageFont.truetype(candidate, font_size)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()

            text = WATERMARK_TEXT
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = max(10, int(font_size * 0.5))
            x = w - text_w - pad * 2
            y = h - text_h - pad * 2

            # Soft dark pill behind the text so it stays legible on any
            # background, then the wordmark itself at ~85% opacity — visible
            # without being obnoxious over someone's event flyer.
            draw.rounded_rectangle(
                [x - pad, y - pad, x + text_w + pad, y + text_h + pad],
                radius=pad,
                fill=(0, 0, 0, 90),
            )
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 215))

            watermarked = Image.alpha_composite(base, overlay)
            if path.lower().endswith((".jpg", ".jpeg")):
                watermarked.convert("RGB").save(path, quality=90)
            else:
                watermarked.save(path)
        return True
    except Exception:
        logger.exception("Image watermark failed for %s — leaving original file as-is", path)
        return False


def watermark_video(path: str) -> bool:
    """Burns a BASH wordmark into the bottom-right corner of every frame of
    the video at `path`, in place. Requires the `ffmpeg` binary on PATH —
    if it isn't present, this is a no-op (the plain upload still works,
    it just won't carry the visible watermark). Returns True/False the
    same way as watermark_image."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        logger.warning("ffmpeg not found on PATH — skipping video watermark for %s", path)
        return False

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "mp4"
    tmp_path = f"{path}.wm_tmp.{ext}"

    # Re-encode with a codec that matches the container we're writing back
    # out to — writing mp4-encoded video into a .webm-named file (or vice
    # versa) produces a file that just fails to play. Trimmed clips from
    # the browser trimmer are .webm (vp8/vp9); direct uploads are commonly
    # .mp4/.mov (h264). Audio is always stream-copied untouched — it isn't
    # being altered, so re-encoding it would only cost time for no benefit.
    if ext == "webm":
        video_codec = ["-c:v", "libvpx", "-b:v", "2M"]
        audio_codec = ["-c:a", "libvorbis"]
    else:
        video_codec = ["-c:v", "libx264", "-preset", "veryfast"]
        audio_codec = ["-c:a", "copy"]

    # drawtext: white text, translucent black box behind it, bottom-right
    # corner with a consistent margin regardless of the source resolution.
    drawtext = (
        f"drawtext=text='{WATERMARK_TEXT}':fontcolor=white@0.85:fontsize=h*0.045:"
        f"box=1:boxcolor=black@0.35:boxborderw=10:"
        f"x=w-text_w-24:y=h-text_h-24"
    )
    try:
        result = subprocess.run(
            [
                ffmpeg_bin, "-y", "-i", path,
                "-vf", drawtext,
                *video_codec,
                *audio_codec,
                tmp_path,
            ],
            capture_output=True,
            timeout=180,  # a runaway ffmpeg process must never hang an upload request forever
        )
        if result.returncode != 0 or not shutil_exists(tmp_path):
            logger.error("ffmpeg watermark failed for %s: %s", path, result.stderr.decode(errors="ignore")[-2000:])
            _cleanup(tmp_path)
            return False

        shutil.move(tmp_path, path)
        return True
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg watermark timed out for %s", path)
        _cleanup(tmp_path)
        return False
    except Exception:
        logger.exception("Video watermark failed for %s — leaving original file as-is", path)
        _cleanup(tmp_path)
        return False


def shutil_exists(path: str) -> bool:
    import os
    return os.path.exists(path) and os.path.getsize(path) > 0


def _cleanup(path: str) -> None:
    import os
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass