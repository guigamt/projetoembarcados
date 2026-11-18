"""
Testes do backend com a central simulada (sem rede e sem placa).
Rodar dentro da pasta backend:   python -m pytest -q
"""
import base64
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: E402


@pytest.fixture()
def amb(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BANCO", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "OLLAMA_URL", "")
    monkeypatch.setattr(config, "SMTP_USER", "")
    import ingestao
    import simulador
    from app import cria_app
    monkeypatch.setattr(ingestao, "ATRASO_ALERTA_S", 0)
    sim = simulador.Simulador(tcorr_sel=0, atraso_sel=0)     # Tcorr 0,1 s = 5 passos
    app = cria_app(sim)
    sim._status()
    cli = app.test_client()
    r = cli.post("/api/login", json={"email": config.ADMIN_EMAIL, "senha": config.ADMIN_SENHA})
    assert r.status_code == 200
    cab = {"Authorization": "Bearer " + r.get_json()["token"]}
    return cli, cab, sim


def armar(cli, cab):
    r = cli.post("/api/comando", json={"acao": "armar"}, headers=cab).get_json()
    assert r["status"] == "confirmado", r
    return r


def test_login_obrigatorio(amb):
    cli, cab, sim = amb
    assert cli.get("/api/estado").status_code == 401
    assert cli.post("/api/login", json={"email": "x", "senha": "y"}).status_code == 401


def test_estado_inicial(amb):
    cli, cab, sim = amb
    e = cli.get("/api/estado", headers=cab).get_json()
    assert e["central"] == "DESARMADO" and len(e["zonas"]) == 4
    assert e["conexao"]["online"] and e["simulador"]
    assert all(z["estado"] == "MONITORA" for z in e["zonas"])


def test_arme_confirmado_e_desarme_exige_pin(amb):
    cli, cab, sim = amb
    armar(cli, cab)
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "ARMADO"
    assert cli.post("/api/comando", json={"acao": "desarmar", "pin": "0000"}, headers=cab).status_code == 403
    r = cli.post("/api/comando", json={"acao": "desarmar", "pin": config.ADMIN_PIN}, headers=cab).get_json()
    assert r["status"] == "confirmado"
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "DESARMADO"


def test_arme_recusado_com_porta_aberta(amb):
    cli, cab, sim = amb
    sim.sensor(1, "a", True)
    sim.passos(3)
    r = cli.post("/api/comando", json={"acao": "armar"}, headers=cab).get_json()
    assert r["status"] == "recusado"
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "DESARMADO"


def test_cmd_id_repetido_devolve_resultado_conhecido(amb):
    cli, cab, sim = amb
    r1 = cli.post("/api/comando", json={"acao": "armar", "cmd_id": "abc123"}, headers=cab).get_json()
    cli.post("/api/comando", json={"acao": "desarmar", "pin": config.ADMIN_PIN}, headers=cab)
    r2 = cli.post("/api/comando", json={"acao": "armar", "cmd_id": "abc123"}, headers=cab).get_json()
    assert r1["status"] == r2["status"] == "confirmado"
    # o pedido repetido NAO armou de novo
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "DESARMADO"


def test_comando_vencido_nao_executa(amb):
    cli, cab, sim = amb
    res, _ = sim.comando({"cmd_id": "velho", "acao": "armar", "expira": time.time() - 1})
    assert res == "expirado" and not sim.central.armada


def test_central_sem_conexao(amb):
    cli, cab, sim = amb
    sim.configura(online=False)
    r = cli.post("/api/comando", json={"acao": "armar"}, headers=cab).get_json()
    assert r["status"] == "sem_confirmacao"


def test_disparo_confirmado_gera_um_incidente_e_alerta_com_zona(amb):
    cli, cab, sim = amb
    cli.post("/api/contatos", json={"nome": "Dono", "email": "dono@exemplo.com"}, headers=cab)
    armar(cli, cab)
    sim.sensor(1, "a", True)
    sim.passos(2)
    sim.sensor(1, "b", True)          # segundo sensor dentro de Tcorr
    sim.passos(10)
    e = cli.get("/api/estado", headers=cab).get_json()
    assert e["central"] == "DISPARO" and e["zonas"][0]["estado"] == "AL_NORMAL"
    incs = cli.get("/api/incidentes", headers=cab).get_json()
    assert len(incs) == 1                       # disparo + confirmacao = 1 incidente so
    assert incs[0]["confirmado"] == 1 and incs[0]["degradado"] == 0 and incs[0]["zona"] == 1
    assert incs[0]["confianca"] == "alta"
    al = cli.get("/api/alertas", headers=cab).get_json()
    assert len(al) == 1 and "Zona 1" in al[0]["texto"] and "Zonas violadas" in al[0]["texto"]


def test_disparo_sem_confirmacao_fica_degradado(amb):
    cli, cab, sim = amb
    armar(cli, cab)
    sim.sensor(2, "b", True)
    sim.passos(2)
    assert cli.get("/api/estado", headers=cab).get_json()["zonas"][1]["estado"] == "CONFIRMA"
    sim.passos(10)
    z = cli.get("/api/estado", headers=cab).get_json()["zonas"][1]
    assert z["estado"] == "AL_DEG" and z["deg"] and z["motivo"] == "sem_confirmacao"
    inc = cli.get("/api/incidentes", headers=cab).get_json()[0]
    assert inc["degradado"] == 1 and inc["confirmado"] == 0 and inc["prob_falso"] > 0.5


def test_duas_zonas_aparecem_no_alerta(amb):
    cli, cab, sim = amb
    cli.post("/api/contatos", json={"nome": "Dono", "email": "dono@exemplo.com"}, headers=cab)
    armar(cli, cab)
    sim.sensor(1, "a", True)
    sim.sensor(3, "a", True)
    sim.passos(10)
    textos = " ".join(a["texto"] for a in cli.get("/api/alertas", headers=cab).get_json())
    assert "Zona 1" in textos and "Zona 3" in textos


def test_evento_duplicado_e_descartado(amb):
    cli, cab, sim = amb
    import ingestao
    msg = {"tipo": "disparo", "event_id": "dup-1", "incident_id": "dup-i1", "seq": 1,
           "ts": int(time.time()), "zona": 4, "estado": "CONFIRMA", "central": "ARMADO",
           "zonas": [{"e": "VIGIA"}] * 3 + [{"e": "CONFIRMA"}]}
    assert ingestao.processa(dict(msg)) == "evento"
    assert ingestao.processa(dict(msg)) == "duplicado"
    assert len(cli.get("/api/incidentes", headers=cab).get_json()) == 1


def test_isolamento_e_estatisticas(amb):
    cli, cab, sim = amb
    sim.sensor(3, "en", False)
    sim.passos(3)
    z = cli.get("/api/estado", headers=cab).get_json()["zonas"][2]
    assert z["estado"] == "ISOLADA" and z["deg"] and z["motivo"] == "isolada"
    armar(cli, cab)                             # arma com a zona 3 isolada
    sim.sensor(2, "b", True)
    sim.passos(10)
    e = cli.get("/api/estatisticas?dias=1", headers=cab).get_json()
    assert e["total_disparos"] == 1 and e["disparos_degradados"] == 1
    assert e["proporcao_degradados"] == 1.0
    assert e["por_zona"]["3"]["entradas_degradado"] == 1


def test_agente_por_regras(amb):
    cli, cab, sim = amb
    r = cli.post("/api/agente", json={"mensagem": "como esta a central?"}, headers=cab).get_json()
    assert "DESARMADO" in r["resposta"] and r["modo"] == "regras"
    r = cli.post("/api/agente", json={"mensagem": "armar o alarme"}, headers=cab).get_json()
    assert "armada" in r["resposta"].lower()
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "ARMADO"
    # desarme pelo agente NAO executa: fica pendente de PIN
    r = cli.post("/api/agente", json={"mensagem": "pode desarmar"}, headers=cab).get_json()
    assert r["acao_pendente"] == "desarmar"
    assert cli.get("/api/estado", headers=cab).get_json()["central"] == "ARMADO"
    sim.sensor(2, "b", True)
    sim.passos(10)
    r = cli.post("/api/agente", json={"mensagem": "qual zona mais entrou em modo degradado?"},
                 headers=cab).get_json()
    assert "zona 2" in r["resposta"].lower() and "calcular_estatisticas" in r["dados"]


def test_rotulo_e_treino_do_modelo(amb):
    cli, cab, sim = amb
    import ingestao
    import ia
    agora = int(time.time())
    for i in range(24):
        falso = i % 2 == 0
        ingestao.processa({"tipo": "disparo", "event_id": f"t-{i}", "incident_id": f"t-i{i}", "seq": i,
                           "ts": agora - i * 600, "zona": 1 + i % 4,
                           "estado": "AL_DEG" if falso else "AL_NORMAL",
                           "motivo": "sem_confirmacao" if falso else "", "sensor_a": True,
                           "sensor_b": not falso, "central": "ARMADO", "zonas": []})
        r = cli.post(f"/api/incidentes/t-i{i}/rotulo", json={"rotulo": "falso" if falso else "real"}, headers=cab)
        assert r.status_code == 200
    assert ia.treina()
    p_falso, _ = ia.avalia({"zona": 1, "ts_inicio": agora, "confirmado": 0, "degradado": 1,
                            "motivo": "sem_confirmacao", "teste": 0})
    p_real, _ = ia.avalia({"zona": 1, "ts_inicio": agora, "confirmado": 1, "degradado": 0,
                           "motivo": "", "teste": 0})
    assert p_falso > 0.6 > p_real


def test_sas_token_formato():
    import transporte
    chave = base64.b64encode(b"chave-de-teste-123").decode()
    t = transporte.sas_token("meuhub.azure-devices.net", chave, "service", 3600, agora=1700000000)
    assert t.startswith("SharedAccessSignature sr=meuhub.azure-devices.net&sig=")
    assert t.endswith("&se=1700003600&skn=service")
    # mesma entrada, mesma assinatura (HMAC e deterministico)
    assert t == transporte.sas_token("meuhub.azure-devices.net", chave, "service", 3600, agora=1700000000)


def test_consumo_conta_mensagens(amb):
    cli, cab, sim = amb
    c = cli.get("/api/consumo", headers=cab).get_json()
    assert c["hoje"] >= 1 and c["limite_dia"] == 8000
