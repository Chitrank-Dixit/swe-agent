import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from src.config.settings import settings

logger = logging.getLogger("devcoach_structured")
logger.setLevel(settings.LOG_LEVEL)

def log_structured_event(
    session_id: str,
    event_type: str,
    agent_name: str,
    step_name: Optional[str] = None,
    message: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """Logs a structured JSON event to the configured log file."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event_type": event_type,
        "agent_name": agent_name,
        "step_name": step_name,
        "message": message,
        **(extra_data or {})
    }
    
    try:
        with open(settings.LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        logger.error(f"Failed to write structured log event: {e}")
