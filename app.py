from flask import Flask, request, render_template_string, jsonify
import os, json, time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import evaluar_predictor as ev

app = Flask(__name__)

PARTIDOS = ev.leer_partidos()
EQUIPOS = sorted({
    p["local"] for p in PARTIDOS
} | {
    p["visitante"] for p in PARTIDOS
})

PAGINA = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101722">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/static/icons/icon-192.png">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<title>FutbolPredictor</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#101722;color:#f3f6fb;
font-family:Arial,sans-serif;padding:18px}
main{max-width:650px;margin:auto}
h1{color:#58e0a5;text-align:center;margin-bottom:5px}
.sub{text-align:center;color:#aab6c7;margin-bottom:25px}
.card{background:#1b2736;border:1px solid #344357;
border-radius:16px;padding:18px;margin:14px 0}
label{display:block;margin:15px 0 7px;color:#cbd5e1}
select,button{width:100%;padding:14px;border-radius:10px;
font-size:16px}
select{background:#101722;color:white;border:1px solid #52647a}
button{margin-top:20px;background:#32d995;color:#082017;
border:0;font-weight:bold}
.probs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.prob{background:#101722;padding:14px 5px;border-radius:12px;
text-align:center}
.pct{font-size:24px;font-weight:bold;color:#58e0a5;margin-top:8px}
.score{text-align:center;font-size:34px;font-weight:bold;
padding:12px;color:#fff}
small,.muted{color:#aab6c7}
.match{padding:10px 0;border-bottom:1px solid #344357}
.tag{display:inline-block;padding:4px 8px;border-radius:6px;
background:#26394b;margin-right:8px}
footer{text-align:center;color:#aab6c7;font-size:12px;margin:24px 0}

.live-match{padding:12px 0;border-bottom:1px solid #344357}
.live-score{font-size:21px;font-weight:bold;color:#58e0a5;text-align:center}
.live-teams{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center}
.live-teams span:last-child{text-align:right}
.live-status{font-size:12px;color:#ff7783;margin-bottom:7px}

</style>
</head>
<body>
<main>
<h1>⚽ FutbolPredictor</h1>
<div class="sub">Análisis estadístico de partidos</div>


<div class="card" id="card-en-vivo">
<h2>🔴 Partidos en vivo</h2>
<p class="muted" id="estado-vivo">Consultando marcadores reales...</p>
<div id="lista-en-vivo"></div>
</div>

<div class="card">
<h2>Elegir partido</h2>
<form method="post">
<label for="local">Equipo local</label>
<select name="local" id="local" required>
<option value="">Selecciona el equipo local</option>
{% for e in equipos %}
<option value="{{e}}" {% if e == elegido_local %}selected{% endif %}>{{e}}</option>
{% endfor %}
</select>

<label for="visitante">Equipo visitante</label>
<select name="visitante" id="visitante" required>
<option value="">Selecciona el equipo visitante</option>
{% for e in equipos %}
<option value="{{e}}" {% if e == elegido_visitante %}selected{% endif %}>{{e}}</option>
{% endfor %}
</select>
<button type="submit">ANALIZAR PARTIDO</button>
</form>
</div>

{% if error %}
<div class="card">{{error}}</div>
{% endif %}

{% if resultado %}
<div class="card">
<h2>{{ elegido_local }} vs {{ elegido_visitante }}</h2>
<p class="muted">Probabilidades estimadas</p>
<div class="probs">
<div class="prob"><div>🏠 Local (1)</div>
<div class="pct">{{ "%.1f"|format(resultado["1"]*100) }}%</div></div>
<div class="prob"><div>🤝 Empate (X)</div>
<div class="pct">{{ "%.1f"|format(resultado["X"]*100) }}%</div></div>
<div class="prob"><div>✈️ Visitante (2)</div>
<div class="pct">{{ "%.1f"|format(resultado["2"]*100) }}%</div></div>
</div>
<p>Pronóstico principal:</p>
<div class="score">{{ nombre_pronostico }}</div>
<p>Marcador individual más probable:</p>
<div class="score">{{ marcador[0] }} - {{ marcador[1] }}</div>
</div>

{% for equipo, partidos in formas %}
<div class="card">
<h3>Últimos partidos: {{equipo}}</h3>
{% if partidos %}
{% for p in partidos %}
<div class="match">
<span class="tag">{{p.res}}</span>
{{p.rival}} · {{p.gf}} - {{p.gc}}
<small> · {{p.fecha}}</small>
</div>
{% endfor %}
<p><b>Puntos:</b> {{ puntos[loop.index0] }} de {{ partidos|length * 3 }}</p>
{% else %}
<p>No hay resultados recientes disponibles.</p>
{% endif %}
</div>
{% endfor %}
{% endif %}

<footer>
Basado en {{total_partidos}} partidos históricos.<br>
Estimaciones estadísticas; no garantizan resultados futuros.
</footer>
</main>

<script>

async function cargarPartidosEnVivo() {
  const estado = document.getElementById("estado-vivo");
  const lista = document.getElementById("lista-en-vivo");
  try {
    const respuesta = await fetch("/api/en-vivo", {cache: "no-store"});
    const datos = await respuesta.json();
    if (!respuesta.ok || !datos.ok) {
      throw new Error(datos.error || "No se pudo consultar la API");
    }
    lista.replaceChildren();
    if (!datos.partidos.length) {
      estado.textContent = "No hay partidos en juego en este momento.";
      return;
    }
    estado.textContent = "Marcadores en directo";
    for (const p of datos.partidos) {
      const tarjeta = document.createElement("div");
      tarjeta.className = "live-match";
      const liga = document.createElement("small");
      liga.textContent = p.liga;
      const estadoPartido = document.createElement("div");
      estadoPartido.className = "live-status";
      estadoPartido.textContent = p.estado;
      const equipos = document.createElement("div");
      equipos.className = "live-teams";
      const local = document.createElement("span");
      local.textContent = p.local;
      const marcador = document.createElement("strong");
      marcador.className = "live-score";
      marcador.textContent = p.goles_local + " - " + p.goles_visitante;
      const visitante = document.createElement("span");
      visitante.textContent = p.visitante;
      equipos.append(local, marcador, visitante);
      tarjeta.append(liga, estadoPartido, equipos);
      lista.append(tarjeta);
    }
  } catch (e) {
    estado.textContent = "No se pudieron cargar los marcadores. Intenta más tarde.";
  }
}
cargarPartidosEnVivo();
setInterval(cargarPartidosEnVivo, 600000);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(console.error);
  });
}
</script>

</body>
</html>
"""

def forma_reciente(equipo):
    encontrados = []
    for p in PARTIDOS:
        if p["local"] == equipo:
            gf, gc, rival = p["gl"], p["gv"], p["visitante"]
        elif p["visitante"] == equipo:
            gf, gc, rival = p["gv"], p["gl"], p["local"]
        else:
            continue

        res = "G" if gf > gc else "E" if gf == gc else "P"
        encontrados.append({
            "fecha": p["fecha"].strftime("%d/%m/%Y"),
            "rival": rival,
            "gf": gf,
            "gc": gc,
            "res": res,
            "_fecha": p["fecha"],
        })

    encontrados.sort(key=lambda x: x["_fecha"])
    ultimos = encontrados[-5:]
    for p in ultimos:
        del p["_fecha"]
    puntos = sum(3 if p["res"] == "G" else
                 1 if p["res"] == "E" else 0 for p in ultimos)
    return ultimos, puntos

@app.route("/", methods=["GET", "POST"])
def inicio():
    elegido_local = request.form.get("local", "")
    elegido_visitante = request.form.get("visitante", "")
    resultado = None
    marcador = None
    nombre_pronostico = ""
    error = None
    formas = []
    puntos = []

    if request.method == "POST":
        if elegido_local not in EQUIPOS or elegido_visitante not in EQUIPOS:
            error = "Selecciona dos equipos de la lista."
        elif elegido_local == elegido_visitante:
            error = "Selecciona dos equipos diferentes."
        elif len(PARTIDOS) < ev.MIN_HISTORIAL:
            error = "No hay suficientes partidos históricos."
        else:
            resultado, pronostico, marcador = ev.predecir(
                PARTIDOS, elegido_local, elegido_visitante
            )
            nombres = {
                "1": "Victoria del equipo local",
                "X": "Empate",
                "2": "Victoria del equipo visitante",
            }
            nombre_pronostico = nombres[pronostico]

            for equipo in (elegido_local, elegido_visitante):
                recientes, pts = forma_reciente(equipo)
                formas.append((equipo, recientes))
                puntos.append(pts)

    return render_template_string(
        PAGINA,
        equipos=EQUIPOS,
        elegido_local=elegido_local,
        elegido_visitante=elegido_visitante,
        resultado=resultado,
        marcador=marcador,
        nombre_pronostico=nombre_pronostico,
        error=error,
        formas=formas,
        puntos=puntos,
        total_partidos=len(PARTIDOS),
    )



CACHE_EN_VIVO = {"momento": 0, "datos": None}

@app.route("/api/en-vivo")
def partidos_en_vivo():
    clave = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not clave:
        return jsonify({"ok": False, "error": "Falta configurar la clave de API."}), 503

    ahora = time.time()
    if CACHE_EN_VIVO["datos"] is not None and ahora - CACHE_EN_VIVO["momento"] < 1200:
        return jsonify(CACHE_EN_VIVO["datos"])

    try:
        req = Request(
            "https://v3.football.api-sports.io/fixtures?live=all",
            headers={"x-apisports-key": clave, "Accept": "application/json"}
        )
        with urlopen(req, timeout=15) as respuesta:
            contenido = json.loads(respuesta.read().decode("utf-8"))

        if contenido.get("errors"):
            errores = contenido.get("errors")
            if isinstance(errores, dict):
                diagnostico = ", ".join(str(k) for k in errores.keys())
            else:
                diagnostico = "error_devuelto_por_el_proveedor"

            return jsonify({
                "ok": False,
                "error": "API-Football rechazó la consulta.",
                "diagnostico": diagnostico or "error_no_especificado"
            }), 502

        partidos = []
        for item in contenido.get("response", []):
            fixture = item.get("fixture", {})
            equipos = item.get("teams", {})
            goles = item.get("goals", {})
            liga = item.get("league", {})
            estado = fixture.get("status", {})
            partidos.append({
                "liga": liga.get("name") or "Competición",
                "local": (equipos.get("home") or {}).get("name") or "Local",
                "visitante": (equipos.get("away") or {}).get("name") or "Visitante",
                "goles_local": goles.get("home") if goles.get("home") is not None else 0,
                "goles_visitante": goles.get("away") if goles.get("away") is not None else 0,
                "estado": str(estado.get("short") or "EN JUEGO") +
                    ((" · " + str(estado["elapsed"]) + "'") if estado.get("elapsed") is not None else "")
            })

        resultado = {"ok": True, "partidos": partidos}
        CACHE_EN_VIVO["momento"] = ahora
        CACHE_EN_VIVO["datos"] = resultado
        return jsonify(resultado)

    except (HTTPError, URLError, TimeoutError, ValueError):
        return jsonify({
            "ok": False,
            "error": "No fue posible conectar con el proveedor de marcadores."
        }), 502


@app.route("/manifest.webmanifest")
def manifiesto_pwa():
    from flask import send_from_directory
    return send_from_directory(
        "static", "manifest.webmanifest",
        mimetype="application/manifest+json"
    )

@app.route("/sw.js")
def servicio_pwa():
    from flask import send_from_directory
    respuesta = send_from_directory(
        "static", "sw.js",
        mimetype="application/javascript"
    )
    respuesta.headers["Service-Worker-Allowed"] = "/"
    respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta

if __name__ == "__main__":
    print("FutbolPredictor listo.")
    print("Equipos:", len(EQUIPOS))
    print("Partidos históricos:", len(PARTIDOS))
    print("Abre en el navegador: http://127.0.0.1:8080")
    app.run(host="127.0.0.1", port=8080, debug=False)
