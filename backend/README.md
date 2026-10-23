# DoE Platform – Backend (MVP Phase 1)

Design-of-Experiments-Generator für die Labor-Automation (Xelsius-Integration vorbereitet).

## Architektur

```
backend/
  app/
    core/          # DoE-Kernlogik (frei von Framework-Abhängigkeiten)
      factorial.py       # Voll- und fraktionell-faktorielle Designs
      plackett_burman.py # Screening-Designs (Hadamard/Paley)
      rsm.py             # Central Composite, Box-Behnken
      generator.py       # Randomisierung, Replikate, Blöcke, Einheiten-Mapping
      models.py          # Pydantic-Datenmodell (Design-Request)
    api/routes.py  # REST-API (FastAPI, TMS XData-kompatibel, X-API-Key-Auth)
    static/        # Web-UI (Proof of Concept)
  tests/
```

Der Kern ist bewusst framework-frei als eigenes Paket gebaut, damit er später
in die Xelsius-Plattform übernommen werden kann, ohne die REST-API mitzuziehen.

## Designs

| Typ | Anwendung | Läufe (Beispiele) |
|---|---|---|
| Vollfaktoriell | kleine Faktorzahlen, Haupteffekte + Interaktionen | 2ᵏ |
| Fraktionell-faktoriell (Res. III–V) | Screening mit Interaktions-Info | 2ᵏ⁻ᵖ |
| Plackett-Burman | grobes Screening vieler Faktoren | 8–64 |
| Central Composite (rotatable/orthogonal/face-centered) | Response-Surface, Optimierung | 2ᵏ+2k+n₀ |
| Box-Behnken | Response-Surface ohne Eckpunkte | 2k(k−1)+n₀ |

## Starten (lokales Netzwerk)

```bash
pip install -r requirements.txt
DOE_API_KEY=<key> uvicorn app.api.routes:app --host <lan-ip> --port 8000
# UI: http://<lan-ip>:8000/
# API-Doku: http://<lan-ip>:8000/docs
```

Ohne `DOE_API_KEY` läuft der Server offen (nur für Entwicklung).
Integration der Automation (TMS XData, curl): siehe [INTEGRATION.md](INTEGRATION.md).
Docker: `docker build -t doe-platform . && docker run -e DOE_API_KEY=<key> -p 8000:8000 doe-platform`

## API

- `GET /health` – Status
- `GET /designs/types` – verfügbare Design-Typen
- `POST /designs` – Design generieren (JSON: Faktoren mit low/high in realen Einheiten,
  Optionen: resolution, center_points, alpha, replicates, blocks, randomize, seed)
- `POST /designs/export?fmt=csv|json` – Ausführungsplan als CSV/JSON (für Automation)

## Tests

```bash
python -m pytest tests/ -q
```

## Roadmap

- Phase 1: Design-Generator + Export + Status-Tracking ✔
- Phase 2 (dies): Auswertung – Ergebnis-Rückmeldung, Modellfit/ANOVA (R²/Q²),
  Desirability-Optimierung ✔
- Phase 3: KI-Schicht – Bayesian Optimization / Active Learning für Versuchsempfehlungen,
  Priors aus Vorversuchen, Assistent-UI; Visualisierung (Kontur-/Oberflächenplots)
