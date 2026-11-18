"""
Modelo de referencia das MEFs em Python (ciclo a ciclo).

Serve para conferir a LOGICA das tabelas de transicao antes de ir para o
Vivado. Cada chamada de passo() equivale a uma borda de subida do clock,
igual ao process(clk) do VHDL. Os testes em test_modelo.py usam os mesmos
cenarios dos testbenches tb_mef_zona.vhd e tb_mef_central.vhd.
"""

ISOLADA, MONITORA, VIGIA, CONFIRMA, AL_NORMAL, AL_DEG = range(6)
NOMES_ZONA = ["ISOLADA", "MONITORA", "VIGIA", "CONFIRMA", "AL_NORMAL", "AL_DEG"]


class MefZona:
    def __init__(self, clk_hz=1000, tcorr_sel=0):
        self.clk_hz = clk_hz
        self.t_diag = clk_hz // 2
        self.tcorr_lim = [clk_hz // 10, clk_hz // 2, clk_hz, 2 * clk_hz][tcorr_sel]
        self.est = MONITORA
        self.t = 0
        self.diag_cnt = 0
        self.diag_ok = False
        self.deg_ret = False
        self.motivo_ret = 0
        self.rec = False
        self.teste_r = False
        self.teste_u = False
        self.viu_r = False
        self.viu_u = False
        # entradas (ficam guardadas para calcular as saidas)
        self.r = self.u = self.f = False

    def passo(self, en=True, armada=False, r=False, u=False, f=False, rec_deg=False):
        self.r, self.u, self.f = r, u, f
        e = self.est
        if not en:
            self.est = ISOLADA
            self.t = 0
            self.diag_cnt = 0
            self.diag_ok = False
            self.rec = False
            return

        if e == ISOLADA:
            if not armada:
                self.est = MONITORA
                self.diag_cnt = 0
                self.diag_ok = False

        elif e == MONITORA:
            diag_ok_antes = self.diag_ok
            if not self.diag_ok:
                if self.diag_cnt == self.t_diag - 1:
                    self.diag_ok = True
                else:
                    self.diag_cnt += 1
            limpa_rec = False
            if rec_deg and self.deg_ret:
                self.rec, self.teste_r, self.teste_u = True, False, False
            elif self.rec:
                tr, tu = self.teste_r, self.teste_u
                if r:
                    self.teste_r = True
                if u:
                    self.teste_u = True
                if tr and tu and not r and not u and not f:
                    self.deg_ret = False
                    self.motivo_ret = 0
                    limpa_rec = True
            if limpa_rec:
                self.rec = False
            if armada and diag_ok_antes and not r and not u:
                self.est = VIGIA
                self.viu_r = self.viu_u = False
                self.rec = False

        elif e == VIGIA:
            if not armada:
                self.est = MONITORA
            elif r or u:
                self.viu_r, self.viu_u = r, u
                if f:
                    self.est, self.deg_ret, self.motivo_ret = AL_DEG, True, 2
                elif r and u:
                    self.est = AL_NORMAL
                else:
                    self.est = CONFIRMA
                    self.t = 0

        elif e == CONFIRMA:
            if r:
                self.viu_r = True
            if u:
                self.viu_u = True
            if not armada:
                self.est = MONITORA
            elif f:
                self.est, self.deg_ret, self.motivo_ret = AL_DEG, True, 2
            elif r and u:
                self.est = AL_NORMAL
            elif self.t >= self.tcorr_lim:
                self.est, self.deg_ret, self.motivo_ret = AL_DEG, True, 1
            else:
                self.t += 1

        elif e == AL_NORMAL:
            if not armada:
                self.est = MONITORA
            elif f:
                self.est, self.deg_ret, self.motivo_ret = AL_DEG, True, 2

        elif e == AL_DEG:
            if not armada:
                self.est = MONITORA

    # ----- saidas (Moore) -----
    @property
    def al(self):
        return self.est in (CONFIRMA, AL_NORMAL, AL_DEG)

    @property
    def deg(self):
        if self.est == ISOLADA:
            return True
        if self.est == CONFIRMA:
            return False
        return self.deg_ret or self.f

    @property
    def pronta(self):
        return self.est == MONITORA and self.diag_ok and not self.r and not self.u

    @property
    def motivo(self):
        if self.est == ISOLADA:
            return 3
        if self.est == CONFIRMA:
            return 0
        if self.f:
            return 2
        return self.motivo_ret


DESARMADO, ARMADO, ATRASO, DISPARADO = range(4)
ATRASOS_S = [0, 5, 10, 20, 30, 60, 90, 120]


class MefCentral:
    def __init__(self, clk_hz=10, nevoa_s=10, atraso_sel=0):
        self.clk_hz = clk_hz
        self.nevoa_s = nevoa_s
        self.atraso_sel = atraso_sel
        self.est = DESARMADO
        self.seg_cnt = 0
        self.rest = 0
        self.nev_cnt = 0
        self.cmd_ok = False
        self.cmd_feito = False

    def passo(self, arm_req=False, disarm_req=False, al_z=0, en_z=0b1111, pronta_z=0b1111):
        self.cmd_feito = False
        pode_armar = en_z != 0 and ((pronta_z | (~en_z & 0xF)) == 0xF)
        if disarm_req:
            self.est = DESARMADO
            self.rest = 0
            self.cmd_ok = True
            self.cmd_feito = True
            return
        e = self.est
        if e == DESARMADO:
            if arm_req:
                self.cmd_feito = True
                self.cmd_ok = pode_armar
                if pode_armar:
                    self.est = ARMADO
        elif e == ARMADO:
            if arm_req:
                self.cmd_ok, self.cmd_feito = True, True
            if al_z != 0:
                self.seg_cnt = 0
                self.nev_cnt = 0
                if self.atraso_sel == 0:
                    self.est = DISPARADO
                else:
                    self.est = ATRASO
                    self.rest = ATRASOS_S[self.atraso_sel]
        elif e == ATRASO:
            if arm_req:
                self.cmd_ok, self.cmd_feito = True, True
            if self.seg_cnt == self.clk_hz - 1:
                self.seg_cnt = 0
                self.rest -= 1
                if self.rest == 0:
                    self.est = DISPARADO
            else:
                self.seg_cnt += 1
        elif e == DISPARADO:
            if arm_req:
                self.cmd_ok, self.cmd_feito = True, True
            if self.nev_cnt < self.nevoa_s:
                if self.seg_cnt == self.clk_hz - 1:
                    self.seg_cnt = 0
                    self.nev_cnt += 1
                else:
                    self.seg_cnt += 1

    @property
    def armada(self):
        return self.est != DESARMADO

    @property
    def disparo(self):
        return self.est == DISPARADO

    @property
    def pre_alarme(self):
        return self.est == ATRASO

    @property
    def nevoa(self):
        return self.est == DISPARADO and self.nev_cnt < self.nevoa_s
