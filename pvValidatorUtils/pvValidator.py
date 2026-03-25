#!/usr/bin/python
import argparse
import os
import sys

from pvValidatorUtils import epicsUtils, pvUtils, version
from pvValidatorUtils.exceptions import PVValidatorError


def pvinput(args):
    """Handle input for PV validation"""
    pvepics = None

    if args.iocserver:  # PVs from the input IOC
        pvepics = epicsUtils(args.iocserver)

    elif args.pvfile:  # PVs from a text file
        if os.path.isfile(args.pvfile):
            pvepics = epicsUtils()
        else:
            raise argparse.ArgumentTypeError(f"{args.pvfile} is not a valid file")

    elif args.epicsdb:  # PVs from an EPICS DB
        max_args = 2
        if len(args.epicsdb) <= max_args:
            dbfile = args.epicsdb[0]
            if os.path.isfile(dbfile):
                pvepics = epicsUtils()
            else:
                raise argparse.ArgumentTypeError(f"{dbfile} is not a valid file")
        else:
            raise argparse.ArgumentTypeError(
                f"too many arguments for -e, the maximum is {max_args}"
            )

    elif args.msi:  # PVs from a substitution file
        max_args = 3
        if len(args.msi) <= max_args:
            subsfile = args.msi[0]
            if os.path.isfile(subsfile):
                pvepics = epicsUtils()
            else:
                raise argparse.ArgumentTypeError(f"{subsfile} is not a valid file")
        else:
            raise argparse.ArgumentTypeError(
                f"too many arguments for -m, the maximum is {max_args}"
            )

    return pvepics


class DiscoverAction(argparse.Action):
    """Custom action to handle immediate discovery"""

    def __call__(self, parser, namespace, values, option_string=None):
        print(epicsUtils(True).getServerList())
        raise SystemExit(0)


def main():
    """Main function to handle the EPICS PV Validation Tool"""
    parser = argparse.ArgumentParser(
        description=f"EPICS PV Validation Tool ({version})",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=150),
        epilog="Copyright 2021 - Alfio Rizzo (alfio.rizzo@ess.eu)",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s " + version,
        help="print version and exit",
    )

    parser.add_argument(
        "-d",
        "--discover",
        action=DiscoverAction,
        nargs=0,
        help="discover IOC servers and exit",
    )

    # Input parser
    input_parser_group = parser.add_mutually_exclusive_group(required=True)
    input_parser_group.add_argument(
        "-s",
        dest="iocserver",
        metavar="(IP[:PORT] | GUID)",
        help="IOC server IP[:PORT] or GUID to get PV list (online validation)",
    )
    input_parser_group.add_argument(
        "-i",
        dest="pvfile",
        metavar="pvfile",
        default=None,
        help="input PV list file (offline validation)",
    )
    input_parser_group.add_argument(
        "-e",
        dest="epicsdb",
        nargs="+",
        metavar=("dbfile", "VAR=VALUE"),
        default=None,
        help="input EPICS db file (.db) [VAR=VALUE, ...] (offline validation)",
    )
    input_parser_group.add_argument(
        "-m",
        dest="msi",
        nargs="+",
        default=None,
        metavar=("subsfile", "path_to_templates VAR=VALUE"),
        help="input substitution file (.substitutions) [/path/to/templates VAR=VALUE, ...] (offline validation)",
    )

    # Naming parser
    naming_parser_group = parser.add_mutually_exclusive_group()
    naming_parser_group.add_argument(
        "-n",
        dest="nameservice",
        default="prod",
        choices=["prod", "test"],
        help="select naming service endpoint to connect: prod(uction), test(ing) [default=prod]",
    )
    naming_parser_group.add_argument(
        "--noapi",
        dest="noapi",
        action="store_true",
        default=False,
        help="check only PV format and rules, skip connection to naming service endpoint",
    )

    # Output parser
    output_parser_group = parser.add_mutually_exclusive_group()
    output_parser_group.add_argument(
        "-o",
        dest="csvfile",
        metavar="csvfile",
        default=None,
        help="write the validation table directly to CSV file",
    )
    output_parser_group.add_argument(
        "--stdout",
        dest="stdout",
        action="store_true",
        default=False,
        help="write the validation table directly to STDOUT",
    )
    output_parser_group.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "html"],
        default=None,
        metavar="FORMAT",
        help="output format: json or html (writes to STDOUT)",
    )

    args = parser.parse_args()

    # Handle --format json/html separately (uses new reporter module)
    if args.output_format:
        pvepics = pvinput(args)
        _run_with_reporter(args, pvepics)
        return

    pvepics = pvinput(args)

    try:
        pv = pvUtils(
            pvepics=pvepics,
            namingservice=args.nameservice,
            checkonlyfmt=args.noapi,
            pvfile=args.pvfile,
            csvfile=args.csvfile,
            epicsdb=args.epicsdb,
            msiobj=args.msi,
            stdout=args.stdout,
        )
        pv.run()
    except PVValidatorError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except SystemExit:
        raise  # Let SystemExit propagate (from validation failures)
    except RuntimeError as e:
        # C++ exceptions from SWIG come through as RuntimeError
        print(f"EPICS error: {e}")
        sys.exit(10)


def _run_with_reporter(args, pvepics):
    """Run validation and output via JSON or HTML reporter."""
    from pvValidatorUtils.parser import parse_pv
    from pvValidatorUtils.reporter import HTMLReporter, JSONReporter
    from pvValidatorUtils.rules import (
        Severity,
        ValidationResult,
        check_all_rules,
        check_property_uniqueness,
    )

    # Build PV list (same logic as pvUtils)
    pv_list = []
    if args.pvfile:
        with open(args.pvfile, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("%") and not line.startswith("#"):
                    pv_list.append(line.split()[0])
    else:
        for pv in pvepics.pvstringlist:
            pv_list.append(pv)

    # Validate each PV
    results = []
    device_properties = {}  # device_key → [properties]

    for pv_str in pv_list:
        components = parse_pv(pv_str)
        if components is None:
            results.append(ValidationResult(pv=pv_str, format_valid=False))
            continue

        msgs = check_all_rules(components)
        result = ValidationResult(
            pv=pv_str,
            format_valid=True,
            components=components,
            messages=msgs,
        )
        results.append(result)

        # Collect properties per device for uniqueness check
        ess_name = components.ess_name
        device_properties.setdefault(ess_name, []).append(components.property)

    # Uniqueness checks
    for dev_key, props in device_properties.items():
        if len(props) > 1:
            uniqueness_msgs = check_property_uniqueness(dev_key, props)
            for pv_str, msgs in uniqueness_msgs.items():
                for result in results:
                    if result.pv == pv_str:
                        result.messages.extend(msgs)

    # Generate output
    metadata = {"version": version, "document": "ESS-0000757"}

    if args.output_format == "json":
        reporter = JSONReporter()
        print(reporter.generate(results, metadata))
    elif args.output_format == "html":
        reporter = HTMLReporter()
        print(reporter.generate(results, metadata))
