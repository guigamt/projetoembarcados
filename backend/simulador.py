"""
Central SIMULADA. Usa o mesmo modelo das MEFs da pasta modelo/ e gera as mesmas
mensagens JSON que a ESP32 gera. Serve para desenvolver e testar o painel, os
alertas e o agente sem a placa, e como plano B na apresentacao (o painel avisa
"MODO SIMULADO").
"""
import os
import sys
import threading
import time

import ingestao

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modelo"))
from modelo_mef import MefZona, MefCentral, NOMES_ZONA  # noqa: E402

NOMES_CENTRAL = ["DESARMADO", "ARMADO", "ATRASO", "DISPARO"]
MOTIVOS = ["", "sem_confirmacao", "falha_sensor", "isolada"]
CLK_HZ = 50                 # 50 passos por segundo de simulacao


class Simulador:
    nome = "simulador"

    def __init__(self, tcorr_sel=2, atraso_sel=0):
        self.trava = threading.RLock()
        self.zonas = [MefZona(CLK_HZ, tcorr_sel) for _ in range(4)]
        self.central = MefCentral(CLK_HZ, 10, atraso_sel)
        self.sens = [{"a": False, "b": False, "f": False, "en": True} for _ in range(4)]
        self.teste = False
        self.boot = int(time.time()) % 100000
        self.n_evento = 0
        self.n_incidente = 0
        self.inc_zona = [0, 0, 0, 0]
        self.anterior = None
        self.cmds = {}              # cmd_id -> resultado (para pedidos repetidos)
        self.online = True          # False = simula central sem internet
        self.pend_arm = self.pend_dis = self.pend_rec = False
        self.ultimo_status = 0
        for _ in range(CLK_HZ):     # diagnostico inicial das zonas
            self._passo()
        self.anterior = self._foto()

    # ------------------------------------------------------------ MEFs
    def _passo(self):
        arm, dis, rec = self.pend_arm, self.pend_dis, self.pend_rec
        self.pend_arm = self.pend_dis = self.pend_rec = False
        armada = self.central.armada
        al = en = pronta = 0
        for i, z in enumerate(self.zonas):
            s = self.sens[i]
            if z.al:
                al |= 1 << i
            if s["en"]:
                en |= 1 << i
            if z.pronta:
                pronta |= 1 << i
        for i, z in enumerate(self.zonas):
            s = self.sens[i]
            z.passo(en=s["en"], armada=armada, r=s["a"], u=s["b"], f=s["f"], rec_deg=rec)
        self.central.passo(arm_req=arm, disarm_req=dis, al_z=al, en_z=en, pronta_z=pronta)

    def _foto(self):
        return {
            "central": NOMES_CENTRAL[self.central.est],
            "teste": self.teste,
            "zonas": [{"e": NOMES_ZONA[z.est], "deg": bool(z.deg), "motivo": MOTIVOS[z.motivo],
                       "f": bool(self.sens[i]["f"]), "a": bool(z.viu_r), "b": bool(z.viu_u)}
                      for i, z in enumerate(self.zonas)],
        }

    # ------------------------------------------------------------ mensagens
    def _evento(self, tipo, zona, incidente, foto):
        self.n_evento += 1
        msg = {"tipo": tipo, "event_id": f"sim-{self.boot}-{self.n_evento}", "seq": self.n_evento,
               "ts": int(time.time()), "ts_estimado": False, "zona": zona,
               "central": foto["central"], "teste": foto["teste"],
               "zonas": [{k: z[k] for k in ("e", "deg", "motivo", "f")} for z in foto["zonas"]]}
        if incidente:
            msg["incident_id"] = f"sim-{self.boot}-i{incidente}"
        if zona:
            z = foto["zonas"][zona - 1]
            msg.update(estado=z["e"], deg=z["deg"], motivo=z["motivo"],
                       sensor_a=z["a"], sensor_b=z["b"], falha=z["f"])
        if self.online:
            ingestao.processa(msg)

    def _status(self):
        f = self._foto()
        self.ultimo_status = time.time()
        if not self.online:
            return
        ingestao.processa({"tipo": "status", "ts": int(time.time()), "fpga_ok": True,
                           "central": f["central"], "teste": f["teste"],
                           "modo_deg": any(z["deg"] for z in f["zonas"]),
                           "zonas": [{k: z[k] for k in ("e", "deg", "motivo", "f")} for z in f["zonas"]],
                           "rssi": -55, "fila": 0, "perdidos": 0, "boot": self.boot,
                           "uptime_s": self.n_evento})

    def _compara(self):
        """Mesma logica do comparaQuadros() do firmware."""
        a, n = self.anterior, self._foto()
        if a == n:
            return False
        alarme = ("CONFIRMA", "AL_NORMAL", "AL_DEG")
        for i in range(4):
            za, zn = a["zonas"][i], n["zonas"][i]
            if za == zn:
                continue
            antes, agora = za["e"] in alarme, zn["e"] in alarme
            tipo = "estado"
            if not antes and agora:
                self.n_incidente += 1
                self.inc_zona[i] = self.n_incidente
                tipo = "disparo"
            elif antes and agora:
                tipo = {"AL_NORMAL": "confirmacao", "AL_DEG": "degradacao"}.get(zn["e"], "evidencia")
            elif antes and not agora:
                tipo = "fim_alarme"
            elif zn["e"] == "ISOLADA" and za["e"] != "ISOLADA":
                tipo = "isolada"
            elif zn["f"] and not za["f"]:
                tipo = "falha"
            elif zn["deg"] and not za["deg"]:
                tipo = "degradada"
            elif not zn["deg"] and za["deg"]:
                tipo = "recuperada"
            self._evento(tipo, i + 1, self.inc_zona[i] if (antes or agora) else 0, n)
            if antes and not agora:
                self.inc_zona[i] = 0
        if a["central"] != n["central"]:
            self._evento("central", 0, 0, n)
        if a["teste"] != n["teste"]:
            self._evento("teste_inicio" if n["teste"] else "teste_fim", 0, 0, n)
        self.anterior = n
        return True

    def passos(self, n):
        """Avanca n ciclos e gera os eventos das mudancas."""
        with self.trava:
            mudou = False
            for _ in range(n):
                self._passo()
                mudou = self._compara() or mudou
            if mudou or time.time() - self.ultimo_status > 60:
                self._status()

    # ------------------------------------------------------------ interface
    def inicia(self):
        self._status()

        def laco():
            while True:
                time.sleep(0.1)
                self.passos(CLK_HZ // 10)
        threading.Thread(target=laco, daemon=True).start()

    def comando(self, payload):
        """Mesmas regras do trataComando() do firmware."""
        with self.trava:
            if not self.online:
                return "sem_conexao", "simulador: central sem internet"
            cid = payload.get("cmd_id")
            if cid in self.cmds:
                return self.cmds[cid], "resultado ja conhecido (cmd_id repetido)"
            if time.time() > payload.get("expira", 0):
                return "expirado", "comando vencido"
            if payload.get("acao") == "armar":
                self.pend_arm = True
            elif payload.get("acao") == "desarmar":
                self.pend_dis = True
            else:
                return "erro", "acao desconhecida"
            self.passos(1)
            res = "confirmado" if self.central.cmd_ok else "recusado"
            self.cmds[cid] = res
            self.passos(2)
            return res, "resposta da central simulada"

    def sensor(self, zona, campo, valor):
        """campo: a | b | f | en"""
        with self.trava:
            self.sens[zona - 1][campo] = bool(valor)

    def reconhece_deg(self):
        with self.trava:
            self.pend_rec = True

    def configura(self, atraso_sel=None, teste=None, online=None):
        with self.trava:
            if atraso_sel is not None:
                self.central.atraso_sel = int(atraso_sel)
            if teste is not None:
                self.teste = bool(teste)
            if online is not None:
                self.online = bool(online)

    def situacao(self):
        with self.trava:
            return {"sensores": self.sens, "atraso_sel": self.central.atraso_sel,
                    "teste": self.teste, "online": self.online}
