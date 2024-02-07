# pvValidator.py

Tool to validate EPICS PVs based on CHESS document [ESS-0000757](https://chess.esss.lu.se/enovia/link/ESS-0000757/21308.51166.43264.12914/valid).

**On Centos7 the installation is only via a pre-compiled pip package**

Requirements: `Python3` and `pip3`

`pip3 install pvValidatorUtils -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user`


**Requirements for compilation from sources for newer Linux distributions or WSL**:
- python recommended version >=3.8
- python3 development tool ( `python3-dev(el)` )
- python setuptools module
- c++
- swig ( http://www.swig.org ), you can install it via `apt` (Debian-based distros, e.g. Ubuntu) or `dnf` (Red Hat-based distros, e.g. Fedora)
- EPICS 7
- `cmake` (version >=3.0)
- Optional (only for developers)
  - `pytest`
  - `run-iocsh` ( `pip install run-iocsh -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user` )

**Compilation**
- Create a directory called e.g. `build`, preferably outside the local git cloned repo (e.g. `mkdir /tmp/build`)

- Source your EPICS environment

- Go into  the `build` directory and launch

  `cmake <PATH_TO_YOUR_GIT_CLONE_DIR>`

- In some Linux distribution (e.g. Debian) as default is required to create a virtual environment to install externally mananged packages ([PEP 688](https://peps.python.org/pep-0668)), to skip the creation of the virtual environment add this option in the cmake

  `cmake -DNO_PIP_ENV=1 <PATH_TO_YOUR_GIT_CLONE_DIR>`
- If you want to compile against a different version of `python` that the one found in the build check in the first place add

  `cmake <PATH_TO_YOUR_GIT_CLONE_DIR> -DMY_PYTHON_VERSION=X.Y` (e.g. `-DMY_PYTHON_VERSION=3.7`)
- If you need to compile with the C++ 11 option add the following

  `cmake <PATH_TO_YOUR_GIT_CLONE_DIR> -DCMAKE_CXX_STANDARD=11`
- If the build check is ok, then you can do
  - `make` and `make install` or directly
  - `make install` (It will do a local installation of the python modules).

- Optional (for test running)
  - `ctest -V`


Then you can run the CLI **pvValidator.py**
```
$ pvValidator.py -h
usage: pvValidator.py [-h] [-v] (-d | -s IOCSERVER | -i PVFILE | -e EPICSDB [MACRODEF ...])
                        [-o CSVFILE | --stdout] [-n {prod,dev,stag} | --noapi]

EPICS PV Validation Tool (1.7.0)

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         print version and exit
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
