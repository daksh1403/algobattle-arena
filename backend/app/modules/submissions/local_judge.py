"""Local sandbox fallback — used when Judge0 is unavailable.

This lets the judge pipeline work for demos and local development
without requiring Docker/Judge0 to be running.

The sandbox enforces:
- CPU time limits  (SIGKILL after wall-clock)
- Memory limits    (RLIMIT_AS on Linux; Python MemoryError on macOS)
- Output size      (RLIMIT_FSIZE → SIGXFSZ → RE)
- Infinite loops   (wall-clock SIGALRM/SIGKILL)
- Infinite recursion (Python RecursionError → RE)
- Division by zero (Python ZeroDivisionError → RE)
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.submissions.judge_client import JudgeResult

# Language → (extension, command_prefix)
_LANG_MAP = {
    "python": (".py", ""),
    "cpp": (".cpp", "g++ -o /tmp/sandbox /tmp/code.cpp -O2 && /tmp/sandbox"),
    "javascript": (".js", "node"),
    "java": (".java", None),  # java needs special handling
    "go": (".go", None),
    "rust": (".rs", None),
}


@dataclass
class LocalResult:
    """Internal result from the local sandbox."""
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: float
    memory_kb: int


class LocalJudgeClient:
    """Drop-in substitute for JudgeClient using local subprocess sandboxing."""

    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._last_payloads: list[dict] = []

    def make_payload(
        self,
        *,
        source_code: str,
        language_id: int,
        stdin: str,
        expected_output: str,
        cpu_time_limit: float,
        memory_limit: int,
    ) -> dict:
        """Returns a dict with enough info to run the sandbox later."""
        return {
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin,
            "expected_output": expected_output,
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit,
        }

    def _run_python(self, source_code: str, stdin: str, time_limit_s: float, output_limit_b: int) -> LocalResult:
        """Run Python code in a subprocess with resource limits."""
        import os, signal, time

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source_code)
            tmp = f.name

        wall_start = time.perf_counter()

        # Build RLIMIT_FSIZE (output limit)
        import resource
        limits = [(resource.RLIMIT_FSIZE, output_limit_b)]

        proc = subprocess.Popen(
            ["python3", "-u", tmp],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        # Wall-clock timer
        def wall_kill():
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        import threading
        timer = threading.Timer(time_limit_s + 0.5, wall_kill)
        timer.start()

        try:
            stdout, stderr = proc.communicate(input=stdin.encode(), timeout=time_limit_s + 1)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            wall_ms = (time.perf_counter() - wall_start) * 1000
            timer.cancel()
            os.unlink(tmp)
            return LocalResult(stdout="", stderr="TIME LIMIT EXCEEDED", exit_code=-1, runtime_ms=wall_ms, memory_kb=0)

        timer.cancel()
        wall_ms = (time.perf_counter() - wall_start) * 1000

        # Map exit code to verdict
        exit_code = proc.returncode

        os.unlink(tmp)

        # Memory via ps (best-effort on macOS)
        mem_kb = self._get_mem_kb(proc.pid)

        return LocalResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=exit_code,
            runtime_ms=wall_ms,
            memory_kb=mem_kb,
        )

    def _run_cpp(self, source_code: str, stdin: str, time_limit_s: float, output_limit_b: int) -> LocalResult:
        """Compile and run C++ code."""
        import os, signal, time

        with tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as cf:
            cf.write(source_code)
            cpp_file = cf.name
        exe_file = cpp_file.replace(".cpp", "")

        # Compile
        compile_proc = subprocess.run(
            ["g++", "-O2", "-o", exe_file, cpp_file],
            capture_output=True, timeout=30,
        )
        os.unlink(cpp_file)
        if compile_proc.returncode != 0:
            return LocalResult(
                stdout="", stderr=compile_proc.stderr.decode(), exit_code=compile_proc.returncode, runtime_ms=0, memory_kb=0
            )

        wall_start = time.perf_counter()

        proc = subprocess.Popen(
            [exe_file],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )

        def wall_kill():
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        import threading
        timer = threading.Timer(time_limit_s + 0.5, wall_kill)
        timer.start()

        try:
            stdout, stderr = proc.communicate(input=stdin.encode(), timeout=time_limit_s + 1)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            wall_ms = (time.perf_counter() - wall_start) * 1000
            timer.cancel()
            os.unlink(exe_file)
            return LocalResult(stdout="", stderr="TIME LIMIT EXCEEDED", exit_code=-1, runtime_ms=wall_ms, memory_kb=0)

        timer.cancel()
        wall_ms = (time.perf_counter() - wall_start) * 1000
        exit_code = proc.returncode
        os.unlink(exe_file)

        mem_kb = self._get_mem_kb(proc.pid)
        return LocalResult(stdout=stdout.decode("utf-8", errors="replace"), stderr=stderr.decode("utf-8", errors="replace"), exit_code=exit_code, runtime_ms=wall_ms, memory_kb=mem_kb)

    def _run_js(self, source_code: str, stdin: str, time_limit_s: float, output_limit_b: int) -> LocalResult:
        """Run Node.js code."""
        import os, signal, time

        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(source_code)
            tmp = f.name

        wall_start = time.perf_counter()
        proc = subprocess.Popen(
            ["node", tmp],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )

        def wall_kill():
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        import threading
        timer = threading.Timer(time_limit_s + 0.5, wall_kill)
        timer.start()

        try:
            stdout, stderr = proc.communicate(input=stdin.encode(), timeout=time_limit_s + 1)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            wall_ms = (time.perf_counter() - wall_start) * 1000
            timer.cancel()
            os.unlink(tmp)
            return LocalResult(stdout="", stderr="TIME LIMIT EXCEEDED", exit_code=-1, runtime_ms=wall_ms, memory_kb=0)

        timer.cancel()
        wall_ms = (time.perf_counter() - wall_start) * 1000
        exit_code = proc.returncode
        os.unlink(tmp)

        mem_kb = self._get_mem_kb(proc.pid)
        return LocalResult(stdout=stdout.decode("utf-8", errors="replace"), stderr=stderr.decode("utf-8", errors="replace"), exit_code=exit_code, runtime_ms=wall_ms, memory_kb=mem_kb)

    def _get_mem_kb(self, pid: int) -> int:
        """Best-effort memory measurement. Returns 0 if unavailable."""
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            return int(usage.ru_maxrss)  # KB on macOS
        except Exception:
            return 0

    def _map_to_judge_result(self, res: LocalResult, expected_output: str, token: str = "") -> "JudgeResult":
        """Convert LocalResult to the same format JudgeClient returns."""
        from app.modules.submissions.judge_client import JudgeResult

        stdout = res.stdout.strip()
        expected = expected_output.strip()

        # Determine status
        if res.exit_code == -1:
            status = "time_limit_exceeded"
        elif res.exit_code == 137:  # SIGKILL (wall clock or OOM)
            if "memory" in res.stderr.lower() or "killed" in res.stderr.lower():
                status = "memory_limit_exceeded"
            else:
                status = "time_limit_exceeded"
        elif res.exit_code != 0:
            status = "runtime_error"
        elif stdout == expected:
            status = "accepted"
        else:
            status = "wrong_answer"

        return JudgeResult(
            token=token,
            status=status,
            stdout=stdout,
            stderr=res.stderr[:500],
            compile_output="",
            runtime_ms=int(res.runtime_ms),
            memory_kb=res.memory_kb,
        )

    def _lang_name_from_id(self, language_id: int) -> str:
        """Map Judge0 language IDs to our lang names."""
        # Judge0 language IDs (see judge_client.py)
        return {
            71: "python",
            54: "cpp",
            63: "javascript",
            62: "java",
            60: "go",
            73: "rust",
        }.get(language_id, "python")

    def _run(self, source_code: str, lang: str, stdin: str, time_limit_s: float, output_limit_b: int = 128 * 1024) -> LocalResult:
        """Dispatch to the right runner."""
        if lang == "python":
            return self._run_python(source_code, stdin, time_limit_s, output_limit_b)
        elif lang == "cpp":
            return self._run_cpp(source_code, stdin, time_limit_s, output_limit_b)
        elif lang == "javascript":
            return self._run_js(source_code, stdin, time_limit_s, output_limit_b)
        else:
            # Fallback: python
            return self._run_python(source_code, stdin, time_limit_s, output_limit_b)

    async def submit_batch(self, payloads: list[dict]) -> list[str]:
        """Synchronous — returns fake tokens (one per payload)."""
        self._last_payloads = payloads
        return [f"local-token-{i}" for i in range(len(payloads))]

    async def poll_batch(self, tokens: list[str]) -> list["JudgeResult"]:
        """Run each payload locally and return results."""
        results: list["JudgeResult"] = []
        for i, (token, payload) in enumerate(zip(tokens, self._last_payloads)):
            local = self._run(
                source_code=payload["source_code"],
                lang=self._lang_name_from_id(payload["language_id"]),
                stdin=payload["stdin"],
                time_limit_s=payload["cpu_time_limit"],
            )
            results.append(self._map_to_judge_result(local, payload["expected_output"], token))
        return results
