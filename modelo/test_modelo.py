"""Testes do modelo de referencia. Rodar com:  python -m pytest modelo -q"""
from modelo_mef import (MefZona, MefCentral, ISOLADA, MONITORA, VIGIA, CONFIRMA,
                        AL_NORMAL, AL_DEG, DESARMADO, ARMADO, ATRASO, DISPARADO)

CLK = 1000
TC = CLK // 10          # Tcorr = 0,1 s = 100 ciclos


def zona_em_vigia(sel=0):
    z = MefZona(CLK, sel)
    for _ in range(CLK // 2 + 2):
        z.passo()
    assert z.pronta
    z.passo(armada=True)
    assert z.est == VIGIA and not z.al and not z.deg
    return z


def n(z, k, **kw):
    for _ in range(k):
        z.passo(armada=True, **kw)


def test_repouso_nao_dispara():
    z = zona_em_vigia()
    n(z, 500)
    assert z.est == VIGIA and not z.al and not z.deg


def test_so_reed_alarme_imediato_e_deg_depois_de_tcorr():
    z = zona_em_vigia()
    n(z, 1, r=True)
    assert z.est == CONFIRMA and z.al and not z.deg      # AL na hora, DEG = 0
    n(z, TC, r=True)
    assert z.est == CONFIRMA and not z.deg               # ainda dentro de Tcorr
    n(z, 1, r=True)
    assert z.est == AL_DEG and z.al and z.deg and z.motivo == 1


def test_so_ultrassom_alarme_imediato_e_deg_depois_de_tcorr():
    z = zona_em_vigia()
    n(z, 1, u=True)
    assert z.est == CONFIRMA and z.al and not z.deg
    n(z, TC + 1, u=True)
    assert z.est == AL_DEG and z.viu_u and not z.viu_r


def test_confirmacao_antes_do_prazo():
    z = zona_em_vigia()
    n(z, 1, r=True)
    n(z, TC // 2, r=True)
    n(z, 1, r=True, u=True)
    assert z.est == AL_NORMAL and z.al and not z.deg
    assert z.viu_r


def test_confirmacao_exatamente_no_limite_tem_prioridade():
    z = zona_em_vigia()
    n(z, 1, r=True)
    n(z, TC, r=True)                 # t chegou em Tcorr
    n(z, 1, r=True, u=True)          # RU = 11 no limite
    assert z.est == AL_NORMAL and not z.deg


def test_confirmacao_depois_do_prazo_fica_degradado():
    z = zona_em_vigia()
    n(z, 1, r=True)
    n(z, TC + 1, r=True)
    assert z.est == AL_DEG
    n(z, 10, r=True, u=True)
    assert z.est == AL_DEG and z.deg  # DEG retido


def test_ru_simultaneo_vai_direto_para_al_normal():
    z = zona_em_vigia()
    n(z, 1, r=True, u=True)
    assert z.est == AL_NORMAL and not z.deg


def test_troca_01_10_e_volta_a_00_nao_reinicia_contador():
    z = zona_em_vigia()
    n(z, 1, r=True)
    n(z, 40, r=True)
    n(z, 30, u=True)                 # 10 -> 01
    n(z, 30)                         # volta a 00
    assert z.est == CONFIRMA
    n(z, 1)
    assert z.est == AL_DEG           # 40 + 30 + 30 = 100 = Tcorr, estoura igual


def test_falha_com_evidencia_degrada_sem_esperar():
    z = zona_em_vigia()
    n(z, 5, f=True)
    assert z.est == VIGIA and not z.al and z.deg      # so falha: DEG, sem alarme
    n(z, 1, f=True, r=True)
    assert z.est == AL_DEG and z.al and z.deg and z.motivo == 2


def test_falha_com_alarme_retido():
    z = zona_em_vigia()
    n(z, 1, r=True, u=True)
    assert z.est == AL_NORMAL
    n(z, 1, f=True)
    assert z.est == AL_DEG


def test_al_retido_ate_desarme_e_deg_retido_ate_teste():
    z = zona_em_vigia()
    n(z, TC + 2, r=True)
    assert z.est == AL_DEG
    n(z, 50)                          # sensor voltou ao repouso: AL continua
    assert z.al
    z.passo(armada=False)
    assert z.est == MONITORA and not z.al and z.deg   # DEG continua
    z.passo(rec_deg=True)             # reconhecimento
    z.passo()
    assert z.deg                      # ainda falta o teste
    z.passo(r=True); z.passo(r=True)
    z.passo(u=True); z.passo(u=True)
    z.passo(); z.passo()
    assert not z.deg and z.motivo == 0


def test_isolamento():
    z = zona_em_vigia()
    z.passo(en=False, armada=True)
    assert z.est == ISOLADA and not z.al and z.deg and z.motivo == 3
    z.passo(en=False, armada=True, r=True, u=True)
    assert not z.al                   # isolada nao dispara
    z.passo(en=True, armada=True)
    assert z.est == ISOLADA           # so volta com a central desarmada
    z.passo(en=True, armada=False)
    assert z.est == MONITORA and not z.pronta         # refaz o diagnostico


def test_nao_arma_com_sensor_ativo():
    z = MefZona(CLK)
    for _ in range(CLK):
        z.passo(r=True)
    assert not z.pronta
    z.passo(armada=True, r=True)
    assert z.est == MONITORA


# ---------------------------- central ----------------------------
def central_armada(sel=0, clk=10):
    c = MefCentral(clk, 10, sel)
    c.passo(arm_req=True)
    assert c.est == ARMADO and c.cmd_ok and c.cmd_feito
    return c


def test_arme_recusado_com_zona_nao_pronta():
    c = MefCentral()
    c.passo(arm_req=True, pronta_z=0b1101)
    assert c.est == DESARMADO and c.cmd_feito and not c.cmd_ok
    c.passo(arm_req=True, en_z=0b1101, pronta_z=0b1101)   # zona 2 isolada: aceita
    assert c.est == ARMADO and c.cmd_ok
    c2 = MefCentral()
    c2.passo(arm_req=True, en_z=0)
    assert c2.est == DESARMADO and not c2.cmd_ok          # nenhuma zona habilitada


def test_atraso_zero_dispara_no_ciclo_seguinte():
    c = central_armada(0)
    c.passo(al_z=0b0001)
    assert c.disparo


def test_atraso_120s_exato():
    clk = 10
    c = central_armada(7, clk)
    c.passo(al_z=0b0100)
    assert c.pre_alarme and c.rest == 120
    for _ in range(120 * clk - 1):
        c.passo(al_z=0b0100)
    assert c.pre_alarme
    c.passo(al_z=0b0100)
    assert c.disparo


def test_duas_zonas_no_mesmo_ciclo():
    c = central_armada(1)
    c.passo(al_z=0b1010)
    assert c.pre_alarme and c.rest == 5


def test_desarme_tem_prioridade_e_cancela_atraso():
    c = central_armada(2)
    c.passo(al_z=1)
    c.passo(al_z=1, disarm_req=True, arm_req=True)
    assert c.est == DESARMADO and c.cmd_ok
    c = central_armada(0)
    c.passo(al_z=1, disarm_req=True)       # alarme e desarme no mesmo ciclo
    assert c.est == DESARMADO


def test_nevoa_desliga_apos_tempo_maximo():
    clk = 10
    c = central_armada(0, clk)
    c.passo(al_z=1)
    assert c.nevoa
    for _ in range(10 * clk):
        c.passo(al_z=1)
    assert c.disparo and not c.nevoa
