import logging
from datetime import datetime

from voice.paths import LOGS_DIR as LOG_DIR

LOG_FILE = LOG_DIR / "transcripts.log"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("voice_assistant")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def log_transcript(text: str, intent: str | None = None) -> None:
    logger = setup_logging()
    timestamp = datetime.now().isoformat(timespec="seconds")
    if intent:
        logger.info(f"[{timestamp}] transcript='{text}' intent='{intent}'")
    else:
        logger.info(f"[{timestamp}] transcript='{text}' intent=None")
