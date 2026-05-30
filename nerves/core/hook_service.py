#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingTCPServer
import threading

AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AGENTS_ROOT))
sys.path.insert(0, str(AGENTS_ROOT / "nerves" / "core"))

# Eagerly load core libraries
try:
    import core_scar_memory as scar_memory
    import core_reflex as reflex
    if scar_memory:
        print("[SRA Server] Eagerly warming up FastEmbed model in RAM...", file=sys.stderr)
        scar_memory._get_embedding_model()
        print("[SRA Server] FastEmbed model loaded successfully.", file=sys.stderr)
except Exception as e:
    print(f"[SRA Server] Eager loading warning: {e}", file=sys.stderr)
    scar_memory = None
    reflex = None

# ── Scar Consult B+C Hybrid ──────────────────────────────────
# B: In-process fastembed (already warm) + direct Qdrant search
# C: TTL cache by command prefix (5 min)
import time as _time

_scar_cache = {}          # {cmd_prefix: (timestamp, advisory_str | None)}
_SCAR_CACHE_TTL = 300     # 5 minutes
_SCAR_SCORE_THRESHOLD = 0.82
_qdrant_client_cached = None


def _cmd_prefix(cmd_line: str) -> str:
    """Extract first 2 tokens of command for cache key grouping."""
    tokens = cmd_line.strip().split()[:2]
    return " ".join(tokens).lower()


def _scar_consult_fast(cmd_line: str) -> str:
    """
    In-process scar consult with TTL cache.

    Path:
        1. Check cache (0ms) → hit? return cached advisory
        2. Miss → embed in-process (~50ms) → Qdrant search (~50ms)
        3. Store result in cache (hit or miss) with TTL

    Returns advisory string or "" if no relevant scars.
    """
    global _qdrant_client_cached

    if not scar_memory:
        return ""

    # ── C: Cache check ──
    prefix = _cmd_prefix(cmd_line)
    now = _time.time()
    if prefix in _scar_cache:
        ts, cached_advisory = _scar_cache[prefix]
        if now - ts < _SCAR_CACHE_TTL:
            return cached_advisory or ""

    # ── B: In-process embed + search ──
    try:
        # Use the already-warm fastembed model (loaded at boot)
        vector = scar_memory._embed(cmd_line)

        # Get or create Qdrant client (reuse connection)
        if _qdrant_client_cached is None:
            _qdrant_client_cached = scar_memory._get_client()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        results = _qdrant_client_cached.search(
            collection_name=scar_memory.COLLECTION_NAME,
            query_vector=vector,
            limit=3,
            score_threshold=_SCAR_SCORE_THRESHOLD,
        )

        if results:
            rules = []
            for r in results:
                payload = r.payload or {}
                rule = payload.get("prevention_rule", "")
                if rule:
                    rules.append(rule)

            if rules:
                advisory = " | ".join(rules[:2])
                _scar_cache[prefix] = (now, advisory)
                return advisory

        # No match — cache the miss too (avoid re-querying)
        _scar_cache[prefix] = (now, None)
        return ""

    except Exception as exc:
        print(f"[SRA Server] Scar consult fast error: {exc}", file=sys.stderr)
        _scar_cache[prefix] = (now, None)  # Cache errors as miss
        return ""

class ThreadingHTTPServer(ThreadingTCPServer, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Silence connection reset exceptions when clients exit abruptly
        import traceback
        tb = traceback.format_exc()
        if "ConnectionResetError" in tb or "ConnectionAbortedError" in tb or "BrokenPipeError" in tb or "WinError 10054" in tb:
            pass
        else:
            super().handle_error(request, client_address)

class SRAHookHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            # Client closed connection or exited, which is normal for CLI hook invocations
            pass

    def log_message(self, format, *args):
        # Silence default request logs to avoid cluttering output
        pass

    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "healthy"}).encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            input_data = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            body = json.dumps({"error": f"Invalid JSON: {e}"}).encode('utf-8')
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/pre-tool":
            response_data = self.handle_pre_tool(input_data)
        elif self.path == "/post-tool":
            response_data = self.handle_post_tool(input_data)
        elif self.path == "/on-error":
            response_data = self.handle_on_error(input_data)
        elif self.path == "/shutdown":
            body = json.dumps({"status": "shutdown"}).encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=self.server.shutdown).start()
            return
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(response_data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(body)

    def handle_pre_tool(self, input_data):
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        
        print(f"[SRA Server] PreToolUse intercepting: {tool_name}", file=sys.stderr)
        
        # 1. Evaluate KG Guard
        file_writing_tools = {"write_to_file", "replace_file_content", "multi_replace_file_content"}
        if tool_name in file_writing_tools and tool_input:
            target_file = tool_input.get("TargetFile")
            if target_file:
                angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
                if not angati_exe.exists():
                    angati_exe = AGENTS_ROOT / "angati.exe"
                
                if angati_exe.exists():
                    try:
                        res = subprocess.run(
                            [str(angati_exe), "kg", "guard", "--file", str(target_file), "--action", "edit"],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="ignore",
                            timeout=15,
                            check=False
                        )
                        if res.returncode == 2:
                            print(f"[SRA Server] Blocked by KG Guard for file {target_file}", file=sys.stderr)
                            return {
                                "decision": "deny",
                                "message": "Blocked by KG Guard (Exit Code 2). Write sandbox patch to C:\\Users\\pesil\\EAIS\\_sandbox_patches\\ instead."
                            }
                        elif res.returncode == 1:
                            print(f"[SRA Server] Caution by KG Guard for file {target_file}", file=sys.stderr)
                    except subprocess.TimeoutExpired:
                        print("[SRA Server] KG Guard timed out — allowing by default", file=sys.stderr)
                    except Exception as exc:
                        print(f"[SRA Server] Failed to run KG Guard: {exc}", file=sys.stderr)
        
        # 2. Circuit Breaker
        if tool_input:
            instruction = f"Executing tool {tool_name} with arguments: {json.dumps(tool_input)}"
            if scar_memory:
                try:
                    if scar_memory.circuit_breaker_check(instruction):
                        print("[SRA Server] Circuit breaker tripped!", file=sys.stderr)
                        return {
                            "decision": "deny",
                            "message": "Circuit breaker broken: This exact failure pattern has occurred >= 3 times in 1 hour."
                        }
                except Exception as exc:
                    print(f"[SRA Server] Circuit breaker error: {exc}", file=sys.stderr)
            
            # 2.5 Scar Memory Consult — in-process B+C hybrid
            #     B: fastembed (already warm) + direct Qdrant → ~100ms
            #     C: TTL cache by command prefix → 0ms on cache hit
            if scar_memory and tool_name == "run_command":
                try:
                    cmd_line = tool_input.get("CommandLine", "")
                    if cmd_line:
                        advisory = _scar_consult_fast(cmd_line)
                        if advisory:
                            print(f"[SRA Server] Scar advisory for run_command: {advisory}", file=sys.stderr)
                            return {
                                "decision": "allow",
                                "message": f"[SCAR ADVISORY] Similar command failed before: {advisory}"
                            }
                except Exception as exc:
                    print(f"[SRA Server] Scar consult error: {exc}", file=sys.stderr)

            # 3. Reflex
            if reflex:
                try:
                    reflex_output = reflex.run_reflex(instruction)
                    if reflex_output:
                        print(f"[SRA Server] Reflex advisory: {reflex_output}", file=sys.stderr)
                except Exception as e:
                    print(f"[SRA Server] Reflex error: {e}", file=sys.stderr)
                    
        return {"decision": "allow"}

    def handle_post_tool(self, input_data):
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        
        print(f"[SRA Server] PostToolUse processing: {tool_name}", file=sys.stderr)
        
        is_git_commit_or_merge = False
        if tool_name == "run_command":
            cmd_line = tool_input.get("CommandLine", "").lower()
            if "git commit" in cmd_line or "git merge" in cmd_line:
                is_git_commit_or_merge = True

        if is_git_commit_or_merge:
            try:
                subprocess.run(
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
            except subprocess.TimeoutExpired:
                print("[SRA Server] gitnexus analyze timed out", file=sys.stderr)
            except Exception as exc:
                print(f"[SRA Server] gitnexus analyze error: {exc}", file=sys.stderr)

            angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
            if not angati_exe.exists():
                angati_exe = AGENTS_ROOT / "angati.exe"
            if angati_exe.exists():
                try:
                    subprocess.run(
                        [str(angati_exe), "memory", "stats"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        timeout=15,
                        check=False
                    )
                except subprocess.TimeoutExpired:
                    print("[SRA Server] memory stats timed out", file=sys.stderr)
                except Exception as exc:
                    print(f"[SRA Server] memory stats error: {exc}", file=sys.stderr)
        return {"status": "ok"}

    def handle_on_error(self, input_data):
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_output = input_data.get("tool_output", "")
        error_msg = input_data.get("error", "") or str(tool_output)[:500]
        
        print(f"[SRA Server] OnError processing: {tool_name}", file=sys.stderr)
        
        # ── Record to Scar Memory ─────────────────────────────────
        # Close the feedback loop: /on-error → scar → /pre-tool consult
        if scar_memory and tool_name == "run_command":
            cmd_line = tool_input.get("CommandLine", "unknown command")
            try:
                scar_memory.record_scar(
                    failed_action=cmd_line[:300],
                    error_signature=error_msg[:300],
                    recovery_action="",
                    prevention_rule=f"Command failed: {cmd_line[:100]}. Error: {error_msg[:150]}",
                    context="hook_on_error/run_command",
                )
                print(f"[SRA Server] Scar recorded for: {cmd_line[:80]}", file=sys.stderr)
                # Invalidate cache for this command prefix so next consult picks it up
                prefix = _cmd_prefix(cmd_line)
                _scar_cache.pop(prefix, None)
            except Exception as exc:
                print(f"[SRA Server] Scar record error: {exc}", file=sys.stderr)
        
        # ── Incident Responder ────────────────────────────────────
        incident_responder = AGENTS_ROOT / "nerves" / "workers" / "incident_responder.py"
        if incident_responder.exists():
            try:
                subprocess.run(
                    ["python", str(incident_responder), "check"],
                    cwd=str(AGENTS_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=30,
                    check=False
                )
            except subprocess.TimeoutExpired:
                print("[SRA Server] incident responder timed out", file=sys.stderr)
            except Exception as exc:
                print(f"[SRA Server] incident responder error: {exc}", file=sys.stderr)
        return {"status": "ok"}

def check_angati_version_async():
    """Runs asynchronously in a daemon thread to check version compatibility of local and brain angati.exe."""
    def run_check():
        import os
        import hashlib
        
        # 1. Resolve local path
        local_path = None
        env_local = os.environ.get("ANGATI_LOCAL_EXE_PATH")
        if env_local:
            local_path = Path(env_local)
        else:
            cand1 = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
            cand2 = AGENTS_ROOT / "angati.exe"
            if cand1.exists():
                local_path = cand1
            else:
                local_path = cand2

        # 2. Resolve brain path
        brain_path = None
        env_brain = os.environ.get("ANGATI_BRAIN_EXE_PATH")
        if env_brain:
            brain_path = Path(env_brain)
        else:
            home = Path.home()
            candidates = [
                home / "EAIS" / "test_scaffold" / "angati.exe",
                home / "EAIS" / "spine" / "angati" / "angati.exe",
                home / ".gemini" / "antigravity" / "tools" / "angati" / "angati.exe",
            ]
            for cand in candidates:
                if cand.exists():
                    brain_path = cand
                    break
            if not brain_path:
                brain_path = candidates[-1]

        # 3. Check exists
        if not local_path.exists() or not brain_path.exists():
            return

        # 4. Compute hashes chunked
        def get_sha256(p):
            sha = hashlib.sha256()
            try:
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        sha.update(chunk)
                return sha.hexdigest()
            except Exception:
                return None

        local_hash = get_sha256(local_path)
        brain_hash = get_sha256(brain_path)

        if not local_hash or not brain_hash:
            return

        # 5. Warn on mismatch
        if local_hash != brain_hash:
            print("[SRA Server] WARNING: Local angati.exe version mismatch detected! Please manually restart the hook server to synchronize the binary.", file=sys.stderr)

    t = threading.Thread(target=run_check, daemon=True)
    t.start()
    return t

def main():
    check_angati_version_async()
    port = 9105
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, SRAHookHandler)
    print(f"[SRA Server] Running SRA Hybrid Hook Server on port {port}...", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("[SRA Server] Stopping server...", file=sys.stderr)

if __name__ == "__main__":
    main()
