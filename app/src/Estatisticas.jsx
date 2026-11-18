import { useEffect, useState } from "react";
import { api } from "./api.js";

function Barra({ valor, max, rotulo, cor }) {
  const pct = max ? Math.round((valor / max) * 100) : 0;
  return (
    <div className="barra">
      <span className="rot">{rotulo}</span>
      <div className="trilho"><div className={"cheio " + (cor || "")} style={{ width: pct + "%" }} /></div>
      <span className="val">{valor}</span>
    </div>
  );
}

function tempo(s) {
  if (s < 120) return s + " s";
  if (s < 7200) return Math.floor(s / 60) + " min";
  return (s / 3600).toFixed(1) + " h";
}

export default function Estatisticas() {
  const [dias, setDias] = useState(7);
  const [e, setE] = useState(null);
  const [c, setC] = useState(null);

  useEffect(() => {
    api("/estatisticas?dias=" + dias).then(setE).catch(() => setE(null));
    api("/consumo").then(setC).catch(() => setC(null));
  }, [dias]);

  if (!e) return <p className="fraco centro">Carregando...</p>;
  const zonas = Object.entries(e.por_zona);
  const maxDisp = Math.max(1, ...zonas.map(([, v]) => v.disparos));
  const maxDeg = Math.max(1, ...zonas.map(([, v]) => v.entradas_degradado));
  const maxHora = Math.max(1, ...e.disparos_por_hora);

  return (
    <>
      <div className="seletor">
        {[1, 7, 30].map((d) => (
          <button key={d} className={dias === d ? "ativa" : ""} onClick={() => setDias(d)}>{d === 1 ? "Hoje" : d + " dias"}</button>
        ))}
      </div>
      <p className="fraco pequeno centro">{e.de} até {e.ate}</p>

      <section className="cartoes">
        <div className="cartao"><div className="n">{e.total_disparos}</div><div>disparos</div></div>
        <div className="cartao"><div className="n">{e.disparos_degradados}</div><div>degradados</div></div>
        <div className="cartao"><div className="n">{Math.round(e.proporcao_degradados * 100)}%</div><div>proporção</div></div>
      </section>

      <h2>Disparos por zona</h2>
      {zonas.map(([z, v]) => <Barra key={z} rotulo={"Z" + z} valor={v.disparos} max={maxDisp} cor="vermelho" />)}

      <h2>Entradas em modo degradado</h2>
      {zonas.map(([z, v]) => (
        <div key={z}>
          <Barra rotulo={"Z" + z} valor={v.entradas_degradado} max={maxDeg} cor="ambar" />
          <div className="fraco pequeno recuo">tempo degradada: {tempo(v.tempo_degradado_s)} - marcados falsos: {v.falsos} - testes: {v.testes}</div>
        </div>
      ))}

      <h2>Disparos por hora do dia</h2>
      <div className="horas">
        {e.disparos_por_hora.map((n, h) => (
          <div key={h} className="col" title={h + "h: " + n}>
            <div className="pilar" style={{ height: Math.round((n / maxHora) * 60) + "px" }} />
            <span>{h % 6 === 0 ? h : ""}</span>
          </div>
        ))}
      </div>

      {e.recomendacoes.length > 0 && (
        <>
          <h2>Recomendações</h2>
          {e.recomendacoes.map((r, i) => <p key={i} className="item fino">{r}</p>)}
        </>
      )}

      {c && (
        <>
          <h2>Consumo de dados (IoT Hub)</h2>
          <Barra rotulo="hoje" valor={c.hoje} max={c.limite_dia} cor="azul" />
          <p className="fraco pequeno">{c.hoje} de {c.limite_dia} mensagens por dia do plano gratuito.</p>
        </>
      )}
    </>
  );
}
