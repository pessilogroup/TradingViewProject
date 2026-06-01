import subprocess
import os
import logging
from pathlib import Path
import threading

log = logging.getLogger(__name__)

def ingest_semantic_event_bg(text: str, category: str = "knowledge"):
    """
    Ingest a semantic event to Angati L1 cache in a background thread.
    Non-blocking, zero-latency to the caller.
    """
    def run_ingest():
        try:
            # Resolve project root and angati.exe path
            project_root = Path(__file__).resolve().parent.parent.parent
            angati_exe = project_root / "angati.exe"
            
            # Setup environment to isolate the database
            env = os.environ.copy()
            env["ANGATI_AGENTS_ROOT"] = str(project_root)
            
            # Spawn process to ingest
            res = subprocess.run(
                [str(angati_exe), "memory", "ingest", "--text", text, "--category", category],
                cwd=str(project_root),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=False
            )
            if res.returncode == 0:
                log.info(f"[Semantic Ingestion] Successfully ingested event ({category}): {text[:100]}...")
            else:
                log.warning(f"[Semantic Ingestion] Ingest command failed with code {res.returncode}: {res.stderr.strip()}")
        except Exception as e:
            log.warning(f"[Semantic Ingestion] Background ingestion error: {e}")

    threading.Thread(target=run_ingest, daemon=True).start()
