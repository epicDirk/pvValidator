#!/usr/bin/python


import argparse
import os
import sys

from pvValidatorUtils import epicsUtils, pvUtils, version


def main():

    parser = argparse.ArgumentParser(
        description="EPICS PV Validation Tool",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, width=200),
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s " + version,
        help="Print version and exit",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-d", "--discover", action="store_true", help="discover IOC Servers and exit"
    )
    group.add_argument(
        "-s",
        "--server",
        dest="iocserver",
        help="IOC server IP or GUID to get PV list (online validation)",
    )
    group.add_argument(
        "-i",
        "--inpvfile",
        dest="pvfile",
        default=None,
        help="Input PV list file (offline validation)",
    )
    group.add_argument(
        "-e",
        "--epicsdb",
        dest="epicsdb",
        default=None,
        help="Input EPICS DB file (.db) [macro definition file] (offline validation)",
        metavar=("EPICSDB", "MACRODEF"),
        nargs="+",
    )
    outgroup = parser.add_mutually_exclusive_group(required=False)
    outgroup.add_argument(
        "-o",
        "--outcsvfile",
        dest="csvfile",
        default=None,
        help="Write Validation Table directly on csv file (do not start interactive session)",
    )
    outgroup.add_argument(
        "--stdout",
        dest="stdout",
        action="store_true",
        default=False,
        help="Write Validation Table directly on STDOUT (do not start interactive session)",
    )
    namegroup = parser.add_mutually_exclusive_group(required=False)
    namegroup.add_argument(
        "-n",
        "--nameservice",
        dest="nameservice",
        default="prod",
        choices=["prod", "dev", "stag"],
        help="Select Naming Service endpoint: prod(uction), dev(elopment), stag(ing) [Default=prod]",
    )
    namegroup.add_argument(
        "--noapi",
        dest="noapi",
        action="store_true",
        default=False,
        help="Check only PV format and rules, skip connection to Naming Service endpoint",
    )

    args = parser.parse_args()

    if args.discover:
        print(epicsUtils(True).getServerList())
        sys.exit()

    if args.iocserver:
        pvepics = epicsUtils(args.iocserver)

    if args.pvfile:
        if os.path.isfile(args.pvfile):
            pvepics = epicsUtils(False)
        else:
            parser.error(args.pvfile + " is not a valid file")

    if args.epicsdb:
        if os.path.isfile(args.epicsdb[0]):
            pvepics = epicsUtils(False)
            if len(args.epicsdb) > 1 and not os.path.isfile(args.epicsdb[1]):
                parser.error(args.epicsdb[1] + " is not a valid file")
        else:
            parser.error(args.epicsdb[0] + " is not a valid file")

    pv = pvUtils(
        pvepics, args.nameservice, args.noapi, args.pvfile, args.csvfile, args.epicsdb, args.stdout
    )
    pv.run()


if __name__ == "__main__":
    main()
