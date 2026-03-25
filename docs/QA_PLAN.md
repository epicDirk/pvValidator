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
| Validierungsregeln (alle ESS-0000757 Regeln) | 59 | Grün | Ja |
| API-Mocking (Naming Service Simulation) | 28 | Grün | Ja |
| VCR Cassettes (echte ESS-Daten) | 24 | Grün | Ja |
| YAML Rule Loader | 17 | Grün | Ja |
| JSON/HTML Reporter | 11 | Grün | Ja |
| Original pvValidator Tests | 4 | Grün | Ja |
| **Gesamt** | **182+** | **Grün** | **Ja** |

**Kriterium:** Alle Tests müssen grün sein. Kein Test darf ESS-Netzwerk erfordern (außer mit `--ess-network` Flag).

### 1.2 Zu testen vor Release

| Test | Wie | Erwartet |
|------|-----|----------|
| Docker Build | `docker build -t pvvalidator .` | Erfolgreich |
| Docker Tests | `docker run --rm pvvalidator` | 182+ passed, 0 failed |
| CLI --noapi | `pvValidator -i test/pvlist_ok.txt --noapi` | Exit 0, keine Fehler |
| CLI --format json | `pvValidator -i test/pvlist_ok.txt --noapi --format json` | Valides JSON |
| CLI --format html | `pvValidator -i test/pvlist_ok.txt --noapi --format html > report.html` | Öffnet im Browser |
| Web-UI | Öffne `pvValidatorUtils/web/index.html` → "Load Examples" | Alle Validierungen korrekt |
| Bekannte gute PVs | `DTL-010:EMR-TT-001:Temperature` | VALID |
| Bekannte schlechte PVs | `DTL-010:EMR-TT-001:Temperature-S` | Error PROP-SP |
| Leere Eingabe | `pvValidator -i /dev/null --noapi` | Exit 0 |

### 1.3 Online-Tests (im ESS-Netz)

| Test | Wie | Erwartet |
|------|-----|----------|
| Naming Service erreichbar | `pvValidator -i test/pvlist_ok.txt -n prod` | "registered in the Naming Service" |
| Unregistrierter Name | `pvValidator -i test/pvlist_api.txt -n prod` | "not registered" |
| IOC Discovery | `pvValidator -d` | Liste von IOCs mit GUID |
| Online-Validierung | `pvValidator -s <IOC-IP>` | Tabelle mit Ergebnissen |

---

## 2. Regelabdeckung ESS-0000757

### 2.1 Implementierte Regeln

| ESS-0000757 Abschnitt | Regel | Implementiert | Rule-ID | Getestet |
|------------------------|-------|--------------|---------|----------|
| §3, Rule 1 | Alphanumerisch | Ja | ELEM-1 | Ja |
| §3, Rule 2 | Startet mit Buchstabe | Ja | ELEM-2 | Ja |
| §3, Rule 5 | Min 1 Zeichen | Ja (Parser) | FMT | Ja |
| §3, Rule 6 | Max 6 Zeichen | Ja | ELEM-6 | Ja |
| §3 | Max 60 Zeichen gesamt | Ja | PV-LEN | Ja |
| §5.2.1 | Scientific Index (1-4 Digits) | Ja | IDX-STYLE | Ja |
| §5.2.2 | P&ID Index (3 Digits + optional) | Ja | IDX-STYLE | Ja |
| §5.2.3 | SC-IOC Index Digits only | Ja | IDX-SC | Ja |
| §6.2, Rule 1 | Property unique (Confusables) | Ja | PROP-1 | Ja |
| §6.2, Rule 2 | Property max 25 Zeichen | Ja | PROP-2 | Ja |
| §6.2, Rule 3 | Property min 4 Zeichen | Ja (Warning) | PROP-3 | Ja |
| §6.2, Rule 9a | Setpoint -SP | Ja | PROP-SP | Ja |
| §6.2, Rule 9b | Readback -RB | Ja | PROP-RB | Ja |
| §6.2, Rule 10 | Internal PV # | Ja | PROP-INT | Ja |
| §6.2, Rule 11 | Alphanumerisch, startet mit Buchstabe | Ja | PROP-11 | Ja |
| Annex C | Legacy Prefixes (Warnung) | Ja | LEGACY | Ja |

### 2.2 Bekannte Lücken

| Regel | Status | Begründung |
|-------|--------|------------|
| PascalCase Empfehlung | Nicht implementiert | Schwer automatisch zu erkennen |
| Einheiten in Property | Nicht implementiert | Benötigt Wörterbuch-basierte Erkennung |
| Semantische Validierung | Nicht implementiert | Dokumentiert als außerhalb des Scope (ESS-0000757 §6.11) |

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

### 3.2 Statische Analyse

| Tool | Ergebnis |
|------|----------|
| flake8 | Konfiguriert (.flake8), keine kritischen Fehler |
| mypy | Neue Module: fehlerfrei (mit `--ignore-missing-imports`) |
| SWIG-generierte Module: bekannte Warnungen (ignoriert) |

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
| Docker Build funktioniert | Ja |
| GitLab CI Pipeline definiert | Ja (.gitlab-ci.yml) |
| GitHub Actions definiert | Ja (.github/workflows/test.yml) |
| VCR Cassettes aufgenommen | Ja (60 Parts, 9 Names) |
| Pre-Commit Hook | Nicht implementiert (ESS .db Dateien nutzen Macros — statische Analyse nicht möglich) |

---

## 6. Dokumentation

| Dokument | Vorhanden |
|----------|-----------|
| README.md | Ja — komplett neu geschrieben |
| CONTRIBUTING.md | Ja |
| ONLINE_MODE_SETUP.md | Ja |
| HOW_TO_RECORD.md (Cassettes) | Ja |
| Architecture Diagram (HTML) | Ja |
| YAML Rule Reference | Ja (ess-0000757-rev10.yaml) |
| Standard Properties Catalog | Ja (standard_properties.yaml) |

---

## 7. Abnahme-Checkliste (Sign-Off)

Vor der Freigabe für den ESS-Einsatz:

- [ ] Alle automatischen Tests grün (182+)
- [ ] Docker Build erfolgreich
- [ ] Online-Validierung getestet (im ESS-Netz)
- [ ] CLI-Optionen manuell getestet (--noapi, --format, -i, -e, -s)
- [ ] Web-UI getestet (Load Examples, Datei-Upload, JSON Export)
- [ ] Bekannte ESS PVs validiert (DTL-010:EMR-TT-001:Temperature = VALID)
- [ ] Bekannte fehlerhafte PVs erkannt (Temperature-S = Error PROP-SP)
- [ ] VCR Cassettes aufgenommen und Tests grün
- [ ] README gelesen und Anleitung nachvollziehbar
- [ ] Kein Sicherheitsrisiko (keine Credentials im Code, keine Schreibzugriffe auf Naming Service)
- [ ] Code Review durch zweite Person

**Sign-Off:**

| Rolle | Name | Datum | Unterschrift |
|-------|------|-------|-------------|
| Entwickler | | | |
| Reviewer | | | |
| ICS-Verantwortlicher | | | |
