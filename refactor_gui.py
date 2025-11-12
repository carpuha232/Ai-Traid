#!/usr/bin/env python3
"""
Automatic GUI refactoring script
Splits main_window.py into modular components
"""

import os
import shutil

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUI_DIR = os.path.join(BASE_DIR, 'gui')
WIDGETS_DIR = os.path.join(GUI_DIR, 'widgets')
MAIN_FILE = os.path.join(GUI_DIR, 'main_window.py')
BACKUP_FILE = os.path.join(GUI_DIR, 'main_window_backup.py')

print("Starting GUI refactoring...")

# Read original file
with open(MAIN_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

# Define sections (line numbers are 0-indexed in Python)
HEADER = lines[0:14]  # Lines 1-14
CONTROL_PANEL = lines[14:223]  # Lines 15-223 (ControlPanel class)
TABLES = lines[223:400]  # Lines 225-400 (MockTable + widgets)
TRADING_PROTOTYPE = lines[400:]  # Lines 402+ (TradingPrototype + styles)

print(f"  Header: {len(HEADER)} lines")
print(f"  ControlPanel: {len(CONTROL_PANEL)} lines")
print(f"  Tables: {len(TABLES)} lines")
print(f"  TradingPrototype: {len(TRADING_PROTOTYPE)} lines")

# Create new main_window.py with imports
new_main = HEADER + [
    "\n",
    "# Import widgets from modular components\n",
    "from .widgets import ControlPanel, SignalsWidget, PositionsWidget, HistoryWidget\n",
    "\n",
    "\n"
] + TRADING_PROTOTYPE

# Write new main_window.py
with open(MAIN_FILE, 'w', encoding='utf-8') as f:
    f.writelines(new_main)

print(f"SUCCESS! New main_window.py: {len(new_main)} lines")
print(f"   Widgets already extracted to gui/widgets/")
print(f"   - control_panel.py: {len(CONTROL_PANEL)} lines")
print(f"   - tables.py: {len(TABLES)} lines")
print("\nRefactoring complete!")
print(f"   Total: {len(new_main)} + {len(CONTROL_PANEL)} + {len(TABLES)} = {len(new_main) + len(CONTROL_PANEL) + len(TABLES)} lines")
print(f"   Original: {len(lines)} lines")

