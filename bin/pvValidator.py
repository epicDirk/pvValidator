#!/usr/bin/python


from pvValidatorUtils import epicsUtils, pvUtils, version
import sys
import os
import argparse


def main():

    parser = argparse.ArgumentParser(
        description="EPICS PV Validation Tool",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=60),
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s " + version,
        help="print version and exit",
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
        help="input PV list file (offline validation)",
    )
    parser.add_argument(
        "-o",
        "--outcsvfile",
        dest="csvfile",
        default=None,
        help="write Validation Table direclty on csv file (do not start interactive session)",
    )
    parser.add_argument(
        "--noapi",
        dest="noapi",
        action="store_true",
        default=False,
        help="check only PV format and rules, skip connection to Naming Service",
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

    pv = pvUtils(pvepics, args.noapi, args.pvfile, args.csvfile)
    pv.run()


if __name__ == "__main__":
    main()
