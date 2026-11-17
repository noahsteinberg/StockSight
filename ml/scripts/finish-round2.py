"""Finish the bounded round unattended, then write a readable comparison.

Run from ml/ with the pinned interpreter. If a round is already running, wait
without reading its output or consuming an AI session. Never remove its lock.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))

from stocksight_data import research_round2 as r  # noqa: E402


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise OSError(ctypes.get_last_error(), "Cannot inspect the owning process")
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def write_summary() -> None:
    path = r.TRACKED / "research_round2.json"
    result = json.loads(path.read_text())
    if not result["all_five_complete"]:
        raise RuntimeError("Incomplete round; do not publish a final comparison.")
    results = result["results"]
    rows = []
    for name, entry in results.items():
        s = entry["summary"]
        delta = entry["balanced_accuracy_minus_reversal_5d"]
        low, high = delta["ci95"]
        rows.append(f"| `{name}` | {s['mean_bal_acc']:.6f} | {s['mean_accuracy']:.6f} | "
                    f"{s['mean_brier']:.6f} | {s['folds_passing_gate_proxies']}/5 | "
                    f"{delta['point']:+.6f} [{low:+.6f}, {high:+.6f}] |")
    baseline = results[r.BASE_NAME]
    max_diff = max(abs(v) for f in baseline["folds"] for v in f["reproduction"]["metric_differences"].values())
    eligible = result["new_eligible"]
    selected = result["finalists_train_only"]
    if not eligible:
        recommendation = "None of the four new configurations meets the existing training-fold eligibility rules. Stop this round; retain the prior approach as the comparison reference. This does not overturn the earlier finding that no model passed validation."
    elif selected == [r.BASE_NAME]:
        recommendation = "Some new configurations meet training-fold eligibility, but the repeated baseline still ranks first under the existing rule. Retain that approach; do not spend another validation access on this round automatically."
    else:
        recommendation = (f"The existing training-fold selection rule provisionally selects `{selected[0]}`. "
                          "It is a research candidate, not a promoted or deployable model. Review paired differences, coverage, and uncertainty before deciding whether a separately justified validation access is worthwhile.")
    text = f"""## Results

Completed {result['created_at']}. The baseline and all four new configurations completed six folds. Selection summaries use folds 1-5, matching the original rule. **No validation or final-test model evaluation was run.**

### Baseline and data audit

- The cleaned dataset SHA-256 matches the original frozen snapshot.
- All six baseline folds reproduced archived accuracy, balanced accuracy, and Brier within 1e-6. Maximum absolute difference: {max_diff:.10g}.
- Five independent stock/date traces checked labels, calendar targets, bad bars, per-stock historical returns, and the late-2018 boundary.
- Coverage ranges from {min(f['coverage'] for e in results.values() for f in e['folds']):.4%} to {max(f['coverage'] for e in results.values() for f in e['folds']):.4%} of each original evaluation fold. All configurations use identical common observations.
- Existing gates, original experiment reports, and validation-access history remain protected by their pre-run hashes.

### Comparison

The first three metrics are unweighted means over the five common folds. The final column pools their observations for a paired date-block bootstrap difference against reversal. These two summaries have different weighting and should not be subtracted from one another.

| Configuration | Mean balanced accuracy | Mean accuracy | Mean Brier (lower better) | Folds passing proxies | Pooled gain over reversal [95% CI] |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

New configurations eligible under existing rules: {', '.join(f'`{n}`' for n in eligible) or 'none'}.

### Recommendation

{recommendation}

Four configurations are new, in addition to the previous 34. The repeated baseline is a reproduction attempt, not another novel configuration. Confidence intervals are exploratory and unadjusted for choosing among configurations. Passing training proxies does not mean passing the frozen validation gates. The previous validation results have already been seen, so they cannot be described as a fresh holdout.

The machine-readable report contains all six folds, simple-baseline scores, coverage, runtime, and paired balanced-accuracy/Brier differences against both reversal and the reproduced model. Per-fold predictions remain in ignored local storage. Attempt logs retain failures and interruptions.

### Application handoff

The prediction remains a five-session relative beat/lag research task. No inference artifact or API endpoint was added. Continue frontend/API work against the agreed fields and an explicit prediction-unavailable state. A serving decision needs separate review.
"""
    document = ML / "docs" / "RESEARCH_ROUND2.md"
    original = document.read_text(encoding="utf-8")
    document.write_text(original.split("## Results\n", 1)[0] + text, encoding="utf-8")
    ledger = ML / "docs" / "ledger.md"
    existing = ledger.read_text(encoding="utf-8")
    heading = "## Research round 2: bounded follow-up"
    if heading not in existing:
        ledger.write_text(existing + f"\n\n{heading}\n\nFour fixed HGB follow-ups and baseline reproduction are reported in [RESEARCH_ROUND2.md](RESEARCH_ROUND2.md). Previous results above are preserved. {recommendation} No validation or test access was added.\n", encoding="utf-8")
    print(f"Readable report: {document}", flush=True)


def main() -> None:
    os.chdir(ML)
    lock = r.ROOT / "run.lock"
    while lock.exists():
        pid = int(lock.read_text())
        if not pid_alive(pid):
            raise RuntimeError(f"Stale lock owned by PID {pid}; inspect it before manually removing it.")
        time.sleep(30)
    r.require_reproduced_baseline()
    subprocess.run([sys.executable, "-u", "-m", "stocksight_data.research_round2", "run", "--threads", "4"], check=True)
    write_summary()


if __name__ == "__main__":
    main()
