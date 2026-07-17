#!/usr/bin/env python3
"""Compute the exact `sec-ch-ua` (User-Agent Client Hints brand list) that a given
Chrome major version emits.

Use it to check rule G7 in references/request-rules.md — i.e. whether a
captured `sec-ch-ua` matches what real Chrome sends for its User-Agent version.

Usage:
    python sec_ch_ua.py 149                 # print expected sec-ch-ua for Chrome 149
    python sec_ch_ua.py 149.0.0.0           # full version string also accepted
    python sec_ch_ua.py --check 149 '<sec-ch-ua value>'   # compare a captured value
"""
import sys

# GREASE tables (verbatim from the Go source).
_LEGACY_CHARS = [" ", " ", ";"]
_CHARS = [" ", "(", ":", "-", ".", "/", ")", ";", "=", "?", "_"]
_VERSIONS = ["8", "99", "24"]
_ORDERS = [
    [0, 1, 2], [0, 2, 1], [1, 0, 2],
    [1, 2, 0], [2, 0, 1], [2, 1, 0],
]


def _fmt(brand: str, version: str) -> str:
    return f'"{brand}";v="{version}"'


def _greased_brand(seed: int, num: int, order) -> str:
    if num <= 102 or num == 104:
        brand = f"{_LEGACY_CHARS[order[0]]}Not{_LEGACY_CHARS[order[1]]}A{_LEGACY_CHARS[order[2]]}Brand"
        version = "99"
    elif num == 103:
        brand = (
            f"{_CHARS[(seed % (len(_CHARS) - 1)) + 1]}Not"
            f"{_CHARS[(seed + 1) % len(_CHARS)]}A"
            f"{_CHARS[(seed + 2) % len(_CHARS)]}Brand"
        )
        version = _VERSIONS[seed % len(_VERSIONS)]
    else:  # >= 105
        brand = f"Not{_CHARS[seed % len(_CHARS)]}A{_CHARS[(seed + 1) % len(_CHARS)]}Brand"
        version = _VERSIONS[seed % len(_VERSIONS)]
    return _fmt(brand, version)


def client_hint_ua(major_version: str, major_version_number: int, brand: str = "Google Chrome") -> str:
    """Return the exact sec-ch-ua string for the given Chrome major version."""
    seed = major_version_number
    if major_version_number <= 102:
        seed = 0  # legacy behavior (matches Chromium)
    order = _ORDERS[seed % len(_ORDERS)]
    greased = [None, None, None]
    greased[order[0]] = _greased_brand(seed, major_version_number, order)
    greased[order[1]] = _fmt("Chromium", major_version)
    greased[order[2]] = _fmt(brand, major_version)
    return ", ".join(greased)


def sec_ch_ua(version: str, brand: str = "Google Chrome") -> str:
    """Convenience: accept '149' or '149.0.0.0'."""
    major = version.split(".", 1)[0].strip()
    return client_hint_ua(major, int(major), brand)


# --- self-test vectors (from the Go test suite) -----------------------------------
_TESTS = {
    "80.0.0.0": '" Not A;Brand";v="99", "Chromium";v="80", "Google Chrome";v="80"',
    "98.0.0.0": '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
    "99.0.0.0": '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
    "100.0.0.0": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
    "101.0.0.0": '" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
    "102.0.0.0": '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
    "103.0.0.0": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
    "104.0.0.0": '"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"',
    "105.0.0.0": '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
    "106.0.0.0": '"Chromium";v="106", "Google Chrome";v="106", "Not;A=Brand";v="99"',
    "107.0.0.0": '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
    "108.0.0.0": '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
}


def _run_selftest() -> int:
    failures = 0
    for version, want in _TESTS.items():
        got = sec_ch_ua(version)
        ok = got == want
        failures += not ok
        print(f"[{'ok' if ok else 'FAIL'}] {version:10} {got}")
        if not ok:
            print(f"           want {want}")
    print(f"\n{len(_TESTS) - failures}/{len(_TESTS)} passed")
    return 1 if failures else 0


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--selftest":
        return _run_selftest()
    if argv[0] == "--check":
        version, actual = argv[1], argv[2]
        expected = sec_ch_ua(version)
        match = actual.strip() == expected
        print(f"expected: {expected}")
        print(f"actual:   {actual.strip()}")
        print("MATCH" if match else "MISMATCH - sec-ch-ua does not match real Chrome (rule G7)")
        return 0 if match else 1
    print(sec_ch_ua(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
