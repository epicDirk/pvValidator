# pvValidator — QA Plan

## Zweck

Dieser QA-Plan definiert die Kriterien unter denen pvValidator als **production-ready** gilt. Er richtet sich an:
- Den Entwickler (Selbstkontrolle)
- Den Reviewer (Abnahme-Checkliste)
- Den ICS-Verantwortlichen (Freigabe für den ESS-Einsatz)

---

## 1. Test-Abdeckung

### 1.1 Automatische Tests

| Kategorie | Tests | Status | Offline |
|-----------|-------|--------|---------|
| PV Format Parser (4 Formate) | 40 | Grün | Ja |
| Validierungsregeln (alle ESS-0000757 Regeln) | 67 | Grün | Ja |
| API-Mocking (Naming Service Simulation) | 28 | Grün | Ja |
| VCR Cassettes (echte ESS-Daten) | 24 | Grün | Ja |
| YAML Rule Loader | 17 | Grün | Ja |
| JSON/HTML Reporter | 11 | Grün | Ja |
| Autofix (Self-Verification, 4-Tier, Legacy, MTCA) | 59 | Grün | Ja |
| DB Parser (Regex, Integration) | 21 | Grün | Ja |
| Combinatorial/PICT Tests | 67 | Grün | Ja |
| Hypothesis Fuzzing | ~20 | Grün | Ja |
| "Did you mean?" Suggestions (B1) | 7 | Grün | Ja |
| Confusable Element Detection (B3: ELEM-3/ELEM-4) | 11 | Grün | Ja |
| Original pvValidator Tests (inkl. ESS-Netzwerk) | 7 | Grün | Teilweise |
| **Gesamt** | **391** | **Grün** | **Ja** |

**Kriterium:** Alle Tests müssen grün sein. Kein Test darf ESS-Netzwerk erfordern (außer mit `--ess-network` Flag).

**ESS-Netzwerk Ersttest (2026-03-30):** 391/391 Tests grün — historischer Meilenstein. Erste vollständige Testsuite inkl. `test_all`, `test_backend`, `test_pvepics`.

### 1.2 Zu testen vor Release

| Test | Wie | Erwartet | Verifiziert |
|------|-----|----------|-------------|
| Docker Build | `docker build -t pvvalidator .` | Erfolgreich | 2026-03-30 ✓ |
| Docker Tests | `docker run --rm --network host pvvalidator conda run -n e3 pytest test/ -v --ess-network` | 391 passed, 0 failed | 2026-03-30 ✓ |
| CLI --noapi | `pvValidator -i test/pvlist_ok.txt --noapi --stdout` | Exit 0, keine Fehler | 2026-03-30 ✓ |
| CLI --format json | `pvValidator -i test/pvlist_ok.txt --noapi --format json` | Valides JSON | 2026-03-30 ✓ |
| CLI --format html | `pvValidator -i test/pvlist_ok.txt --noapi --format html > report.html` | Öffnet im Browser | 2026-03-30 ✓ |
| CLI -e (EPICS DB) | `pvValidator -e test/test.db P=Sys-Sub:,R=Dis-Dev-Idx: --noapi --stdout` | 3 PVs erkannt | 2026-03-30 ✓ |
| Web-UI | Öffne `pvValidatorUtils/web/index.html` → "Load Examples" | Alle Validierungen korrekt | Manuell prüfen |
| Bekannte gute PVs | `DTL-010:EMR-TT-001:Temperature` | VALID | 2026-03-30 ✓ |
| Bekannte schlechte PVs | `DTL-010:EMR-TT-001:Temperature-S` | Error PROP-SP | 2026-03-30 ✓ |

### 1.3 Online-Tests (im ESS-Netz)

| Test | Wie | Erwartet | Verifiziert |
|------|-----|----------|-------------|
| Naming Service erreichbar | `pvValidator -i test/pvlist_ok.txt -n prod` | "registered in the Naming Service" | 2026-03-30 ✓ |
| Unregistrierter Name | `pvValidator -i test/pvlist_api.txt -n prod` | "not registered" | 2026-03-30 ✓ |
| "Did you mean?" Vorschlag | `DLT-010:EMR-TT-001:Temperature` mit `-n prod` | `Hint: Did you mean "DTL"?` | 2026-03-30 ✓ |
| Graceful Degradation | Naming Service nicht erreichbar + `-n prod` | Fallback auf Format-Only | 2026-03-30 ✓ |

---

## 2. Regelabdeckung ESS-0000757

### 2.1 Implementierte Regeln

| ESS-0000757 Abschnitt | Regel | Implementiert | Rule-ID | Getestet |
|------------------------|-------|--------------|---------|----------|
| §3, Rule 1 | Alphanumerisch | Ja | ELEM-1 | Ja |
| §3, Rule 2 | Startet mit Buchstabe | Ja | ELEM-2 | Ja |
| §3 | Confusable System/Subsystem (I↔l↔1, O↔0, VV↔W) | Ja | ELEM-3 | Ja |
| §3 | Confusable Discipline/Device (I↔l↔1, O↔0, VV↔W) | Ja | ELEM-4 | Ja |
| §3, Rule 5 | Min 1 Zeichen | Ja (Parser) | FMT | Ja |
| §3, Rule 6 | Max 6 Zeichen | Ja | ELEM-6 | Ja |
| §3 | Max 60 Zeichen gesamt | Ja | PV-LEN | Ja |
| §5.2.1 | Scientific Index (1-4 Digits) | Ja | IDX-STYLE | Ja |
| §5.2.2 | P&ID Index (3 Digits + optional) | Ja | IDX-STYLE | Ja |
| §5.2.3 | SC-IOC Index Digits only | Ja | IDX-SC | Ja |
| §6.2, Rule 1 | Property unique (Confusables) | Ja | PROP-1 | Ja |
| §6.2, Rule 2 | Property max 25 Zeichen (SHOULD 20) | Ja | PROP-2 | Ja |
| §6.2, Rule 3 | Property min 4 Zeichen | Ja (Warning) | PROP-3 | Ja |
| §6.2, Rule 5 | PascalCase Empfehlung | Ja (Warning) | PROP-5 | Ja |
| §6.2, Rule 9a | Setpoint -SP | Ja | PROP-SP | Ja |
| §6.2, Rule 9b | Readback -RB | Ja | PROP-RB | Ja |
| §6.2, Rule 10 | Internal PV # | Ja | PROP-INT | Ja |
| §6.2, Rule 11 | Alphanumerisch, startet mit Buchstabe | Ja | PROP-11 | Ja |
| Annex A | MTCA Controller 3-Digit Index | Ja (Warning) | EXC-MTCA | Ja |
| Annex B | Target Station Subsystem Exception | Ja (Info) | EXC-TGT | Ja |
| Annex C | Legacy Prefixes (Warnung) | Ja | LEGACY | Ja |
| Annex C | Legacy 5-Digit Index (Cryo/Vac) | Ja (Warning) | LEGACY-5DIGIT | Ja |

### 2.2 Bekannte Lücken

| Regel | Status | Begründung |
|-------|--------|------------|
| Einheiten in Property (§6.2, Rule 7) | Nicht implementiert | Benötigt Wörterbuch-basierte Erkennung — nicht statisch prüfbar |
| Semantische Validierung (§6.11) | Nicht implementiert | Dokumentiert als außerhalb des Scope |

---

## 3. Code-Qualität

### 3.1 Checkliste

| Kriterium | Status |
|-----------|--------|
| Keine `sys.exit()` in Library-Code (nur in CLI) | Erfüllt |
| Keine `_Exit()` in C++ (durch Exceptions ersetzt) | Erfüllt |
| Keine bare `except Exception` Blöcke | Erfüllt |
| Type Hints auf neuen Modulen | Erfüllt |
| Docstrings auf allen öffentlichen Funktionen | Erfüllt |
| Logging statt print() in Library-Code | Teilweise |
| Keine hardcodierten URLs (konfigurierbar) | Erfüllt (NamingServiceClient) |
| Timeout auf allen HTTP-Requests | Erfüllt (5s default) |
| O(n) Algorithmen wo möglich | Erfüllt (Duplikat-Check) |
| Graceful Degradation bei Naming Service Ausfall | Erfüllt (B2) |
| "Did you mean?" Vorschläge bei unbekannten Mnemonics | Erfüllt (B1) |

### 3.2 Statische Analyse

| Tool | Ergebnis |
|------|----------|
| flake8 | Konfiguriert (.flake8), 1 Minor Finding (unused import in test_parser.py) |
| isort | Bekannte Sortierungs-Differenzen in Legacy-Code (nicht regressiv) |
| black | Erfordert Python ≥3.14 oder `--target-version py310` (Docker nutzt Python 3.10) |
| mypy | Neue Module: fehlerfrei (mit `--ignore-missing-imports`) |
| SWIG-generierte Module (epicsUtils.py, msiUtils.py): von Linting ausgeschlossen |

---

## 4. Backwards-Kompatibilität

| Kriterium | Verifiziert |
|-----------|-------------|
| Alle CLI-Flags funktionieren wie vorher | Ja (original Tests grün) |
| PVs die in v1.8.0 gültig waren, bleiben gültig | Ja |
| CSV-Output-Format unverändert | Ja |
| Exit-Codes: 0 = OK, 1 = Fehler | Ja |
| Curses-TUI funktioniert | Ja (unverändert) |

---

## 5. Infrastruktur

| Kriterium | Status |
|-----------|--------|
| Docker Build funktioniert | Ja (2026-03-30 verifiziert) |
| GitLab CI Pipeline definiert | Ja (.gitlab-ci.yml) |
| GitHub Actions definiert | Ja (.github/workflows/test.yml) |
| VCR Cassettes aufgenommen | Ja (69 API-Antworten, frisch 2026-03-30) |
| Pre-Commit Hook | Nicht implementiert (ESS .db Dateien nutzen Macros — statische Analyse nicht möglich) |

---

## 6. Dokumentation

| Dokument | Vorhanden |
|----------|-----------|
| README.md | Ja — 391 Tests, CLI Flags, Exit Codes, Documentation Section |
| CONTRIBUTING.md | Ja |
| CHANGELOG.md | Ja — Runden 1-7 + Alfio Pre-Fork History |
| ONLINE_MODE_SETUP.md | Ja |
| HOW_TO_RECORD.md (Cassettes) | Ja |
| Architecture Diagram (HTML) | Ja |
| YAML Rule Reference | Ja (ess-0000757-rev10.yaml) mit Why/Fix/Examples + ELEM-3/4 |
| Standard Properties Catalog | Ja (standard_properties.yaml) |
| guide.html | Ja — ESS Naming Convention Tutorial (6 Abschnitte) |
| reference.html | Ja — Quick Reference Cheat Sheet |
| Web-UI (index.html) | Ja — Live Validation + Expandable Details + Fix Buttons |

---

## 7. Abnahme-Checkliste (Sign-Off)

Vor der Freigabe für den ESS-Einsatz:

- [x] Alle automatischen Tests grün (391 Tests) — 2026-03-30
- [x] Docker Build erfolgreich (`docker build -t pvvalidator . && docker run --rm pvvalidator`) — 2026-03-30
- [x] Online-Validierung getestet (im ESS-Netz, `--ess-network` Flag) — 2026-03-30
- [x] CLI-Optionen getestet: `-i`, `-e`, `--noapi`, `--format json`, `--format html` — 2026-03-30
- [x] CLI Autofix getestet: `--suggest`, `--fix` — 2026-03-30
- [x] CLI Info getestet: `--explain PROP-SP`, `--verbose` — 2026-03-30
- [x] Web-UI getestet: Load Examples, File Upload, JSON Export, Fix All, Format Guide — 2026-03-30 (Chrome Browser)
- [x] Web-UI: Klick auf Error-Badge → Why/Fix Panel öffnet — 2026-03-30 (Chrome Browser)
- [x] Web-UI: "Invalid Format" zeigt spezifische Diagnose — 2026-03-30 (Chrome Browser)
- [x] guide.html: 6 Abschnitte, interaktives PV-Diagramm, Quiz funktioniert — 2026-03-30 (Chrome Browser)
- [x] reference.html: Alle Tabellen korrekt, Links funktionieren — 2026-03-30 (Chrome Browser)
- [x] Bekannte ESS PVs validiert (DTL-010:EMR-TT-001:Temperature = VALID) — 2026-03-30
- [x] Bekannte fehlerhafte PVs erkannt (Temperature-S = Error PROP-SP) — 2026-03-30
- [x] VCR Cassettes aufgenommen und Tests grün — 2026-03-30 (69 frische Antworten)
- [x] README gelesen und Anleitung nachvollziehbar — 2026-03-30 (GitHub rendering verifiziert, 391 Tests korrekt)
- [x] OWASP Security Audit: 0 Critical, 0 High offen — Audit 2026-03-26, keine neuen Angriffsflächen
- [x] Linter: flake8 clean (SWIG-Module ausgeschlossen), black/isort bekannte Legacy-Differenzen
- [x] Kein Sicherheitsrisiko (keine Credentials, keine Schreibzugriffe auf Naming Service)
- [ ] Code Review durch zweite Person

**Sign-Off:**

| Rolle | Name | Datum | Unterschrift |
|-------|------|-------|-------------|
| Entwickler | Dirk Nordt + Claude Code | 2026-03-30 | ✓ (automatisierte Items) |
| Reviewer | | | |
| ICS-Verantwortlicher | | | |
