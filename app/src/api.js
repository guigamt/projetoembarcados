// api.js - chamadas ao backend. O token do login fica so na memoria e no
// sessionStorage (some quando fecha o app).
let token = null;
try { token = sessionStorage.getItem("token"); } catch { /* sem storage */ }

export function temToken() { return !!token; }

export function sair() {
  token = null;
  try { sessionStorage.removeItem("token"); } catch { /* sem storage */ }
}

export async function api(caminho, opcoes = {}) {
  const cab = { "Content-Type": "application/json" };
  if (token) cab.Authorization = "Bearer " + token;
  let r;
  try {
    r = await fetch("/api" + caminho, {
      method: opcoes.metodo || (opcoes.corpo ? "POST" : "GET"),
      headers: cab,
      body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
    });
  } catch {
    throw new Error("Sem acesso ao servidor");
  }
  if (r.status === 401 && caminho !== "/login") {
    sair();
    window.location.reload();
  }
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || "Erro " + r.status);
  return dados;
}

export async function entrar(email, senha) {
  const d = await api("/login", { corpo: { email, senha } });
  token = d.token;
  try { sessionStorage.setItem("token", token); } catch { /* sem storage */ }
}

export function hora(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function idade(s) {
  if (s == null) return "nunca";
  if (s < 60) return `há ${s} s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  return `há ${Math.floor(s / 3600)} h`;
}

// nomes amigaveis dos estados que vem do FPGA
export const NOME_ZONA = {
  ISOLADA: "Isolada", MONITORA: "Em repouso", VIGIA: "Vigiando",
  CONFIRMA: "Disparou (confirmando)", AL_NORMAL: "ALARME confirmado", AL_DEG: "ALARME degradado",
};
export const NOME_CENTRAL = {
  DESARMADO: "Desarmado", ARMADO: "Armado", ATRASO: "Disparo em contagem", DISPARO: "ALARME DISPARADO",
  DESCONHECIDO: "Sem dados",
};
export const NOME_MOTIVO = {
  sem_confirmacao: "segundo sensor não confirmou", falha_sensor: "falha de sensor", isolada: "zona isolada",
};
export const NOME_STATUS = {
  confirmado: "Confirmado pela central", recusado: "Recusado pela central",
  sem_confirmacao: "Sem confirmação da central", expirado: "Comando vencido", erro: "Erro no envio",
  pendente: "Pendente",
};
