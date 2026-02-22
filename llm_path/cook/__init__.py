"""Cook module for preprocessing traces for visualization.

Public API:
- cook_traces(): Main entry point for cooking trace files
- TraceCooker: Class for processing traces in memory
- Data classes: CookedMessage, CookedTool, CookedRequest, CookedOutput, ApiFormat
"""

from .cooker import TraceCooker, cook_traces
from .models import ApiFormat, CookedMessage, CookedOutput, CookedRequest, CookedTool

__all__ = [
    "cook_traces",
    "TraceCooker",
    "CookedMessage",
    "CookedTool",
    "CookedRequest",
    "CookedOutput",
    "ApiFormat",
]
