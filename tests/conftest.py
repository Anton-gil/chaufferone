"""Test env: a throwaway SQLite DB, the demo clock pinned, and no hosted LLM calls.

Must run before any `app.*` import, because settings and the engine are built at import.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="chaufferone-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DEMO_SNAPSHOT_PATH"] = str(_TMP / "snapshot.db")
os.environ["DEMO_TODAY"] = "2026-09-30"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["VOICE_LLM_ENABLED"] = "false"
os.environ["UPI_PAYEE_VPA"] = "demo.teammate@okaxis"
os.environ["DEMO_SENDERS"] = "[]"
