import csv
import math
from pathlib import Path
from datetime import datetime

ARCHIVOS = [
    Path("datos/partidos_e0_2425.csv"),
    Path("datos/partidos_e0_2526.csv"),
]
PESO_FORMA = 0.30
ULTIMOS = 10
MIN_HISTORIAL = 40


def leer_partidos():
    partidos = []

    for archivo in ARCHIVOS:
        if not archivo.exists():
            print(f"ERROR: no encuentro {archivo}")
            raise SystemExit(1)

        with archivo.open("r", encoding="utf-8-sig", newline="") as f:
            for fila in csv.DictReader(f):
                try:
                    fecha = datetime.strptime(
                        fila["Date"].strip(), "%d/%m/%Y"
                    ).date()
                    local = fila["HomeTeam"].strip()
                    visitante = fila["AwayTeam"].strip()
                    gl = int(fila["FTHG"])
                    gv = int(fila["FTAG"])
                except (KeyError, ValueError, AttributeError):
                    continue

                if local and visitante:
                    partidos.append({
                        "fecha": fecha,
                        "local": local,
                        "visitante": visitante,
                        "gl": gl,
                        "gv": gv,
                        "resultado": (
                            "1" if gl > gv else
                            "2" if gl < gv else "X"
                        ),
                        "temporada": archivo.stem,
                    })

    partidos.sort(key=lambda p: (
        p["fecha"], p["local"], p["visitante"]
    ))
    return partidos


def promedio(valores, defecto):
    return sum(valores) / len(valores) if valores else defecto


def poisson(lam, goles):
    if lam <= 0:
        return 1.0 if goles == 0 else 0.0
    return math.exp(
        -lam + goles * math.log(lam) - math.lgamma(goles + 1)
    )


def predecir(historial, local, visitante):
    media_local = promedio([p["gl"] for p in historial], 1.45)
    media_visitante = promedio([p["gv"] for p in historial], 1.15)

    local_casa = [p for p in historial if p["local"] == local]
    visitante_fuera = [
        p for p in historial if p["visitante"] == visitante
    ]

    gl_local = promedio(
        [p["gl"] for p in local_casa], media_local
    )
    gc_local = promedio(
        [p["gv"] for p in local_casa], media_visitante
    )
    gl_visitante = promedio(
        [p["gv"] for p in visitante_fuera], media_visitante
    )
    gc_visitante = promedio(
        [p["gl"] for p in visitante_fuera], media_local
    )

    base_local = gl_local * gc_visitante / max(media_local, 0.1)
    base_visitante = (
        gl_visitante * gc_local / max(media_visitante, 0.1)
    )

    local_hist = [
        p for p in historial
        if p["local"] == local or p["visitante"] == local
    ][-ULTIMOS:]

    visita_hist = [
        p for p in historial
        if p["local"] == visitante or p["visitante"] == visitante
    ][-ULTIMOS:]

    def goles_equipo(partido, equipo):
        if partido["local"] == equipo:
            return partido["gl"], partido["gv"]
        return partido["gv"], partido["gl"]

    local_gf = promedio(
        [goles_equipo(p, local)[0] for p in local_hist],
        media_local
    )
    local_gc = promedio(
        [goles_equipo(p, local)[1] for p in local_hist],
        media_visitante
    )
    visita_gf = promedio(
        [goles_equipo(p, visitante)[0] for p in visita_hist],
        media_visitante
    )
    visita_gc = promedio(
        [goles_equipo(p, visitante)[1] for p in visita_hist],
        media_local
    )

    forma_local = local_gf * visita_gc / max(media_local, 0.1)
    forma_visitante = (
        visita_gf * local_gc / max(media_visitante, 0.1)
    )

    eg_local = max(
        0.05,
        (1 - PESO_FORMA) * base_local
        + PESO_FORMA * forma_local
    )
    eg_visitante = max(
        0.05,
        (1 - PESO_FORMA) * base_visitante
        + PESO_FORMA * forma_visitante
    )

    pl = [poisson(eg_local, g) for g in range(11)]
    pv = [poisson(eg_visitante, g) for g in range(11)]

    p1 = px = p2 = 0.0
    mejor_marcador = (0, 0)
    mejor_prob = -1.0

    for i, pi in enumerate(pl):
        for j, pj in enumerate(pv):
            prob = pi * pj

            if i > j:
                p1 += prob
            elif i == j:
                px += prob
            else:
                p2 += prob

            if prob > mejor_prob:
                mejor_prob = prob
                mejor_marcador = (i, j)

    total = p1 + px + p2
    probabilidades = {
        "1": p1 / total,
        "X": px / total,
        "2": p2 / total,
    }
    pronostico = max(probabilidades, key=probabilidades.get)

    return probabilidades, pronostico, mejor_marcador


def evaluar(partidos, nombre, filtro):
    correctos = total = exactos = 0
    perdida = 0.0

    for partido in partidos:
        if not filtro(partido):
            continue

        # Solo se permite usar partidos de fechas anteriores.
        historial = [
            p for p in partidos
            if p["fecha"] < partido["fecha"]
        ]

        if len(historial) < MIN_HISTORIAL:
            continue

        probs, pred, marcador = predecir(
            historial, partido["local"], partido["visitante"]
        )

        total += 1
        if pred == partido["resultado"]:
            correctos += 1

        if marcador == (partido["gl"], partido["gv"]):
            exactos += 1

        perdida -= math.log(
            max(probs[partido["resultado"]], 1e-12)
        )

    if total == 0:
        print(f"\n{nombre}: no hubo suficientes partidos.")
        return

    print(f"\n--- {nombre} ---")
    print(f"Partidos evaluados: {total}")
    print(
        f"Aciertos 1X2: {correctos}/{total} "
        f"({100 * correctos / total:.1f}%)"
    )
    print(
        f"Marcador exacto: {exactos}/{total} "
        f"({100 * exactos / total:.1f}%)"
    )
    print(f"Log loss promedio: {perdida / total:.4f}")
    print("(En log loss, un valor menor es mejor.)")


def main():
    partidos = leer_partidos()

    if not partidos:
        print("ERROR: no se pudieron leer los CSV.")
        return

    print("=== EVALUACION HISTORICA SIN DATOS FUTUROS ===")
    print(f"Partidos cargados: {len(partidos)}")
    print(f"Peso de forma reciente: {int(PESO_FORMA * 100)}%")
    print(f"Historial mínimo: {MIN_HISTORIAL} partidos")

    evaluar(
        partidos, "TEMPORADA 2024/25",
        lambda p: p["temporada"] == "partidos_e0_2425"
    )
    evaluar(
        partidos, "TEMPORADA 2025/26",
        lambda p: p["temporada"] == "partidos_e0_2526"
    )
    evaluar(
        partidos, "TOTAL DE LAS DOS TEMPORADAS",
        lambda p: True
    )

    print("\nIMPORTANTE:")
    print("Se excluyen todos los partidos de la misma fecha.")
    print("Es una evaluación histórica, no una garantía futura.")


if __name__ == "__main__":
    main()
