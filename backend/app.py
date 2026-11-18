"""
Backend da central de alarme (Flask).

  /api/login          entra no painel (devolve um token)
  /api/estado         central, 4 zonas, conexao e idade do dado
  /api/comando        arme / desarme (desarme exige PIN)
  /api/eventos        historico de eventos
  /api/incidentes     disparos (um por incidente) + marcar real/falso
  /api/estatisticas   numeros calculados aqui (o agente so explica)
  /api/agente         pergunta em texto (a voz vira texto no celular)
  /api/contatos       quem recebe os alertas
  /api/alertas        alertas enviados
  /api/consumo        mensagens por dia (cota do IoT Hub F1)
  /api/sim/...        so no modo simulado: mexe nos sensores da central simulada

O aplicativo (PWA em React) fica em ../app/dist e e servido por este mesmo servidor.

Rodar:  python app.py      (abre em http://localhost:8000)
"""
import functools
import json
import os
import time
import uuid

import jwt
from flask import Flask, jsonify, request, send_from_directory, g

import agente
import alertas
import config
import db
import estatisticas
import ia
import transporte

PASTA_APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "dist")
NUM_ESTADO = {"ISOLADA": 0, "MONITORA": 1, "VIGIA": 2, "CONFIRMA": 3, "AL_NORMAL": 4, "AL_DEG": 5}


def cria_app(central=None):
    app = Flask(__name__, static_folder=None)
    db.inicia()
    app.central = central or transporte.cria()

    # ------------------------------------------------------------ login
    def protegido(f):
        @functools.wraps(f)
        def dentro(*a, **k):
            cab = request.headers.get("Authorization", "")
            try:
                dados = jwt.decode(cab.replace("Bearer ", ""), config.SECRET_KEY, algorithms=["HS256"])
            except jwt.PyJWTError:
                return jsonify(erro="login necessario"), 401
            g.usuario = dados["email"]
            return f(*a, **k)
        return dentro

    @app.post("/api/login")
    def login():
        d = request.get_json(silent=True) or {}
        u = db.um("SELECT * FROM usuarios WHERE email=?", (d.get("email", "").strip().lower(),))
        if not u or not db.confere_hash(d.get("senha", ""), u["senha_hash"]):
            return jsonify(erro="e-mail ou senha incorretos"), 401
        token = jwt.encode({"email": u["email"], "exp": int(time.time()) + 12 * 3600},
                           config.SECRET_KEY, algorithm="HS256")
        return jsonify(token=token, nome=u["nome"])

    # ------------------------------------------------------------ estado
    def le_estado():
        agora = int(time.time())
        linha = db.um("SELECT * FROM estado WHERE id=1")
        if not linha:
            return {"central": "DESCONHECIDO", "zonas": [], "modo_deg": False, "teste": False,
                    "conexao": {"online": False, "idade_s": None, "ts_recebido": None},
                    "simulador": app.central.nome == "simulador"}
        e = json.loads(linha["json"])
        idade = agora - linha["ts_recebido"]
        zonas = []
        for i, z in enumerate(e.get("zonas") or []):
            zonas.append({"zona": i + 1, "nome": config.ZONAS.get(i + 1), "estado": z.get("e"),
                          "deg": bool(z.get("deg")), "motivo": z.get("motivo") or "",
                          "falha": bool(z.get("f")), "sensores": list(config.SENSORES[i + 1])})
        pend = db.um("SELECT cmd_id, acao, ts_pedido FROM comandos WHERE status='pendente' "
                     "ORDER BY ts_pedido DESC LIMIT 1")
        return {
            "central": e.get("central"), "modo_deg": bool(e.get("modo_deg")),
            "teste": bool(e.get("teste")), "zonas": zonas,
            "conexao": {"online": idade <= config.ESTADO_VELHO_S, "idade_s": idade,
                        "ts_recebido": linha["ts_recebido"], "ts_dispositivo": linha["ts_dispositivo"],
                        "rssi": e.get("rssi"), "fila": e.get("fila"), "perdidos": e.get("perdidos"),
                        "fpga_ok": e.get("fpga_ok"), "boot": e.get("boot")},
            "comando_pendente": pend, "simulador": app.central.nome == "simulador"}

    @app.get("/api/estado")
    @protegido
    def estado():
        return jsonify(le_estado())

    # ------------------------------------------------------------ comandos
    def pede_comando(acao, origem, usuario, cmd_id=None):
        """Autoriza, registra, envia e espera a resposta da central."""
        cmd_id = cmd_id or uuid.uuid4().hex[:16]
        ja = db.um("SELECT * FROM comandos WHERE cmd_id=?", (cmd_id,))
        if ja and ja["status"] != "pendente":
            return {"cmd_id": cmd_id, "status": ja["status"], "detalhe": "resultado ja conhecido"}
        agora = int(time.time())
        expira = agora + config.VALIDADE_COMANDO_S
        if not ja:
            db.executa("INSERT INTO comandos (cmd_id, acao, origem, usuario, ts_pedido, expira, status) "
                       "VALUES (?,?,?,?,?,?, 'pendente')", (cmd_id, acao, origem, usuario, agora, expira))
        resultado, detalhe = app.central.comando({"cmd_id": cmd_id, "acao": acao, "expira": expira})
        status = {"confirmado": "confirmado", "recusado": "recusado", "expirado": "expirado",
                  "sem_conexao": "sem_confirmacao", "sem_resposta_fpga": "sem_confirmacao"}.get(resultado, "erro")
        db.executa("UPDATE comandos SET status=?, ts_resposta=?, detalhe=? WHERE cmd_id=?",
                   (status, int(time.time()), f"{resultado}: {detalhe}", cmd_id))
        return {"cmd_id": cmd_id, "status": status, "detalhe": detalhe}

    @app.post("/api/comando")
    @protegido
    def comando():
        d = request.get_json(silent=True) or {}
        acao = d.get("acao")
        if acao not in ("armar", "desarmar"):
            return jsonify(erro="acao deve ser armar ou desarmar"), 400
        if acao == "desarmar":
            u = db.um("SELECT pin_hash FROM usuarios WHERE email=?", (g.usuario,))
            if not db.confere_hash(str(d.get("pin", "")), u["pin_hash"]):
                return jsonify(erro="PIN incorreto"), 403
        origem = d.get("origem") if d.get("origem") in ("painel", "voz", "agente") else "painel"
        return jsonify(pede_comando(acao, origem, g.usuario, d.get("cmd_id")))

    @app.get("/api/comandos")
    @protegido
    def comandos():
        return jsonify(db.consulta("SELECT * FROM comandos ORDER BY ts_pedido DESC LIMIT 30"))

    # ------------------------------------------------------------ historico
    @app.get("/api/eventos")
    @protegido
    def eventos():
        a = request.args
        return jsonify(estatisticas.consultar_eventos(a.get("zona"), a.get("dias", 7),
                                                      min(int(a.get("limite", 100)), 500)))

    @app.get("/api/incidentes")
    @protegido
    def incidentes():
        dias = int(request.args.get("dias", 30))
        linhas = db.consulta("SELECT * FROM incidentes WHERE ts_inicio>=? ORDER BY ts_inicio DESC LIMIT 200",
                             (int(time.time()) - dias * 86400,))
        for l in linhas:
            l["nome"] = config.ZONAS.get(l["zona"])
            l["confianca"] = ia.confianca(l["prob_falso"])
        return jsonify(linhas)

    @app.post("/api/incidentes/<iid>/rotulo")
    @protegido
    def rotulo(iid):
        r = (request.get_json(silent=True) or {}).get("rotulo")
        if r not in ("real", "falso", None):
            return jsonify(erro="rotulo deve ser real, falso ou null"), 400
        db.executa("UPDATE incidentes SET rotulo=? WHERE incident_id=?", (r, iid))
        return jsonify(ok=True, modelo_treinado=ia.treina())

    @app.get("/api/estatisticas")
    @protegido
    def estat():
        a = request.args
        return jsonify(estatisticas.calcular_estatisticas(a.get("zona") or None, a.get("dias", 7)))

    @app.get("/api/consumo")
    @protegido
    def consumo():
        return jsonify(estatisticas.consumo())

    # ------------------------------------------------------------ agente
    @app.post("/api/agente")
    @protegido
    def fala_agente():
        pergunta = ((request.get_json(silent=True) or {}).get("mensagem") or "").strip()
        if not pergunta:
            return jsonify(erro="mensagem vazia"), 400
        ctx = agente.Contexto(le_estado, pede_comando, g.usuario)
        return jsonify(agente.responde(pergunta[:500], ctx))

    # ------------------------------------------------------------ contatos / alertas
    @app.get("/api/contatos")
    @protegido
    def contatos():
        return jsonify(db.consulta("SELECT * FROM contatos ORDER BY id"))

    @app.post("/api/contatos")
    @protegido
    def novo_contato():
        d = request.get_json(silent=True) or {}
        if not d.get("nome") or not (d.get("email") or d.get("whatsapp") or d.get("telegram_chat")):
            return jsonify(erro="informe o nome e pelo menos um canal"), 400
        cur = db.executa("INSERT INTO contatos (nome, email, whatsapp, callmebot_key, telegram_chat) "
                         "VALUES (?,?,?,?,?)", (d["nome"], d.get("email"), d.get("whatsapp"),
                                                d.get("callmebot_key"), d.get("telegram_chat")))
        return jsonify(id=cur.lastrowid)

    @app.delete("/api/contatos/<int:cid>")
    @protegido
    def apaga_contato(cid):
        db.executa("DELETE FROM contatos WHERE id=?", (cid,))
        return jsonify(ok=True)

    @app.post("/api/contatos/teste")
    @protegido
    def testa_alerta():
        alertas.envia(f"teste:{int(time.time())}", "Teste de alerta da central",
                      "[TESTE] Este e um alerta de teste enviado pelo painel da central de alarme.")
        return jsonify(db.consulta("SELECT canal, destino, ok, detalhe FROM alertas ORDER BY id DESC LIMIT 6"))

    @app.get("/api/alertas")
    @protegido
    def lista_alertas():
        return jsonify(db.consulta("SELECT * FROM alertas ORDER BY id DESC LIMIT 50"))

    # ------------------------------------------------------------ simulador
    @app.route("/api/sim", methods=["GET", "POST"])
    @protegido
    def sim():
        c = app.central
        if c.nome != "simulador":
            return jsonify(erro="o backend esta ligado na central real"), 400
        if request.method == "POST":
            d = request.get_json(silent=True) or {}
            if "zona" in d:
                c.sensor(int(d["zona"]), d.get("campo", "a"), d.get("valor"))
            if d.get("reconhecer"):
                c.reconhece_deg()
            c.configura(d.get("atraso_sel"), d.get("teste"), d.get("online"))
        return jsonify(c.situacao())

    # ------------------------------------------------------------ aplicativo (PWA)
    @app.get("/")
    @app.get("/<path:caminho>")
    def estatico(caminho="index.html"):
        if caminho.startswith("api/"):
            return jsonify(erro="rota inexistente"), 404
        if not os.path.exists(os.path.join(PASTA_APP, caminho)):
            caminho = "index.html"
        return send_from_directory(PASTA_APP, caminho)

    return app


if __name__ == "__main__":
    app = cria_app()
    app.central.inicia()
    modo = "SIMULADOR" if app.central.nome == "simulador" else "AZURE IoT HUB"
    print(f"\n  Central de alarme - backend no modo {modo}\n  Painel: http://localhost:8000\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), threaded=True)
