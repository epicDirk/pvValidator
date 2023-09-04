# pvValidator.py

Tool to validate EPICS PVs based on CHESS document [ESS-0000757](https://chess.esss.lu.se/enovia/link/ESS-0000757/21308.51166.43264.12914/valid).

**Install via pip package on CentOS7 Distribution**

Requiremenmts: `Python3` and `pip3`

`pip3 install pvValidatorUtils -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user`


**Requirements for compilation from sources**:
- python3 development tool ( `python3-dev(el)` , python recommended version >=3.80)
- python setuptools module
- c++
- swig ( http://www.swig.org ), you can install it via `apt` (debian/ubuntu) or `dnf/yum` (fedora/centos)
- EPICS 7
- Recommended: `cmake` (version >=3.0, in CentOS7 distro is called `cmake3`).
- Optional (for test running)
  - `pytest`
  - `run-iocsh` ( `pip install run-iocsh -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user` )

**Compile with cmake (recommended)**
- Create a directory called e.g. `build`, preferably outside the local git cloned repo (e.g. `mkdir /tmp/build`)

- Source your EPICS environment

- Go into  the `build` directory and launch

  `cmake (cmake3) <PATH_TO_YOUR_GIT_CLONE_DIR>`
- If you want to compile against a different version of `python` that the one found in the build check in the first place add

  `cmake (cmake3) <PATH_TO_YOUR_GIT_CLONE_DIR> -DMY_PYTHON_VERSION=X.Y` (e.g. `-DMY_PYTHON_VERSION=3.7`)
- If you need to compile with the C++ 11 option (for instance against EPICS >= 7.0.5 mounted in ESS NFS disk)  add the following

  `cmake (cmake3) <PATH_TO_YOUR_GIT_CLONE_DIR> [-DMY_PYTHON_VERSION=X.Y] -DCMAKE_CXX_STANDARD=11`
- If the build check is ok, then you can do
  - `make` and `make install` or directly
  - `make install` (It will do a local installation of the python modules).

Otherwise `cmake` will exit warning about the missing package(s) or env. In case fix the issues and restart from the beginning.

- Optional (for test running)
  - `ctest -V`

**Compile with built-in Makefile**:
- Export `PYBINDPATH` env variable to the python binding include path (e.g. `export PYBINDPATH=/usr/include/pythonXXX`)
- Export `CFLAGS=-std=c++11` env variable if you need to compile for instance against EPICS >= 7.0.5 mounted in ESS NFS disk
- Source your EPICS environment then do
  - `make`
  - `make install` (It will do a local installation of the python modules).
  - `make test` (optional, for test running)

If the `EPICS` enviroment is not sourced or `PYBINDPATH` not set, Makefile will stop compilation.


Then you can run the CLI **pvValidator.py**
```
$ pvValidator.py -h
usage: pvValidator.py [-h] [-V] (-d | -s IOCSERVER | -i PVFILE | -e EPICSDB [MACRODEF ...])
                        [-o CSVFILE | --stdout] [-n {prod,dev,stag} | --noapi]

EPICS PV Validation Tool (1.7.0)

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         print version and exit
  -d, --discover        discover IOC Servers and exit
  -s IOCSERVER, --server IOCSERVER
                        IOC server IP[:PORT] or GUID to get PV list (online validation)
  -i PVFILE, --inpvfile PVFILE
                        input PV list file (offline validation)
  -e EPICSDB [MACRODEF ...], --epicsdb EPICSDB [MACRODEF ...]
                        input EPICS DB file (.db) [macro definition file] (offline validation)
  -o CSVFILE, --outcsvfile CSVFILE
                        write Validation Table directly on csv file (do not start interactive session)
  --stdout              Write Validation Table directly on STDOUT (do not start interactive session)
  -n {prod,dev,stag}, --nameservice {prod,dev,stag}
                        Select Naming Service endpoint: prod(uction), dev(elopment), stag(ing) [Default=prod]
  --noapi               check only PV format and rules, skip connection to Naming Service endpoint

Copyright 2021 - Alfio Rizzo (alfio.rizzo@ess.eu)
```

For more details please see the [documentation](doc/pvvalidator.md)
