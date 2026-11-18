import { useEffect, useState } from "react";
import { api, entrar, sair, temToken } from "./api.js";
import Painel from "./Painel.jsx";
import Historico from "./Historico.jsx";
import Estatisticas from "./Estatisticas.jsx";
import Agente from "./Agente.jsx";
import Ajustes from "./Ajustes.jsx";

const ABAS = [
  ["painel", "Painel"], ["historico", "Histórico"], ["estat", "Números"],
  ["agente", "Agente"], ["ajustes", "Ajustes"],
];

function Login({ aoEntrar }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  async function envia(e) {
    e.preventDefault();
    setErro("");
    try {
      await entrar(email, senha);
      aoEntrar();
    } catch (x) {
      setErro(x.message);
    }
  }
  return (
    <form className="login" onSubmit={envia}>
      <h1>Central de Alarme</h1>
      <p className="fraco">4 zonas - FPGA + ESP32</p>
      <input type="email" placeholder="E-mail" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <input type="password" placeholder="Senha" value={senha} onChange={(e) => setSenha(e.target.value)} required />
      {erro && <p className="erro">{erro}</p>}
      <button className="btn primario">Entrar</button>
    </form>
  );
}

export default function App() {
  const [logado, setLogado] = useState(temToken());
  const [aba, setAba] = useState("painel");
  const [estado, setEstado] = useState(null);
  const [semServidor, setSemServidor] = useState(false);

  // busca o estado a cada 2 s
  useEffect(() => {
    if (!logado) return undefined;
    let vivo = true;
    async function busca() {
      try {
        const e = await api("/estado");
        if (vivo) { setEstado(e); setSemServidor(false); }
      } catch {
        if (vivo) setSemServidor(true);
      }
    }
    busca();
    const t = setInterval(busca, 2000);
    return () => { vivo = false; clearInterval(t); };
  }, [logado]);

  if (!logado) return <Login aoEntrar={() => setLogado(true)} />;

  return (
    <div className="app">
      {estado?.simulador && <div className="faixa aviso">MODO SIMULADO - central de teste, sem a placa</div>}
      {semServidor && <div className="faixa perigo">Sem acesso ao servidor. Os dados abaixo podem estar antigos.</div>}
      <main>
        {aba === "painel" && <Painel estado={estado} />}
        {aba === "historico" && <Historico />}
        {aba === "estat" && <Estatisticas />}
        {aba === "agente" && <Agente />}
        {aba === "ajustes" && <Ajustes simulador={!!estado?.simulador} aoSair={() => { sair(); setLogado(false); }} />}
      </main>
      <nav className="abas">
        {ABAS.map(([id, nome]) => (
          <button key={id} className={aba === id ? "ativa" : ""} onClick={() => setAba(id)}>{nome}</button>
        ))}
      </nav>
    </div>
  );
}
