# Tests package marker.
import os

# Several CLI tests run `pilot run --source .` from the project root. With the stream autolog on by default
# (U33) they would write events into this project's real coordination stream, as happened once before.
os.environ["UAOS_STREAM_AUTOLOG"] = "0"
