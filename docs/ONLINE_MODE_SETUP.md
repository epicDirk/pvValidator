# pvValidator Online Mode — Setup-Anleitung für ESS

Diese Anleitung erklärt wie du pvValidator mit Zugriff auf den ESS Naming Service einrichtest. Damit validiert das Tool nicht nur Format und Regeln, sondern prüft auch ob PV-Namen tatsächlich im Naming Service registriert sind.

---

## Voraussetzungen

- Zugang zum ESS-Netzwerk (direkt oder VPN)
- Git installiert
- Docker Desktop installiert (empfohlen) ODER Python 3.10+ mit EPICS 7

---

## Option A: Docker (empfohlen, 5 Minuten)

### 1. Repository klonen

```bash
git clone https://github.com/epicDirk/pvValidator.git
cd pvValidator
```

### 2. Docker Image bauen

Außerhalb des ESS-Netzes:
```bash
docker build -t pvvalidator .
```

Im ESS-Netz (offizieller e3-Weg):
```bash
docker build --build-arg ESS_NETWORK=true -t pvvalidator .
```

### 3. Online validieren

```bash
# PVs aus einer Textdatei gegen den Naming Service prüfen
docker run --rm -v $(pwd):/data pvvalidator \
  conda run --no-capture-output -n e3 \
  pvValidator -i /data/meine-pvs.txt -n prod

# PVs von einem laufenden IOC validieren (braucht Netzwerk zum IOC)
docker run --rm --network host pvvalidator \
  conda run --no-capture-output -n e3 \
  pvValidator -s 172.30.6.12
```

### 4. VCR Cassettes aufnehmen (einmalig, optional)

Damit die Tests auch offline gegen echte Naming-Service-Daten laufen:

```bash
docker run --rm -v $(pwd)/pvvalidator/test/cassettes:/app/test/cassettes pvvalidator \
  conda run --no-capture-output -n e3 \
  python test/record_cassettes.py
```

---

## Option B: Ohne Docker (e3 Conda Environment)

### 1. e3 installieren

```bash
# Miniforge installieren (https://conda-forge.org/download/)
conda config --prepend channels ess-conda-local
conda config --set channel_alias https://artifactory.esss.lu.se/artifactory/api/conda
conda config --set channel_priority strict

conda create --name=e3 epics-base require swig cmake python=3.10
conda activate e3
```

### 2. pvValidator kompilieren

```bash
git clone https://github.com/epicDirk/pvValidator.git
cd pvValidator/pvvalidator
mkdir build && cd build
cmake -DMY_PYTHON_VERSION=3.10 ..
make install
cd ..
pip install -e ".[test]"
```

### 3. Online validieren

```bash
# Format + Regeln + Naming Service
pvValidator -i meine-pvs.txt -n prod

# Nur Format + Regeln (kein Naming Service)
pvValidator -i meine-pvs.txt --noapi

# Output als JSON
pvValidator -i meine-pvs.txt --format json

# Output als HTML Report
pvValidator -i meine-pvs.txt --format html > report.html
```

---

## Verfügbare CLI-Optionen

| Flag | Beschreibung |
|------|-------------|
| `-s IP[:PORT]` | Online: PVs von laufendem IOC holen |
| `-i datei.txt` | Offline: PV-Liste aus Textdatei |
| `-e datei.db MACROS` | Offline: PVs aus EPICS .db Datei |
| `-m datei.substitutions` | Offline: PVs aus Substitution-Datei |
| `-n prod\|test` | Naming Service Endpoint (Default: prod) |
| `--noapi` | Nur Format + Regeln, kein Naming Service |
| `-o datei.csv` | Ergebnis als CSV speichern |
| `--stdout` | Ergebnis auf stdout ausgeben |
| `--format json\|html` | Ergebnis als JSON oder HTML |
| `--suggest` | Auto-Fix Vorschläge anzeigen (NEU) |
| `-d` | IOC-Server im Netzwerk entdecken |
| `-v` | Version anzeigen |

---

## Naming Service Endpoints

| Endpoint | URL | Wann nutzen |
|----------|-----|-------------|
| Production | naming.esss.lu.se | Produktions-Validierung |
| Test | naming-test-01.cslab.esss.lu.se | Zum Testen neuer Namen |

---

## Troubleshooting

**"Fail to connect to Naming Service"**
→ Du bist nicht im ESS-Netz. VPN einschalten oder `--noapi` nutzen.

**"No module named pvValidatorUtils"**
→ `pip install -e .` im pvvalidator-Verzeichnis ausführen.

**SWIG Compilation Error**
→ `source /path/to/epics/environment` vor dem cmake.

**Docker: "naming.esss.lu.se not found"**
→ Docker-Container hat kein DNS zum ESS-Netz. Nutze `--network host`.
