# pvValidator

Validates EPICS Process Variable names against the ESS Naming Convention ([ESS-0000757](https://chess.esss.lu.se/enovia/link/ESS-0000757)).

pvValidator catches naming mistakes before they reach production. It checks format, property rules, and registration against the ESS Naming Service. Point it at a running IOC or feed it files. It'll tell you what's wrong.

## What It Checks

**Format.** All four valid ESS structures: `Sys-Sub:Dis-Dev-Idx:Property`, `Sys:Dis-Dev-Idx:Property`, `Sys-Sub::Property`, `Sys::Property`.

**Property rules.** Length limits (60 chars total, 25 chars property). Suffix enforcement (`-SP` for setpoints, `-RB` for readbacks). Confusable character detection: `I`/`l`/`1`, `O`/`0`, `VV`/`W`, leading zeros. Duplicate properties within the same device.

**Structure elements.** System, Subsystem, Discipline, Device: max 6 characters, alphanumeric, must start with a letter.

**Device index.** Scientific style (1-4 digits) and P&ID style (3 digits + optional lowercase).

**Naming Service.** Checks whether the ESS name is registered and `ACTIVE` in the production or test Naming Service.

Each rule traces back to a specific section of ESS-0000757. Rules live in a YAML file, so updating to a new revision doesn't require code changes.

## Quick Start

**Pre-compiled (CentOS7):**
```bash
pip3 install pvValidatorUtils \
  -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple --user
```

**From source** (needs Python 3.8+, SWIG, CMake 3.12+, EPICS 7, C++ compiler):
```bash
source /path/to/epics/environment
mkdir build && cd build
cmake -DMY_PYTHON_VERSION=3.10 /path/to/pvvalidator
make install
```

**Docker** (recommended for development):
```bash
docker build -t pvvalidator .
docker run pvvalidator              # run tests
docker run -it pvvalidator bash     # interactive shell
```

The Docker image uses the official e3 setup: conda-forge for EPICS base, ESS Artifactory for `require` and ESS-specific packages.

## Usage

```bash
# Online: validate PVs from a running IOC
pvValidator -s 172.30.6.12

# Offline: validate from a text file
pvValidator -i pvlist.txt

# Offline: validate from an EPICS database with macros
pvValidator -e myioc.db P=Sys-Sub:,R=Dis-Dev-Idx:

# Offline: validate from a substitution file
pvValidator -m myioc.substitutions /path/to/templates

# Format and rules only (skip Naming Service)
pvValidator -i pvlist.txt --noapi

# Write results to CSV
pvValidator -i pvlist.txt -o results.csv

# Auto-fix: show suggestions for all violations
pvValidator -i pvlist.txt --suggest --noapi

# Auto-fix: apply safe fixes automatically
pvValidator -i pvlist.txt --fix --noapi

# Explain a specific rule
pvValidator --explain PROP-SP

# JSON output with fix suggestions
pvValidator -i pvlist.txt --format json --noapi
```

**Exit codes:** 0 = all valid, 1 = validation errors found, 10 = EPICS/system error.

## Documentation

Three standalone HTML documents are included in `pvValidatorUtils/web/`:

- **[guide.html](pvValidatorUtils/web/guide.html)** &mdash; Tutorial for new users. Explains ESS-0000757, PV name anatomy, formats, property rules, common mistakes, and ESS tools.
- **[reference.html](pvValidatorUtils/web/reference.html)** &mdash; Quick reference cheat sheet. All rules in one page.
- **[index.html](pvValidatorUtils/web/index.html)** &mdash; Interactive Web-UI with live validation, expandable error explanations, and one-click auto-fix.

## Architecture

```
CLI (pvValidator.py)
 └── Orchestrator (pvUtils.py)
      ├── Parser (parser.py)               4 ESS format types, PVComponents dataclass
      ├── Rules (rules.py)                 All validation rules, O(n) duplicate check
      ├── Naming Client (naming_client.py) ESS Naming Service REST API, cached
      ├── Rule Loader (rule_loader.py)     YAML rule configuration
      ├── Reporter (reporter.py)           JSON and HTML output
      └── C++/SWIG
           ├── epicsUtils                  PVAccess RPC, IOC discovery
           └── msiUtils                    Macro substitution (msi port)
```

## Testing

370 tests, all runnable without ESS network access:

```bash
# Offline tests (default)
pytest test/ -v -k "not backend and not pvepics and not test_all"

# Include ESS Naming Service tests (needs network)
pytest test/ -v --ess-network
```

Tests cover format parsing (40), validation rules (67), API mocking (28), rule loader (17), autofix (30), cassettes (24), reporter (11), hypothesis fuzzing, DB parser (21), combinatorial/PICT (67), and the original pvValidator tests (4).

## Rule Configuration

Rules are defined in `pvValidatorUtils/data/rules/ess-0000757-rev10.yaml`. Each rule has an ID, severity, message, and reference to the corresponding ESS-0000757 section.

When ESS-0000757 gets a new revision, edit the YAML. The validation engine reads it at startup. No code changes, no recompilation.

## Author

Alfio Rizzo (alfio.rizzo@ess.eu)

## License

GNU General Public License v3.0
