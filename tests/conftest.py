"""Test configuration — ensure project root is on sys.path for imports."""
import sys
import os

# Add project root to sys.path so `from core.xxx import ...` works
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
