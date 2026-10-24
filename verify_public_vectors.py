"""Re-run the instructor's public t-paired vectors against the CLI."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "gpower_clone.py"
VECTORS = ROOT / "public_vectors.jsonl"

def run_case(case: dict) -> tuple[dict, list[str]]:
    argv = [sys.executable, str(CLI)]
    for field, value in case["input"].items():
        argv.extend(("--" + field, str(value)))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(argv, text=True, capture_output=True, env=env, check=False)
    issues = []
    if proc.returncode != 0:
        issues.append(f"exit code {proc.returncode}")
    if len(proc.stdout.splitlines()) != 1:
        issues.append("stdout must contain exactly one JSON line")
    try:
        actual = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}, issues + ["stdout is not valid JSON"]
    for field, expected in case["expected"].items():
        value = actual.get(field)
        if isinstance(expected, int) and not isinstance(expected, bool):
            if value != expected or isinstance(value, bool):
                issues.append(f"{field}: expected integer {expected}, got {value!r}")
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            issues.append(f"{field}: expected number {expected}, got {value!r}")
        elif abs(value - expected) > max(1e-6, abs(expected) * 1e-6):
            issues.append(f"{field}: expected {expected}, got {value}")
    return actual, issues

def main() -> int:
    cases = [json.loads(line) for line in VECTORS.read_text(encoding="utf-8").splitlines() if line.strip()]
    failed = 0
    apriori_total = apriori_exact = 0
    for case in cases:
        actual, issues = run_case(case)
        if case["input"].get("mode") == "a-priori":
            apriori_total += 1
            if not issues and actual.get("n_total") == case["expected"].get("n_total"):
                apriori_exact += 1
        print(f"{'PASS' if not issues else 'FAIL'} {case['id']}")
        for issue in issues:
            print(f"  {issue}")
        failed += bool(issues)
    print(f"Public vectors: {len(cases) - failed}/{len(cases)} passed")
    print(f"Public a-priori N: {apriori_exact}/{apriori_total} exact")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())