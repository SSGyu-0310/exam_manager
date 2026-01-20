import re
from urllib.parse import urlparse

from app.services.file_paths import get_upload_folder


_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def extract_upload_filename(url, upload_relative):
    """Extract and sanitize filename from upload URL."""
    if not url:
        return None

    # Use file_paths helper for folder resolution
    from app.services.file_paths import get_upload_folder

    upload_folder = get_upload_folder()

    path = urlparse(url).path or url
    path = path.strip()
    if path.startswith("/"):
        path = path[1:]
    if path.startswith("static/"):
        path = path[len("static/") :]

    # Use file_paths helper for filename sanitization
    from app.services.file_paths import sanitize_filename

    upload_relative = (upload_relative or "").strip("/")
    if upload_relative:
        prefix = f"{upload_relative}/"
        if path.startswith(prefix):
            filename = path[len(prefix) :]
            return sanitize_filename(filename) or None
    return None
    path = urlparse(url).path or url
    path = path.strip()
    if path.startswith("/"):
        path = path[1:]
    if path.startswith("static/"):
        path = path[len("static/") :]
    upload_relative = (upload_relative or "").strip("/")
    if upload_relative:
        prefix = f"{upload_relative}/"
        if path.startswith(prefix):
            filename = path[len(prefix) :]
            return filename or None
    return None


def strip_markdown_images(content, upload_folder, keep_unmatched=True):
    """Strip and sanitize markdown image references.

    Args:
        content: Content to process
        upload_folder: Upload folder path (resolved by file_paths.get_upload_folder)
        keep_unmatched: If True, keep original markdown for unmatched references

    Returns:
        Tuple of (cleaned content, found filename or None)
    """
    if not content:
        return "", None

    found_filename = None

    def _replace(match):
        nonlocal found_filename
        url = match.group(1).strip()
        from app.services.file_paths import sanitize_filename

        filename = sanitize_filename(url)
        if filename:
            if found_filename is None:
                found_filename = filename
            return match.group(0) if keep_unmatched else ""

    cleaned = _MARKDOWN_IMAGE_PATTERN.sub(_replace, content)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, found_filename
