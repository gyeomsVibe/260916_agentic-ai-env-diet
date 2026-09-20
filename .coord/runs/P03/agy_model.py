"""Run agy with a fixed model (default model quota exhausted during P03 measurement)."""

import shutil
import subprocess
import sys

MODEL = "gemini-3.7-flash-high"
completed = subprocess.run([shutil.which("agy"), "--model", MODEL, *sys.argv[1:]])
raise SystemExit(completed.returncode)
