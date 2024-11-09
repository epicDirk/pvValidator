#!/usr/bin/python
import argparse
import os
import sys

from pvValidatorUtils import epicsUtils, pvUtils, version


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
        sys.exit()


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

    args = parser.parse_args()

    pvepics = pvinput(args)

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
