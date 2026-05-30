#!/usr/bin/env python3
"""
Guardrail Registry — Declarative Safety Policies

Formalizes the Angati hook service's inline guardrail logic into a
declarative registry, aligning with Google ADK's callback/guardrail
architecture pattern.

Each guardrail is a named policy with:
    - type: Lifecycle hook point (before_tool, after_tool, on_error)
    - tools: Which tools trigger this guardrail ("*" = all)
    - handler: Function name that implements the check
    - short_circuit: If True, a violation blocks execution (ADK: return error)
    - description: Human-readable explanation

Architecture Note:
    This replaces the hardcoded if/elif chains in hook_service.py's
    handle_pre_tool() and handle_post_tool() with a data-driven loop.

Isomorphism:
    ADK before_tool_callback  ↔  Guardrail type="before_tool"
    ADK after_tool_callback   ↔  Guardrail type="after_tool"
    ConsensusEngine GO/BLOCK  ↔  short_circuit=True/False

References:
    - KI: google-adk-deep-research §8 (Callback & Guardrail System)
    - antigravity_perspective.md §15 (Native Muscle Exclusivity)
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Guardrail Handler Functions
# ---------------------------------------------------------------------------

def kg_guard_check(tool_name: str, tool_input: dict, context: dict) -> dict:
    """
    Knowledge Graph Guard — prevents writes to protected files.

    Maps to ADK: before_tool_callback with short-circuit.
    Maps to Angati: ConsensusEngine BLOCK verdict.
    """
    target_file = tool_input.get("TargetFile", "")
    if not target_file:
        return {"verdict": "ALLOW"}

    angati_exe = AGENTS_ROOT / "angati.exe"
    if not angati_exe.exists():
        angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"

    if not angati_exe.exists():
        return {"verdict": "ALLOW", "reason": "angati.exe not found — allowing by default"}

    try:
        res = subprocess.run(
            [str(angati_exe), "kg", "guard", "--file", str(target_file), "--action", "edit"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=15, check=False
        )
        if res.returncode == 2:
            return {
                "verdict": "BLOCK",
                "reason": f"KG Guard blocked write to {target_file} (Exit Code 2)",
                "remediation": r"Write sandbox patch to C:\Users\pesil\EAIS\_sandbox_patches\ instead."
            }
        elif res.returncode == 1:
            return {"verdict": "WARN", "reason": f"KG Guard caution for {target_file}"}
    except subprocess.TimeoutExpired:
        return {"verdict": "ALLOW", "reason": "KG Guard timed out — allowing by default"}
    except Exception as exc:
        return {"verdict": "ALLOW", "reason": f"KG Guard error: {exc}"}

    return {"verdict": "ALLOW"}


def circuit_breaker_check(tool_name: str, tool_input: dict, context: dict) -> dict:
    """
    Circuit Breaker — prevents repeated failure patterns.

    Maps to ADK: before_tool_callback with short-circuit.
    Maps to Angati: Amygdala scar-driven pattern detection.
    """
    try:
        sys.path.insert(0, str(AGENTS_ROOT / "nerves" / "core"))
        import core_scar_memory as scar_memory
    except ImportError:
        return {"verdict": "ALLOW", "reason": "scar_memory not available"}

    instruction = f"Executing tool {tool_name} with arguments: {json.dumps(tool_input)}"

    try:
        if scar_memory.circuit_breaker_check(instruction):
            return {
                "verdict": "BLOCK",
                "reason": "Circuit breaker tripped: This exact failure pattern has occurred >= 3 times in 1 hour."
            }
    except Exception as exc:
        return {"verdict": "ALLOW", "reason": f"Circuit breaker error: {exc}"}

    return {"verdict": "ALLOW"}


def scar_consult_advisory(tool_name: str, tool_input: dict, context: dict) -> dict:
    """
    Scar Consultation — advisory check against historical failures.

    Maps to ADK: before_tool_callback without short-circuit (advisory only).
    Maps to Angati: Hippocampus long-term memory consultation.
    """
    try:
        sys.path.insert(0, str(AGENTS_ROOT / "nerves" / "core"))
        import core_scar_memory as scar_memory
    except ImportError:
        return {"verdict": "ALLOW"}

    cmd_line = tool_input.get("CommandLine", "")
    if not cmd_line:
        return {"verdict": "ALLOW"}

    try:
        results = scar_memory.search_scars(cmd_line, top_k=3)
        if results:
            return {
                "verdict": "WARN",
                "reason": "Similar commands have caused issues before",
                "scars": results[:3]
            }
    except Exception:
        pass

    return {"verdict": "ALLOW"}


def reflex_advisory(tool_name: str, tool_input: dict, context: dict) -> dict:
    """
    Reflex System — keyword-triggered skill advisory.

    Maps to ADK: contextual awareness callbacks.
    Maps to Angati: ReflexSvc (keyword → SKILL.md).
    """
    try:
        sys.path.insert(0, str(AGENTS_ROOT / "nerves" / "core"))
        import core_reflex as reflex
    except ImportError:
        return {"verdict": "ALLOW"}

    instruction = f"Executing tool {tool_name} with arguments: {json.dumps(tool_input)}"
    try:
        output = reflex.run_reflex(instruction)
        if output:
            return {"verdict": "ALLOW", "advisory": output}
    except Exception:
        pass

    return {"verdict": "ALLOW"}


def gitnexus_post_commit(tool_name: str, tool_input: dict, context: dict) -> dict:
    """
    GitNexus Post-Commit — updates knowledge graph after git operations.

    Maps to ADK: after_tool_callback.
    Maps to Angati: Post-commit KG ingestion.
    """
    cmd_line = tool_input.get("CommandLine", "").lower()
    if "git commit" not in cmd_line and "git merge" not in cmd_line:
        return {"verdict": "SKIP"}

    try:
        subprocess.run(
            ["npx", "gitnexus", "analyze", "--embeddings"],
            cwd=str(AGENTS_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=120, shell=True, check=False
        )
    except Exception as exc:
        return {"verdict": "ALLOW", "reason": f"gitnexus error: {exc}"}

    return {"verdict": "ALLOW", "action": "gitnexus_analyze_completed"}


# ---------------------------------------------------------------------------
# Guardrail Registry (The Data-Driven Backbone)
# ---------------------------------------------------------------------------

FILE_WRITING_TOOLS = frozenset({
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
})

GUARDRAILS = {
    "kg_guard": {
        "type": "before_tool",
        "tools": FILE_WRITING_TOOLS,
        "handler": kg_guard_check,
        "short_circuit": True,
        "description": "Knowledge Graph Guard — blocks writes to protected files"
    },
    "circuit_breaker": {
        "type": "before_tool",
        "tools": {"*"},  # Applies to all tools
        "handler": circuit_breaker_check,
        "short_circuit": True,
        "description": "Circuit Breaker — prevents repeated failure patterns"
    },
    "scar_consult": {
        "type": "before_tool",
        "tools": {"run_command"},
        "handler": scar_consult_advisory,
        "short_circuit": False,
        "description": "Scar Consultation — advisory check against historical failures"
    },
    "reflex": {
        "type": "before_tool",
        "tools": {"*"},
        "handler": reflex_advisory,
        "short_circuit": False,
        "description": "Reflex System — keyword-triggered skill advisory"
    },
    "gitnexus_post_commit": {
        "type": "after_tool",
        "tools": {"run_command"},
        "handler": gitnexus_post_commit,
        "short_circuit": False,
        "description": "GitNexus Post-Commit — KG update after git operations"
    },
}


# ---------------------------------------------------------------------------
# Guardrail Evaluation Engine
# ---------------------------------------------------------------------------

def evaluate_guardrails(
    lifecycle_type: str,
    tool_name: str,
    tool_input: dict,
    context: dict = None
) -> dict:
    """
    Evaluate all guardrails matching the given lifecycle type and tool.

    Args:
        lifecycle_type: "before_tool" or "after_tool"
        tool_name: Name of the tool being invoked
        tool_input: Tool arguments
        context: Additional context (session state, etc.)

    Returns:
        dict with keys:
            - decision: "allow" | "deny"
            - verdicts: List of individual guardrail results
            - message: Denial reason if blocked
    """
    if context is None:
        context = {}

    verdicts = []
    blocked = False
    block_message = ""

    for name, guardrail in GUARDRAILS.items():
        if guardrail["type"] != lifecycle_type:
            continue

        # Check if this guardrail applies to the current tool
        tools = guardrail["tools"]
        if "*" not in tools and tool_name not in tools:
            continue

        # Execute the guardrail handler
        try:
            result = guardrail["handler"](tool_name, tool_input, context)
            result["guardrail"] = name
            verdicts.append(result)

            # Short-circuit on BLOCK
            if guardrail["short_circuit"] and result.get("verdict") == "BLOCK":
                blocked = True
                block_message = result.get("reason", f"Blocked by guardrail: {name}")
                break

        except Exception as exc:
            verdicts.append({
                "guardrail": name,
                "verdict": "ERROR",
                "reason": str(exc)
            })

    return {
        "decision": "deny" if blocked else "allow",
        "message": block_message if blocked else "",
        "verdicts": verdicts
    }
