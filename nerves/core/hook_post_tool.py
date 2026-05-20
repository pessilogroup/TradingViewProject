#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    # 1. Read stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception as e:
        print(f"Error parsing stdin: {e}", file=sys.stderr)
        print(json.dumps({}))
        return

    # Extract tool information
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    
    print(f"[PostToolUse] Processing tool: {tool_name}", file=sys.stderr)

    # 2. Check for Git commit / merge commands
    is_git_commit_or_merge = False
    if tool_name == "run_command":
        cmd_line = tool_input.get("CommandLine", "").lower()
        if "git commit" in cmd_line or "git merge" in cmd_line:
            is_git_commit_or_merge = True

    if is_git_commit_or_merge:
        print("[PostToolUse] Git change detected. Running EKG & GitNexus automatic index refresh...", file=sys.stderr)
        
        # Run npx gitnexus analyze --embeddings
        try:
            print("[PostToolUse] Running: npx gitnexus analyze --embeddings", file=sys.stderr)
            res = subprocess.run(
                ["npx", "gitnexus", "analyze", "--embeddings"],
                cwd=str(AGENTS_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=120,
                shell=True,
                check=False
            )
            if res.returncode == 0:
                print("[OK] [PostToolUse] GitNexus index refreshed successfully.", file=sys.stderr)
            else:
                print(f"[WARN] [PostToolUse] GitNexus index refresh failed with exit code {res.returncode}", file=sys.stderr)
                if res.stderr:
                    print(res.stderr, file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("[WARN] [PostToolUse] GitNexus analyze timed out after 120s", file=sys.stderr)
        except Exception as exc:
            print(f"Failed to execute gitnexus analyze: {exc}", file=sys.stderr)

        # Run angati memory stats
        angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
        if angati_exe.exists():
            try:
                print("[PostToolUse] Running: angati memory stats", file=sys.stderr)
                res = subprocess.run(
                    [str(angati_exe), "memory", "stats"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=15,
                    check=False
                )
                if res.returncode == 0:
                    print(f"[OK] [PostToolUse] EKG statistics: {res.stdout.strip()}", file=sys.stderr)
                else:
                    print(f"[WARN] [PostToolUse] EKG memory stats failed: {res.stderr.strip()}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("[WARN] [PostToolUse] EKG memory stats timed out", file=sys.stderr)
            except Exception as exc:
                print(f"Failed to run angati memory stats: {exc}", file=sys.stderr)
    
    # Silence is golden, print empty JSON
    print(json.dumps({}))

if __name__ == "__main__":
    main()
