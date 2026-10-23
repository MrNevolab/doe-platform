#!/usr/bin/env python3
"""Praxistest: DoE-Plattform im LAN testen (geschlossener Loop).

Aufruf:  python3 praxistest.py <server-ip> [api-key]
Beispiel: python3 praxistest.py 192.168.220.115 meinkey

Testet: health -> auth -> design -> status -> results -> analyze -> optimize
"""
import json
import sys
import urllib.error
import urllib.request

IP = sys.argv[1] if len(sys.argv) > 1 else None
KEY = sys.argv[2] if len(sys.argv) > 2 else ""
PORT = sys.argv[3] if len(sys.argv) > 3 else "8000"
BASE = f"http://{IP}:{PORT}" if IP else f"http://127.0.0.1:{PORT}"

passed, failed = 0, 0


def ok(msg):
    global passed
    passed += 1
    print(f"   PASS: {msg}")


def bad(msg):
    global failed
    failed += 1
    print(f"   FAIL: {msg}")


def call(method, path, data=None, key=KEY, timeout=5):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    req = urllib.request.Request(
        BASE + path, data=json.dumps(data).encode() if data else None,
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"detail": str(e)}


print(f"Praxistest gegen {BASE} (Key: {'ja' if KEY else 'nein'})\n")

# 1. Health
print("== 1. Health-Check")
code, body = call("GET", "/health")
if code == 200:
    ok(f"Server erreichbar ({code})")
else:
    bad(f"Server nicht erreichbar (HTTP {code}): {body}")
    print("   Abbruch.")
    sys.exit(1)

# 2. Auth
if KEY:
    print("\n== 2. Auth-Check (falscher Key muss 401 liefern)")
    code, _ = call("POST", "/designs", {"design_type": "full_factorial",
                                        "factors": [{"name": "A", "low": 0, "high": 1}]},
                   key="falsch")
    ok(f"falscher Key abgewiesen ({code})") if code == 401 else bad(f"falscher Key NICHT abgewiesen ({code})")

# 3. Design
print("\n== 3. CCD-Design generieren (2 Faktoren)")
code, d = call("POST", "/designs", {
    "design_type": "central_composite",
    "factors": [{"name": "Temp", "unit": "C", "low": 20, "high": 80},
                {"name": "Rpm", "unit": "rpm", "low": 200, "high": 800}],
    "alpha": "rotatable", "center_points": 4, "seed": 1})
if code != 200:
    bad(f"Design-Erstellung fehlgeschlagen ({code}): {d}")
    sys.exit(1)
did = d["design_id"]
ok(f"design_id={did}, n_runs={d['n_runs']}, alle Runs pending: "
   f"{all(r['status'] == 'pending' for r in d['runs'])}")

# 4. Status-Rueckkanal
print("\n== 4. Status-Rueckkanal")
code, _ = call("PATCH", f"/designs/{did}/runs/1", {"status": "running"})
ok(f"run 1 -> running ({code})") if code == 200 else bad(f"PATCH running fehlgeschlagen ({code})")
code, _ = call("PATCH", f"/designs/{did}/runs/1", {"status": "done"})
ok(f"run 1 -> done ({code})") if code == 200 else bad(f"PATCH done fehlgeschlagen ({code})")
code, _ = call("PATCH", f"/designs/{did}/runs/1", {"status": "banane"})
ok(f"ungueltiger Status abgewiesen ({code})") if code == 422 else bad(f"ungueltiger Status akzeptiert ({code})")

# 5. Ergebnisse
print("\n== 5. Messwerte zurueckmelden (simulierter Prozess, wahres Optimum 60C/700rpm)")
n_reported = 0
for run in d["runs"]:
    y = 95 - 0.012 * (run["factors"]["Temp"] - 60) ** 2 - 0.00007 * (run["factors"]["Rpm"] - 700) ** 2
    code, _ = call("POST", f"/designs/{did}/results",
                   {"run_id": run["run_id"], "response": "yield", "value": round(y, 2)})
    if code == 200:
        n_reported += 1
    else:
        bad(f"results run {run['run_id']} fehlgeschlagen ({code})")
ok(f"{n_reported} Messwerte gemeldet")

# 6. Status-Summary
print("\n== 6. Fortschritt abfragen")
code, st = call("GET", f"/designs/{did}/status")
if code == 200 and st.get("complete"):
    ok(f"alle {st['n_runs']} Runs done")
else:
    bad(f"Status unvollstaendig: {st}")

# 7. Modellfit
print("\n== 7. Modellfit (quadratisch)")
code, fit = call("POST", f"/designs/{did}/analyze", {"response": "yield", "model": "quadratic"})
if code == 200:
    ok(f"R2={fit['r2']:.3f} Q2={fit['q2']:.3f} RMSE={fit['rmse']:.3f}, "
       f"Top-Term: {fit['coefficients'][0]['term']} (p={fit['coefficients'][0]['p']:.4f})")
    if fit["r2"] < 0.9:
        bad("R2 < 0.9 - Modell erklaert die Daten schlecht")
else:
    bad(f"Fit fehlgeschlagen ({code}): {fit}")

# 8. Optimierung
print("\n== 8. Optimierung (maximize yield)")
code, opt = call("POST", f"/designs/{did}/optimize",
                 {"response": "yield", "goal": "maximize", "model": "quadratic"})
if code == 200:
    t = opt["best_setpoints"]["Temp"]
    r = opt["best_setpoints"]["Rpm"]
    ok(f"Optimum: Temp={t:.0f} C, Rpm={r:.0f} rpm, predicted={opt['best_predicted']:.1f}")
    if abs(t - 60) <= 3 and abs(r - 700) <= 40 and abs(opt["best_predicted"] - 95) < 1:
        ok("Optimum nahe wahrem Optimum (60C/700rpm/95) - Loop funktional korrekt")
    else:
        bad("Optimum weicht stark vom wahren Optimum ab")
else:
    bad(f"Optimierung fehlgeschlagen ({code}): {opt}")

print("\n===========================================")
print(f" ERGEBNIS: {passed} bestanden, {failed} fehlgeschlagen")
if failed == 0:
    print(" => PRAXISTEST BESTANDEN: bereit fuer Phase 3")
else:
    print(" => Fehler klaeren (Details oben)")
print("===========================================")
sys.exit(1 if failed else 0)
