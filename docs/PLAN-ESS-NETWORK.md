# Plan: ESS Network Deployment + Verification + QA

**For:** New Claude Code context window on ESS-network machine
**Read FIRST:** `status/HANDOVER2ess.md` — the full project briefing

---

## Context

This project was developed on an external Windows PC WITHOUT ESS network access. Everything was tested in Docker containers. The following things have NEVER been tested with the real ESS infrastructure:

- ❌ Full test suite with `--ess-network` flag (test_all, test_backend always failed)
- ❌ Live Naming Service validation (naming.esss.lu.se was unreachable)
- ❌ Live IOC discovery and validation (`pvValidator -s` / `pvValidator -d`)
- ❌ EPICS DB file validation with real .db files from ESS IOCs
- ❌ Substitution file validation with real .substitutions files
- ❌ ESS GitLab CI pipeline (needs `ess-network` runner tag)
- ❌ Fresh VCR cassette recording from current Naming Service state
- ❌ Correct behavior of retry logic with the real Naming Service

**Your job:** Run everything that couldn't be run before, fix anything that breaks, and prepare the v2.0.0 release.

---

## Phase 1: Environment Setup (do this first)

### 1.1 Check what's available
```bash
docker --version          # Docker available?
conda --version           # Conda available?
which pvValidator         # pvValidator already installed?
python --version          # Python version?
ping naming.esss.lu.se    # ESS Naming Service reachable?
curl -s https://naming.esss.lu.se/ | head -5   # API responds?
```

### 1.2 Build environment
**If Docker is available (preferred):**
```bash
cd /path/to/pvValidator
docker build -t pvvalidator .
```

**If no Docker but conda/e3:**
```bash
cd pvvalidator
pip install -e ".[test]"
```

**If nothing:** See HANDOVER2ess.md "Docker Situation" section for alternatives.

---

## Phase 2: Run All Tests (the tests that NEVER ran)

### 2.1 Full test suite with ESS network
```bash
# In Docker:
docker run --rm --network host pvvalidator \
  conda run --no-capture-output -n e3 pytest test/ -v --ess-network --tb=short

# Or natively:
pytest test/ -v --ess-network --tb=short
```

**Expected:** ALL 370+ tests pass. If test_all fails, check the CSV output path.

### 2.2 Record fresh VCR cassettes
```bash
# In Docker:
docker run -it --network host pvvalidator bash
cd test
bash record_cassettes.sh
# Copy updated cassettes out:
exit
docker cp <container_id>:/app/test/cassettes/naming_service_prod.json test/cassettes/

# Or natively:
cd test
python record_cassettes.py
```

### 2.3 Re-run tests with fresh cassettes
```bash
pytest test/test_cassettes.py -v
```

---

## Phase 3: Live ESS Validation (never done before)

### 3.1 Naming Service: Known PVs
```bash
# These PVs should be registered in the prod Naming Service:
echo -e "DTL-010:EMR-TT-001:Temperature\nPBI-BCM01:Ctrl-MTCA-100:Status\nCWM-CWS03:WtrC-PT-011:Pressure" > /tmp/known_pvs.txt
pvValidator -i /tmp/known_pvs.txt -n prod --stdout
```
**Expected:** All three VALID with registered names.

### 3.2 Naming Service: Test endpoint
```bash
pvValidator -i /tmp/known_pvs.txt -n test --stdout
```

### 3.3 IOC Discovery
```bash
pvValidator -d
```
**Expected:** List of IOC servers on ESS network, or "not available" if none broadcasting.

### 3.4 Live IOC Validation (if an IOC is found)
```bash
pvValidator -s <IOC_IP:PORT>
```

### 3.5 New CLI features with real data
```bash
pvValidator --suggest -i /tmp/known_pvs.txt -n prod
pvValidator --fix -i /tmp/known_pvs.txt --noapi
pvValidator --explain PROP-SP
pvValidator --format json -i /tmp/known_pvs.txt -n prod
pvValidator --format html -i /tmp/known_pvs.txt -n prod > /tmp/report.html
```

### 3.6 Real EPICS DB files (if available)
Find a real .db file from an ESS IOC:
```bash
find /opt -name "*.db" 2>/dev/null | head -5
# or
find $EPICS_BASE -name "*.db" 2>/dev/null | head -5
```
Then validate:
```bash
pvValidator -e /path/to/real.db P=RealSys-RealSub:,R=RealDis-RealDev-RealIdx: --noapi --stdout
```

---

## Phase 4: ESS GitLab CI Pipeline

### 4.1 Test the pipeline (if you have GitLab access)
```bash
cd pvvalidator
# Push to a test branch on YOUR fork (not Alfio's origin!)
git push github improved:test-ci-run
```
Or if you have ESS GitLab fork access:
```bash
git remote add essfork https://gitlab.esss.lu.se/<your-username>/pvvalidator.git
git push essfork improved
```
Check: Does `lint` (black/isort/flake8) pass? Does `build` compile SWIG? Does `test:offline` pass? Does `test:api` pass with `ess-network` runner?

### 4.2 Fix any CI issues
If the PreCommit lint stage fails, it's likely because:
- SWIG-generated files (epicsUtils.py, msiUtils.py) fail flake8 — this is expected, but the ESS PreCommit include might not exclude them
- Solution: Add `--exclude` pattern to flake8 in the PreCommit config, or contact ESS ICS about excluding generated files

---

## Phase 5: Verify All Documentation

### 5.1 Web-UI in browser
Open `pvvalidator/pvValidatorUtils/web/index.html` in a browser and verify:
- [ ] Titillium Web font loads (check DevTools → Fonts)
- [ ] IBM Plex Mono font loads in code areas
- [ ] Load Examples → annotated comments visible
- [ ] Click error badge → Why/Fix panel expands
- [ ] "Fix" button works on auto-fixable errors
- [ ] "Fix All" button applies all safe fixes
- [ ] "Format Guide" button shows sidebar
- [ ] "ESS-0000757 Rev. 10" tag links to guide.html
- [ ] "Invalid Format" shows specific diagnosis

### 5.2 guide.html
- [ ] Opens, all 6 sections render
- [ ] Interactive PV diagram (click segments)
- [ ] Quiz works
- [ ] ESS links correct (CHESS, Naming Service, e3, Artifactory)

### 5.3 reference.html
- [ ] All tables render
- [ ] "New to ESS naming?" link works

### 5.4 README.md on GitHub
Check https://github.com/epicDirk/pvValidator — does the README render correctly?

---

## Phase 6: QA Sign-Off

Open `pvvalidator/docs/QA_PLAN.md` and go through EVERY checkbox. This document has 19 checkboxes. Fill in all of them.

---

## Phase 7: Release

After ALL of the above passes:

### 7.1 Tag v2.0.0
```bash
cd pvvalidator
git tag v2.0.0
git push github v2.0.0
```

### 7.2 Merge to master (after Dirk's explicit approval)
```bash
git checkout master
git merge improved
git push github master
```

### 7.3 Update status files
```bash
# status/state.md — set phase to "Released v2.0.0"
# status/decisions.md — add release decision entry
```

---

## If Something Breaks

The most likely issues on the ESS network:

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| test_all fails with timeout | Naming Service slow | Retry logic should handle it (3 retries). If still failing, increase timeout in naming_client.py |
| test_backend fails | PV names in apifile not registered | Check if the test PVs still exist in the Naming Service |
| SWIG compilation fails | Wrong EPICS_BASE path | `echo $EPICS_BASE` — must point to e3 installation |
| Docker DNS fails for naming.esss.lu.se | Docker networking | Use `--network host` |
| GitLab lint fails on SWIG files | ESS PreCommit includes epicsUtils.py | Exclude generated files from flake8 |
| Fonts don't load in Web-UI | fonts/ folder not next to HTML | Check relative path: `web/fonts/*.woff2` must exist |

---

## Files Modified During This Session (for git diff context)

If you need to commit anything, the branch is `improved` and the remote is `github`:
```bash
git add -A
git commit -m "ESS network verification: <describe what you did>"
git push github improved
```
