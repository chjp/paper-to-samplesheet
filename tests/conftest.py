from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "paper-to-samplesheet" / "scripts"
sys.path.insert(0, str(SCRIPTS))
