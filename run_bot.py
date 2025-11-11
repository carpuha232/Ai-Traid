#!/usr/bin/env python3
"""Simple launcher to avoid path issues."""
import sys
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# Add to path
sys.path.insert(0, script_dir)

# Import and run
if __name__ == "__main__":
    from main import main
    main()

