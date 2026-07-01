# Changelog

All notable changes to pvValidator are documented here.

## [Unreleased] — QA round 2: correctness & robustness (2026-07-01)

### Fixed
- **P0 — structural errors are now status- and exit-effective.** The classic `pvUtils`
  pipeline wrote element/index/legacy findings to `datainfo` only, so a structural error
  (e.g. ELEM-6, a 7-char System) left `VRuleD=True` and `--noapi` exited **0**. Structural
  ERROR/WARNING now flow through `_checkDataMsg` into `PVErrList`/`PVWarnList`
  (`PVErrList`/`PVWarnList` are initialised in `__init__`). *Verified: exit 1 in the real CLI.*
- **P0 — pure-Python import decoupling.** `import pvValidatorUtils.parser` no longer pulls in
  `pvUtils → tabview → curses`: `__init__` exposes `pvUtils` lazily, `curses` is guarded in
  `tabview`, and `pvValidator.py` imports SWIG lazily (a plain `-i` file needs no `epicsUtils`).
  Pure-Python modules and `--explain`/`--format`/`--suggest` now work without `_curses`/EPICS.
- **Two rule paths unified.** The classic path now also runs `check_legacy_index`,
  `check_pascal_case`, `check_mtca_naming` — same coverage as the JSON/HTML reporter.
- **Exit codes consistent across output modes.** `--format json/html` and `--suggest/--fix`
  now exit 1 when errors are present (previously always 0).
- **naming_client:** `check_connectivity()` uses `raise_for_status()` + the configured
  `timeout` (HTTP 5xx no longer counts as "reachable"); JSON shape is validated
  (dict/list mismatches raise `NamingServiceResponseError` instead of `AttributeError`);
  `_sys_cache`/`_dev_cache` are bounded; transient connection/timeout failures are **not**
  cached as "not approved"; `search_parts` tolerates malformed JSON / wrong shape → `[]`.
- **Rule-ID drift.** `LEGACY` → `LEGACY-PREFIX` (rules, autofix, web UI); `IDX-STYLE`,
  `PROP-EMPTY`, `IDX-LONG` added to the YAML so `--explain` resolves them. New
  `test_rule_id_sync.py` fails if any emitted rule ID is missing from the YAML/allowlist.
- **Property character rule** is now an allowlist (ASCII alphanumeric + `-_`), so spaces,
  tabs and non-ASCII (`Foo Bar`, `Temp°C`) are correctly flagged (were passing as VALID).
- **`--verbose` no longer hijacks `-o`/`--stdout`** (the CSV was silently not written);
  `--suggest/--fix` combined with `--format`/`-o` is now rejected with a clear error.
- **C++ MSI:** `subFile` gets a constructor (`fp=nullptr`), fixing undefined behaviour when
  `fopen()` fails and cleanup reads an uninitialised `FILE*`; `addMacroReplacements` no longer
  leaks the `macParseDefns` pairs array on the empty-definition / install-failure paths.
- **Smaller:** no-longer-spurious `PROP-3` for short known properties with `-SP`/`-RB`
  (`On-SP`); `_checkValidName` splits the system part on the first dash only (`split("-",1)`);
  reporter summary buckets partition the total (warnings-only no longer double-counted);
  the parser rejects a trailing-dash empty index; CSV output no longer crashes on empty input.

### Changed
- **Test selection is marker-based.** `test_pvepics`→`epics_ioc`, `test_backend`→`ess_network`;
  the fragile `-k "not backend and not pvepics and not test_all"` (which also dropped six
  legitimate `test_all_*` offline tests via substring match) is gone from README / GitLab CI /
  Dockerfile. `run_iocsh` is imported lazily so offline collection never breaks. New `swig`
  marker auto-skips SWIG-dependent tests where the extension is absent.
- **CI/build:** the GitLab offline job selects tests by marker (no `-k`). The local Docker build
  (outer, dev tooling — not part of this repo) was additionally hardened: base pinned to a digest,
  the editable install split into its own `RUN` so `|| true` no longer masks it (only the ESS-only
  `run-iocsh` extra may fail).
- **`test_pvprop`:** corrected the inverted, previously-dead warning assertion and added real
  warning-only PVs so the branch actually runs.

### Added
- `test/test_qa_round2.py` — regression tests for the new findings (parser, rules, naming_client,
  reporter exit/summary). `test/test_rule_id_sync.py` — YAML↔code rule-ID sync gate.

## [Unreleased] — Packaging fix + QA round (2026-07-01)

### Fixed
- **Packaging (the reported bug)**: `pyproject.toml` `package-data` was missing
  `data/**/*`, so a real (non-editable) `pip install` shipped without
  `ess-0000757-rev10.yaml` and silently fell back to the ~6-rule built-in defaults.
  Added `data/**/*`, `include-package-data`, and a `MANIFEST.in` so **both** wheel and
  sdist ship the rule data; constrained `packages.find` to `pvValidatorUtils*`
  (`test/` no longer leaks into the wheel).
- **Package import**: guarded the `msiUtils` SWIG import (importing the *module*, so
  `pvUtils` can call `msiUtils.msiUtils(...)`) so the package imports without compiled
  SWIG — fixes the pure-Python CI, which previously errored at collection (last two runs
  were red).
- **test_validator**: mark `test_all` as `ess_network` — it queries the Naming Service,
  so `docker run --rm pvvalidator` (offline) no longer fails on it; it now skips cleanly.
- **CI**: the `test-results` artifact upload was accidentally attached to the `test-distribution`
  job (which has no matrix and produces no junit XML) — moved it back under `test-pure-python`.

### Changed
- **pyproject.toml**: modern SPDX license expression (`GPL-3.0-only`), dropped the
  deprecated GPL classifier, pinned `requests`/`pyyaml` floors, single author entry.
  Build now emits zero setuptools deprecation warnings.
- **naming_client.py**: bounded response caches, `close()`/context-manager,
  malformed-JSON handling, distinct connection-vs-HTTP logging.
- **PV-list input**: read files as `utf-8-sig` (tolerate a leading BOM from Windows editors).
- **LEGACY_PREFIXES**: single source of truth in `rules.py` (autofix now imports it
  instead of keeping its own copy).

### Added
- `test/test_packaging.py` + CI jobs (GitHub `test-distribution`, GitLab `test:dist`)
  that build the real wheel/sdist and assert the rule YAML is bundled — the gate that
  would have caught the reported bug.
- Regression tests: HTML-report escaping, builtin-defaults↔YAML sync, v1.8.0
  backwards-compatibility, naming-client robustness.
- `docs/ESS-RESOURCES.md` (naming API repos, e3 env versions, artifactory), linked from
  CONTRIBUTING; fixed the documented CMake version (3.0+ → 3.12+).

## [2.0.0] — 2026-03-30

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

## [Round 7] — 2026-03-26 (in progress)

### Added
- **Autofix self-verification** (Semgrep pattern): every suggestion is validated before
  being shown — fixes that introduce new ERRORs are automatically downgraded to MANUAL
- **Four-tier applicability model**: Safe / Suggested / Template / Manual (Ruff/Clippy-inspired)
- **New autofix rules**: Legacy prefix stripping (Cmd_, P_, FB_, SP_), MTCA index zero-padding
- **CLI flags**: `--suggest` (show fix suggestions), `--fix` (apply safe fixes),
  `--explain RULE_ID` (show full rule documentation), `--verbose` (detailed output)
- **Educational YAML content**: every rule now has `why`, `fix`, `example_good`, `example_bad`
  fields accessible via `--explain` and Web-UI tooltips
- 23 new autofix tests (391 total)

### Changed
- `FixSuggestion.auto_fixable` is now a computed property based on `applicability` tier
- `Applicability` enum replaces boolean `auto_fixable` parameter

### Web-UI
- Expandable error details: click any badge to see Why + Fix explanation
- "Fix" buttons on auto-fixable errors (suffix, case, legacy prefix)
- "Fix All" toolbar button applies all safe fixes at once
- Format diagnosis: "Invalid Format" now shows specific cause
- Missing JS rules synced: PROP-5, PROP-2-WARN, LEGACY-5DIGIT, EXC-MTCA
- RULE_INFO map with educational content for all rules

### Documentation
- `reference.html`: standalone interactive ESS PV Naming Quick Reference
  (formats, elements, index, property rules, suffixes, confusables,
  standard abbreviations, common mistakes)

## [Round 6] — 2026-03-26

### Changed
- epicsUtils.cxx: split discoverServers (250 LOC) into createDiscoverySocket,
  buildBroadcastList, receiveResponses sub-methods
- epicsUtils.cxx: all fprintf(stderr) → EPICS LOG macros, strncmp → std::string
- tabview.py: split display() into _render_header_bar + _render_table
- pvUtils.py: infovalidation string-concat → list + join pattern
- test_validator.py: private method calls → run() end-to-end tests

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

---

## Pre-Fork History (by Alfio Rizzo)

### [1.8.0] — 2024-11-18
- Removed .py extension from CLI entry point
- Added msiUtils C++ code (msi modification for substitution files)
- Added input substitution file support
- Added related tests, improved code readability

### [1.7.0] — 2024-02-08
- Updated for ESS Naming Convention Rev. 9
- Optimized code, removed Makefile built-in, changed packaging tool
- Added unit tests, removed staging/development naming service endpoints

### [1.6.0] — 2023-03-03
- Added error verbosity when a Name is canceled or modified in the Naming Service

### [1.5.0] — 2022-06-23
- Added --stdout option, added exit code

### [1.4.0] — 2022-02-03
- Improved code speed (caching API check for System and Device Structure)
- Fixed multiple leading-zero regex bugs (1.4.1, 1.4.2, 1.4.3)

### [1.3.0] — 2021-04-09
- Added option to read EPICS DB files
- Added CMakeLists.txt, skip comments when parsing .db files

### [1.2.0] — 2021-03-26
- Added comment option on input PV file, added documentation

### [1.1.0] — 2021-03-03
- Added Naming Server option endpoint (Production, Development, Staging)
