"""Handle downloading and caching of artwork imagery and related assets."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .browsers import USER_AGENT
from .models import Artwork


class ImageDownloadError(RuntimeError):
    """Raised when an artwork image cannot be downloaded successfully."""


def _resolve_default_output_directory() -> Path:
    """Return the canonical directory for cached artwork images."""

    package_root = Path(__file__).resolve().parents[1]
    return package_root / "out" / "images"


@dataclass(slots=True)
class ArtworkImageDownloader:
    """Download artwork imagery while enforcing type and size checks."""

    max_retries: int = 3
    backoff_factor: float = 0.5
    allowed_content_types: Iterable[str] = (
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    )
    max_file_size_bytes: int | None = 15 * 1024 * 1024
    output_directory: Path = field(default_factory=_resolve_default_output_directory)
    opener: Callable[[urllib.request.Request], object] = urllib.request.urlopen
    sleep_function: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        normalized_types = tuple(
            content_type.lower() for content_type in self.allowed_content_types
        )
        object.__setattr__(self, "allowed_content_types", normalized_types)
        object.__setattr__(self, "output_directory", Path(self.output_directory))

    def download_artwork_image(self, artwork: Artwork) -> Artwork:
        """Download ``artwork``'s primary image and persist it locally."""

        if artwork.image_url is None:
            return artwork

        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1")

        image_url = str(artwork.image_url)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                request = urllib.request.Request(image_url, headers={"User-Agent": USER_AGENT})
                with self.opener(request) as response:  # type: ignore[arg-type]
                    content_type = self._extract_content_type(response)
                    self._validate_content_type(content_type)

                    data = response.read()
                    if not data:
                        raise ImageDownloadError("Downloaded image is empty")

                    if (
                        self.max_file_size_bytes is not None
                        and len(data) > self.max_file_size_bytes
                    ):
                        raise ImageDownloadError(
                            "Downloaded image exceeds the configured maximum size"
                        )

                    target_path = self._resolve_target_path(artwork, content_type)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(data)

                    update_payload = {"image_path": str(target_path)}
                    if hasattr(artwork, "model_copy"):
                        return artwork.model_copy(update=update_payload)
                    return artwork.copy(update=update_payload)  # type: ignore[attr-defined]

            except ImageDownloadError:
                raise
            except (urllib.error.URLError, OSError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    message = (
                        f"Failed to download artwork image after {attempt} attempts: {error}"
                    )
                    raise ImageDownloadError(message) from error
                sleep_duration = self.backoff_factor * (2 ** (attempt - 1))
                self.sleep_function(sleep_duration)

        if last_error is not None:  # pragma: no cover - defensive guard
            raise ImageDownloadError("Failed to download artwork image") from last_error
        return artwork  # pragma: no cover - unreachable without errors

    def _extract_content_type(self, response: object) -> str:
        """Return the response content type in lowercase form."""

        header_value: str | None = None
        if hasattr(response, "headers") and response.headers is not None:
            header_value = response.headers.get("Content-Type")
        if header_value is None and hasattr(response, "getheader"):
            header_value = response.getheader("Content-Type")  # type: ignore[attr-defined]
        if header_value is None and hasattr(response, "info"):
            info = response.info()  # type: ignore[attr-defined]
            if info is not None:
                header_value = info.get("Content-Type")
        if header_value is None:
            raise ImageDownloadError("Response did not include a Content-Type header")
        return header_value.split(";")[0].strip().lower()

    def _validate_content_type(self, content_type: str) -> None:
        """Ensure the response content type is in the allowed list."""

        if content_type not in self.allowed_content_types:
            raise ImageDownloadError(
                f"Content type '{content_type}' is not allowed for artwork imagery"
            )

    def _resolve_target_path(self, artwork: Artwork, content_type: str) -> Path:
        """Determine the output filename for the downloaded image."""

        extension_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        extension = extension_map.get(content_type, ".bin")
        slug = artwork.slug or "artwork"
        return self.output_directory / f"{slug}{extension}"


__all__ = ["ArtworkImageDownloader", "ImageDownloadError"]
