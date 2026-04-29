# -*- coding: utf-8 -*-
"""
SQM Inventory - Database Mixin
==============================

v2.9.91 - Extracted from gui_app.py

Database operations, connection management, and diagnostics
"""

import os
import logging
import sqlite3
from ..utils.ui_constants import CustomMessageBox
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseMixin:
    """
    Database operations mixin
    
    Mixed into SQMInventoryApp class
    """
    
    def _init_database(self, db_path: Optional[str] = None) -> None:
        """Initialize database connection"""

        
        if db_path:
            self.db_path = db_path
        else:
            # Default path
            self.db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "db", "sqm_inventory.db"
            )
        
        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        try:
            from engine_modules.inventory import InventoryEngine
            self.engine = InventoryEngine(db_path=self.db_path)
            self._log(f"OK Database connected: {self.db_path}")
            
        except ImportError:
            try:
                from engine import Engine
                self.engine = Engine(db_path=self.db_path)
                self._log("OK Database connected (legacy engine)")
            except ImportError:
                CustomMessageBox.showerror(self.root, "Error", "Database engine not found")
                self.engine = None
        except (sqlite3.Error, OSError) as e:
            CustomMessageBox.showerror(self.root, "Database Error", f"Failed to connect:\n{e}")
            self.engine = None
    


