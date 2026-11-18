import { useEffect, useState } from "react";
import { api } from "./api.js";

function Contatos() {
  const [lista, setLista] = useState([]);
  const [f, setF] = useState({ nome: "", email: "", whatsapp: "", callmebot_key: "", telegram_chat: "" });
  const [msg, setMsg] = useState("");

  const carrega = () => api("/contatos").then(setLista).catch(() => {});
  useEffect(() => { carrega(); }, []);

  async function salva(e) {
    e.preventDefault();
    setMsg("");
    try {
      await api("/contatos", { corpo: f });
      setF({ nome: "", email: "", whatsapp: "", callmebot_key: "", telegram_chat: "" });
      carrega();
    } catch (x) {
      setMsg(x.message);
    }
  }
  async function testa() {
    setMsg("Enviando...");
    try {
      const r = await api("/contatos/teste", { metodo: "POST" });
      setMsg(r.map((a) => `${a.canal}: ${a.ok ? "enviado" : "falhou (" + a.detalhe + ")"}`).join(" | ") || "Nenhum contato cadastrado.");
    } catch (x) {
      setMsg(x.message);
    }
  }
  const campo = (k, rotulo, tipo) => (
    <input type={tipo || "text"} placeholder={rotulo} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
  );

  return (
    <>
      <h2>Contatos que recebem os alertas</h2>
      {lista.map((c) => (
        <div key={c.id} className="item fino linha">
          <span><b>{c.nome}</b> <span className="fraco pequeno">{[c.email, c.whatsapp, c.telegram_chat && "Telegram"].filter(Boolean).join(" - ")}</span></span>
          <button className="mini" onClick={() => api("/contatos/" + c.id, { metodo: "DELETE" }).then(carrega)}>Remover</button>
        </div>
      ))}
      <form className="form" onSubmit={salva}>
        {campo("nome", "Nome")}
        {campo("email", "E-mail", "email")}
        {campo("whatsapp", "WhatsApp com DDI (ex.: +5511999990000)")}
        {campo("callmebot_key", "Chave do CallMeBot (WhatsApp)")}
        {campo("telegram_chat", "Chat ID do Telegram (opcional)")}
        <div className="linha">
          <button className="btn primario">Adicionar</button>
          <button type="button" className="btn" onClick={testa}>Enviar alerta de teste</button>
        </div>
      </form>
      {msg && <p className="fraco pequeno">{msg}</p>}
    </>
  );
}

// So aparece quando o backend esta no modo simulado
function Simulador() {
  const [s, setS] = useState(null);
  const manda = (corpo) => api("/sim", { corpo }).then(setS).catch(() => {});
  useEffect(() => { api("/sim").then(setS).catch(() => {}); }, []);
  if (!s) return null;
  const ATRASOS = [0, 5, 10, 20, 30, 60, 90, 120];

  return (
    <>
      <h2>Central simulada</h2>
      <p className="fraco pequeno">Faz o papel das chaves e dos sensores da maquete. A = sensor A, B = sensor B, F = falha injetada.</p>
      {s.sensores.map((z, i) => (
        <div key={i} className="item fino linha">
          <b>Z{i + 1}</b>
          {[["a", "A"], ["b", "B"], ["f", "F"], ["en", "Habilitada"]].map(([k, n]) => (
            <label key={k} className="chave">
              <input type="checkbox" checked={!!z[k]} onChange={(e) => manda({ zona: i + 1, campo: k, valor: e.target.checked })} /> {n}
            </label>
          ))}
        </div>
      ))}
      <div className="item fino linha">
        <label>Atraso{" "}
          <select value={s.atraso_sel} onChange={(e) => manda({ atraso_sel: Number(e.target.value) })}>
            {ATRASOS.map((a, i) => <option key={i} value={i}>{a} s</option>)}
          </select>
        </label>
        <label className="chave"><input type="checkbox" checked={s.teste} onChange={(e) => manda({ teste: e.target.checked })} /> TESTE</label>
        <label className="chave"><input type="checkbox" checked={s.online} onChange={(e) => manda({ online: e.target.checked })} /> Internet</label>
      </div>
      <button className="btn" onClick={() => manda({ reconhecer: true })}>Reconhecer DEG (botão BTNL)</button>
    </>
  );
}

export default function Ajustes({ simulador, aoSair }) {
  return (
    <>
      <Contatos />
      {simulador && <Simulador />}
      <h2>Conta</h2>
      <button className="btn" onClick={aoSair}>Sair</button>
    </>
  );
}
