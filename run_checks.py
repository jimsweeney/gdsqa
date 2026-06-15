r"""run_checks - the gdsqa runner.

    python run_checks.py suite

Runs the pytest suite and writes _checks/result.json + last.log before printing (dropped-launch recovery)."""
import sys, os, json, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CHK = os.path.join(HERE, "_checks")
os.makedirs(CHK, exist_ok=True)
PY = sys.executable


def _write(result, log):
    result["ts"] = time.time()
    with open(os.path.join(CHK, "last.log"), "w", encoding="utf-8") as f:
        f.write(log)
    with open(os.path.join(CHK, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def suite():
    t0 = time.time()
    p = subprocess.run([PY, "-m", "pytest", "-q", os.path.join(HERE, "tests")],
                       cwd=HERE, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    last = out.strip().splitlines()[-1] if out.strip() else ""
    status = "PASS" if p.returncode == 0 else "FAIL"
    _write({"mode": "suite", "status": status, "summary": last, "dur": round(time.time() - t0, 1)}, out)
    print(out.rstrip())
    print(f"CHECKS_DONE status={status} mode=suite dur={time.time()-t0:.1f}s")
    return 0 if p.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(suite())
