"""
Reducao de falso-positivo.

Cada disparo (incidente) recebe uma probabilidade de ser falso. Ela NAO bloqueia
nada: a sirene e as contramedidas sao decididas pelo FPGA. A nota so entra no
texto do alerta ("confianca alta/baixa") e nas estatisticas.

Dois niveis:
  1. regras  - usadas desde o primeiro dia, baseadas no que o FPGA informa
  2. modelo  - regressao logistica (scikit-learn), treinada quando o usuario ja
               marcou pelo menos MIN_ROTULOS incidentes como "real" ou "falso"
               no historico do aplicativo
"""
import time

import db

MIN_ROTULOS = 20
_modelo = None
_treinado_com = 0


def _taxa_falso_zona(zona):
    r = db.um("SELECT COUNT(*) n, SUM(rotulo='falso') f FROM incidentes "
              "WHERE zona=? AND rotulo IS NOT NULL", (zona,))
    if not r or not r["n"]:
        return 0.0
    return (r["f"] or 0) / r["n"]


def _outras_zonas_perto(inc):
    r = db.um("SELECT COUNT(DISTINCT zona) n FROM incidentes WHERE zona<>? "
              "AND ts_inicio BETWEEN ? AND ?",
              (inc["zona"], inc["ts_inicio"] - 60, inc["ts_inicio"] + 60))
    return r["n"] if r else 0


def caracteristicas(inc):
    hora = time.localtime(inc["ts_inicio"] or time.time()).tm_hour
    return [
        1.0 if inc["confirmado"] else 0.0,             # os dois sensores viram
        1.0 if inc["degradado"] else 0.0,              # nao confirmou em Tcorr
        1.0 if inc["motivo"] == "falha_sensor" else 0.0,
        float(min(_outras_zonas_perto(inc), 3)),       # outras zonas no mesmo minuto
        _taxa_falso_zona(inc["zona"]),                 # historico da zona
        1.0 if 0 <= hora < 6 else 0.0,                 # madrugada
        1.0 if inc["teste"] else 0.0,
    ]


def _regras(inc):
    """Nota por regras. Devolve (probabilidade de ser falso, explicacao)."""
    p = 0.35
    motivos = []
    if inc["confirmado"]:
        p -= 0.25
        motivos.append("os dois sensores da zona confirmaram")
    if inc["degradado"] and inc["motivo"] == "sem_confirmacao":
        p += 0.25
        motivos.append("só um sensor atuou dentro do tempo de confirmação")
    if inc["motivo"] == "falha_sensor":
        p += 0.20
        motivos.append("a zona tinha falha de sensor diagnosticada")
    n = _outras_zonas_perto(inc)
    if n:
        p -= 0.15 * min(n, 2)
        motivos.append(f"{n} outra(s) zona(s) dispararam no mesmo minuto")
    taxa = _taxa_falso_zona(inc["zona"])
    if taxa > 0.5:
        p += 0.15
        motivos.append("esta zona tem histórico de alarmes falsos")
    if inc["teste"]:
        p = 0.95
        motivos = ["disparo feito em modo TESTE"]
    return max(0.02, min(0.98, p)), "; ".join(motivos) or "sem informação adicional"


def treina():
    """Treina a regressao logistica com os incidentes rotulados. True se treinou."""
    global _modelo, _treinado_com
    dados = db.consulta("SELECT * FROM incidentes WHERE rotulo IN ('real','falso') AND teste=0")
    classes = {d["rotulo"] for d in dados}
    if len(dados) < MIN_ROTULOS or len(classes) < 2:
        return False
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        return False
    x = [caracteristicas(d) for d in dados]
    y = [1 if d["rotulo"] == "falso" else 0 for d in dados]
    _modelo = LogisticRegression(max_iter=500).fit(x, y)
    _treinado_com = len(dados)
    return True


def avalia(inc):
    """Devolve (prob_falso, explicacao) para um incidente (dict da tabela)."""
    p_regra, explicacao = _regras(inc)
    n = db.um("SELECT COUNT(*) n FROM incidentes WHERE rotulo IN ('real','falso') AND teste=0")["n"]
    if n >= MIN_ROTULOS and n != _treinado_com:
        treina()
    if _modelo is not None and not inc["teste"]:
        p_modelo = float(_modelo.predict_proba([caracteristicas(inc)])[0][1])
        # media entre as regras e o modelo, para o modelo nao decidir sozinho
        return round((p_regra + p_modelo) / 2, 2), explicacao + f" (modelo treinado com {_treinado_com} casos)"
    return round(p_regra, 2), explicacao


def confianca(prob_falso):
    if prob_falso is None:
        return "indefinida"
    if prob_falso < 0.3:
        return "alta"
    if prob_falso < 0.6:
        return "média"
    return "baixa"
