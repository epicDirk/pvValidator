#!/usr/bin/env python3
"""Record VCR cassettes from the live ESS Naming Service.

Run this ONCE while connected to the ESS network.
After recording, cassettes are saved to test/cassettes/ and can be
committed to the repo. All future test runs replay these cassettes
without needing network access.

Usage:
    # From the pvvalidator directory, with ESS network access:
    python test/record_cassettes.py

    # Or via pytest:
    pytest test/record_cassettes.py -v -s

What it records:
    - System lookups (DTL, PBI, ISrc, Tgt, CWM, YMIR, etc.)
    - Subsystem lookups (010, BCM01, CS, CWS03, etc.)
    - Discipline lookups (EMR, Ctrl, WtrC, Proc, MC, ISS, SC, etc.)
    - Device lookups (TT, PT, MTCA, IOC, MCU, Magtr, etc.)
    - Full device name lookups (registered and unregistered)
    - Edge cases: OBSOLETE, DELETED, nonexistent names
"""

import json
import pathlib
import sys

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROD_URL = "https://naming.esss.lu.se/"
PARTS_URL = PROD_URL + "rest/parts/mnemonic/"
NAMES_URL = PROD_URL + "rest/deviceNames/"
CASSETTE_DIR = pathlib.Path(__file__).parent / "cassettes"

HEADERS = {"accept": "application/json"}
TIMEOUT = 10

# Systems to record (common ESS systems from ESS-0000757)
SYSTEMS = [
    "DTL",
    "PBI",
    "ISrc",
    "Tgt",
    "CWM",
    "YMIR",
    "LOKI",
    "DREAM",
    "RFQ",
    "MEBT",
    "MBL",
    "HBL",
    "TD",
    "MO",
    "TRef",
    "Acc",
    "CrS",
    "ACF",
    "TS2",
    "G02",
    "LoKI",
]

# Subsystems to record
SUBSYSTEMS = [
    "010",
    "BCM01",
    "CS",
    "CWS03",
    "SpScn",
    "HeC1010",
    "ChpSy1",
    "M",
    "D1",
    "TWDS1000",
]

# Disciplines to record
DISCIPLINES = [
    "EMR",
    "Ctrl",
    "WtrC",
    "Proc",
    "MC",
    "ISS",
    "SC",
    "PBI",
    "RFS",
    "BMD",
    "Cryo",
    "Vac",
    "CnPw",
]

# Devices to record
DEVICES = [
    "TT",
    "PT",
    "MTCA",
    "IOC",
    "MCU",
    "Magtr",
    "CPU",
    "EVR",
    "ACCT",
    "BCM",
    "PCV",
    "YSV",
    "EH",
    "CT",
    "AMC",
    "FSM",
    "PID",
]

# Full device names to record (mix of registered and likely-unregistered)
DEVICE_NAMES = [
    "DTL-010:EMR-TT-001",
    "PBI-BCM01:Ctrl-MTCA-100",
    "CWM-CWS03:WtrC-PT-011",
    "ISrc-CS:ISS-Magtr-01",
    "Tgt-HeC1010:Proc-TT-003",
    "DTL-010",
    "DTL",
    "NONEXIST-999:FAKE-XX-001",
    "QQQQQQ-010:EMR-TT-001",
]


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def record_endpoint(url, label):
    """Fetch a URL and return the JSON response."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = resp.json() if resp.status_code == 200 else {"_status": resp.status_code}
        print(f"  OK  {label} -> {len(str(data))} bytes")
        return data
    except Exception as e:
        print(f"  FAIL {label} -> {e}")
        return {"_error": str(e)}


def main():
    print("=" * 60)
    print("pvValidator VCR Cassette Recorder")
    print("=" * 60)

    # Check connectivity
    print(f"\nChecking connectivity to {PROD_URL}...")
    try:
        resp = requests.head(PROD_URL, timeout=5)
        print(f"  Connected (HTTP {resp.status_code})")
    except Exception as e:
        print(f"  FAILED: {e}")
        print("\n  You need ESS network access to record cassettes.")
        print("  Connect via VPN or run this on an ESS machine.")
        sys.exit(1)

    cassettes = {
        "parts_mnemonic": {},
        "device_names": {},
        "_metadata": {
            "source": PROD_URL,
            "recorded_by": "record_cassettes.py",
        },
    }

    # Record system lookups
    print(f"\nRecording {len(SYSTEMS)} systems...")
    for sys_name in SYSTEMS:
        cassettes["parts_mnemonic"][sys_name] = record_endpoint(
            PARTS_URL + sys_name, f"parts/{sys_name}"
        )

    # Record subsystem lookups
    print(f"\nRecording {len(SUBSYSTEMS)} subsystems...")
    for sub in SUBSYSTEMS:
        cassettes["parts_mnemonic"][sub] = record_endpoint(
            PARTS_URL + sub, f"parts/{sub}"
        )

    # Record discipline lookups
    print(f"\nRecording {len(DISCIPLINES)} disciplines...")
    for dis in DISCIPLINES:
        cassettes["parts_mnemonic"][dis] = record_endpoint(
            PARTS_URL + dis, f"parts/{dis}"
        )

    # Record device lookups
    print(f"\nRecording {len(DEVICES)} devices...")
    for dev in DEVICES:
        cassettes["parts_mnemonic"][dev] = record_endpoint(
            PARTS_URL + dev, f"parts/{dev}"
        )

    # Record full device name lookups
    print(f"\nRecording {len(DEVICE_NAMES)} device names...")
    for name in DEVICE_NAMES:
        cassettes["device_names"][name] = record_endpoint(
            NAMES_URL + name, f"deviceNames/{name}"
        )

    # Save cassettes
    CASSETTE_DIR.mkdir(exist_ok=True)
    output_file = CASSETTE_DIR / "naming_service_prod.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(cassettes, f, indent=2, ensure_ascii=False)

    total = len(cassettes["parts_mnemonic"]) + len(cassettes["device_names"])
    print(f"\n{'=' * 60}")
    print(f"Done! Recorded {total} API responses.")
    print(f"Saved to: {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
    print("\nNext steps:")
    print("  1. git add test/cassettes/")
    print("  2. git commit -m 'Add VCR cassettes from ESS Naming Service'")
    print("  3. All API tests now work offline!")
    print("=" * 60)


if __name__ == "__main__":
    main()
