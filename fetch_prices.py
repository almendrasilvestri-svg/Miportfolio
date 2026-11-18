"""Baja precios de cierre y lista de tickers desde BYMA (API publica de open.bymadata.com.ar)
y genera data.json para la pagina de cartera.

Si algo falla, el script termina con error SIN pisar el data.json anterior.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
import urllib3

# BYMA usa una cadena de certificados que Python no reconoce por defecto.
urllib3.disable_warnings()

BASE = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free"
HEAD = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://open.bymadata.com.ar",
    "Referer": "https://open.bymadata.com.ar/",
}
# (endpoint, tipo por defecto): tp = titulo publico, on = obligacion negociable, ac = accion / CEDEAR
PANELES = [
    ("leading-equity", "ac"),
    ("general-equity", "ac"),
    ("cedears", "ac"),
    ("public-bonds", "tp"),
    ("negociable-obligations", "on"),
]
# Se prueban en orden hasta que uno devuelva datos (la API no esta documentada oficialmente).
CUERPOS = [
    {"excludeZeroPxAndQty": False, "T0": False, "T1": True, "T2": False, "page_size": 5000},
    {"T0": False, "T1": True, "T2": False, "page_size": 5000},
    {"page_size": 5000},
]
TIPO_POR_SEC = {"GO": "tp", "CORP": "on", "CS": "ac", "CD": "ac"}


def traer(panel):
    for cuerpo in CUERPOS:
        try:
            r = requests.post(f"{BASE}/{panel}", json=cuerpo, headers=HEAD, timeout=60, verify=False)
            if r.status_code != 200:
                print(f"  {panel}: HTTP {r.status_code} con cuerpo {list(cuerpo)}")
                continue
            d = r.json()
            items = d.get("data", []) if isinstance(d, dict) else d
            if items:
                return items
            print(f"  {panel}: respuesta vacia con cuerpo {list(cuerpo)}")
        except Exception as e:  # noqa: BLE001
            print(f"  {panel}: error {e}")
        time.sleep(0.5)
    return []


def precio(it):
    for k in ("closingPrice", "trade", "settlementPrice"):
        v = it.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def main():
    out = {}
    for panel, tipo_def in PANELES:
        items = traer(panel)
        n = 0
        for it in items:
            sym = (it.get("symbol") or "").strip().upper()
            p = precio(it)
            if not sym or p is None:
                continue
            tipo = TIPO_POR_SEC.get(it.get("securityType"), tipo_def)
            ccy = it.get("denominationCcy") or "ARS"
            plazo = str(it.get("settlementType") or "")
            previo = out.get(sym)
            # Si hay mas de un plazo para el mismo ticker, se prefiere 24hs (tipo "2").
            if previo and previo[4] == "2" and plazo != "2":
                continue
            out[sym] = [sym, tipo, ccy, p, plazo]
            n += 1
        print(f"{panel}: {len(items)} filas, {n} con precio")
        time.sleep(0.5)

    if len(out) < 50:
        sys.exit(f"Solo se obtuvieron {len(out)} instrumentos: no se actualiza data.json")

    hoy = datetime.now(timezone(timedelta(hours=-3))).date().isoformat()
    data = {
        "fecha": hoy,
        "items": [[s, t, c, p] for s, t, c, p, _ in sorted(out.values())],
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(data['items'])} instrumentos al {hoy}")


if __name__ == "__main__":
    main()
