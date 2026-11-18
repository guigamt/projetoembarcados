import { useState } from "react";

// Pede o PIN antes de desarmar (confirmacao autenticada)
export default function PedePin({ aoConfirmar, aoCancelar }) {
  const [pin, setPin] = useState("");
  return (
    <div className="fundo-modal">
      <form className="modal" onSubmit={(e) => { e.preventDefault(); aoConfirmar(pin); }}>
        <h3>Confirmar desarme</h3>
        <p className="fraco">Digite o PIN para desarmar a central.</p>
        <input autoFocus inputMode="numeric" type="password" placeholder="PIN" value={pin}
               onChange={(e) => setPin(e.target.value)} />
        <div className="linha">
          <button type="button" className="btn" onClick={aoCancelar}>Cancelar</button>
          <button className="btn perigo">Desarmar</button>
        </div>
      </form>
    </div>
  );
}
