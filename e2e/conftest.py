"""Deixa o pytest importar o roteiro (e2e_tres_apis.py) desta pasta."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
