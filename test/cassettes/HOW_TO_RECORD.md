# VCR Cassettes aufnehmen

## Was passiert hier?

Manche Tests brauchen Antworten vom ESS Naming Service (naming.esss.lu.se). Cassettes sind gespeicherte Kopien dieser Antworten. Einmal aufnehmen, danach laufen alle Tests ohne ESS-Netzwerk.

**Du brauchst:** Einen PC im ESS-Netzwerk + Git Bash (oder ein beliebiges Terminal mit curl)
**Du brauchst NICHT:** Python, Docker, unser Projekt, oder sonstige Software

---

## Schritt 1: Script auf einen USB-Stick kopieren

Kopiere diese eine Datei auf einen USB-Stick:
```
C:\Users\dirkn\Documents\pvValidator\pvvalidator\test\record_cassettes.sh
```

Oder schick sie dir per E-Mail.

## Schritt 2: Am ESS-Rechner

1. Stecke den USB-Stick ein
2. Kopiere `record_cassettes.sh` in einen beliebigen Ordner (z.B. Desktop)
3. **Rechtsklick** auf eine leere Stelle im Ordner
4. Klicke auf **"Git Bash Here"** (oder öffne ein Terminal)

Falls kein Git Bash vorhanden: Jedes Linux-Terminal, PowerShell, oder WSL funktioniert auch — es braucht nur `curl` und `bash`.

## Schritt 3: Script starten

```
bash record_cassettes.sh
```

Du siehst:
```
============================================================
  pvValidator VCR Cassette Recorder
============================================================

Prüfe Verbindung zu https://naming.esss.lu.se ...
  Verbunden (HTTP 200)

Nehme Systeme auf (21 Stück)...
  OK  parts/DTL
  OK  parts/PBI
  ...

============================================================
  Fertig!
  Datei: cassettes/naming_service_prod.json
  Größe: 45 KB
============================================================
```

**Dauert ca. 30 Sekunden.**

## Schritt 4: Datei mitnehmen

Die Datei liegt jetzt im gleichen Ordner wo das Script lag:
```
cassettes/naming_service_prod.json
```

Kopiere diesen `cassettes` Ordner auf den USB-Stick (oder per E-Mail).

## Schritt 5: Zurück auf deinem Rechner

Kopiere `naming_service_prod.json` hierhin:
```
C:\Users\dirkn\Documents\pvValidator\pvvalidator\test\cassettes\naming_service_prod.json
```

Fertig. Ab jetzt laufen alle Tests offline.

---

## Falls es nicht klappt

**"Keine Verbindung zum Naming Service"**
→ Du bist nicht im ESS-Netz. Frag IT ob du Netzwerk-Zugang brauchst.

**"bash: command not found" oder "curl: command not found"**
→ Auf dem ESS-Rechner ist vermutlich Linux — versuche direkt: `sh record_cassettes.sh`

**Kann ich etwas kaputt machen?**
Nein. Das Script liest nur Daten. Es ändert nichts am Server.

**Muss ich das nochmal machen?**
Nur wenn ESS neue Systeme oder Devices registriert. Normalerweise einmal und fertig.
