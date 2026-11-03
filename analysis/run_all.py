"""Run every analysis script in order; each writes its report to analysis/output/<name>.txt."""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for script in sorted(HERE.glob("0*_*.py")):
    t0 = time.time()
    print(f"=== {script.name}", flush=True)
    res = subprocess.run([sys.executable, script.name], cwd=HERE, stdout=subprocess.DEVNULL)
    if res.returncode != 0:
        sys.exit(f"{script.name} failed (rc={res.returncode})")
    print(f"    done in {time.time() - t0:.0f}s -> output/{script.stem}.txt", flush=True)
