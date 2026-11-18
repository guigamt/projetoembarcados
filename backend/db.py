"""Banco de dados (SQLite). Um arquivo so, sem servidor e sem custo."""
import sqlite3
import threading
import time
import hashlib
import hmac
import os

import config

_local = threading.local()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, pin_hash TEXT);

CREATE TABLE IF NOT EXISTS contatos (
    id INTEGER PRIMARY KEY, nome TEXT, email TEXT, whatsapp TEXT, callmebot_key TEXT,
    telegram_chat TEXT, ativo INTEGER DEFAULT 1);

-- um registro por mensagem de evento da ESP32 (event_id unico = deduplicacao)
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY, event_id TEXT UNIQUE, incident_id TEXT, seq INTEGER,
    ts_evento INTEGER, ts_recebido INTEGER, ts_estimado INTEGER,
    zona INTEGER, tipo TEXT, estado TEXT, deg INTEGER, motivo TEXT,
    sensor_a INTEGER, sensor_b INTEGER, falha INTEGER, teste INTEGER,
    central TEXT, extra TEXT, bruto TEXT);
CREATE INDEX IF NOT EXISTS ix_eventos_ts ON eventos(ts_evento);

-- um registro por disparo de zona. Confirmacao/degradacao atualizam o mesmo.
CREATE TABLE IF NOT EXISTS incidentes (
    incident_id TEXT PRIMARY KEY, zona INTEGER, ts_inicio INTEGER, ts_fim INTEGER,
    estado TEXT, confirmado INTEGER DEFAULT 0, degradado INTEGER DEFAULT 0, motivo TEXT,
    sensor_a INTEGER DEFAULT 0, sensor_b INTEGER DEFAULT 0, teste INTEGER DEFAULT 0,
    prob_falso REAL, explicacao TEXT, rotulo TEXT);

CREATE TABLE IF NOT EXISTS estado (
    id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT, ts_dispositivo INTEGER, ts_recebido INTEGER);

CREATE TABLE IF NOT EXISTS comandos (
    cmd_id TEXT PRIMARY KEY, acao TEXT, origem TEXT, usuario TEXT, ts_pedido INTEGER,
    expira INTEGER, status TEXT, ts_resposta INTEGER, detalhe TEXT);

CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY, chave TEXT, canal TEXT, destino TEXT, ts INTEGER,
    ok INTEGER, detalhe TEXT, texto TEXT);

-- consumo de dados por dia (cota do IoT Hub F1: 8000 mensagens/dia)
CREATE TABLE IF NOT EXISTS consumo (dia TEXT PRIMARY KEY, mensagens INTEGER, bytes INTEGER);

CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
"""


def conexao():
    """Uma conexao por thread (o coletor e os alertas rodam em threads proprias)."""
    con = getattr(_local, "con", None)
    if con is None or getattr(_local, "arquivo", None) != config.BANCO:
        con = sqlite3.connect(config.BANCO, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        _local.con = con
        _local.arquivo = config.BANCO
    return con


def consulta(sql, args=()):
    return [dict(r) for r in conexao().execute(sql, args).fetchall()]


def um(sql, args=()):
    r = conexao().execute(sql, args).fetchone()
    return dict(r) if r else None


def executa(sql, args=()):
    con = conexao()
    cur = con.execute(sql, args)
    con.commit()
    return cur


def gera_hash(texto):
    sal = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", texto.encode(), sal, 100_000)
    return sal.hex() + ":" + h.hex()


def confere_hash(texto, guardado):
    try:
        sal, h = guardado.split(":")
        novo = hashlib.pbkdf2_hmac("sha256", texto.encode(), bytes.fromhex(sal), 100_000)
        return hmac.compare_digest(novo.hex(), h)
    except (ValueError, AttributeError):
        return False


def inicia():
    con = conexao()
    con.executescript(ESQUEMA)
    con.commit()
    if not um("SELECT id FROM usuarios LIMIT 1"):
        executa("INSERT INTO usuarios (email, nome, senha_hash, pin_hash) VALUES (?,?,?,?)",
                (config.ADMIN_EMAIL.lower(), "Administrador",
                 gera_hash(config.ADMIN_SENHA), gera_hash(config.ADMIN_PIN)))


def meta_le(chave, padrao=None):
    r = um("SELECT valor FROM meta WHERE chave=?", (chave,))
    return r["valor"] if r else padrao


def meta_grava(chave, valor):
    executa("INSERT INTO meta (chave, valor) VALUES (?,?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, str(valor)))


def conta_consumo(n_bytes):
    dia = time.strftime("%Y-%m-%d")
    executa("INSERT INTO consumo (dia, mensagens, bytes) VALUES (?,1,?) "
            "ON CONFLICT(dia) DO UPDATE SET mensagens=mensagens+1, bytes=bytes+excluded.bytes",
            (dia, n_bytes))
