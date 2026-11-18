"""
Alertas ao usuario: e-mail (SMTP), WhatsApp (CallMeBot) e Telegram.
Todos gratuitos. Cada contato cadastrado recebe por todos os canais que tiver
preenchido, entao um disparo sempre sai por mais de um caminho.

O texto do alerta sempre diz QUAIS zonas foram violadas.
"""
import smtplib
import threading
import time
from email.mime.text import MIMEText

import requests

import config
import db
import ia

ESTADOS_ALARME = ("CONFIRMA", "AL_NORMAL", "AL_DEG")


def _email(destino, assunto, texto):
    if not config.SMTP_USER:
        return False, "SMTP nao configurado no .env"
    msg = MIMEText(texto, "plain", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = config.SMTP_USER
    msg["To"] = destino
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_SENHA)
        s.sendmail(config.SMTP_USER, [destino], msg.as_string())
    return True, "enviado"


def _whatsapp(telefone, chave, texto):
    # CallMeBot: o contato precisa ativar antes (ver docs/04_nuvem_passo_a_passo.md)
    r = requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": telefone, "text": texto, "apikey": chave}, timeout=20)
    return r.status_code == 200, f"HTTP {r.status_code}"


def _telegram(chat, texto):
    if not config.TELEGRAM_TOKEN:
        return False, "TELEGRAM_TOKEN nao configurado no .env"
    r = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": chat, "text": texto}, timeout=20)
    return r.status_code == 200, f"HTTP {r.status_code}"


def _envia_tudo(chave, assunto, texto, so_email):
    for c in db.consulta("SELECT * FROM contatos WHERE ativo=1"):
        canais = []
        if c["email"]:
            canais.append(("email", c["email"], lambda c=c: _email(c["email"], assunto, texto)))
        if not so_email and c["whatsapp"] and c["callmebot_key"]:
            canais.append(("whatsapp", c["whatsapp"],
                           lambda c=c: _whatsapp(c["whatsapp"], c["callmebot_key"], texto)))
        if not so_email and c["telegram_chat"]:
            canais.append(("telegram", c["telegram_chat"], lambda c=c: _telegram(c["telegram_chat"], texto)))
        for canal, destino, funcao in canais:
            # nao repete o mesmo alerta para o mesmo destino
            if db.um("SELECT id FROM alertas WHERE chave=? AND canal=? AND destino=?",
                     (chave, canal, destino)):
                continue
            try:
                ok, detalhe = funcao()
            except Exception as e:             # rede fora, senha errada etc.
                ok, detalhe = False, f"erro: {e}"
            db.executa("INSERT INTO alertas (chave, canal, destino, ts, ok, detalhe, texto) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (chave, canal, destino, int(time.time()), int(ok), detalhe, texto))


def envia(chave, assunto, texto, so_email=False, espera=True):
    """Dispara os envios em outra thread para nao atrasar o recebimento dos eventos."""
    t = threading.Thread(target=_envia_tudo, args=(chave, assunto, texto, so_email), daemon=True)
    t.start()
    if espera:
        t.join()


def texto_disparo(zonas_violadas, quando, teste):
    """zonas_violadas: lista de numeros de zona. Monta o texto com o detalhe de cada uma."""
    linhas = []
    for z in zonas_violadas:
        inc = db.um("SELECT * FROM incidentes WHERE zona=? ORDER BY ts_inicio DESC LIMIT 1", (z,))
        nome = config.ZONAS.get(z, f"Zona {z}")
        if not inc:
            linhas.append(f"- Zona {z} - {nome}")
            continue
        a, b = config.SENSORES[z]
        sens = [n for n, viu in ((a, inc["sensor_a"]), (b, inc["sensor_b"])) if viu]
        det = "sensores: " + (" + ".join(sens) if sens else "não informado")
        if inc["confirmado"]:
            det += " (confirmado pelos dois)"
        elif inc["degradado"]:
            det += " (MODO DEGRADADO: " + (inc["motivo"] or "sem confirmação").replace("_", " ") + ")"
        det += f". Confiança: {ia.confianca(inc['prob_falso'])}"
        linhas.append(f"- Zona {z} - {nome}: {det}")
    hora = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(quando))
    cab = "[TESTE] " if teste else ""
    return (f"{cab}ALARME DISPARADO em {hora}\n"
            f"Zonas violadas ({len(zonas_violadas)}):\n" + "\n".join(linhas) +
            "\nAbra o painel para ver o estado e desarmar.")


def zonas_em_alarme(msg):
    return [i + 1 for i, z in enumerate(msg.get("zonas", [])) if z.get("e") in ESTADOS_ALARME]
