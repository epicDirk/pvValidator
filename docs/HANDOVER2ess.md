# pvValidator — Handover to ESS Network Machine

**Date:** 2026-03-26
**From:** Dirk Nordt (dirk.nordt@esss.se) + Claude Code
**To:** New Claude Code session on ESS-network machine
**Location of project:** `C:\Users\dirkn\Documents\pvValidator` (entire folder copied)

---

## IMPORTANT: Where You Are vs. Where This Was Built

**This project was developed on an EXTERNAL Windows PC (Dirk's home/laptop machine) WITHOUT access to the ESS network.** That means:

- **The ESS Naming Service** (naming.esss.lu.se) was NOT reachable during development
- **No real IOC** was available for live testing
- **The `test_all` test** has NEVER passed (it requires ESS network → always errored)
- **The `test:api` GitLab CI job** was never triggered (needs `ess-network` runner tag)
- **VCR cassettes** were recorded earlier on an ESS machine (dirknordt@CI0021478), not during this session
- **Docker was available** on the external PC — all 370 tests ran in Docker containers

**You are now on an ESS-network machine.** This means:

- ✅ `naming.esss.lu.se` is reachable → you can run ALL tests including online validation
- ✅ Real IOCs may be accessible → you can test `pvValidator -s <IOC_IP>`
- ✅ ESS GitLab (`gitlab.esss.lu.se`) is reachable → you can test the CI pipeline
- ✅ ESS Artifactory is reachable → conda packages install without issues
- ⚠️ **Docker may or may NOT be installed on this machine** — see section below

### Docker Situation

On the external PC, Docker Desktop was installed and all testing happened inside Docker containers (the `Dockerfile` at the project root builds a full e3/EPICS environment with SWIG compilation).

**On this ESS machine, Docker may not be available.** Check first:
```bash
docker --version
```

**If Docker IS available:**
```bash
cd C:\Users\dirkn\Documents\pvValidator
docker build -t pvvalidator .
docker run --rm pvvalidator                         # offline tests
docker run --rm --network host pvvalidator \
  conda run --no-capture-output -n e3 pytest test/ -v --ess-network   # ALL tests
```

**If Docker is NOT available, you have two options:**

**Option A: Native EPICS environment (if e3 is installed on this machine)**
```bash
# Check if e3/EPICS is available
which pvValidator
# or
conda activate e3
```
If e3 is installed, you can run tests directly:
```bash
cd pvvalidator
pip install -e ".[test]"
pytest test/ -v --ess-network
```

**Option B: Install Docker (if permitted)**
```bash
# On CentOS/RHEL (typical ESS machine):
sudo yum install docker
sudo systemctl start docker
sudo usermod -aG docker $USER
# Then logout/login and use Docker as above
```

**Option C: Run only pure-Python tests (no SWIG needed)**
```bash
cd pvvalidator
pip install -e ".[test]"
pytest test/test_parser.py test/test_rules.py test/test_autofix.py \
       test/test_pict.py test/test_db_parser.py test/test_rule_loader.py \
       test/test_reporter.py test/test_fuzzing.py -v
```
This runs ~300 of the 370 tests without needing SWIG/EPICS compilation. The remaining ~70 tests (test_validator, test_naming_api, test_cassettes) need compiled SWIG modules.

---

## What Is This Project?

pvValidator validates EPICS Process Variable names against the ESS Naming Convention (ESS-0000757 Rev. 10). It was originally written by Alfio Rizzo (ESS, alfio.rizzo@ess.eu) as a single-file validator. Over 7 rounds of development with Claude Code, it has been refactored into a modular architecture with 370 tests, a Web-UI, auto-fix suggestions, educational content, and comprehensive QA.

**This is a showcase project for Claude Code at ESS.** Quality matters.

---

## What's In This Folder

```
C:\Users\dirkn\Documents\pvValidator\
├── pvvalidator/                    ← THE GIT REPO (this is where you work)
│   ├── pvValidatorUtils/           ← Python package (6 modules + C++/SWIG)
│   │   ├── parser.py              ← PV name parser (4 ESS formats)
│   │   ├── rules.py               ← All validation rules
│   │   ├── autofix.py             ← Auto-fix suggestions (4-tier, self-verifying)
│   │   ├── naming_client.py       ← ESS Naming Service REST client
│   │   ├── rule_loader.py         ← YAML rule configuration
│   │   ├── reporter.py            ← JSON + HTML report output
│   │   ├── pvUtils.py             ← Orchestrator (legacy pipeline)
│   │   ├── pvValidator.py         ← CLI entry point
│   │   ├── tabview.py             ← Legacy curses TUI
│   │   ├── __init__.py            ← Lazy SWIG import
│   │   ├── exceptions.py          ← Exception hierarchy
│   │   ├── data/rules/            ← YAML rules with Why/Fix/Examples
│   │   └── web/                   ← Web-UI + Guide + Reference + Fonts
│   ├── src/                       ← C++ source (epicsUtils, msiUtils)
│   ├── test/                      ← 370 tests (13 test files)
│   ├── docs/                      ← QA_PLAN.md, ONLINE_MODE_SETUP.md
│   ├── .github/workflows/         ← GitHub Actions CI
│   ├── .gitlab-ci.yml             ← ESS GitLab CI
│   ├── pyproject.toml             ← v2.0.0, GPL-3.0-only
│   ├── CMakeLists.txt             ← SWIG build (cmake 3.12+)
│   ├── README.md                  ← Full documentation
│   ├── CHANGELOG.md               ← All rounds + Alfio pre-fork history
│   └── CONTRIBUTING.md
│
├── input/                         ← Source material (PDFs, DOCX, web extracts, e3 mirror)
├── analysis/                      ← Extracted rules, analysis reports
├── output/                        ← Generated HTML visualizations
├── status/                        ← Project management (state, decisions, handover)
│   ├── state.md                   ← Current project state
│   ├── decisions.md               ← Architecture decision log
│   ├── feedback.md                ← Feedback log
│   ├── HANDOVER.md                ← Original handover (for context windows)
│   └── HANDOVER2ess.md            ← THIS FILE
│
└── Dockerfile                     ← e3 Docker container for building + testing
```

---

## Git Status

**Branch:** `improved` (default on GitHub, contains all our work)
**Version:** 2.0.0 (in pyproject.toml, NOT yet tagged)
**26 commits** from us on top of Alfio's original code

**Remotes:**
- `github` → `https://github.com/epicDirk/pvValidator.git` (our fork)
- `origin` → `https://gitlab.esss.lu.se/icshwi/pvvalidator.git` (Alfio's original)

**Tags:** v1.0.0 through v1.8.0 (all Alfio's). No v2.0.0 tag yet.

**Important:** Do NOT push to `origin` (Alfio's repo) without explicit permission.

### Our 26 Commits (newest first)

| Commit | Round | What |
|--------|-------|------|
| `54f0d42` | Fonts | Self-hosted WOFF2 fonts (Titillium Web + IBM Plex Mono) |
| `f78c26a` | 7k | Format guide sidebar, HTML reporter suggestions, QA plan update |
| `e02ce7d` | 7j | black + isort + flake8 formatting (ESS GitLab CI ready) |
| `41e61d4` | 7i | QA fixes: bugs, Python↔JS consistency, missing RULE_INFO entries |
| `81e797a` | — | README update (370 tests, new CLI flags) |
| `8ed9015` | 7h | guide.html — ESS Naming Convention Tutorial |
| `6f11865` | 7g | DRY _load_pv_list, reporter integration, interactive mode, annotated examples |
| `f0ec7b1` | 7f | Production readiness: version bump, logging, encoding, retry, --unsafe |
| `790706a` | 7e | reference.html + CHANGELOG with pre-fork history |
| `013c488` | 7d | Web-UI: expandable error details, fix buttons, format diagnosis |
| `6795e05` | — | CHANGELOG update |
| `5f021b0` | 7c | YAML educational content (why/fix/examples for all rules) |
| `36d6b07` | 7b | CLI: --suggest, --fix, --explain, --verbose, --debug flags |
| `12efdf5` | 7a | Autofix overhaul: self-verification, 4-tier, legacy prefix, MTCA |
| `c61a81a` | 6 | Refactoring: discoverServers split, display split, infovalidation, range-for |
| `8b45d47` | — | CHANGELOG for Round 5 |
| `7525c10` | 5 | 4 new ESS-0000757 rules + Google Fonts removed |
| `ab91ac6` | — | Document known gaps |
| `ec6d395` | — | README + CHANGELOG added |
| `e1cd69e` | 4c | pvUtils dead state cleanup |
| `5eb2653` | 4b | tabview crash fixes, test fixes, CMake hardening |
| `663535c` | 4a | SWIG %exception, epicsUtils security fixes |
| `84f0b5a` | 3 | Security (OWASP 32 findings), accessibility, PICT tests |
| `8ffd2ba` | 2.1 | Autofix hardening, 20/25-char alignment |
| `7f0b79a` | 2 | Auto-fix suggestions, fuzzing, GitHub Actions |
| `998a7ea` | 1 | Modular architecture, 6 new modules, Docker, Web-UI |

---

## What You Need To Do On The ESS Machine

### Phase 1: Verify Everything Works

#### 1.1 Docker Build + Test (offline)
```bash
cd C:\Users\dirkn\Documents\pvValidator
docker build -t pvvalidator .
docker run --rm pvvalidator
```
**Expected:** 370 passed, 2 deselected, 1 error (test_all = no ESS network in Docker)

#### 1.2 Docker with ESS Network
```bash
docker run --rm --network host pvvalidator conda run --no-capture-output -n e3 \
  pytest test/ -v --ess-network
```
**Expected:** ALL tests pass including test_all, test_backend, test_pvepics (if IOC available)

**This is the test that has NEVER been run** — we didn't have ESS network access.

#### 1.3 CLI Tests on ESS Network
```bash
# Enter the Docker container
docker run -it --network host pvvalidator bash

# Online validation against real IOC (if available)
pvValidator -s <IOC_IP>

# Online validation with Naming Service
pvValidator -i test/pvlist_ok.txt -n prod

# Test new CLI flags
pvValidator --suggest --noapi -i test/pvlist_rule.txt
pvValidator --fix --noapi -i test/pvlist_rule.txt
pvValidator --explain PROP-SP
pvValidator --format json --noapi -i test/pvlist_ok.txt
```

#### 1.4 Naming Service Connectivity
```bash
# From ESS network (NOT Docker)
curl -s https://naming.esss.lu.se/rest/parts/mnemonic/DTL | python -m json.tool
```
**Expected:** JSON response with DTL system data.

#### 1.5 Record Fresh VCR Cassettes
The existing cassettes were recorded earlier. Record fresh ones from the current Naming Service state:
```bash
docker run -it --network host pvvalidator bash
cd test
bash record_cassettes.sh
# Or: python record_cassettes.py
```
Then copy the updated `cassettes/naming_service_prod.json` out and commit.

---

### Phase 2: Verify Git Documentation

Check that everything on GitHub matches what's in the code:

#### 2.1 README.md
- [ ] Test count says 370 — match?
- [ ] CLI examples work as documented
- [ ] Exit codes (0/1/10) are correct
- [ ] Documentation section lists guide.html, reference.html, index.html

#### 2.2 CHANGELOG.md
- [ ] All 7 rounds documented
- [ ] Pre-fork history (v1.1.0–v1.8.0) present
- [ ] Known gaps section (PROP-7, ELEM-3/4)

#### 2.3 guide.html
- [ ] Opens in browser, all 6 sections render
- [ ] Interactive PV diagram works (click segments)
- [ ] Quiz works
- [ ] ESS infrastructure links are correct (CHESS, Naming Service, e3, Artifactory)
- [ ] Fonts load (Titillium Web visible, not system fallback)

#### 2.4 reference.html
- [ ] All tables render correctly
- [ ] "New to ESS naming?" link to guide.html works
- [ ] Fonts load correctly

#### 2.5 index.html (Web-UI)
- [ ] Load Examples → annotated comments visible
- [ ] Click error badge → Why/Fix panel expands
- [ ] "Fix" button on auto-fixable errors works
- [ ] "Fix All" button works
- [ ] "Format Guide" button opens sidebar
- [ ] "ESS-0000757 Rev. 10" tag links to guide.html
- [ ] Format diagnosis shows specific error (not just "Invalid Format")
- [ ] Fonts load (Titillium Web + IBM Plex Mono, not system)

#### 2.6 pyproject.toml
- [ ] Version: 2.0.0
- [ ] License: GPL-3.0-only
- [ ] Authors: Alfio Rizzo + Dirk Nordt
- [ ] Package-data includes `web/**/*` (for fonts)

---

### Phase 3: ESS-Specific Testing (ONLY possible on ESS network)

These tests could NEVER be run from Windows outside ESS:

#### 3.1 Full Naming Service Validation
```bash
# Create a file with known ESS PV names
echo -e "DTL-010:EMR-TT-001:Temperature\nPBI-BCM01:Ctrl-MTCA-100:Status\nCWM-CWS03:WtrC-PT-011:Pressure" > /tmp/ess_pvs.txt

# Run with production Naming Service
pvValidator -i /tmp/ess_pvs.txt -n prod --stdout

# Run with test Naming Service
pvValidator -i /tmp/ess_pvs.txt -n test --stdout
```

**Expected:** All known PVs should be VALID with registered names.

#### 3.2 IOC Discovery
```bash
pvValidator -d
```
**Expected:** List of IOC servers on the ESS network (or "IOC Server(s) not available" if none broadcasting).

#### 3.3 Live IOC Validation
If an IOC is running on the ESS network:
```bash
pvValidator -s <IOC_IP:PORT>
```
This fetches the PV list from the IOC via PVAccess RPC and validates every PV.

#### 3.4 EPICS DB File Validation
```bash
# With a real .db file from an ESS IOC
pvValidator -e /path/to/real.db P=Sys-Sub:,R=Dis-Dev-Idx:
```

#### 3.5 Substitution File Validation
```bash
pvValidator -m /path/to/real.substitutions /path/to/templates
```

#### 3.6 GitLab CI Pipeline
If you have access to the ESS GitLab Runner:
```bash
# Push to a test branch on origin (Alfio's repo) or a fork
git push origin improved:test-ci-pipeline
```
Check that the `lint`, `build`, `test:offline`, and `test:api` stages pass.

---

### Phase 4: Additional QA

#### 4.1 Security Verification
```bash
# Verify no external font requests
# Open index.html in Chrome → DevTools → Network tab → should show ONLY local fonts

# Verify no hardcoded credentials
grep -rn "password\|secret\|token\|api_key" pvValidatorUtils/ --include="*.py"
# Expected: 0 matches
```

#### 4.2 Flake8 + Black Verification
```bash
pip install black isort flake8
black --check --target-version py310 pvValidatorUtils/ test/
isort --check --profile black pvValidatorUtils/ test/
flake8 pvValidatorUtils/ test/ --max-line-length 120 --ignore E501,W503,E203 \
  --exclude pvValidatorUtils/epicsUtils.py,pvValidatorUtils/msiUtils.py
```
**Expected:** All clean. epicsUtils.py/msiUtils.py are excluded (SWIG-generated).

#### 4.3 Test Edge Cases
```bash
# Empty input
pvValidator --suggest --noapi -i /dev/null

# Very long PV names
echo "ABCDEFGHIJKLMNOP:EMR-TT-001:VeryLongPropertyNameThatDefinitelyExceedsTheLimits" | \
  pvValidator --suggest --noapi -i /dev/stdin

# Unicode characters (should handle gracefully)
echo "DTL-010:EMR-TT-001:Ünlaut" | pvValidator --suggest --noapi -i /dev/stdin
```

#### 4.4 Performance Test
```bash
# Generate 1000 PVs
python -c "
for i in range(1000):
    print(f'DTL-{i%100:03d}:EMR-TT-{i:03d}:Temperature')
" > /tmp/big_pvlist.txt

time pvValidator --suggest --noapi -i /tmp/big_pvlist.txt > /dev/null
```
**Expected:** < 5 seconds for 1000 PVs.

---

### Phase 5: Release Actions

After all tests pass:

#### 5.1 Tag v2.0.0
```bash
cd pvvalidator
git tag v2.0.0
git push github v2.0.0
```

#### 5.2 Merge to Master (after Dirk's approval)
```bash
git checkout master
git merge improved
git push github master
```

#### 5.3 QA Sign-Off
Open `docs/QA_PLAN.md` and fill in ALL checkboxes. This requires a human.

---

## Important Context

### ESS Infrastructure (correct names + URLs)

| System | URL | Notes |
|--------|-----|-------|
| **CHESS** (document mgmt) | `https://chess.esss.lu.se/` | ESS-0000757 lives here |
| **ESS-0000757** | `https://chess.esss.lu.se/enovia/link/ESS-0000757` | The naming convention |
| **ESS Naming Service** (prod) | `https://naming.esss.lu.se/` | Reachable from ESS network |
| **ESS Naming Service** (test) | `naming-test-01.cslab.esss.lu.se` | |
| **ESS Artifactory** | `https://artifactory.esss.lu.se/` | Public, no VPN needed |
| **e3 Documentation** | `https://e3.pages.ess.eu/` | EPICS Environment |
| **ESS GitLab** | `https://gitlab.esss.lu.se/icshwi/pvvalidator` | Alfio's original repo |
| **Our GitHub Fork** | `https://github.com/epicDirk/pvValidator` | Branch: improved |

### Known Limitations

1. **Docker DNS:** Docker containers cannot resolve `naming.esss.lu.se` even on ESS network. Use `--network host` or `--noapi`.
2. **EPICS .db Macros:** Files with `$(P)$(R)` macros cannot be validated statically. Macros must be resolved first (`-e dbfile P=Sys-Sub:,R=Dis-Dev-Idx:`).
3. **`--suggest`/`--fix`/`--format` do NOT work with `-e` or `-m`** — these flags only work with `-i` (plain text PV list). The error message explains this.
4. **SWIG-generated files** (`epicsUtils.py`, `msiUtils.py`) fail flake8 — this is expected and cannot be fixed (files are overwritten on each build).

### Git Config in Repo
```
user.email = dirk.nordt@esss.se
user.name = Dirk Nordt
```

### Project Quality Standards
- **Dirk's words:** "Das soll eine Werbung für Claude Code sein — wir können uns nicht blamieren."
- Senior-level quality expected
- Every feature must be tested
- Every rule traces back to ESS-0000757
- Status folder (state.md, decisions.md) must be kept current
- No workarounds — always fix the root cause

---

---

## Essential Source Material (input/ folder)

This folder contains everything we used to build pvValidator. It is NOT in the git repo — it's project context.

### input/ess-documents/ — THE SOURCE OF TRUTH

| File | What | Why It Matters |
|------|------|---------------|
| **ESS-0000757.docx** | The official ESS Naming Convention, Rev. 10, 33 pages | **THE reference document.** Every validation rule traces back to this. |
| ICALEPCS2023-FullStack-PLC-to-EPICS-AlfioRizzo.pdf | Alfio's ICALEPCS paper | Shows pvValidator in the PLC→EPICS integration stack |
| CCDB-Controls-Configuration-Database-ESS.pdf | CCDB architecture | Context: how PV names flow through the ESS system |
| ESS-ICS-Handbook-Carling-2016.pdf | ICS Handbook | Background on ESS EPICS infrastructure |
| ESS-Cryogenic-Controls-Design-2021.pdf | Cryo naming examples | Real-world examples (Cryo/Vac 5-digit index = legacy) |
| ICALEPCS2023-proceedings-THMBCMO11.pdf | Conference proceedings | Additional context |
| IntegratedControlSystemOverview.pdf | ICS overview | ESS control system architecture |

### input/web-extracts/ — API + Tool Documentation

| File | What |
|------|------|
| **ESS-Naming-Service-API.md** | REST API documentation (endpoints, parameters, responses) — manually extracted from naming.esss.lu.se |
| ESS-Naming-Convention-Presentation.md | Presentation slides about the naming convention |
| ESS-ICS-current-overview.md | Current ICS architecture overview |
| e3-documentation-overview.md | e3 EPICS Environment documentation |
| e3-supplementary-tools.md | e3 supplementary tools (run-iocsh, etc.) |

### input/e3-offline/ — e3 Documentation Mirror

**166 HTML files** — complete HTTrack mirror of `e3.pages.ess.eu`. Fully navigable offline. This was created because the live e3 documentation had intermittent availability issues. Open `input/e3-offline/index.html` in a browser.

---

## Essential Analysis Files (analysis/ folder)

These were created by extracting and structuring the content from ESS-0000757.docx:

| File | What | Why It Matters |
|------|------|---------------|
| **ESS-0000757-extracted.md** | Complete Pandoc extraction of the .docx | Machine-readable version of all 33 pages |
| **ESS-0000757-rules-structured.md** | All rules in table format | The structured rule reference we used to build rules.py |
| pvvalidator-analysis-report.md | Deep analysis of the original codebase | Documents what Alfio's code did and where we improved |
| research/ (5 files) | Web research results | parser-testing, swig-testing, ci-artifacts, api-testing, rule-encoding |

---

## The YAML Rule File — Heart of the Validation Engine

**File:** `pvvalidator/pvValidatorUtils/data/rules/ess-0000757-rev10.yaml`

This file defines EVERY validation rule. Each rule has:
- `id` — unique identifier (e.g., PROP-SP, ELEM-6)
- `severity` — error / warning / info
- `message` — what the user sees
- `reference` — section in ESS-0000757
- `why` — plain-English explanation (for --explain and Web-UI tooltips)
- `fix` — actionable guidance
- `example_good` / `example_bad` — correct and incorrect PV examples

**To update rules for ESS-0000757 Rev. 11:** Edit this YAML file. No code changes needed.

There's also `pvValidatorUtils/data/standard_properties.yaml` — Tables 6-10 from ESS-0000757 (standard property names and abbreviations).

---

## Output Files (output/ folder)

| File | What |
|------|------|
| ess-naming-convention.html | Interactive visualization of the naming convention (created with visualize skill) |
| architecture-before-after.html | Before/after architecture diagram showing the refactoring |

---

## Working With Dirk — Important Context

### Arbeitsstil
- **ADHS-Modus:** Explicit pressure signals when procrastinating. Don't sugarcoat.
- **Root Cause, not workarounds.** If something is broken, fix the cause. Don't patch around it.
- **Quality over speed.** "Das soll eine Werbung für Claude Code sein."
- **Senior-level expected.** Every edge case thought through. Every rule checked against ESS-0000757.
- **Status folder always current.** Update state.md and decisions.md after every significant change.
- **German** in communication, **English** in code/commits/docs.
- **Has only Git + Docker on Windows.** No Python natively installed. Docker Desktop runs.
- **ESS employee** (dirk.nordt@esss.se) at the European Spallation Source in Lund, Sweden.

### Claude Code Skills

**18 skills installed** on the original machine (`C:\Users\dirkn\.claude\skills\`). If the ESS machine has a fresh Claude Code installation, these skills may need to be reinstalled.

**Skills we USED for this project (across 2 context windows):**

| Skill | How We Used It | Which Round |
|-------|---------------|-------------|
| **docx** | Extracted ESS-0000757.docx content via Pandoc | Round 1 (Context 1) |
| **oberweb** | 5-dimensional web research: Parser Testing, SWIG compilation, CI artifacts, API testing, Rule Encoding, ESS ecosystem tools, autofix best practices (eslint/ruff/clippy/semgrep) | Round 1 + Round 7 |
| **visualize** | Created `ess-naming-convention.html` (interactive visualization with live PV parser) and `architecture-before-after.html` | Round 1 (Context 1) |
| **oberscribe** | README.md professionally rewritten, tone of voice guidance for error messages | Round 1 + Round 7 |
| **frontend-design** | Web-UI built from scratch (Titillium Web, ESS brand colors, live validation, expandable panels, fix buttons, format guide sidebar) | Round 1 + Round 7 |
| **design-auditor** | Web-UI audited against 18 professional design rules (WCAG accessibility, contrast, touch targets, semantic HTML, focus styles) | Round 3 |
| **oberagent** | Agent dispatch for Explore/Plan/Search agents throughout development | All rounds |

**Skills we PLANNED to use but didn't get to:**

| Skill | Status | Recommendation |
|-------|--------|---------------|
| **ux-writing** (github.com/content-designer/ux-writing-skill) | Never installed | **Should be installed and applied** to all RULE_INFO texts in Web-UI, YAML why/fix content, guide.html, and reference.html for professional microcopy quality |
| **simplify** | Planned for code redundancy check | Run `/simplify` on autofix.py, pvValidator.py, pvUtils.py |
| **OWASP Security** (agamm/claude-code-owasp) | We did the audit manually with 3 parallel agents (32 findings, 10 fixed) but didn't use the dedicated skill | Could re-run with dedicated skill for completeness |
| **Trail of Bits** (trailofbits/skills) | C++ memory safety audit done manually | Could verify with dedicated skill |
| **pypict** (omkamal/pypict-claude-skill) | We generated PICT tests manually (67 test cases) | Done — skill not needed anymore |
| **design-for-ai** (ryanthedev/design-for-ai) | Applied manually (rule reference tooltips, progressive disclosure) | Done — skill not needed anymore |
| **design-lenses** (andrejkanuch/design-lenses) | Never used | Optional — design review framework |

**Skills the ESS window SHOULD use for review + QA:**

| Skill | Task | When | Priority |
|-------|------|------|----------|
| **design-auditor** | Run full audit on index.html, guide.html, reference.html — verify A11y, contrast, touch targets, focus styles, dark patterns after all Round 7 changes | Phase 5 (Verify Docs) | HIGH |
| **oberscribe** | REVIEW mode on all user-facing text: YAML why/fix content, RULE_INFO map in index.html, guide.html body text, reference.html — flag anything that sounds robotic or unclear | Phase 5 | HIGH |
| **ux-writing** | **INSTALL FIRST** (`/install github.com/content-designer/ux-writing-skill`). Then apply to every error message, every Why/Fix text, every tooltip. Checks: purposeful, concise, conversational, clear. This was planned but never done. | Phase 5 | HIGH |
| **simplify** | Run `/simplify` on the 5 most-changed files: `autofix.py`, `pvValidator.py`, `pvUtils.py`, `rules.py`, `index.html` — find redundancies, dead code, opportunities to simplify | Phase 6 (QA) | MEDIUM |
| **oberweb** | Research any ESS-specific issues found during testing (e.g., new Naming Service API changes, e3 updates, PLC Integrator status) | As needed | LOW |
| **frontend-design** | If any Web-UI issues are found during review, use this skill to fix them properly | As needed | LOW |

**Skills to INSTALL on the ESS machine (not currently installed):**

```bash
# Essential for this review:
/install github.com/content-designer/ux-writing-skill

# Optional but recommended:
/install github.com/agamm/claude-code-owasp          # Re-run OWASP security audit
/install github.com/trailofbits/skills                # C++ memory safety verification
```

**Skills installed but NOT needed for this project:**
`antireal-deck`, `humanizer-de`, `knowledge-graph-visualizer`, `marketing`, `obercreate`, `oberprompt`, `obershot`, `pptx`, `skill-creator`, `taxaccon-interview`

**To reinstall skills on the new machine** (if needed):
```bash
# Check what's installed
ls ~/.claude/skills/

# Install a skill from GitHub
/install github.com/content-designer/ux-writing-skill
```

### Dragon Brain (Memory MCP)
Check if Dragon Brain is available:
```bash
docker compose -f "C:/Users/dirkn/Documents/Dragon Brain/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}"
```
If running, start a session:
```
reconnect()
start_session(project_id="coding", focus="pvValidator ESS deployment + QA")
```

### CLAUDE.md Instructions
Global instructions are in `C:\Users\dirkn\.claude\CLAUDE.md`. Read them — they contain important rules about status folders, Dragon Brain logging, German text (use Unicode Umlauts), and skill usage.

---

## Files You MUST Read (in this order)

1. **This file** (`HANDOVER2ess.md`) — you're reading it
2. **`status/state.md`** — current project state (version, tests, commits)
3. **`pvvalidator/README.md`** — user-facing documentation, architecture
4. **`pvvalidator/CHANGELOG.md`** — what changed in each round (1-7)
5. **`status/decisions.md`** — WHY things were done the way they were
6. **`pvvalidator/docs/QA_PLAN.md`** — the sign-off checklist you need to complete
7. **`analysis/ESS-0000757-rules-structured.md`** — the structured rules (your reference for validation logic)
8. **`pvvalidator/pvValidatorUtils/data/rules/ess-0000757-rev10.yaml`** — the actual rule definitions with educational content

### Your Action Plan (START HERE after reading)
9. **`status/PLAN-ESS-NETWORK.md`** — Step-by-step plan for what to do on this ESS machine. 7 phases: Environment Setup → Run All Tests → Live ESS Validation → GitLab CI → Verify Docs → QA Sign-Off → Release. **This is your work queue.**

### Files You Should Skim
- `pvvalidator/docs/ONLINE_MODE_SETUP.md` — ESS network setup guide
- `input/web-extracts/ESS-Naming-Service-API.md` — the REST API you'll be testing against
- `status/HANDOVER.md` — the original handover doc (for context window switches, older but has detailed technical context)
