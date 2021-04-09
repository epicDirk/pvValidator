# pvValidator.py

Tool to validate EPICS PVs based on CHESS document [ESS-3218463](https://chess.esss.lu.se/enovia/link/ESS-3218463/21308.51166.39936.65207/valid).

**Requirements**:
- python 2 or 3 development tool ( `python(3)-dev(el)` )
- setuptools
- c++
- swig ( http://www.swig.org ), you can install it via `apt` (debian/ubuntu) or `dnf/yum` (fedora/centos)
- EPICS 7

**Compilation**:
- Export `PYBINDPATH` env variable to the python binding include path (e.g. `export PYBINDPATH=/usr/include/pythonXXX`)
- Export `CFLAGS=-std=c++11` env variable if you need to compile against EPICS >= 7.0.5 mounted in ESS NFS disk
- Source your EPICS environment then do
`make` and
`make install`

It will do a local installation of the python modules.

Then you can run the CLI **pvValidator.py**
```
pvValidator.py -h
usage: pvValidator.py [-h] [-V] (-d | -s IOCSERVER | -i PVFILE | -e EPICSDB [MACROSUB ...])
                        [-o CSVFILE] [-n {prod,dev,stag} | --noapi]

EPICS PV Validation Tool

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         print version and exit
  -d, --discover        discover IOC Servers and exit
  -s IOCSERVER, --server IOCSERVER
                        IOC server IP or GUID to get PV list (online validation)
  -i PVFILE, --inpvfile PVFILE
                        input PV list file (offline validation)
  -e EPICSDB [MACROSUB ...], --epicsdb EPICSDB [MACROSUB ...]
                        input EPICS DB file (.db) [macro substitution file] (offline validation)
  -o CSVFILE, --outcsvfile CSVFILE
                        write Validation Table directly on csv file (do not start interactive session)
  -n {prod,dev,stag}, --nameservice {prod,dev,stag}
                        Select Naming Service endpoint: prod(uction), dev(elopment), stag(ing) [Default=prod]
  --noapi               check only PV format and rules, skip connection to Naming Service endpoint
```

For more details please see the [documentation](doc/pvvalidator.md)
