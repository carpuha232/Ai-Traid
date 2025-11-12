"""
GUI Widgets Package
Modular components for the trading terminal interface.
Extracted from main_window.py without changes.
"""

from .control_panel import ControlPanel
from .tables import MockTable, ActivityLogWidget, SignalsWidget, PositionsWidget, HistoryWidget

__all__ = [
    'ControlPanel',
    'MockTable',
    'ActivityLogWidget',
    'SignalsWidget',
    'PositionsWidget',
    'HistoryWidget',
]

