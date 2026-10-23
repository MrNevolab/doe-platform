# Integration: TMS XData / Automation

Diese Seite beschreibt den HTTP-Vertrag zwischen der DoE-Plattform und der
Xelsius-Automation (TMS XData-Komponente, Aufruf via `curl`/Ethernet).

## Grundsätzliches

- DoE-Plattform: HTTP/1.1 REST, JSON (`Content-Type: application/json`), Port `8000`
- Alle Endpunkte (außer `/health`) erwarten den Header `X-API-Key`, wenn serverseitig
  `DOE_API_KEY` gesetzt ist (empfohlen im LAN).
- Rückgabewerte der Faktoren sind immer **reale Sollwerte** (z. B. °C, rpm, mL),
  bereits randomisiert und mit `run_id`/`block` versehen.

## Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/health` | Erreichbarkeit prüfen |
| GET | `/designs/types` | verfügbare Design-Typen |
| POST | `/designs` | Design generieren und speichern (liefert `design_id` + Status je Run) |
| GET | `/designs/{design_id}` | gespeichertes Design abrufen (inkl. aktuellem Run-Status) |
| PATCH | `/designs/{design_id}/runs/{run_id}` | **Status-Rückmeldung der Automation** (Body: `{"status": "..."}`) |
| GET | `/designs/{design_id}/status` | Fortschritt abfragen (`status_counts`, `complete`) |
| POST | `/designs/export?fmt=csv` | Ausführungsplan als CSV (jetzt mit `status`-Spalte) |
| POST | `/designs/export?fmt=json` | Ausführungsplan als JSON |
| POST | `/designs/{design_id}/results` | **Messwert-Rückmeldung** (Body: `run_id`, `response`, `value`); setzt Run auf `done` |
| POST | `/designs/{design_id}/analyze` | Modellfit/ANOVA (Body: `response`, `model`: linear/interaction/quadratic) |
| POST | `/designs/{design_id}/optimize` | Optimierung (Body: `response`, `goal`: maximize/minimize/target, optional `target`) |

## Ergebnis-Rückmeldung & Auswertung

Messwert je Run zurückmelden (setzt den Run automatisch auf `done`):

```bash
curl -s http://<server-ip>:8000/designs/<design_id>/results \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{"run_id": 3, "response": "yield", "value": 87.4}'
```

Modell fitten (ANOVA, Koeffizienten mit p-Werten, R²/adj. R²/Q²/RMSE):

```bash
curl -s http://<server-ip>:8000/designs/<design_id>/analyze \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{"response": "yield", "model": "quadratic"}'
```

Optimale Sollwerte finden (Desirability, liefert reale Setpoints):

```bash
curl -s http://<server-ip>:8000/designs/<design_id>/optimize \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{"response": "yield", "goal": "maximize"}'
```

Die Antwort enthält `best_setpoints` (reale Einheiten, direkt als neue
Sollwerte für die Automation nutzbar), `best_predicted`, die vorhergesagte
Spannweite und die Modellgüte (R²/Q²/RMSE) des zugrundeliegenden Fits.

**Empfohlener Workflow (geschlossener Loop):**
1. Screening-Design (PB/frac. faktoriell) → Automatik läuft, Werte via `/results`
2. `analyze` mit `model: linear` → signifikante Faktoren identifizieren
3. RSM-Design (CCD/BB) nur für die signifikanten Faktoren → Automatik
4. `analyze` mit `model: quadratic` → bei gutem Q²: `optimize` → Bestätigungsversuch an Best-Setpoints

## Status-Verwaltung (Run-Lifecycle)

Jeder Run durchläuft: `pending` → `running` → `done` oder `failed`.
Die Automation meldet zurück:

```bash
curl -s -X PATCH http://<server-ip>:8000/designs/<design_id>/runs/<run_id> \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <key>" \
  -d '{"status": "running"}'
```

Fortschritt des gesamten Plans abfragen:

```bash
curl -s http://<server-ip>:8000/designs/<design_id>/status -H "X-API-Key: <key>"
# -> {"design_id": "...", "n_runs": 8, "status_counts": {"done": 5, "pending": 3}, "complete": false}
```

Damit kann XData nach einem Abbruch (Netz, Gerät) erkennen, welche Runs
nachzuholen sind (`status != "done"`), und den Plan an derselben Stelle
wiederaufnehmen.

## curl-Beispiele (XData-Seite)

Design generieren:

```bash
curl -s http://<server-ip>:8000/designs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <key>" \
  -d '{
    "design_type": "plackett_burman",
    "factors": [
      {"name": "Temp",  "unit": "C",   "low": 20,  "high": 80},
      {"name": "Rpm",   "unit": "rpm", "low": 200, "high": 800},
      {"name": "Vol",  "unit": "mL",  "low": 1,   "high": 5}
    ],
    "randomize": true,
    "seed": 42
  }'
```

CSV-Ausführungsplan (eine Kopfzeile + eine Zeile pro Run):

```bash
curl -s "http://<server-ip>:8000/designs/export?fmt=csv" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <key>" \
  -d '{ "design_type": "full_factorial",
        "factors": [{"name": "Temp", "low": 20, "high": 80},
                    {"name": "pH",   "low": 2,  "high": 10}],
        "randomize": false }'
```

Antwort (Beispiel):

```
run_id,block,Temp,pH
1,1,20.0,2.0
2,1,20.0,10.0
...
```

## JSON-Schema des Requests

| Feld | Typ | Pflicht | Bedeutung |
|---|---|--- |---|
| `design_type` | enum | ja | `full_factorial`, `fractional_factorial`, `plackett_burman`, `central_composite`, `box_behnken` |
| `factors` | list | ja | `name`, `low`, `high` (reale Einheiten), optional `unit` |
| `resolution` | int 3–5 | nein | nur `fractional_factorial` (Default 3) |
| `center_points` | int ≥1 | nein | nur RSM-Designs (Default 4) |
| `alpha` | enum | nein | nur `central_composite`: `rotatable`, `orthogonal`, `face_centered` |
| `replicates` | int ≥1 | nein | Default 1 |
| `blocks` | int ≥1 | nein | muss die Run-Zahl teilen |
| `randomize` | bool | nein | Default `true` |
| `seed` | int | nein | für reproduzierbare Randomisierung |

Fehlerfall: HTTP 422 mit `{"detail": "<ursache>"}` – XData kann `detail` direkt loggen.

## XData-Implementierungsnotiz

In XData/delphi-seitig entspricht das einem `TRESTClient`- bzw. HTTP-POST-Aufruf
mit JSON-Body; `curl`-Aufruf = Shell-/Process-Aufruf derselben Ressource.
Empfehlung: CSV-Variante für die Maschinensteuerung (flach, zeilenweise parst),
JSON-Variante für UI/Anzeige mit Metadaten.

## Sicherheit im LAN

- API-Key als Environment-Variable beim Start setzen:
  `DOE_API_KEY=<key> uvicorn app.api.routes:app --host <lan-ip> --port 8000`
- Der Key wird fest in der XData-Konfiguration hinterlegt (URL + Key am Stück)
- Key rotieren nur per Dienstneustart; Abruf immer nur im internen Netz
- Server lauscht absichtlich nur auf der LAN-IP, nicht 0.0.0.0/Internet

Gespeicherte Designs liegen als JSON-Dateien unter `DOE_DATA_DIR` (Default
`/tmp/doe_designs`); für den Produktivbetrieb auf ein persistentes Verzeichnis
oder Volume zeigen lassen.
