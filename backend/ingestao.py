"""
Recebe as mensagens da central (vindas do IoT Hub ou do simulador), grava no
banco sem duplicar, atualiza os incidentes e dispara os alertas.
"""
import json
import threading
import time

import alertas
import config
import db
import ia

ATRASO_ALERTA_S = 2.5     # espera a confirmacao do 2o sensor para o alerta sair completo
_trava = threading.Lock()


def _grava_estado(msg, agora):
    resumo = {k: msg.get(k) for k in ("central", "modo_deg", "teste", "zonas", "rssi", "fila",
                                      "perdidos", "boot", "uptime_s", "fpga_ok")}
    antigo = db.um("SELECT json FROM estado WHERE id=1")
    if antigo and msg.get("tipo") != "status":
        # evento nao traz rssi/fila: mantem o que veio no ultimo status
        velho = json.loads(antigo["json"])
        for k in ("rssi", "fila", "perdidos", "boot", "uptime_s", "fpga_ok"):
            if resumo.get(k) is None:
                resumo[k] = velho.get(k)
        if resumo.get("modo_deg") is None:
            resumo["modo_deg"] = any(z.get("deg") for z in msg.get("zonas", []))
    db.executa("INSERT INTO estado (id, json, ts_dispositivo, ts_recebido) VALUES (1,?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET json=excluded.json, "
               "ts_dispositivo=excluded.ts_dispositivo, ts_recebido=excluded.ts_recebido",
               (json.dumps(resumo), msg.get("ts") or agora, agora))


def _atualiza_incidente(msg):
    iid = msg["incident_id"]
    inc = db.um("SELECT * FROM incidentes WHERE incident_id=?", (iid,))
    if not inc:
        db.executa("INSERT INTO incidentes (incident_id, zona, ts_inicio, estado, teste) "
                   "VALUES (?,?,?,?,?)",
                   (iid, msg["zona"], msg["ts"], msg.get("estado"), int(bool(msg.get("teste")))))
    estado = msg.get("estado")
    if msg["tipo"] == "fim_alarme":
        db.executa("UPDATE incidentes SET ts_fim=? WHERE incident_id=?", (msg["ts"], iid))
    else:
        db.executa(
            "UPDATE incidentes SET estado=?, confirmado=MAX(confirmado,?), degradado=MAX(degradado,?), "
            "motivo=CASE WHEN ?<>'' THEN ? ELSE motivo END, "
            "sensor_a=MAX(sensor_a,?), sensor_b=MAX(sensor_b,?), teste=MAX(teste,?) WHERE incident_id=?",
            (estado, int(estado == "AL_NORMAL"), int(estado == "AL_DEG"),
             msg.get("motivo") or "", msg.get("motivo") or "",
             int(bool(msg.get("sensor_a"))), int(bool(msg.get("sensor_b"))),
             int(bool(msg.get("teste"))), iid))
    inc = db.um("SELECT * FROM incidentes WHERE incident_id=?", (iid,))
    prob, expl = ia.avalia(inc)
    db.executa("UPDATE incidentes SET prob_falso=?, explicacao=? WHERE incident_id=?", (prob, expl, iid))


def _alerta_disparo(chave, zonas, quando, teste):
    def faz():
        texto = alertas.texto_disparo(zonas, quando, teste)
        nomes = ", ".join(f"Z{z}" for z in zonas)
        alertas.envia(chave, f"ALARME DISPARADO - zonas violadas: {nomes}", texto)
    if ATRASO_ALERTA_S > 0:
        threading.Timer(ATRASO_ALERTA_S, faz).start()
    else:
        faz()


def _decide_alertas(msg):
    tipo, teste = msg["tipo"], bool(msg.get("teste"))
    zonas = alertas.zonas_em_alarme(msg)
    if tipo == "central" and msg.get("central") == "DISPARO" and zonas:
        _alerta_disparo("disparo:" + msg["event_id"], zonas, msg["ts"], teste)
    elif tipo == "disparo" and msg.get("central") == "DISPARO":
        # central ja estava disparada e mais uma zona foi violada
        _alerta_disparo("zona:" + msg["incident_id"], [msg["zona"]], msg["ts"], teste)
    elif tipo in ("falha", "degradada", "isolada") and not teste:
        z = msg["zona"]
        texto = (f"MANUTENÇÃO: zona {z} - {config.ZONAS.get(z)} está em modo degradado "
                 f"({(msg.get('motivo') or tipo).replace('_', ' ')}). A cobertura está reduzida. "
                 "Verifique cabo, alinhamento e resposta do sensor.")
        alertas.envia("manut:" + msg["event_id"], f"Manutencao - zona {z} degradada", texto,
                      so_email=True, espera=False)
    elif tipo == "fpga_mudo":
        alertas.envia("manut:" + msg["event_id"], "Central sem resposta",
                      "A ESP32 parou de receber o estado do FPGA. Verifique a central.",
                      so_email=True, espera=False)


def processa(msg, n_bytes=0):
    """Processa uma mensagem (dict). Devolve 'status', 'resposta', 'evento' ou 'duplicado'."""
    agora = int(time.time())
    with _trava:
        db.conta_consumo(n_bytes or len(json.dumps(msg)))
        tipo = msg.get("tipo")

        if tipo == "status":
            _grava_estado(msg, agora)
            return "status"

        if tipo == "resposta":
            db.executa("UPDATE comandos SET detalhe=COALESCE(detalhe,'') || ' | central: ' || ? "
                       "WHERE cmd_id=?", (msg.get("resultado", ""), msg.get("cmd_id")))
            return "resposta"

        if not msg.get("event_id"):
            return "ignorado"
        if not msg.get("ts"):
            msg["ts"] = agora
        cur = db.executa(
            "INSERT OR IGNORE INTO eventos (event_id, incident_id, seq, ts_evento, ts_recebido, "
            "ts_estimado, zona, tipo, estado, deg, motivo, sensor_a, sensor_b, falha, teste, "
            "central, extra, bruto) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (msg["event_id"], msg.get("incident_id"), msg.get("seq"), msg["ts"], agora,
             int(bool(msg.get("ts_estimado"))), msg.get("zona", 0), tipo, msg.get("estado"),
             int(bool(msg.get("deg"))), msg.get("motivo"), int(bool(msg.get("sensor_a"))),
             int(bool(msg.get("sensor_b"))), int(bool(msg.get("falha"))),
             int(bool(msg.get("teste"))), msg.get("central"), msg.get("extra"), json.dumps(msg)))
        if cur.rowcount == 0:
            return "duplicado"        # QoS 1 pode entregar duas vezes: o event_id resolve

        # so atualiza o painel se o evento for mais novo que o estado guardado
        est = db.um("SELECT ts_dispositivo FROM estado WHERE id=1")
        if msg.get("zonas") and (not est or msg["ts"] >= (est["ts_dispositivo"] or 0)):
            _grava_estado(msg, agora)
        if msg.get("incident_id") and msg.get("zona"):
            _atualiza_incidente(msg)
    _decide_alertas(msg)
    return "evento"
