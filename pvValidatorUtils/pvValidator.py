#!/usr/bin/python
import argparse
import logging
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
        epilog="Exit codes: 0 = valid, 1 = validation errors found, 10 = EPICS/system error. Copyright 2021 - Alfio Rizzo (alfio.rizzo@ess.eu)",
    )

    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="enable debug logging (shows detailed internal messages)",
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

    # Input parser (not required when using --explain)
    input_parser_group = parser.add_mutually_exclusive_group(required=False)
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

    # Autofix options
    parser.add_argument(
        "--suggest",
        dest="suggest",
        action="store_true",
        default=False,
        help="show auto-fix suggestions for validation errors",
    )
    parser.add_argument(
        "--fix",
        dest="fix",
        action="store_true",
        default=False,
        help="apply safe auto-fixes and show results (use with -i or -e)",
    )
    parser.add_argument(
        "--unsafe",
        dest="unsafe",
        action="store_true",
        default=False,
        help="also apply suggested (uncertain) fixes (use with --fix)",
    )
    parser.add_argument(
        "--interactive",
        dest="interactive",
        action="store_true",
        default=False,
        help="prompt for each fix individually (use with --fix)",
    )

    # Verbose/explain options
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="show detailed explanations for each validation finding",
    )
    parser.add_argument(
        "--explain",
        dest="explain",
        metavar="RULE_ID",
        default=None,
        help="show full documentation for a specific rule (e.g., --explain PROP-SP)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(name)s: %(levelname)s: %(message)s",
    )

    # Handle --explain (no input needed, just show rule info and exit)
    if args.explain:
        _explain_rule(args.explain)
        return

    # Require input source for all other operations
    if not (args.iocserver or args.pvfile or args.epicsdb or args.msi):
        parser.error("one of the arguments -s -i -e -m is required")

    # --verbose implies --suggest (show fix suggestions alongside validation)
    # But NOT when --format is specified (--format has its own output path)
    if args.verbose and not args.suggest and not args.fix and not args.output_format:
        args.suggest = True

    # Handle --suggest or --fix (uses autofix module)
    if args.suggest or args.fix:
        pvepics = pvinput(args)
        _run_with_autofix(args, pvepics)
        return

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


def _load_pv_list(args, pvepics):
    """Load PV names from file or epicsUtils object.

    Shared by _run_with_reporter() and _run_with_autofix() to avoid
    duplicating the file-reading logic.

    Note: -e (EPICS DB) and -m (substitution) inputs require SWIG compilation
    and are handled by pvUtils.run(). These paths work with the standard
    validation pipeline but not with --suggest/--fix/--format which bypass pvUtils.
    """
    if getattr(args, "epicsdb", None) or getattr(args, "msi", None):
        print(
            "Error: --suggest/--fix/--format do not support -e (EPICS DB) or -m (substitution) input.\n"
            "Use -i with a plain text PV list, or run without --suggest/--fix/--format\n"
            "to use the standard validation pipeline with -e/-m."
        )
        sys.exit(1)
    pv_list = []
    if args.pvfile:
        with open(args.pvfile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("%") and not line.startswith("#"):
                    pv_list.append(line.split()[0])
    elif pvepics:
        for pv in pvepics.pvstringlist:
            pv_list.append(pv)
    return pv_list


def _run_with_reporter(args, pvepics):
    """Run validation and output via JSON or HTML reporter."""
    from pvValidatorUtils.parser import parse_pv
    from pvValidatorUtils.reporter import HTMLReporter, JSONReporter
    from pvValidatorUtils.rules import (
        ValidationResult,
        check_all_rules,
        check_property_uniqueness,
    )

    pv_list = _load_pv_list(args, pvepics)

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

    # Add autofix suggestions to each result
    from pvValidatorUtils.autofix import suggest_fixes

    for result in results:
        result.suggestions = suggest_fixes(result.pv)

    # Generate output
    metadata = {"version": version, "document": "ESS-0000757"}

    if args.output_format == "json":
        reporter = JSONReporter()
        print(reporter.generate(results, metadata))
    elif args.output_format == "html":
        reporter = HTMLReporter()
        print(reporter.generate(results, metadata))


def _explain_rule(rule_id):
    """Show full documentation for a specific validation rule."""
    from pvValidatorUtils.rule_loader import RuleConfig

    config = RuleConfig()
    rule = config.get_rule(rule_id)
    if rule is None:
        # Try case-insensitive match
        for rid in config.list_rules():
            if rid.upper() == rule_id.upper():
                rule = config.get_rule(rid)
                rule_id = rid
                break

    if rule is None:
        print(f"Unknown rule: {rule_id}")
        print(f"Available rules: {', '.join(sorted(config.list_rules()))}")
        sys.exit(1)

    print(f"Rule: {rule_id}")
    print(f"  Severity:  {rule.get('severity', 'unknown')}")
    print(f"  Message:   {rule.get('message', '')}")
    print(f"  Reference: {rule.get('reference', '')}")
    if rule.get("why"):
        print(f"  Why:       {rule['why']}")
    if rule.get("fix"):
        print(f"  Fix:       {rule['fix']}")
    if rule.get("example_good"):
        print(f"  Good:      {rule['example_good']}")
    if rule.get("example_bad"):
        print(f"  Bad:       {rule['example_bad']}")


def _run_with_autofix(args, pvepics):
    """Run validation with auto-fix suggestions or automatic fixing."""
    from pvValidatorUtils.autofix import apply_fixes, suggest_fixes

    pv_list = _load_pv_list(args, pvepics)
    if not pv_list:
        print("No PV names to process.")
        return

    fixed_count = 0
    manual_count = 0
    valid_count = 0

    for pv in pv_list:
        suggestions = suggest_fixes(pv)
        auto_suggestions = [s for s in suggestions if s.auto_fixable]
        manual_suggestions = [
            s for s in suggestions if not s.auto_fixable and s.suggested
        ]

        if not suggestions:
            valid_count += 1
            if not args.fix:
                print(f"  {pv}  ✓")
            continue

        if args.fix and auto_suggestions:
            result = apply_fixes(pv, include_suggested=getattr(args, "unsafe", False))
            if result != pv:
                if getattr(args, "interactive", False):
                    # Interactive mode: prompt for each fix
                    print(f"\n  {pv}")
                    print(f"    → {result}")
                    for s in auto_suggestions:
                        print(
                            f"      [{s.rule_id}] {s.description}  [{s.applicability.value.upper()}]"
                        )
                    try:
                        choice = (
                            input("    Apply? [Y]es / [N]o / [A]ll / [Q]uit > ")
                            .strip()
                            .lower()
                        )
                    except EOFError:
                        choice = "n"
                    if choice in ("q", "quit"):
                        break
                    elif choice in ("a", "all"):
                        args.interactive = False  # disable interactive for remaining
                        fixed_count += 1
                    elif choice in ("y", "yes", ""):
                        fixed_count += 1
                    else:
                        valid_count += 1
                        continue
                else:
                    print(f"  {pv}")
                    print(f"    → {result}")
                    for s in auto_suggestions:
                        print(f"      [{s.rule_id}] {s.description}")
                    fixed_count += 1
            else:
                valid_count += 1
        else:
            # Show suggestions only
            print(f"  {pv}")
            for s in suggestions:
                tier = s.applicability.value.upper()
                if s.suggested:
                    print(f"    [{s.rule_id}] {s.description}  [{tier}]")
                    print(f"      → {s.suggested}")
                else:
                    print(f"    [{s.rule_id}] {s.description}  [{tier}]")

        if manual_suggestions:
            manual_count += 1

    # Summary
    print()
    total = len(pv_list)
    if args.fix:
        print(
            f"Total: {total} PVs | Fixed: {fixed_count} | Need review: {manual_count} | Valid: {valid_count}"
        )
    else:
        need_fix = total - valid_count
        print(f"Total: {total} PVs | Need fixes: {need_fix} | Valid: {valid_count}")
