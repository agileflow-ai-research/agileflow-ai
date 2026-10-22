"""
N4.4 Context Decision (CD1): consolidates persisted TR1, TB1, and FB1 into one decision.

  constants.py  decision vocabulary and versions
  engine.py     pure consolidation (no I/O, no model, no re-evaluation)
  service.py    gate checks, persisted-input loading, and cache reuse
  storage.py    atomic persistence of context-decision.json
  schemas.py    result contracts
"""

from .schemas import Agent4ContextDecisionResult, ContextDecisionStatus
from .service import Agent4ContextDecisionGateError, Agent4ContextDecisionService

__all__ = [
    "Agent4ContextDecisionGateError",
    "Agent4ContextDecisionResult",
    "Agent4ContextDecisionService",
    "ContextDecisionStatus",
]
