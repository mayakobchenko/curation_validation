import os
import sys
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="cv-test-"))
os.environ.setdefault("DEV_MODE", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
