# Tests package marker.
import os

# Several CLI tests run `pilot run --source .` from the project root. With the stream autolog on by default
# (U33) they would write events into this project's real coordination stream, as happened once before.
os.environ["UAOS_STREAM_AUTOLOG"] = "0"

# U47-O1: this file runs only for dotted runs (`python -m unittest tests.test_x`); `discover -s tests` skips it, so
# the same guard also loads from test_000_env_guard.py, which sorts first.
from tests import _env_guard  # noqa: E402,F401
