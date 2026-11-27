"""Normalize phone photos; retain only a bounded, metadata-free JPEG."""

from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image, ImageOps, ImageFilter, ImageStat, UnidentifiedImageError
from threading import BoundedSemaphore
from pillow_heif import register_heif_opener
from pillow_heif import options as heif_options

heif_options.DECODE_THREADS = 1
heif_options.AUX_IMAGES = False
heif_options.DEPTH_IMAGES = False
register_heif_opener()
MAX_PIXELS = 64_000_000  # Includes 48 MP iPhone photos; bound decoding memory.
MAX_EDGE = 2400
DECODE_SLOT = BoundedSemaphore(1)
MAX_HEIF_PIXELS = 16_000_000
PHOTO_PROCESS_TIMEOUT = 40


class InvalidPhoto(ValueError):
    pass


def normalize_photo(data: bytes) -> bytes:
    with DECODE_SLOT:
        with tempfile.TemporaryDirectory(prefix="peak-photo-") as directory:
            source, result = Path(directory, "input"), Path(directory, "normalized.jpg")
            # Avoid a second in-memory copy of the upload. Original bytes exist
            # only in this private temporary directory during the child process.
            with source.open("wb") as stream:
                stream.write(data)
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "peak.images", str(source), str(result)],
                    capture_output=True,
                    timeout=PHOTO_PROCESS_TIMEOUT,
                    check=False,
                    env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)},
                )
            except subprocess.TimeoutExpired:
                raise InvalidPhoto(
                    "This photo took too long to process safely. Use a 12 MP photo or export a smaller JPEG."
                ) from None
            if process.returncode != 0:
                try:
                    message = json.loads(process.stdout).get("error", "")
                except (ValueError, TypeError):
                    message = ""
                allowed = {
                    "Use a JPEG, PNG, WebP or iPhone HEIC photo",
                    "This photo exceeds 64 megapixels; use a lower camera resolution",
                    "This HEIC photo exceeds the safe processing limit. Use a 12 MP camera photo or export it as JPEG.",
                    "This photo could not be opened; try another photo",
                }
                raise InvalidPhoto(
                    message
                    if message in allowed
                    else "This photo could not be processed within the memory limit. Use a 12 MP photo or export a smaller JPEG."
                )
            if not result.exists() or result.stat().st_size > 4 * 1024 * 1024:
                raise InvalidPhoto("This photo could not be processed safely; export a smaller JPEG.")
            return result.read_bytes()


def _normalize_photo(data: bytes) -> bytes:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG", "WEBP", "HEIF"):
                raise InvalidPhoto("Use a JPEG, PNG, WebP or iPhone HEIC photo")
            if image.width * image.height > MAX_PIXELS:
                raise InvalidPhoto("This photo exceeds 64 megapixels; use a lower camera resolution")
            if image.format == "HEIF" and image.width * image.height > MAX_HEIF_PIXELS:
                raise InvalidPhoto(
                    "This HEIC photo exceeds the safe processing limit. Use a 12 MP camera photo or export it as JPEG."
                )
            # JPEG decoders can subsample before allocating the full camera frame.
            image.draft("RGB", (MAX_EDGE, MAX_EDGE))
            image.load()  # Fully validate pixels before accepting the upload.
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            image = ImageOps.exif_transpose(image).convert("RGB")
            # Rebuild pixels so neither EXIF nor a HEIF decoder's metadata is retained.
            clean = Image.new("RGB", image.size)
            clean.paste(image)
            result = BytesIO()
            clean.save(result, "JPEG", quality=90, optimize=True)
            return result.getvalue()
    except InvalidPhoto:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise InvalidPhoto("This photo could not be opened; try another photo") from None


def photo_quality_hints(data: bytes) -> list[str]:
    """Cheap advisory metrics, never a correctness or submission decision."""
    with Image.open(BytesIO(data)) as image:
        small = image.convert("L")
        small.thumbnail((640, 640))
        stats = ImageStat.Stat(small)
        hints = []
        if stats.mean[0] < 60:
            hints.append("This photo looks dark. Try brighter light before requesting a reading.")
        edges = ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES))
        if edges.stddev[0] < 8:
            hints.append(
                "Few clear details are visible. Check focus and make sure your working fills the photo."
            )
        if min(image.size) < 600:
            hints.append(
                "This photo is small. A closer, higher-resolution photo may make handwriting easier to read."
            )
    return hints


def _photo_process(source, target):
    import resource

    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    with source.open("rb") as stream:
        data = _normalize_photo(stream.read())
    with target.open("wb") as stream:
        stream.write(data)


if __name__ == "__main__":
    try:
        _photo_process(Path(sys.argv[1]), Path(sys.argv[2]))
    except InvalidPhoto as error:
        print(json.dumps({"error": str(error)}))
        raise SystemExit(2)
