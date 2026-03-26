# Changelog

All notable changes to pvValidator are documented here.

## [Unreleased] — Round 4 (2026-03-26)

### Security
- **SWIG exception handling**: Added `%exception` directive to both `.i` files — C++ exceptions now propagate as Python `RuntimeError` instead of crashing the process
- **epicsUtils.cxx**: Fixed 4 socket leak paths (SO_RCVTIMEO, getsockname, discoverInterfaces, retry-loop), signed-to-unsigned payload size validation, buffer overread protection in `deserializeString`, null `shared_ptr` guard, `addresses[0]` empty-vector guard
- **msiUtils.cxx** (Round 3): Buffer overflow bounds check in `subGetNextToken`, resource leak cleanup via try/catch in `createDB`, removed static buffer in `makeSubstitutions`, null-after-free guard

### Fixed
- **tabview.py**: Fixed 3 crash paths (narrow terminal < 120 cols, `datainfo=None` in save_csvfile, `_reverse_data` in-place mutation). Fixed `show_cell` guard that never fired, ragged CSV output, `len` builtin shadow
- **test_validator.py**: Fixed `tmpf1.read()` without seek (converted to `tmp_path` fixture), `get_lines()` missing `#` comment skip, hardcoded relative paths
- **DB parser**: Replaced fragile `r.split(",")` with regex-based `record()` extraction — fixes comma-in-field and `startswith("f"/"i")` filter bugs
- **pvValidator.py**: `sys.exit()` replaced with `raise SystemExit(0)` in DiscoverAction
- **epicsUtils.cxx**: Preserved original GUID in error message, extracted duplicate broadcast send code into `sendBroadcast` helper

### Changed
- **CMakeLists.txt**: Minimum CMake version raised to 3.12, added `EPICS_HOST_ARCH` validation, set C++11 standard explicitly
- **pvUtils.py**: Removed dead state (`self.pattern`, `self.headers`, `self.empty`, `self.urlparts`, `self.urlname`), simplified `exist`/`notexist` int sentinels to booleans, eliminated double `parse_pv()` call, removed Python < 3.8 compatibility branch
- **__init__.py**: Lazy SWIG import (try/except with `epicsUtils = None` fallback), removed Python < 3.8 branch
- **reporter.py**: Uses `html.escape(s, quote=True)` instead of manual escaping
- **naming_client.py**: URL-encodes mnemonics before appending to API URLs

### Added — Round 3 (2026-03-26)
- **Web-UI accessibility**: Screen reader label, aria-labels on icon buttons, skip-to-content link, `:focus-visible` styles, contrast fix (#6B7186, WCAG AA 4.6:1), touch targets (44px), semantic `<main>` element
- **Web-UI security**: Rule IDs escaped via `esc()`, 1 MB file size limit, ESS-0000757 rule reference tooltips on all error badges
- **pvUtils.py**: 20-character SHOULD warning, Known Short Properties exception (On/Off/Ok), `effective_property_length()` for < 4 check
- **test_db_parser.py**: 21 tests for regex-based EPICS DB record extraction
- **test_pict.py**: 67 combinatorial (pairwise) tests across Format, ElementLen, PropLen, Suffix, StartChar, Confusable dimensions
- **test_records.db**: Test fixture with edge cases (comma in field, fanout/int64in record types, commented records)

### Removed
- Dead Python 2 compatibility code in tabview.py (3 instances)
- Dead `location_string` branches and `lc_all` in tabview.py
- Hardcoded year "2021" in tabview.py TUI footer

## [Round 5] — 2026-03-26

### Added
- **LEGACY-5DIGIT**: Warn on 5-digit index in Cryo/Vacuum disciplines (Annex C)
- **PROP-5**: Warn on ALL_CAPS/all_lowercase properties (PascalCase recommended, §6.2 Rule 5)
- **EXC-MTCA**: Validate MTCA controller 3-digit index pattern (Annex A)
- **EXC-TGT**: Target Station subsystem length exception — INFO instead of ERROR (Annex B)
- 25 new tests for all new rules (347 total)

### Changed
- Web-UI: Removed Google Fonts external dependency (privacy + true offline mode)
- epicsUtils.cxx: Modernized 4 C++03 iterator loops to range-for
- tabview.py: `string.printable` → `str.isprintable()`
- pvUtils.py: Removed unused pv2/err2 parameters from `_checkDataMsg`

### Known Gaps (ESS-0000757 rules not yet implemented)
- **PROP-7**: No units in property names (SHALL NOT) — cannot be checked statically
- **ELEM-3/4**: Subsystem/Device uniqueness across project — checked via Naming Service API only

## [Round 2] — 2026-03-25

### Added
- Auto-fix suggestions (autofix.py) with convention-checked hardening
- Hypothesis property-based fuzzing (test_fuzzing.py)
- GitHub Actions CI (.github/workflows/test.yml)

### Fixed
- `sys.exit()` removed from pvUtils.py (4 locations, replaced with exceptions)
- C++ `_Exit(10)` replaced with `throw` in epicsUtils.cxx (6 locations)
- Property length: `-SP`/`-RB` suffix correctly excluded from 25-char limit

## [Round 1] — 2026-03-25

### Added
- 6 new Python modules: parser.py, rules.py, naming_client.py, exceptions.py, rule_loader.py, reporter.py
- Test infrastructure: conftest.py, fixtures, API mocking, VCR cassettes
- Docker e3 container (conda-forge + ESS Artifactory)
- Web-UI (Titillium Web, ESS brand colors, live validation)
- YAML rule configuration (ess-0000757-rev10.yaml)
- CI/CD: .gitlab-ci.yml + .github/workflows/test.yml
- README.md, CONTRIBUTING.md, QA_PLAN.md, ONLINE_MODE_SETUP.md

### Fixed
- 6 bug fixes: typos (LENGHT), copy-paste bug (errmsgpv2), docstring typos, dead code (HasAlias), duplicate function (inputAddPath), missing timeout
