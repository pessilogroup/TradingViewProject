"""
claude_cli — Claude CLI integration package.

Public API:
    CliInfrastructure   — async subprocess wrapper (infrastructure layer)
    ClaudeService       — context mgmt + fallback orchestration (service layer)
    AnalysisRequest     — input dataclass for ClaudeService.analyze()
    AnalysisResponse    — output dataclass from ClaudeService.analyze()

Entry points (registered from main.py / telegram_bot.py):
    telegram_commands.register_commands(application)
    event_handler.register_handler()
"""
from .infrastructure import CliInfrastructure, CliResult
from .service import ClaudeService, AnalysisRequest, AnalysisResponse

__all__ = [
    "CliInfrastructure",
    "CliResult",
    "ClaudeService",
    "AnalysisRequest",
    "AnalysisResponse",
]
