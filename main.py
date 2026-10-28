"""Run this standalone Python teaching project."""
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parent
runpy.run_path(str(ROOT/'src/analysis.py'),run_name='__main__')
