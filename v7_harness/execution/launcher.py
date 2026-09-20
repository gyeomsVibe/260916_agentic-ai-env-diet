"""Mock subprocess worker launcher with crash, timeout, and partial-result simulation."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import time
from typing import Any, Callable

from v7_harness.contracts.execution import WorkerDecision, interpret_worker_result

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


def _create_win_job() -> Any:
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        res = kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not res:
            kernel32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


def _assign_process_to_job(job: Any, proc: subprocess.Popen[str]) -> bool:
    if not job or os.name != "nt":
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        handle = int(proc._handle)
        return bool(kernel32.AssignProcessToJobObject(job, handle))
    except Exception:
        return False


def _terminate_process_tree(job: Any, proc: subprocess.Popen[str]) -> bool:
    job_closed = False
    if job and os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel32.TerminateJobObject.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.TerminateJobObject(job, 1)
            kernel32.CloseHandle(job)
            job_closed = True
        except Exception:
            pass
    if os.name == "nt" and not job_closed:
        try:
            # Run tree fallback while the parent still exists so taskkill can
            # enumerate descendants before their parent relationship is lost.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass
    if os.name != "nt":
        try:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
    return job_closed


def _cleanup_job(job: Any) -> None:
    if job and os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(job)
        except Exception:
            pass



def build_worker_script(
    mode: str,
    *,
    attempt_id: str,
    acceptance_hash: str,
    command_id: str = "c1",
) -> str:
    """Generate isolated python script for mock subprocess worker."""
    if mode == "success":
        doc = {
            "schema_version": 1,
            "status": "SUCCEEDED",
            "attempt_id": attempt_id,
            "acceptance_hash": acceptance_hash,
            "result": {"output": "ok", "command_id": command_id},
            "effect_observed": True,
        }
        return f"import json; print({repr(json.dumps(doc))})"
    if mode == "crash":
        return "import sys; sys.stderr.write('worker crashed\\n'); sys.exit(42)"
    if mode == "timeout":
        return "import time; time.sleep(10.0)"
    if mode == "partial_result":
        # Exit 0 with broken / partial payload
        return "print('{\"status\": \"PARTIAL_TRUNCATED')"
    if mode == "unknown_effect":
        # Simulates writing external side-effect then crashing without receiving receipt
        return "import sys; sys.stderr.write('connection lost after write\\n'); sys.exit(55)"
    raise ValueError(f"Unknown mock mode: {mode}")


class MockSubprocessLauncher:
    """Execute worker subprocess strictly outside any SQLite transaction."""

    def __init__(self, default_timeout_sec: float = 1.0) -> None:
        self.default_timeout_sec = default_timeout_sec

    def launch(
        self,
        *,
        attempt_id: str,
        acceptance_hash: str,
        command_id: str = "c1",
        mode: str = "success",
        timeout_sec: float | None = None,
        custom_script: str | None = None,
        on_wait_hook: Callable[[], None] | None = None,
        worker_capability: str | None = None,
        heartbeat: Callable[[], bool] | None = None,
        heartbeat_interval_sec: float = 0.25,
        **kwargs: Any,
    ) -> WorkerDecision:
        timeout = timeout_sec if timeout_sec is not None else self.default_timeout_sec
        script = custom_script or build_worker_script(
            mode,
            attempt_id=attempt_id,
            acceptance_hash=acceptance_hash,
            command_id=command_id,
        )

        job = _create_win_job()
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=os.name != "nt",
        )
        if job and not _assign_process_to_job(job, proc):
            _cleanup_job(job)
            job = None

        if on_wait_hook is not None:
            on_wait_hook()

        if heartbeat_interval_sec <= 0:
            raise ValueError("INVALID_HEARTBEAT_INTERVAL")
        deadline = time.monotonic() + timeout
        try:
            while True:
                if heartbeat is not None and not heartbeat():
                    if _terminate_process_tree(job, proc):
                        job = None
                    proc.communicate(timeout=1.0)
                    return WorkerDecision(False, "NEEDS_RECONCILIATION", "UNKNOWN", False, "LEASE_HEARTBEAT_FAILED")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(proc.args, timeout)
                try:
                    stdout, stderr = proc.communicate(timeout=min(heartbeat_interval_sec, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except subprocess.TimeoutExpired:
            if _terminate_process_tree(job, proc):
                job = None
            try:
                proc.communicate(timeout=1.0)
            except Exception:
                pass
            if worker_capability == "read_only":
                return WorkerDecision(
                    successful=False,
                    result_status="TIMEOUT",
                    effect_state="NONE",
                    retryable=True,
                    error_class="TIMEOUT",
                )
            return WorkerDecision(
                successful=False,
                result_status="NEEDS_RECONCILIATION",
                effect_state="UNKNOWN",
                retryable=False,
                error_class="TIMEOUT",
            )
        finally:
            _cleanup_job(job)

        if mode == "unknown_effect":
            return WorkerDecision(
                successful=False,
                result_status="NEEDS_RECONCILIATION",
                effect_state="UNKNOWN",
                retryable=False,
                error_class="SIDE_EFFECT_UNKNOWN",
            )

        if proc.returncode != 0:
            return WorkerDecision(
                successful=False,
                result_status="ERROR",
                effect_state="NONE",
                retryable=False,
                error_class="WORKER_CRASH",
            )

        # Parse and validate output
        try:
            document = json.loads(stdout.strip())
        except (ValueError, json.JSONDecodeError):
            return WorkerDecision(
                successful=False,
                result_status="ERROR",
                effect_state="NONE",
                retryable=False,
                error_class="VALIDATION",
            )

        if (
            not isinstance(document, dict)
            or document.get("status") != "SUCCEEDED"
            or document.get("attempt_id") != attempt_id
            or document.get("acceptance_hash") != acceptance_hash
            or document.get("effect_observed") is not True
        ):
            return WorkerDecision(
                successful=False,
                result_status="ERROR",
                effect_state="NONE",
                retryable=False,
                error_class="VALIDATION",
            )

        return interpret_worker_result(
            envelope_status="SUCCEEDED",
            exit_code=0,
            response_claim="SUCCESS",
            effect_observed=True,
            provider_error=None,
        )
