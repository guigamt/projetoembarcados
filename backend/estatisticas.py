"""Estatisticas calculadas no backend (o agente so explica estes numeros)."""
import time

import config
import db

EVENTOS_DEG = ("degradada", "degradacao", "falha", "isolada")


def consultar_eventos(zona=None, dias=7, limite=50, tipo=None):
    desde = int(time.time()) - int(dias) * 86400
    sql = "SELECT event_id, incident_id, ts_evento, zona, tipo, estado, deg, motivo, " \
          "sensor_a, sensor_b, falha, teste, central, extra FROM eventos WHERE ts_evento>=?"
    args = [desde]
    if zona:
        sql += " AND zona=?"
        args.append(int(zona))
    if tipo:
        sql += " AND tipo=?"
        args.append(tipo)
    sql += " ORDER BY ts_evento DESC, id DESC LIMIT ?"
    args.append(int(limite))
    return db.consulta(sql, args)


def _tempo_degradado(zona, desde, agora):
    """Soma, em segundos, o tempo em que a zona ficou com DEG = 1 no periodo."""
    evs = db.consulta("SELECT ts_evento, deg FROM eventos WHERE zona=? AND ts_evento>=? "
                      "ORDER BY ts_evento, id", (zona, desde))
    total, inicio = 0, None
    for e in evs:
        if e["deg"] and inicio is None:
            inicio = e["ts_evento"]
        elif not e["deg"] and inicio is not None:
            total += e["ts_evento"] - inicio
            inicio = None
    if inicio is not None:
        total += agora - inicio          # ainda esta degradada
    return total


def calcular_estatisticas(zona=None, dias=7):
    agora = int(time.time())
    dias = max(1, int(dias))
    desde = agora - dias * 86400
    zonas = [int(zona)] if zona else [1, 2, 3, 4]

    por_zona = {}
    for z in zonas:
        r = db.um(
            "SELECT COUNT(*) disparos, COALESCE(SUM(confirmado),0) confirmados, "
            "COALESCE(SUM(degradado),0) degradados, COALESCE(SUM(rotulo='falso'),0) falsos, "
            "COALESCE(SUM(rotulo='real'),0) reais, AVG(prob_falso) prob_falso_media "
            "FROM incidentes WHERE zona=? AND ts_inicio>=? AND teste=0", (z, desde))
        r["nome"] = config.ZONAS.get(z, f"Zona {z}")
        r["testes"] = db.um("SELECT COUNT(*) n FROM incidentes WHERE zona=? AND ts_inicio>=? "
                            "AND teste=1", (z, desde))["n"]
        r["entradas_degradado"] = db.um(
            "SELECT COUNT(*) n FROM eventos WHERE zona=? AND ts_evento>=? AND teste=0 "
            "AND tipo IN ('degradada','degradacao','falha','isolada')", (z, desde))["n"]
        r["tempo_degradado_s"] = _tempo_degradado(z, desde, agora)
        if r["prob_falso_media"] is not None:
            r["prob_falso_media"] = round(r["prob_falso_media"], 2)
        por_zona[z] = r

    total = sum(v["disparos"] for v in por_zona.values())
    degr = sum(v["degradados"] for v in por_zona.values())
    mais_deg = max(por_zona, key=lambda z: (por_zona[z]["entradas_degradado"],
                                            por_zona[z]["tempo_degradado_s"]))
    mais_disp = max(por_zona, key=lambda z: por_zona[z]["disparos"])

    por_hora = [0] * 24
    filtro = "AND zona=?" if zona else ""
    args = (desde, int(zona)) if zona else (desde,)
    for r in db.consulta(f"SELECT ts_inicio FROM incidentes WHERE ts_inicio>=? AND teste=0 {filtro}", args):
        por_hora[time.localtime(r["ts_inicio"]).tm_hour] += 1

    recomendacoes = []
    for z, v in por_zona.items():
        if v["entradas_degradado"] >= 3 or v["tempo_degradado_s"] > 3600:
            recomendacoes.append(f"Zona {z}: muitas entradas em modo degradado. Verificar cabo, "
                                 "alinhamento e resposta dos sensores.")
        if v["disparos"] >= 3 and v["falsos"] / max(1, v["disparos"]) > 0.5:
            recomendacoes.append(f"Zona {z}: mais da metade dos disparos foi marcada como falsa. "
                                 "Rever posição/sensibilidade do sensor.")

    return {
        "periodo_dias": dias,
        "de": time.strftime("%d/%m/%Y %H:%M", time.localtime(desde)),
        "ate": time.strftime("%d/%m/%Y %H:%M", time.localtime(agora)),
        "total_disparos": total,
        "disparos_degradados": degr,
        "proporcao_degradados": round(degr / total, 2) if total else 0.0,
        "zona_mais_degradada": mais_deg if por_zona[mais_deg]["entradas_degradado"] else None,
        "zona_mais_disparos": mais_disp if por_zona[mais_disp]["disparos"] else None,
        "por_zona": por_zona,
        "disparos_por_hora": por_hora,
        "recomendacoes": recomendacoes,
    }


def consumo(dias=7):
    linhas = db.consulta("SELECT dia, mensagens, bytes FROM consumo ORDER BY dia DESC LIMIT ?", (int(dias),))
    hoje = time.strftime("%Y-%m-%d")
    msgs_hoje = next((l["mensagens"] for l in linhas if l["dia"] == hoje), 0)
    return {"limite_dia": config.LIMITE_MSG_DIA, "hoje": msgs_hoje,
            "uso_hoje": round(msgs_hoje / config.LIMITE_MSG_DIA, 3), "dias": linhas}
