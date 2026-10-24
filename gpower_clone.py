"""Thin command-line wrapper for the paired-power calculation engine."""
from __future__ import annotations

import json
import math
import platform
import re
import sys
from typing import NoReturn

import paired_power


class CliError(Exception):
    def __init__(self, message: str, code: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.field = field


FLAGS = {
    "test": "test",
    "mode": "mode",
    "tails": "tails",
    "dz": "dz",
    "alpha": "alpha",
    "power": "power",
    "n_total": "n_total",
    "beta_alpha_ratio": "beta_alpha_ratio",
}
MODES = {
    "a-priori": ("tails", "dz", "alpha", "power"),
    "post-hoc": ("tails", "dz", "alpha", "n_total"),
    "compromise": ("tails", "dz", "beta_alpha_ratio", "n_total"),
    "criterion": ("tails", "dz", "power", "n_total"),
    "sensitivity": ("tails", "alpha", "power", "n_total"),
}


def fail(message: str, code: str, field: str | None = None) -> NoReturn:
    raise CliError(message, code, field)


def parse_pairs(argv: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if not token.startswith("--") or token == "--":
            fail(f"Unexpected argument: {token}", "INVALID_VALUE")
        flag = token[2:]
        field = FLAGS.get(flag)
        if field is None:
            fail(f"Unknown parameter: {token}", "UNKNOWN_PARAM", flag.replace("-", "_"))
        if field in parsed:
            fail(f"Duplicate parameter: {token}", "INVALID_VALUE", field)
        if index + 1 >= len(argv) or argv[index + 1].startswith("--"):
            fail(f"Missing value for {token}", "INVALID_VALUE", field)
        parsed[field] = argv[index + 1]
        index += 2
    return parsed


def parse_integer(raw: str, field: str) -> int:
    if re.fullmatch(r"[+-]?[0-9]+", raw) is None:
        fail("Expected an integer value", "INVALID_VALUE", field)
    try:
        return int(raw, 10)
    except ValueError:
        # Python may limit extremely long integer strings; a syntactically
        # valid n_total of that size is outside the stated range.
        if field == "n_total":
            fail("n_total is outside the supported range", "OUT_OF_RANGE", field)
        fail("Expected an integer value", "INVALID_VALUE", field)


def parse_number(raw: str, field: str) -> float:
    pattern = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    if re.fullmatch(pattern, raw) is None:
        fail("Expected a finite number using a period as the decimal separator", "INVALID_VALUE", field)
    try:
        value = float(raw)
    except ValueError:
        fail("Expected a finite number", "INVALID_VALUE", field)
    if not math.isfinite(value):
        fail("Value must be finite", "INVALID_VALUE", field)
    return value


def validate(values: dict[str, str]) -> tuple[str, dict[str, int | float]]:
    if "test" not in values:
        fail("Missing required parameter --test", "MISSING_PARAM", "test")
    if values["test"] != "t-paired":
        fail("Unsupported test", "UNSUPPORTED", "test")
    if "mode" not in values:
        fail("Missing required parameter --mode", "MISSING_PARAM", "mode")
    mode = values["mode"]
    required = MODES.get(mode)
    if required is None:
        fail("Unsupported mode", "UNSUPPORTED", "mode")

    allowed = set(required) | {"test", "mode"}
    for field in values:
        if field not in allowed:
            fail("Parameter is unknown or irrelevant for this mode", "UNKNOWN_PARAM", field)
    for field in required:
        if field not in values:
            fail(f"Missing required parameter --{field.replace('_', '-')}", "MISSING_PARAM", field)

    parsed: dict[str, int | float] = {}
    for field in required:
        raw = values[field]
        if field == "tails":
            value = parse_integer(raw, field)
            if value not in (1, 2):
                fail("tails must be 1 or 2", "OUT_OF_RANGE", field)
            parsed[field] = value
        elif field == "n_total":
            value = parse_integer(raw, field)
            if value < 3 or value > 2147483646:
                fail("n_total must be between 3 and 2147483646", "OUT_OF_RANGE", field)
            parsed[field] = value
        else:
            value = parse_number(raw, field)
            if field in ("alpha", "power"):
                if value < 1e-7 or value > 0.9999999:
                    fail(f"{field} must be between 1e-7 and 0.9999999", "OUT_OF_RANGE", field)
            elif field == "dz":
                minimum = 1e-5 if mode == "a-priori" else 0.0
                if value <= minimum or value > 20.0:
                    qualifier = "greater than 1e-5" if mode == "a-priori" else "positive"
                    fail(f"dz must be {qualifier} and at most 20", "OUT_OF_RANGE", field)
            elif field == "beta_alpha_ratio":
                if value < 0.01 or value > 100.0:
                    fail("beta_alpha_ratio must be between 0.01 and 100", "OUT_OF_RANGE", field)
            parsed[field] = value

    if "alpha" in parsed and "power" in parsed and parsed["power"] < parsed["alpha"]:
        fail("power must be greater than or equal to alpha", "INCONSISTENT", "power")
    return mode, parsed


def emit_error(error: str, code: str, field: str | None = None) -> None:
    obj: dict[str, str] = {"error": error, "code": code}
    if field is not None:
        obj["field"] = field
    print(json.dumps(obj, separators=(",", ":"), allow_nan=False))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--version"]:
        print(json.dumps({
            "contract_version": "1.0.0",
            "name": "paired-power",
            "engine": f"Python {platform.python_version()}",
        }, separators=(",", ":"), allow_nan=False))
        return 0
    if "--version" in args:
        emit_error("--version cannot be combined with other parameters", "INVALID_VALUE", "version")
        return 2
    try:
        mode, values = validate(parse_pairs(args))
        result = paired_power.calculate(mode, values)
        print(json.dumps(result, separators=(",", ":"), allow_nan=False))
        return 0
    except CliError as exc:
        emit_error(str(exc), exc.code, exc.field)
        return 2
    except paired_power.NoSolutionError as exc:
        emit_error(str(exc), "NO_SOLUTION")
        return 2
    except Exception:
        emit_error("Unexpected internal error", "INTERNAL_ERROR")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
