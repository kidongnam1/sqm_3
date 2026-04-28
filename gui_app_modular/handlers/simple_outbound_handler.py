"""
SQM Inventory - Simple Outbound Handler
=======================================

v2.9.91 - Extracted from gui_app.py

Simple outbound dialog for quick quantity-based outbound
"""

import logging

logger = logging.getLogger(__name__)


class SimpleOutboundHandlerMixin:
    """
    Simple outbound handler mixin
    
    Mixed into SQMInventoryApp class
    """
