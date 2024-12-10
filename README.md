# pvValidator

Tool to validate EPICS PVs based on CHESS document [ESS-0000757](https://chess.esss.lu.se/enovia/link/ESS-0000757/21308.51166.43264.12914/valid).

**On Centos7 the installation is only via a pre-compiled pip package**

Requirements: `Python3` and `pip3`

`pip3 install pvValidatorUtils -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user`

**Platform supported**

Linux, WSL

**Requirements for compilation from sources for newer Linux distributions or WSL**
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

  `cmake -DNO_PIP_VENV=1 <PATH_TO_YOUR_GIT_CLONE_DIR>`
- If you want to compile against a different version of `python` that the one found in the build check in the first place add

  `cmake <PATH_TO_YOUR_GIT_CLONE_DIR> -DMY_PYTHON_VERSION=X.Y` (e.g. `-DMY_PYTHON_VERSION=3.10`)
- If you need to compile with the C++ 11 option add the following

  `cmake <PATH_TO_YOUR_GIT_CLONE_DIR> -DCMAKE_CXX_STANDARD=11`
- If the build check is ok, then you can do
  - `make` and `make install` or directly
  - `make install` (It will do a local installation of the python modules).

- Optional (for test running)
  - `ctest -V`


Then you can run the CLI **pvValidator**
```
 $ pvValidator -h
usage: pvValidator [-h] [-v] [-d] (-s (IP[:PORT] | GUID) | -i pvfile | -e dbfile [VAR=VALUE ...] | -m subsfile
                   [path_to_templates VAR=VALUE ...]) [-n {prod,test} | --noapi] [-o csvfile | --stdout]

EPICS PV Validation Tool (1.8.0)

options:
  -h, --help            show this help message and exit
  -v, --version         print version and exit
  -d, --discover        discover IOC servers and exit
  -s (IP[:PORT] | GUID)
                        IOC server IP[:PORT] or GUID to get PV list (online validation)
  -i pvfile             input PV list file (offline validation)
  -e dbfile [VAR=VALUE ...]
                        input EPICS db file (.db) [VAR=VALUE, ...] (offline validation)
  -m subsfile [path_to_templates VAR=VALUE ...]
                        input substitution file (.substitutions) [path_to_templates VAR=VALUE, ...] (offline validation)
  -n {prod,test}        select naming service endpoint to connect: prod(uction), test(ing) [default=prod]
  --noapi               check only PV format and rules, skip connection to naming service endpoint
  -o csvfile            write the validation table directly to CSV file
  --stdout              write the validation table directly to STDOUT

Copyright 2021 - Alfio Rizzo (alfio.rizzo@ess.eu)
```

For more details please see the [documentation](doc/pvvalidator.md)

## Author
Alfio Rizzo (alfio.rizzo@ess.eu)

## Acknowledgment

EPICS https://epics-controls.org

## License
GNU GENERAL PUBLIC LICENSE, Version 3, 29 June 2007
