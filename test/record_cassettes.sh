#!/bin/bash
# ============================================================
# pvValidator VCR Cassette Recorder
#
# Braucht NUR: Git Bash (kommt mit Git) + ESS Netzwerk
# Kein Python, kein Docker nötig.
#
# Aufruf:
#   Rechtsklick im Ordner pvvalidator → "Git Bash Here"
#   Dann: bash test/record_cassettes.sh
# ============================================================

PROD_URL="https://naming.esss.lu.se"
PARTS_URL="$PROD_URL/rest/parts/mnemonic"
NAMES_URL="$PROD_URL/rest/deviceNames"
# Output neben dem Script — funktioniert überall, auch ohne Projekt-Ordner
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/cassettes"
OUTPUT_FILE="$OUTPUT_DIR/naming_service_prod.json"

mkdir -p "$OUTPUT_DIR"

echo "============================================================"
echo "  pvValidator VCR Cassette Recorder"
echo "============================================================"
echo ""

# Verbindung prüfen
echo "Prüfe Verbindung zu $PROD_URL ..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$PROD_URL")

if [ "$STATUS" != "200" ] && [ "$STATUS" != "302" ]; then
    echo ""
    echo "  FEHLER: Keine Verbindung zum Naming Service (HTTP $STATUS)"
    echo ""
    echo "  Du brauchst ESS-Netzwerk-Zugang (VPN oder ESS-Maschine)."
    echo "  Bitte VPN einschalten und nochmal versuchen."
    exit 1
fi
echo "  Verbunden (HTTP $STATUS)"
echo ""

# Systeme
SYSTEMS="DTL PBI ISrc Tgt CWM YMIR LOKI DREAM RFQ MEBT MBL HBL TD MO TRef Acc CrS ACF TS2 G02 LoKI"
# Subsysteme
SUBSYSTEMS="010 BCM01 CS CWS03 SpScn HeC1010 ChpSy1 M D1 TWDS1000"
# Disciplines
DISCIPLINES="EMR Ctrl WtrC Proc MC ISS SC PBI RFS BMD Cryo Vac CnPw"
# Devices
DEVICES="TT PT MTCA IOC MCU Magtr CPU EVR ACCT BCM PCV YSV EH CT AMC FSM PID"
# Full Names
FULLNAMES="DTL-010:EMR-TT-001 PBI-BCM01:Ctrl-MTCA-100 CWM-CWS03:WtrC-PT-011 ISrc-CS:ISS-Magtr-01 Tgt-HeC1010:Proc-TT-003 DTL-010 DTL NONEXIST-999:FAKE-XX-001 QQQQQQ-010:EMR-TT-001"

# JSON-Datei starten
echo "{" > "$OUTPUT_FILE"
echo '  "_metadata": {"source": "'$PROD_URL'", "recorded_by": "record_cassettes.sh"},' >> "$OUTPUT_FILE"

# Parts aufnehmen
echo '  "parts_mnemonic": {' >> "$OUTPUT_FILE"
FIRST=true

fetch_part() {
    local MNEMONIC=$1
    local RESULT=$(curl -s -H "accept: application/json" --connect-timeout 5 "$PARTS_URL/$MNEMONIC" 2>/dev/null)
    if [ -z "$RESULT" ]; then
        RESULT="[]"
    fi
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        echo "," >> "$OUTPUT_FILE"
    fi
    printf '    "%s": %s' "$MNEMONIC" "$RESULT" >> "$OUTPUT_FILE"
    echo "  OK  parts/$MNEMONIC"
}

echo "Nehme Systeme auf ($( echo $SYSTEMS | wc -w ) Stück)..."
for S in $SYSTEMS; do fetch_part "$S"; done

echo ""
echo "Nehme Subsysteme auf ($( echo $SUBSYSTEMS | wc -w ) Stück)..."
for S in $SUBSYSTEMS; do fetch_part "$S"; done

echo ""
echo "Nehme Disciplines auf ($( echo $DISCIPLINES | wc -w ) Stück)..."
for D in $DISCIPLINES; do fetch_part "$D"; done

echo ""
echo "Nehme Devices auf ($( echo $DEVICES | wc -w ) Stück)..."
for D in $DEVICES; do fetch_part "$D"; done

echo "" >> "$OUTPUT_FILE"
echo "  }," >> "$OUTPUT_FILE"

# Device Names aufnehmen
echo '  "device_names": {' >> "$OUTPUT_FILE"
FIRST=true

echo ""
echo "Nehme Device Names auf ($( echo $FULLNAMES | wc -w ) Stück)..."
for N in $FULLNAMES; do
    RESULT=$(curl -s -H "accept: application/json" --connect-timeout 5 "$NAMES_URL/$N" 2>/dev/null)
    if [ -z "$RESULT" ]; then
        RESULT="{}"
    fi
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        echo "," >> "$OUTPUT_FILE"
    fi
    printf '    "%s": %s' "$N" "$RESULT" >> "$OUTPUT_FILE"
    echo "  OK  deviceNames/$N"
done

echo "" >> "$OUTPUT_FILE"
echo "  }" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

# Ergebnis
FILESIZE=$(wc -c < "$OUTPUT_FILE")
FILESIZE_KB=$((FILESIZE / 1024))

echo ""
echo "============================================================"
echo "  Fertig!"
echo "  Datei: $OUTPUT_FILE"
echo "  Größe: ${FILESIZE_KB} KB"
echo ""
echo "  Die Cassettes sind aufgenommen."
echo "  Ab jetzt laufen alle Tests offline."
echo "============================================================"
