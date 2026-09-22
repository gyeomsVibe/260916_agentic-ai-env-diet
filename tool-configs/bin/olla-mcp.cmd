@echo off
set "PYTHONPATH=D:/AI-Models/olla-release;%PYTHONPATH%"
python -P -m v7_harness.olla_mcp %*
