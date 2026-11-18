"""
Agente (texto e voz). A voz e transcrita no celular e chega aqui como texto,
entao texto e voz usam exatamente as mesmas funcoes e a mesma autenticacao.

O modelo de linguagem NAO calcula nada e NAO manda na central:
  * os numeros vem de estatisticas.py (o modelo so explica)
  * arme passa pela mesma funcao do painel (autoriza, cmd_id, validade, resposta)
  * desarme nunca e executado pelo agente: ele devolve "acao_pendente" e o
    aplicativo pede o PIN do usuario antes de mandar

Com OLLAMA_URL configurado usa um modelo local com chamada de funcoes.
Sem Ollama (ou se ele falhar) cai num interpretador por palavras-chave, para a
demonstracao nao depender do modelo.
"""
import json
import re

import requests

import config
import estatisticas

FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "estado_atual", "description": "Estado atual da central e das 4 zonas.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "consultar_eventos",
        "description": "Lista os ultimos eventos registrados (disparos, falhas, isolamentos).",
        "parameters": {"type": "object", "properties": {
            "zona": {"type": "integer", "description": "1 a 4. Omitir para todas."},
            "dias": {"type": "integer", "description": "Periodo em dias (padrao 7)."},
            "limite": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "calcular_estatisticas",
        "description": "Contagem de disparos, proporcao de disparos degradados, tempo de falha "
                       "e zona que mais degradou, por zona e periodo.",
        "parameters": {"type": "object", "properties": {
            "zona": {"type": "integer"}, "dias": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "solicitar_arme", "description": "Pede para ARMAR a central.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "solicitar_desarme",
        "description": "Pede para DESARMAR a central (o usuario ainda confirma com o PIN).",
        "parameters": {"type": "object", "properties": {}}}},
]

SISTEMA = (
    "Voce e o assistente de uma central de alarme residencial de 4 zonas. Responda em portugues, "
    "em poucas frases. Use SEMPRE as funcoes para obter dados; nunca invente numeros. Ao citar "
    "estatisticas diga o periodo e os numeros. Se uma zona degradou muito, recomende verificar "
    "cabo, alinhamento ou resposta do sensor. Voce nao desarma a central sozinho: chame "
    "solicitar_desarme e avise que o usuario precisa confirmar com o PIN.")


class Contexto:
    """Funcoes que o agente pode chamar. Recebe do app.py o que precisa de autorizacao."""

    def __init__(self, le_estado, pede_comando, usuario):
        self.le_estado = le_estado
        self.pede_comando = pede_comando
        self.usuario = usuario
        self.dados = {}
        self.acao_pendente = None

    def chama(self, nome, args):
        args = {k: v for k, v in (args or {}).items() if v not in (None, "", 0)}
        if nome == "estado_atual":
            r = self.le_estado()
        elif nome == "consultar_eventos":
            r = estatisticas.consultar_eventos(args.get("zona"), args.get("dias", 7),
                                               min(int(args.get("limite", 10)), 30))
        elif nome == "calcular_estatisticas":
            r = estatisticas.calcular_estatisticas(args.get("zona"), args.get("dias", 7))
        elif nome == "solicitar_arme":
            r = self.pede_comando("armar", "agente", self.usuario)
        elif nome == "solicitar_desarme":
            self.acao_pendente = "desarmar"
            r = {"status": "aguardando_confirmacao", "aviso": "o usuario precisa confirmar com o PIN"}
        else:
            r = {"erro": "funcao desconhecida"}
        self.dados[nome] = r
        return r


# ---------------------------------------------------------------- LLM (Ollama)
def _com_llm(pergunta, ctx):
    msgs = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pergunta}]
    for _ in range(4):
        r = requests.post(config.OLLAMA_URL.rstrip("/") + "/api/chat", timeout=60, json={
            "model": config.OLLAMA_MODELO, "messages": msgs, "tools": FERRAMENTAS, "stream": False})
        r.raise_for_status()
        m = r.json()["message"]
        msgs.append(m)
        chamadas = m.get("tool_calls") or []
        if not chamadas:
            return m.get("content", "").strip()
        for c in chamadas:
            f = c["function"]
            args = f.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            res = ctx.chama(f["name"], args)
            msgs.append({"role": "tool", "content": json.dumps(res, ensure_ascii=False, default=str)})
    return "Não consegui concluir a consulta."


# ---------------------------------------------------------------- regras (sem LLM)
def _zona_da_frase(t):
    m = re.search(r"zona\s*(\d)", t)
    return int(m.group(1)) if m and m.group(1) in "1234" else None


def _dias_da_frase(t):
    if "hoje" in t:
        return 1
    if "mes" in t or "mês" in t:
        return 30
    m = re.search(r"(\d+)\s*dias?", t)
    return int(m.group(1)) if m else 7


def _fmt_tempo(s):
    if s < 120:
        return f"{int(s)} s"
    if s < 7200:
        return f"{int(s // 60)} min"
    return f"{s / 3600:.1f} h"


def _por_regras(pergunta, ctx):
    t = pergunta.lower()
    zona, dias = _zona_da_frase(t), _dias_da_frase(t)

    if re.search(r"\bdesarm|deslig(a|ue) o alarme", t):
        ctx.chama("solicitar_desarme", {})
        return "Para desarmar preciso da sua confirmação com o PIN."
    if re.search(r"\barm(a|e|ar)\b|lig(a|ue) o alarme|ativ(a|e|ar) o alarme", t):
        r = ctx.chama("solicitar_arme", {})
        if r.get("status") == "confirmado":
            return "Central armada. A confirmação veio da própria central."
        if r.get("status") == "recusado":
            return "A central RECUSOU o arme: existe zona habilitada que não está pronta (porta aberta ou sensor ativo)."
        return f"Não consegui armar: {r.get('status')} ({r.get('detalhe', '')})."

    if re.search(r"degrad|falha|manuten|problema", t):
        e = ctx.chama("calcular_estatisticas", {"zona": zona, "dias": dias})
        z = e["zona_mais_degradada"]
        if not z:
            return f"Nos últimos {dias} dia(s) nenhuma zona entrou em modo degradado."
        v = e["por_zona"][z]
        return (f"De {e['de']} até {e['ate']}, a zona {z} ({v['nome']}) foi a que mais entrou em modo "
                f"degradado: {v['entradas_degradado']} vez(es), somando {_fmt_tempo(v['tempo_degradado_s'])}. "
                f"No período, {e['disparos_degradados']} de {e['total_disparos']} disparos foram degradados. "
                "Recomendo verificar cabo, alinhamento e resposta do sensor dessa zona.")

    if re.search(r"quant|estat|dispar|alarmes?|resumo|relat", t):
        e = ctx.chama("calcular_estatisticas", {"zona": zona, "dias": dias})
        partes = [f"zona {z}: {v['disparos']}" for z, v in e["por_zona"].items()]
        txt = (f"De {e['de']} até {e['ate']} foram {e['total_disparos']} disparo(s) "
               f"({', '.join(partes)}). Degradados: {e['disparos_degradados']} "
               f"({int(e['proporcao_degradados'] * 100)}%).")
        if e["recomendacoes"]:
            txt += " " + " ".join(e["recomendacoes"])
        return txt

    if re.search(r"event|histor|aconteceu|ultim", t):
        evs = ctx.chama("consultar_eventos", {"zona": zona, "dias": dias, "limite": 5})
        if not evs:
            return "Não há eventos registrados nesse período."
        import time
        linhas = [f"{time.strftime('%d/%m %H:%M', time.localtime(e['ts_evento']))} - "
                  f"{'zona ' + str(e['zona']) if e['zona'] else 'central'}: {e['tipo']}"
                  f"{' (' + e['estado'] + ')' if e['estado'] else ''}" for e in evs]
        return "Últimos eventos: " + "; ".join(linhas) + "."

    e = ctx.chama("estado_atual", {})
    zs = ", ".join(f"Z{z['zona']} {z['estado']}{' (degradada)' if z['deg'] else ''}" for z in e["zonas"])
    conexao = "" if e["conexao"]["online"] else " ATENÇÃO: a central está sem conexão, este é o último estado conhecido."
    return f"A central está {e['central']}. Zonas: {zs}.{conexao}"


def responde(pergunta, ctx):
    """Devolve dict com resposta, dados usados, acao pendente e o modo (llm ou regras)."""
    modo, resposta = "regras", None
    if config.OLLAMA_URL:
        try:
            resposta = _com_llm(pergunta, ctx)
            modo = "llm"
        except Exception as e:
            print("[agente] LLM indisponivel, usando regras:", e)
            ctx.dados.clear()
            ctx.acao_pendente = None
    if not resposta:
        resposta = _por_regras(pergunta, ctx)
        modo = "regras"
    return {"resposta": resposta, "dados": ctx.dados, "acao_pendente": ctx.acao_pendente, "modo": modo}
