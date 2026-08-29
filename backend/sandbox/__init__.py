"""
Algobattle Remote Runtime Environment (RRE)
==========================================

A robust, deterministic code execution environment for competitive programming.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     Judge Coordinator                        │
    │         (Manages submission lifecycle, retries)              │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                     Sandbox Runner                           │
    │    (Process isolation, resource enforcement, verdict)         │
    │                                                              │
    │  Features:                                                   │
    │  - Multi-language: Python, C++, Java, JavaScript           │
    │  - Resource limits: CPU time, memory, output size           │
    │  - Deterministic execution (seeded RNG, isolated env)         │
    │  - Disruption handling: OOM, TLE, infinite loops            │
    └─────────────────────────────────────────────────────────────┘

Verdicts:
    AC  - All test cases passed
    WA  - Wrong answer (output mismatch)
    TLE - Time limit exceeded
    MLE - Memory limit exceeded
    OLE - Output limit exceeded
    RE  - Runtime error (exception, crash)
    CE  - Compilation error
    IE  - Internal error (system failure)
"""

from .sandbox_runner import (
    SandboxRunner,
    RunResult,
    DisruptionScenario,
    Verdict,
    test_disruptions,
    test_determinism,
)

__all__ = [
    "SandboxRunner",
    "RunResult",
    "DisruptionScenario",
    "Verdict",
    "test_disruptions",
    "test_determinism",
]
