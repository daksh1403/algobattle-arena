#!/usr/bin/env python3
"""
Universal Sandbox Runner - Cross-Platform Code Execution
=====================================================

Works on: macOS, Linux, Windows

Features:
- Process isolation
- Resource limits (CPU time, memory, output)
- Wall-clock enforcement
- Disruption handling
- Multi-language support
- Deterministic execution

OS Detection:
- Uses platform-specific optimizations where available
- Falls back gracefully on unsupported platforms
"""

from __future__ import annotations

import enum
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import shutil
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

# ============================================================================
# Platform Detection
# ============================================================================

PLATFORM = platform.system().lower()
IS_LINUX = PLATFORM == "linux"
IS_MACOS = PLATFORM == "darwin"
IS_WINDOWS = PLATFORM == "windows"


# ============================================================================
# Constants
# ============================================================================

class Verdict(str, enum.Enum):
    """All possible submission verdicts."""
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"
    PENDING = "pending"
    RUNNING = "running"


@dataclass
class RunResult:
    """Result from code execution."""
    verdict: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    runtime_ms: float = 0.0
    memory_kb: float = 0.0
    cpu_time_ms: float = 0.0
    token: str = ""
    error_detail: str = ""

    def is_terminal(self) -> bool:
        return self.verdict in {
            Verdict.ACCEPTED,
            Verdict.WRONG_ANSWER,
            Verdict.TIME_LIMIT_EXCEEDED,
            Verdict.MEMORY_LIMIT_EXCEEDED,
            Verdict.OUTPUT_LIMIT_EXCEEDED,
            Verdict.RUNTIME_ERROR,
            Verdict.COMPILATION_ERROR,
            Verdict.INTERNAL_ERROR,
        }


# ============================================================================
# Resource Monitor (Cross-Platform)
# ============================================================================

class ResourceMonitor:
    """Monitor CPU and memory usage cross-platform."""
    
    @staticmethod
    def get_process_stats(pid: int) -> tuple[float, int]:
        """Get CPU time (ms) and memory (KB) for a process."""
        cpu_ms = 0.0
        mem_kb = 0
        
        try:
            if IS_LINUX:
                cpu_ms, mem_kb = ResourceMonitor._linux_stats(pid)
            elif IS_MACOS:
                cpu_ms, mem_kb = ResourceMonitor._macos_stats(pid)
            elif IS_WINDOWS:
                cpu_ms, mem_kb = ResourceMonitor._windows_stats(pid)
        except (ProcessLookupError, FileNotFoundError, PermissionError):
            pass
        
        return cpu_ms, mem_kb
    
    @staticmethod
    def _linux_stats(pid: int) -> tuple[float, int]:
        """Linux: Read from /proc."""
        cpu_ms = 0.0
        mem_kb = 0
        
        # Get CPU time from /proc/[pid]/stat
        try:
            with open(f"/proc/{pid}/stat") as f:
                stat = f.read().split()
                # utime + stime in clock ticks, convert to ms
                clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                cpu_time = (int(stat[13]) + int(stat[14])) / clk_tck * 1000
                cpu_ms = cpu_time
        except (FileNotFoundError, IndexError, ValueError):
            pass
        
        # Get memory from /proc/[pid]/status
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem_kb = int(line.split()[1])
                        break
        except (FileNotFoundError, ValueError):
            pass
        
        return cpu_ms, mem_kb
    
    @staticmethod
    def _macos_stats(pid: int) -> tuple[float, int]:
        """macOS: Use ps command."""
        cpu_ms = 0.0
        mem_kb = 0
        
        try:
            # Get CPU percentage and memory
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "%cpu,rss"],
                capture_output=True,
                text=True,
                timeout=1
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 2:
                    # CPU is percentage, RSS is KB
                    cpu_ms = 0.0  # Can't get absolute CPU time easily on macOS
                    mem_kb = int(parts[1])
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        
        return cpu_ms, mem_kb
    
    @staticmethod
    def _windows_stats(pid: int) -> tuple[float, int]:
        """Windows: Use wmic."""
        cpu_ms = 0.0
        mem_kb = 0
        
        try:
            result = subprocess.run(
                ["wmic", "process", "where", f"ProcessId={pid}", "get", "WorkingSetSize"],
                capture_output=True,
                text=True,
                timeout=1
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                mem_kb = int(lines[1].strip()) // 1024
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        
        return cpu_ms, mem_kb


# ============================================================================
# Process Killer (Cross-Platform)
# ============================================================================

class ProcessKiller:
    """Kill processes and process trees cross-platform."""
    
    @staticmethod
    def kill(pid: int) -> None:
        """Kill a process and all its children."""
        try:
            if IS_WINDOWS:
                ProcessKiller._kill_windows(pid)
            else:
                ProcessKiller._kill_unix(pid)
        except (ProcessLookupError, PermissionError):
            pass
    
    @staticmethod
    def _kill_unix(pid: int) -> None:
        """Kill on Unix-like systems."""
        try:
            # Kill process group first (handles child processes)
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            # Try just the process
            os.kill(pid, signal.SIGKILL)
    
    @staticmethod
    def _kill_windows(pid: int) -> None:
        """Kill on Windows."""
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


# ============================================================================
# Wall Clock Timer (Cross-Platform)
# ============================================================================

class WallClockTimer:
    """Monitor wall-clock time cross-platform."""
    
    def __init__(self, timeout_ms: int):
        self.timeout_ms = timeout_ms
        self.start_time = time.perf_counter()
        self._stopped = False
        self._kill_callback = None
        self._thread = None
    
    def start(self, pid: int, killer_callback):
        """Start monitoring."""
        self._kill_callback = killer_callback
        
        if IS_WINDOWS:
            # Windows doesn't have SIGALRM, use threading
            self._thread = threading.Thread(target=self._windows_monitor, args=(pid,), daemon=True)
            self._thread.start()
        else:
            # Unix: use threading with sleep
            self._thread = threading.Thread(target=self._unix_monitor, args=(pid,), daemon=True)
            self._thread.start()
    
    def _unix_monitor(self, pid: int) -> None:
        """Unix wall clock monitor."""
        timeout_s = self.timeout_ms / 1000
        time.sleep(timeout_s)
        
        if not self._stopped:
            try:
                # Check if still running
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                self._kill_callback(pid)
            except (ProcessLookupError, PermissionError):
                pass
    
    def _windows_monitor(self, pid: int) -> None:
        """Windows wall clock monitor."""
        timeout_s = self.timeout_ms / 1000
        time.sleep(timeout_s)
        
        if not self._stopped:
            self._kill_callback(pid)
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._stopped = True
        if self._thread:
            self._thread.join(timeout=1)
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in ms."""
        return (time.perf_counter() - self.start_time) * 1000


# ============================================================================
# Disruption Scenarios
# ============================================================================

class DisruptionScenario:
    """Code templates for testing disruption handling."""
    
    @staticmethod
    def infinite_loop() -> str:
        return "while True: pass"
    
    @staticmethod
    def infinite_recursion() -> str:
        return """
import sys
sys.setrecursionlimit(10000)
def recurse(n): return recurse(n+1)
recurse(0)
"""
    
    @staticmethod
    def memory_bomb() -> str:
        return """
lst = []
while True:
    lst.append(bytearray(1000000))
"""
    
    @staticmethod
    def division_by_zero() -> str:
        return "result = 1 / 0"
    
    @staticmethod
    def index_error() -> str:
        return "print([1,2,3][100])"
    
    @staticmethod
    def segmentation_fault_c() -> str:
        return """
#include <stdio.h>
int main() {
    int *p = NULL;
    printf("%d\\n", *p);
    return 0;
}
"""


# ============================================================================
# Main Sandbox Runner
# ============================================================================

class SandboxRunner:
    """
    Cross-platform code execution sandbox.
    
    Works on: macOS, Linux, Windows
    """
    
    def __init__(
        self,
        language: str = "python",
        cpu_time_s: int = 5,
        wall_time_s: int = 10,
        memory_kb: int = 256 * 1024,
        output_kb: int = 128,
    ):
        self.language = language.lower()
        self.cpu_time_s = cpu_time_s
        self.wall_time_s = wall_time_s
        self.memory_kb = memory_kb
        # The JVM reserves large VIRTUAL regions on startup (compressed
        # class space ~1GB + heap + metaspace + code cache) even though its
        # actual RSS stays near -Xmx. RLIMIT_AS must cover that virtual
        # footprint or the JVM dies with "Could not reserve enough space".
        # Actual memory use is still bounded by -Xmx256m in _run_java.
        if self.language == "java":
            self.memory_kb = max(self.memory_kb, 2048 * 1024)
        self.output_kb = output_kb
        self.token = uuid.uuid4().hex[:8]
    
    def run(
        self,
        code: str,
        stdin: str = "",
        expected_stdout: Optional[str] = None,
    ) -> RunResult:
        """
        Execute code and return result.
        
        Args:
            code: Source code to execute
            stdin: Standard input
            expected_stdout: Expected output (for comparison)
        
        Returns:
            RunResult with verdict and execution stats
        """
        start_time = time.perf_counter()
        
        # Dispatch to language-specific runner
        if self.language in ("python", "python3"):
            return self._run_python(code, stdin, expected_stdout, start_time)
        elif self.language in ("cpp", "c++", "c"):
            return self._run_cpp(code, stdin, expected_stdout, start_time)
        elif self.language in ("javascript", "node", "nodejs"):
            return self._run_javascript(code, stdin, expected_stdout, start_time)
        elif self.language == "java":
            return self._run_java(code, stdin, expected_stdout, start_time)
        elif self.language == "go":
            return self._run_go(code, stdin, expected_stdout, start_time)
        elif self.language == "rust":
            return self._run_rust(code, stdin, expected_stdout, start_time)
        else:
            return RunResult(
                verdict=Verdict.COMPILATION_ERROR,
                stderr=f"Unsupported language: {self.language}",
                runtime_ms=0,
                memory_kb=0,
                token=self.token,
                error_detail="Language not supported",
            )
    
    def _run_python(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Execute Python code."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"solution_{self.token}.py"
            code_file.write_text(code)
            
            # Build command
            cmd = [
                sys.executable,
                "-u",  # Unbuffered
                str(code_file),
            ]
            
            return self._execute_process(
                cmd, stdin, expected_stdout, start_time, tmpdir
            )
    
    def _run_cpp(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Compile and execute C++ code."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"solution_{self.token}.cpp"
            exe_file = Path(tmpdir) / f"solution_{self.token}"
            
            code_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ["g++", "-O2", "-std=c++17", "-o", str(exe_file), str(code_file)],
                capture_output=True,
                timeout=30,
                cwd=tmpdir,
            )
            
            if compile_result.returncode != 0:
                return RunResult(
                    verdict=Verdict.COMPILATION_ERROR,
                    stderr=compile_result.stderr.decode(errors="replace"),
                    runtime_ms=0,
                    memory_kb=0,
                    token=self.token,
                    error_detail="Compilation failed",
                )
            
            # Run
            return self._execute_process(
                [str(exe_file)], stdin, expected_stdout, start_time, tmpdir
            )
    
    def _run_javascript(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Execute JavaScript/Node.js code."""
        
        # Find node
        node_path = shutil.which("node")
        if not node_path:
            # Common macOS locations
            for path in ["/usr/local/bin/node", "/opt/homebrew/bin/node"]:
                if os.path.exists(path):
                    node_path = path
                    break
        
        if not node_path:
            return RunResult(
                verdict=Verdict.INTERNAL_ERROR,
                stderr="Node.js not found",
                runtime_ms=0,
                memory_kb=0,
                token=self.token,
                error_detail="JavaScript runtime not installed",
            )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"solution_{self.token}.js"
            code_file.write_text(code)
            
            return self._execute_process(
                [node_path, str(code_file)],
                stdin, expected_stdout, start_time, tmpdir
            )
    
    def _run_java(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Compile and execute Java code."""
        
        # Extract class name
        import re
        match = re.search(r"public\s+class\s+(\w+)", code)
        if not match:
            return RunResult(
                verdict=Verdict.COMPILATION_ERROR,
                stderr="Could not find public class in Java source",
                runtime_ms=0,
                memory_kb=0,
                token=self.token,
            )
        
        class_name = match.group(1)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"{class_name}.java"
            code_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ["javac", str(code_file)],
                capture_output=True,
                timeout=30,
                cwd=tmpdir,
            )
            
            if compile_result.returncode != 0:
                return RunResult(
                    verdict=Verdict.COMPILATION_ERROR,
                    stderr=compile_result.stderr.decode(errors="replace"),
                    runtime_ms=0,
                    memory_kb=0,
                    token=self.token,
                )
            
            # Run (cap JVM memory so it fits the sandbox budget even in
            # memory-limited containers / VPS instances)
            return self._execute_process(
                ["java", "-Xmx256m", "-XX:MaxMetaspaceSize=128m",
                 "-XX:ReservedCodeCacheSize=64m",
                 "-cp", tmpdir, class_name],
                stdin, expected_stdout, start_time, tmpdir
            )
    
    def _run_go(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Compile and execute Go code."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"solution_{self.token}.go"
            exe_file = Path(tmpdir) / f"solution_{self.token}"
            
            code_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ["go", "build", "-o", str(exe_file), str(code_file)],
                capture_output=True,
                timeout=30,
                cwd=tmpdir,
            )
            
            if compile_result.returncode != 0:
                return RunResult(
                    verdict=Verdict.COMPILATION_ERROR,
                    stderr=compile_result.stderr.decode(errors="replace"),
                    runtime_ms=0,
                    memory_kb=0,
                    token=self.token,
                )
            
            # Run
            return self._execute_process(
                [str(exe_file)],
                stdin, expected_stdout, start_time, tmpdir
            )
    
    def _run_rust(
        self,
        code: str,
        stdin: str,
        expected_stdout: str,
        start_time: float,
    ) -> RunResult:
        """Compile and execute Rust code."""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / f"solution_{self.token}.rs"
            exe_file = Path(tmpdir) / f"solution_{self.token}"
            
            code_file.write_text(code)
            
            # Compile
            compile_result = subprocess.run(
                ["rustc", "-O", "-o", str(exe_file), str(code_file)],
                capture_output=True,
                timeout=60,
                cwd=tmpdir,
            )
            
            if compile_result.returncode != 0:
                return RunResult(
                    verdict=Verdict.COMPILATION_ERROR,
                    stderr=compile_result.stderr.decode(errors="replace"),
                    runtime_ms=0,
                    memory_kb=0,
                    token=self.token,
                )
            
            # Run
            return self._execute_process(
                [str(exe_file)],
                stdin, expected_stdout, start_time, tmpdir
            )
    
    def _execute_process(
        self,
        cmd: list[str],
        stdin: str,
        expected_stdout: str,
        start_time: float,
        work_dir: str,
    ) -> RunResult:
        """Execute a process with resource limits."""
        
        stdout_data = b""
        stderr_data = b""
        exit_code = 0
        max_memory_kb = 0

        # Capture cumulative child CPU time before this spawn (for delta)
        cpu_before = 0.0
        if not IS_WINDOWS:
            try:
                import resource as _r
                _u = _r.getrusage(_r.RUSAGE_CHILDREN)
                cpu_before = (_u.ru_utime + _u.ru_stime) * 1000
            except Exception:
                pass
        
        try:
            # Create stdin file
            stdin_file = Path(work_dir) / "stdin.txt"
            stdin_file.write_text(stdin)
            
            # --- Hard resource limits applied BEFORE exec (Unix only) ---
            # RLIMIT_AS kills on memory overflow, RLIMIT_CPU on CPU time,
            # RLIMIT_STACK on stack overflow, RLIMIT_FSIZE on output overflow.
            rlimits = {
                "RLIMIT_AS": self.memory_kb * 1024,
                "RLIMIT_CPU": max(1, int(self.wall_time_s)),
                "RLIMIT_STACK": 64 * 1024 * 1024,      # 64MB
                "RLIMIT_FSIZE": self.output_kb * 1024,
            }

            def _apply_rlimits():
                if IS_WINDOWS:
                    return
                import resource as _r
                for name, val in rlimits.items():
                    try:
                        rlim = getattr(_r, name)
                        _r.setrlimit(rlim, (val, val))
                    except (AttributeError, ValueError, OSError):
                        pass

            # Start process
            proc = subprocess.Popen(
                cmd,
                stdin=open(stdin_file),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=work_dir,
                start_new_session=not IS_WINDOWS,
                preexec_fn=_apply_rlimits if not IS_WINDOWS else None,
            )
            
            # Wall clock timer
            timer = WallClockTimer(int(self.wall_time_s * 1000))
            
            def kill_callback(pid):
                ProcessKiller.kill(pid)
            
            timer.start(proc.pid, kill_callback)
            
            # --- Live memory monitor: kill early on memory breach ---
            peak_memory = 0
            mem_killed = threading.Event()

            def _mem_monitor():
                nonlocal peak_memory
                while proc.poll() is None:
                    try:
                        _, mem_kb = ResourceMonitor.get_process_stats(proc.pid)
                    except Exception:
                        mem_kb = 0
                    if mem_kb > peak_memory:
                        peak_memory = mem_kb
                    if self.memory_kb > 0 and mem_kb > self.memory_kb:
                        mem_killed.set()
                        ProcessKiller.kill(proc.pid)
                        return
                    time.sleep(0.01)

            mem_thread = threading.Thread(target=_mem_monitor, daemon=True)
            mem_thread.start()
            
            try:
                # Wait for process
                stdout_data, stderr_data = proc.communicate(
                    timeout=self.wall_time_s + 5
                )
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                # Process timed out
                ProcessKiller.kill(proc.pid)
                try:
                    proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                exit_code = -1
            finally:
                timer.stop()
                mem_thread.join(timeout=0.5)
            
            # Get elapsed time
            wall_time_ms = timer.elapsed_ms()
            
            # Real CPU time: delta of cumulative child CPU (before vs after)
            cpu_time_ms = wall_time_ms
            if not IS_WINDOWS:
                try:
                    import resource as _r
                    _u = _r.getrusage(_r.RUSAGE_CHILDREN)
                    cpu_after = (_u.ru_utime + _u.ru_stime) * 1000
                    cpu_time_ms = max(0.0, cpu_after - cpu_before)
                except Exception:
                    pass
            
            # Get memory stats
            max_memory_kb = peak_memory
            if max_memory_kb <= 0 and (proc.poll() is not None or exit_code != 0):
                _, max_memory_kb = ResourceMonitor.get_process_stats(proc.pid)
            
            # Map exit code to verdict
            verdict = self._map_exit_code(exit_code, wall_time_ms, stderr_data)
            
            # Check for specific errors in stderr
            stderr_str = stderr_data.decode(errors="replace")
            if mem_killed.is_set() or "MemoryError" in stderr_str or "memory" in stderr_str.lower():
                verdict = Verdict.MEMORY_LIMIT_EXCEEDED
            
            # Check output limit
            stdout_str = stdout_data.decode(errors="replace")
            if len(stdout_str) > self.output_kb * 1024:
                verdict = Verdict.OUTPUT_LIMIT_EXCEEDED
            
            # Compare output if expected provided
            if expected_stdout is not None and verdict == Verdict.ACCEPTED:
                if stdout_str.strip() != expected_stdout.strip():
                    verdict = Verdict.WRONG_ANSWER
            
            return RunResult(
                verdict=verdict,
                stdout=stdout_str[:1024 * 1024],  # Truncate to 1MB
                stderr=stderr_str[:1024],  # Truncate to 1KB
                exit_code=exit_code,
                runtime_ms=wall_time_ms,
                memory_kb=max_memory_kb,
                cpu_time_ms=cpu_time_ms,
                token=self.token,
            )
            
        except FileNotFoundError as e:
            return RunResult(
                verdict=Verdict.INTERNAL_ERROR,
                stderr=f"Command not found: {e}",
                runtime_ms=0,
                memory_kb=0,
                token=self.token,
                error_detail="Compiler/interpreter not found",
            )
        except Exception as e:
            return RunResult(
                verdict=Verdict.INTERNAL_ERROR,
                stderr=str(e),
                runtime_ms=0,
                memory_kb=0,
                token=self.token,
                error_detail="Execution failed",
            )
    
    def _map_exit_code(
        self,
        exit_code: int,
        wall_time_ms: float,
        stderr: bytes,
    ) -> str:
        """Map exit code to verdict."""
        
        stderr_str = stderr.decode(errors="replace").lower()
        
        # Check for wall clock timeout
        if wall_time_ms > self.wall_time_s * 1000:
            return Verdict.TIME_LIMIT_EXCEEDED
        
        # Success
        if exit_code == 0:
            return Verdict.ACCEPTED
        
        # Killed by signal (negative exit code on Unix)
        if exit_code < 0:
            sig = -exit_code
            # RLIMIT_CPU exceeded → SIGXCPU → TLE
            if hasattr(signal, "SIGXCPU") and sig == signal.SIGXCPU:
                return Verdict.TIME_LIMIT_EXCEEDED
            # RLIMIT_FSIZE exceeded → SIGXFSZ → OLE
            if hasattr(signal, "SIGXFSZ") and sig == signal.SIGXFSZ:
                return Verdict.OUTPUT_LIMIT_EXCEEDED
            # RLIMIT_AS exceeded → MemoryError/SIGKILL by OOM killer
            if sig in (signal.SIGKILL, signal.SIGTERM):
                return Verdict.TIME_LIMIT_EXCEEDED
            elif sig in (signal.SIGSEGV, signal.SIGFPE, signal.SIGABRT):
                return Verdict.RUNTIME_ERROR
            return Verdict.RUNTIME_ERROR
        
        # Exit with error
        if exit_code in (1, 127):
            # Check stderr for specific error types
            if "zerodivision" in stderr_str:
                return Verdict.RUNTIME_ERROR
            elif "index" in stderr_str and "error" in stderr_str:
                return Verdict.RUNTIME_ERROR
            elif "recursion" in stderr_str:
                return Verdict.RUNTIME_ERROR
            elif "memory" in stderr_str:
                return Verdict.MEMORY_LIMIT_EXCEEDED
            return Verdict.RUNTIME_ERROR
        
        return Verdict.RUNTIME_ERROR
    
    def run_batch(
        self,
        code: str,
        runs: list[dict],
    ) -> list[RunResult]:
        """Run code against multiple test cases."""
        results = []
        for run in runs:
            result = self.run(
                code,
                stdin=run.get("stdin", ""),
                expected_stdout=run.get("expected_stdout", ""),
            )
            results.append(result)
        return results


# ============================================================================
# Test Helpers
# ============================================================================

def test_disruptions(runner: SandboxRunner) -> dict:
    """Test all disruption scenarios."""
    scenarios = [
        ("infinite_loop", DisruptionScenario.infinite_loop(), Verdict.TIME_LIMIT_EXCEEDED),
        ("infinite_recursion", DisruptionScenario.infinite_recursion(), Verdict.TIME_LIMIT_EXCEEDED),
        ("memory_bomb", DisruptionScenario.memory_bomb(), Verdict.MEMORY_LIMIT_EXCEEDED),
        ("division_by_zero", DisruptionScenario.division_by_zero(), Verdict.RUNTIME_ERROR),
        ("index_error", DisruptionScenario.index_error(), Verdict.RUNTIME_ERROR),
    ]
    
    results = {}
    for name, code, expected in scenarios:
        try:
            result = runner.run(code)
            passed = result.verdict == expected
            results[name] = {
                "expected": expected,
                "actual": result.verdict,
                "passed": passed,
                "runtime_ms": result.runtime_ms,
            }
        except Exception as e:
            results[name] = {
                "expected": expected,
                "actual": Verdict.INTERNAL_ERROR,
                "passed": False,
                "error": str(e),
            }
    
    return results


def test_determinism(runner: SandboxRunner, code: str, runs: int = 5) -> dict:
    """Test that code produces deterministic results."""
    outputs = []
    verdicts = []
    
    for _ in range(runs):
        result = runner.run(code)
        outputs.append(result.stdout.strip())
        verdicts.append(result.verdict)
    
    return {
        "outputs": outputs,
        "verdicts": verdicts,
        "is_deterministic": len(set(outputs)) == 1 and len(set(verdicts)) == 1,
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json
    from dataclasses import asdict
    
    parser = argparse.ArgumentParser(description="Universal Sandbox Runner")
    parser.add_argument("--code", default="print('hello')", help="Code to run")
    parser.add_argument("--stdin", default="", help="Standard input")
    parser.add_argument("--expected", default="", help="Expected output")
    parser.add_argument("--lang", default="python", help="Language")
    parser.add_argument("--cpu-time", type=int, default=5, help="CPU time limit (s)")
    parser.add_argument("--wall-time", type=int, default=10, help="Wall time limit (s)")
    parser.add_argument("--disruption", action="store_true", help="Run disruption tests")
    parser.add_argument("--determinism", action="store_true", help="Run determinism test")
    parser.add_argument("--json", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    runner = SandboxRunner(
        language=args.lang,
        cpu_time_s=args.cpu_time,
        wall_time_s=args.wall_time,
    )
    
    if args.disruption:
        results = test_disruptions(runner)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Platform: {PLATFORM}")
            print(f"Disruption tests:")
            for name, r in results.items():
                status = "PASS" if r["passed"] else "FAIL"
                print(f"  {name}: {status} (expected={r['expected']}, got={r['actual']})")
    
    elif args.determinism:
        result = test_determinism(runner, args.code)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status = "PASS" if result["is_deterministic"] else "FAIL"
            print(f"Determinism: {status}")
            print(f"  Outputs: {result['outputs']}")
    
    else:
        result = runner.run(args.code, args.stdin, args.expected)
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(f"Verdict: {result.verdict}")
            print(f"Runtime: {result.runtime_ms:.2f}ms")
            print(f"Memory: {result.memory_kb:.0f}KB")
            if result.stdout:
                print(f"Stdout: {result.stdout[:200]}")
            if result.stderr:
                print(f"Stderr: {result.stderr[:200]}")
