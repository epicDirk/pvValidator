# pvValidator

Tool to validate EPICS PVs

**Requirements**: 
- python development tool (python3-dev preferred)
- c++
- swig ( http://www.swig.org ), you can install via `apt` (debian/ubuntu) or `dnf/yum` (fedora/centos)
- EPICS 7

**Compilation**:
- Source your EPICS environment then do
`make` and 
`make install`

It will do a local installation of the python modules.

Then you can run the CLI **pvValidator.py**
```
> pvValidator.py -h
usage: pvValidator.py [-h] [-V] (-d | -s IOCSERVER | -i PVFILE) [-o CSVFILE]
                      [--noapi]

EPICS PV Validation Tool

optional arguments:
  -h, --help                        show this help message and exit
  -V, --version                     print version and exit
  -d, --discover                    discover IOC Servers and exit
  -s IOCSERVER, --server IOCSERVER  IOC server IP or GUID to get PV list
                                    (online validation)
  -i PVFILE, --inpvfile PVFILE      input PV list file (offline validation)
  -o CSVFILE, --outcsvfile CSVFILE  write Validation Table direclty on csv
                                    file (do not start interactive session)
  --noapi                           check only PV format and rules, skip
                                    connection to Naming Service
```
