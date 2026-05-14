"""
DB Tunnels — macOS GUI for managing autossh SSH port-forwarding tunnels.

Public API:
    main()              launch the Qt application
    Tunnel              tunnel configuration dataclass
    ForwardRule         single port-forward rule dataclass
    TunnelManager       manages autossh process lifecycle
    TunnelStatus        enum: STOPPED / STARTING / CONNECTED / ERROR
"""

__version__ = "0.1.0"
__author__ = "Jahidul Islam Munna"
__license__ = "MIT"

from .tunnel_model import Tunnel, ForwardRule
from .tunnel_manager import TunnelManager, TunnelStatus
from .main import main

__all__ = [
    "main",
    "Tunnel",
    "ForwardRule",
    "TunnelManager",
    "TunnelStatus",
    "__version__",
]
