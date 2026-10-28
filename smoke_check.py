"""Check data integrity, then execute the project in a non-interactive backend."""
import os,runpy
from pathlib import Path
os.environ.setdefault('MPLBACKEND','Agg')
from validate_data import validate
print(validate())
runpy.run_path(str(Path(__file__).resolve().parent/'main.py'),run_name='__main__')
