# Contributing to pvValidator

## Setup

### Docker (recommended)

```bash
docker build -t pvvalidator .
docker run -it -v $(pwd):/app pvvalidator bash
```

### From source

Requires Python 3.8+, SWIG, CMake 3.0+, EPICS 7.

```bash
source /path/to/epics/environment
mkdir build && cd build
cmake -DMY_PYTHON_VERSION=3.10 ..
make install
pip install -e ".[test]"
```

## Running Tests

```bash
# All offline tests (default)
pytest test/ -v -k "not backend and not pvepics and not test_all"

# Specific test file
pytest test/test_parser.py -v

# With ESS network access
pytest test/ -v --ess-network
```

## Project Structure

```
pvValidatorUtils/
├── pvValidator.py      CLI entry point
├── pvUtils.py          Orchestrator (legacy, being migrated)
├── parser.py           PV name parser (pure Python)
├── rules.py            Validation rules (pure Python)
├── naming_client.py    ESS Naming Service API client
├── exceptions.py       Exception hierarchy
├── rule_loader.py      YAML rule configuration
├── reporter.py         JSON/HTML report generators
├── tabview.py          curses TUI (legacy)
├── data/
│   ├── rules/ess-0000757-rev10.yaml
│   └── standard_properties.yaml
└── web/
    └── index.html      Standalone web UI
```

## Adding a New Validation Rule

1. Add the rule to `data/rules/ess-0000757-rev10.yaml` with an ID, severity, and reference
2. Implement the check function in `rules.py`
3. Add it to `SINGLE_PV_RULES` list in `rules.py`
4. Write parametrized tests in `test/test_rules.py`
5. Wire it into `pvUtils._checkStructuralRules()` if it should run in the legacy pipeline

## Recording VCR Cassettes

See `test/cassettes/HOW_TO_RECORD.md` for instructions on recording API responses from the ESS Naming Service.

## Code Style

- Python: PEP 8, enforced by flake8 and black
- C++: clang-format
- Code style: enforced by flake8 and black
