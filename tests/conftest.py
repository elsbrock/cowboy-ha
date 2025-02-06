"""Test configuration for cowboy integration."""
import os
import sys
from pathlib import Path

# Add the root directory to Python path
ROOT_DIR = Path(__file__).parents[1].resolve()
sys.path.insert(0, str(ROOT_DIR))
