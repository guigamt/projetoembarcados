import { useRef, useState } from "react";
import { api, NOME_STATUS } from "./api.js";
import PedePin from "./PedePin.jsx";

const Reconhecedor = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

function fala(texto) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(texto);
  u.lang = "pt-BR";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export default function Agente() {
  const [msgs, setMsgs] = useState([{ de: "agente", texto: "Olá. Pergunte sobre o alarme ou peça para armar. Ex.: \"qual zona mais entrou em modo degradado?\"" }]);
  const [texto, setTexto] = useState("");
  const [ouvindo, setOuvindo] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [pedePin, setPedePin] = useState(false);
  const porVoz = useRef(false);

  function poe(m) { setMsgs((a) => [...a, m]); }

  // texto digitado e voz transcrita chegam na MESMA rota do backend
  async function envia(pergunta, voz) {
    if (!pergunta.trim() || ocupado) return;
    porVoz.current = voz;
    poe({ de: "eu", texto: pergunta, voz });
    setTexto("");
    setOcupado(true);
    try {
      const r = await api("/agente", { corpo: { mensagem: pergunta } });
      poe({ de: "agente", texto: r.resposta, dados: r.dados, modo: r.modo });
      if (voz) fala(r.resposta);
      if (r.acao_pendente === "desarmar") setPedePin(true);
    } catch (x) {
      poe({ de: "agente", texto: "Erro: " + x.message });
    }
    setOcupado(false);
  }

  function escuta() {
    if (!Reconhecedor) {
      poe({ de: "agente", texto: "Este navegador não tem reconhecimento de voz. Use o Chrome no celular." });
      return;
    }
    const rec = new Reconhecedor();
    rec.lang = "pt-BR";
    rec.interimResults = false;
    rec.onresult = (e) => envia(e.results[0][0].transcript, true);
    rec.onend = () => setOuvindo(false);
    rec.onerror = () => setOuvindo(false);
    setOuvindo(true);
    rec.start();
  }

  async function desarma(pin) {
    setPedePin(false);
    try {
      const r = await api("/comando", { corpo: { acao: "desarmar", pin, origem: porVoz.current ? "voz" : "agente" } });
      const t = "Desarme: " + (NOME_STATUS[r.status] || r.status) + ".";
      poe({ de: "agente", texto: t });
      if (porVoz.current) fala(t);
    } catch (x) {
      poe({ de: "agente", texto: "Desarme não realizado: " + x.message });
    }
  }

  return (
    <div className="chat">
      <div className="msgs">
        {msgs.map((m, i) => (
          <div key={i} className={"msg " + m.de}>
            {m.voz && <span className="fraco pequeno">(voz) </span>}
            {m.texto}
            {m.modo && <div className="fraco pequeno">resposta gerada por: {m.modo === "llm" ? "modelo de linguagem" : "regras"}</div>}
            {m.dados && Object.keys(m.dados).length > 0 && (
              <details>
                <summary>dados usados (calculados pelo backend)</summary>
                <pre>{JSON.stringify(m.dados, null, 1)}</pre>
              </details>
            )}
          </div>
        ))}
        {ocupado && <div className="msg agente fraco">pensando...</div>}
      </div>
      <form className="entrada" onSubmit={(e) => { e.preventDefault(); envia(texto, false); }}>
        <button type="button" className={"btn mic " + (ouvindo ? "perigo" : "")} onClick={escuta} aria-label="Falar">
          {ouvindo ? "Ouvindo" : "Falar"}
        </button>
        <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Digite a pergunta" />
        <button className="btn primario" disabled={ocupado}>Enviar</button>
      </form>
      {pedePin && <PedePin aoConfirmar={desarma} aoCancelar={() => setPedePin(false)} />}
    </div>
  );
}
