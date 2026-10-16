"""Daily cleanup of generated media so a long-running server doesn't fill its disk."""
import logging
import time

import config

logger = logging.getLogger(__name__)


def prune_media() -> None:
    cutoff = time.time() - config.MEDIA_RETENTION_DAYS * 86400
    removed, freed = 0, 0
    for path in config.IMAGES_DIR.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
    logger.info("Housekeeping: removed %d media file(s) older than %d days (%.1f MB).",
                removed, config.MEDIA_RETENTION_DAYS, freed / 1e6)
