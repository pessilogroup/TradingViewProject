"""
Trade execution lives in the server package, not here.

An older copy of ``engine.py`` used ``core.eventbus`` (invalid; the real module is
``core.event_bus``) and ``trading.exchanges`` (this package has no such submodule),
which caused ``ModuleNotFoundError`` on ``import trading.engine``.

Use the supported entrypoint::

    # From repo root, with ``server`` on ``sys.path`` (same as running the app):
    import engine.trade_engine  # noqa: F401 — registers TradeApproved handler

See ``server/engine/trade_engine.py`` for the v6.0 TradeEngine implementation.
"""

__all__: list[str] = []
