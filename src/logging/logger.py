import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from src.config.settings import settings

# Configure standard logging to console
logger = logging.getLogger("swe_coach")
logger.setLevel(settings.LOG_LEVEL)

# Ensure handlers are not duplicated
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler for structured JSON logs
    file_handler = logging.FileHandler(settings.LOG_FILE_PATH, encoding='utf-8')
    logger.addHandler(file_handler)

def log_agent_action(
    session_id: str,
    agent_name: str,
    step_name: str,
    message: str,
    decision: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None
) -> None:
    """Logs an agent action structured as a JSON string to the structured log file, and prints to console."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "session_id": session_id,
        "agent_name": agent_name,
        "step_name": step_name,
        "message": message,
        "decision": decision,
        **(extra_data or {})
    }
    
    # Write to console in readable format
    logger.info(
        f"[{agent_name}] [Session: {session_id}] [Step: {step_name}] {message}"
        + (f" | Decision: {decision}" if decision else "")
    )
    
    # Write to structured file
    try:
        with open(settings.LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception as e:
        logger.error(f"Failed to write structured log: {e}")

# In-memory metrics tracking (can be queried or linked to OpenTelemetry)
class MetricsTracker:
    def __init__(self) -> None:
        self.session_start_times: Dict[str, float] = {}
        self.skipped_critical_steps: Dict[str, int] = {}
        self.steps_completed: Dict[str, int] = {}

    def start_session(self, session_id: str) -> None:
        self.session_start_times[session_id] = time.time()
        self.skipped_critical_steps[session_id] = 0
        self.steps_completed[session_id] = 0

    def record_step_completed(self, session_id: str) -> None:
        self.steps_completed[session_id] = self.steps_completed.get(session_id, 0) + 1

    def record_critical_step_skipped(self, session_id: str) -> None:
        self.skipped_critical_steps[session_id] = self.skipped_critical_steps.get(session_id, 0) + 1

    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        elapsed = 0.0
        if session_id in self.session_start_times:
            elapsed = time.time() - self.session_start_times[session_id]
        
        return {
            "session_id": session_id,
            "elapsed_seconds": round(elapsed, 2),
            "steps_completed": self.steps_completed.get(session_id, 0),
            "skipped_critical_steps": self.skipped_critical_steps.get(session_id, 0)
        }

metrics_tracker = MetricsTracker()
