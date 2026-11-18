import { useEffect, useState } from "react";
import { api, hora, NOME_ZONA } from "./api.js";

export default function Historico() {
  const [modo, setModo] = useState("disparos");
  const [linhas, setLinhas] = useState([]);
  const [erro, setErro] = useState("");

  async function carrega() {
    try {
      const rota = { disparos: "/incidentes?dias=30", eventos: "/eventos?dias=7&limite=100", alertas: "/alertas" }[modo];
      setLinhas(await api(rota));
      setErro("");
    } catch (x) {
      setErro(x.message);
    }
  }
  useEffect(() => { setLinhas([]); carrega(); const t = setInterval(carrega, 5000); return () => clearInterval(t); }, [modo]);

  async function marca(id, rotulo) {
    await api(`/incidentes/${id}/rotulo`, { corpo: { rotulo } });
    carrega();
  }

  return (
    <>
      <div className="seletor">
        {[["disparos", "Disparos"], ["eventos", "Eventos"], ["alertas", "Alertas enviados"]].map(([id, n]) => (
          <button key={id} className={modo === id ? "ativa" : ""} onClick={() => setModo(id)}>{n}</button>
        ))}
      </div>
      {erro && <p className="erro">{erro}</p>}
      {linhas.length === 0 && <p className="fraco centro">Nada registrado neste período.</p>}

      {modo === "disparos" && linhas.map((i) => (
        <div key={i.incident_id} className="item">
          <div className="topo">
            <b>Zona {i.zona}</b> <span className="fraco">{hora(i.ts_inicio)}</span>
            {i.teste ? <span className="selo azul">TESTE</span> : null}
          </div>
          <div>{i.nome}</div>
          <div className="selos">
            {i.confirmado ? <span className="selo verde">2 sensores</span> : <span className="selo ambar">1 sensor</span>}
            {i.degradado ? <span className="selo ambar">degradado</span> : null}
            <span className={"selo " + ({ alta: "verde", "média": "ambar", baixa: "vermelho" }[i.confianca] || "")}>
              confiança {i.confianca}
            </span>
          </div>
          <div className="fraco pequeno">{i.explicacao}</div>
          <div className="linha">
            <span className="fraco pequeno">Foi um alarme real?</span>
            <button className={"mini " + (i.rotulo === "real" ? "ativa" : "")} onClick={() => marca(i.incident_id, "real")}>Real</button>
            <button className={"mini " + (i.rotulo === "falso" ? "ativa" : "")} onClick={() => marca(i.incident_id, "falso")}>Falso</button>
          </div>
        </div>
      ))}

      {modo === "eventos" && linhas.map((e) => (
        <div key={e.event_id} className="item fino">
          <span className="fraco">{hora(e.ts_evento)}</span>{" "}
          <b>{e.zona ? "Z" + e.zona : "Central"}</b> {e.tipo}
          {e.estado ? " - " + (NOME_ZONA[e.estado] || e.estado) : e.zona ? "" : " - " + e.central}
          {e.teste ? <span className="selo azul">TESTE</span> : null}
          {e.extra ? <span className="fraco"> ({e.extra})</span> : null}
        </div>
      ))}

      {modo === "alertas" && linhas.map((a) => (
        <div key={a.id} className="item">
          <div className="topo">
            <b>{a.canal}</b> <span className="fraco">{a.destino} - {hora(a.ts)}</span>
            <span className={"selo " + (a.ok ? "verde" : "vermelho")}>{a.ok ? "enviado" : "falhou"}</span>
          </div>
          <pre>{a.texto}</pre>
          {!a.ok && <div className="fraco pequeno">{a.detalhe}</div>}
        </div>
      ))}
    </>
  );
}
