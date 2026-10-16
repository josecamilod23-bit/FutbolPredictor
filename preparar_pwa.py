from pathlib import Path
import json, struct, zlib, math

base = Path("static")
(base / "icons").mkdir(parents=True, exist_ok=True)

manifest = {
    "id": "/",
    "name": "FutbolPredictor",
    "short_name": "FutbolPredictor",
    "description": "Analisis estadistico de partidos de futbol",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#101722",
    "theme_color": "#101722",
    "icons": [
        {"src": "/static/icons/icon-192.png",
         "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icons/icon-512.png",
         "sizes": "512x512", "type": "image/png"}
    ]
}
(base / "manifest.webmanifest").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)

sw = r"""
const CACHE = "futbolpredictor-v1";
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.add("/"))
  );
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request).then(response => {
      if (response.ok && url.pathname === "/") {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put("/", copy));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});
"""
(base / "sw.js").write_text(sw, encoding="utf-8")

# Crear iconos PNG sin instalar bibliotecas adicionales
def crear_icono(n, destino):
    pix = bytearray([16, 23, 34] * n * n)

    def punto(x, y, color):
        if 0 <= x < n and 0 <= y < n:
            i = (y * n + x) * 3
            pix[i:i+3] = bytes(color)

    def circulo(cx, cy, r, color):
        for y in range(max(0, int(cy-r)), min(n, int(cy+r+1))):
            for x in range(max(0, int(cx-r)), min(n, int(cx+r+1))):
                if (x-cx)**2 + (y-cy)**2 <= r*r:
                    punto(x, y, color)

    verde = (50, 217, 149)
    blanco = (245, 248, 252)
    negro = (16, 23, 34)
    circulo(n/2, n/2, n*0.39, verde)
    circulo(n/2, n/2, n*0.255, blanco)

    cx, cy, r = n/2, n/2, n*0.105
    vertices = [
        (cx + r*math.cos(-math.pi/2 + k*2*math.pi/5),
         cy + r*math.sin(-math.pi/2 + k*2*math.pi/5))
        for k in range(5)
    ]
    for y in range(int(cy-r-2), int(cy+r+3)):
        for x in range(int(cx-r-2), int(cx+r+3)):
            dentro = False
            j = 4
            for i in range(5):
                xi, yi = vertices[i]
                xj, yj = vertices[j]
                if ((yi > y) != (yj > y)) and (
                    x < (xj-xi)*(y-yi)/(yj-yi+1e-12)+xi
                ):
                    dentro = not dentro
                j = i
            if dentro:
                punto(x, y, negro)

    def linea(x1, y1, x2, y2, color, grosor):
        pasos = max(1, int(math.hypot(x2-x1, y2-y1)))
        for k in range(pasos+1):
            x = round(x1+(x2-x1)*k/pasos)
            y = round(y1+(y2-y1)*k/pasos)
            circulo(x, y, grosor, color)

    for x, y in vertices:
        linea(cx, cy, x, y, negro, max(1, n//100))

    filas = []
    for y in range(n):
        filas.append(b"\x00" + bytes(pix[y*n*3:(y+1)*n*3]))
    def chunk(tipo, datos):
        contenido = tipo + datos
        return struct.pack(">I", len(datos)) + contenido + struct.pack(
            ">I", zlib.crc32(contenido) & 0xffffffff
        )
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(filas), 9))
           + chunk(b"IEND", b""))
    Path(destino).write_bytes(png)

crear_icono(192, "static/icons/icon-192.png")
crear_icono(512, "static/icons/icon-512.png")

# Integrar el manifiesto en la pagina existente
archivo = Path("app.py")
codigo = archivo.read_text(encoding="utf-8")
meta = '''<meta name="theme-color" content="#101722">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/static/icons/icon-192.png">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">'''
viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
if 'rel="manifest"' not in codigo:
    if viewport not in codigo:
        raise SystemExit("No encontre la cabecera esperada. No se modifico app.py.")
    codigo = codigo.replace(viewport, viewport + "\n" + meta, 1)

registro = """
<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(console.error);
  });
}
</script>
"""
if 'navigator.serviceWorker.register("/sw.js")' not in codigo:
    if "</body>" not in codigo:
        raise SystemExit("No encontre el cierre body. No se modifico app.py.")
    codigo = codigo.replace("</body>", registro + "\n</body>", 1)

rutas = '''
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

'''
if '@app.route("/manifest.webmanifest")' not in codigo:
    marcador = 'if __name__ == "__main__":'
    if marcador not in codigo:
        raise SystemExit("No encontre el punto para agregar las rutas.")
    codigo = codigo.replace(marcador, rutas + marcador, 1)

compile(codigo, "app.py", "exec")
archivo.write_text(codigo, encoding="utf-8")
print("Archivos PWA creados.")
print("Cabecera y rutas agregadas.")
