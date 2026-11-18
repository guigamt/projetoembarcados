import { useState } from "react";
import { api, hora, idade, NOME_CENTRAL, NOME_ZONA, NOME_MOTIVO, NOME_STATUS } from "./api.js";
import PedePin from "./PedePin.jsx";

function classeZona(z) {
  if (z.estado === "AL_NORMAL" || z.estado === "AL_DEG" || z.estado === "CONFIRMA") return "alarme";
  if (z.estado === "ISOLADA") return "isolada";
  if (z.deg || z.falha) return "degradada";
  if (z.estado === "VIGIA") return "vigia";
  return "";
}

export default function Painel({ estado }) {
  const [pendente, setPendente] = useState(null);   // "armar" | "desarmar"
  const [resultado, setResultado] = useState(null);
  const [pedePin, setPedePin] = useState(false);

  if (!estado) return <p className="fraco centro">Carregando...</p>;
  const con = estado.conexao || {};
  const online = !!con.online;

  async function manda(acao, pin) {
    setPedePin(false);
    setResultado(null);
    setPendente(acao);
    try {
      const r = await api("/comando", { corpo: { acao, pin, origem: "painel" } });
      setResultado({ ok: r.status === "confirmado", texto: NOME_STATUS[r.status] || r.status });
    } catch (x) {
      setResultado({ ok: false, texto: x.message });
    }
    setPendente(null);
  }

  return (
    <>
      <section className={"central " + (online ? estado.central : "ANTIGO")}>
        <div className="rotulo">Central</div>
        <div className="grande">{NOME_CENTRAL[estado.central] || estado.central}</div>
        <div className="selos">
          {estado.modo_deg && <span className="selo ambar">MODO DEGRADADO</span>}
          {estado.teste && <span className="selo azul">TESTE</span>}
          {con.fpga_ok === false && <span className="selo vermelho">FPGA SEM RESPOSTA</span>}
        </div>
        <div className="conexao">
          {online
            ? <>Conectada - atualizado {idade(con.idade_s)}</>
            : <><b>SEM CONEXÃO</b> - último estado conhecido, de {hora(con.ts_recebido)}</>}
        </div>
        {!online && <div className="conexao">O alarme local continua funcionando na central.</div>}
      </section>

      <section className="linha">
        <button className="btn primario" disabled={!!pendente} onClick={() => manda("armar")}>Armar</button>
        <button className="btn perigo" disabled={!!pendente} onClick={() => setPedePin(true)}>Desarmar</button>
      </section>
      {pendente && <p className="pendente">Operação pendente: aguardando a central confirmar ({pendente})...</p>}
      {resultado && <p className={resultado.ok ? "ok" : "erro"}>{resultado.texto}</p>}

      <h2>Zonas</h2>
      <section className="zonas">
        {estado.zonas.map((z) => (
          <div key={z.zona} className={"zona " + classeZona(z) + (online ? "" : " antiga")}>
            <div className="num">Z{z.zona}</div>
            <div className="corpo">
              <div className="nome">{z.nome}</div>
              <div className="est">{NOME_ZONA[z.estado] || z.estado}</div>
              {z.deg && <div className="det">Cobertura reduzida: {NOME_MOTIVO[z.motivo] || "degradada"}</div>}
              {z.falha && <div className="det">Manutenção: falha de sensor diagnosticada</div>}
            </div>
          </div>
        ))}
      </section>

      <p className="fraco pequeno">
        Sinal Wi-Fi: {con.rssi ?? "-"} dBm - eventos na fila da ESP32: {con.fila ?? "-"} - perdidos: {con.perdidos ?? "-"}
      </p>
      {pedePin && <PedePin aoConfirmar={(pin) => manda("desarmar", pin)} aoCancelar={() => setPedePin(false)} />}
    </>
  );
}
