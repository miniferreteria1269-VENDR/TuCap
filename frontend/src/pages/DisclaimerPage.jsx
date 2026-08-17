import { useState } from "react";

import { acceptDisclaimer } from "../api";

function DisclaimerPage({ onAccepted, onLogout }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const accept = async () => {
    setSaving(true);
    setError("");
    try {
      onAccepted(await acceptDisclaimer());
    } catch (acceptError) {
      setError(acceptError.message);
      setSaving(false);
    }
  };

  return (
    <main className="auth-shell disclaimer-shell">
      <section className="auth-card disclaimer-card">
        <div className="auth-brand">
          <span className="brand-mark auth-logo">T</span>
          <div><h1>TuCap</h1><p>Aviso importante</p></div>
        </div>
        <div className="disclaimer-icon" aria-hidden="true">i</div>
        <p className="eyebrow">Antes de continuar</p>
        <h2>Herramienta de registro matemático</h2>
        <div className="disclaimer-copy">
          <p>TuCap está diseñado únicamente para registrar operaciones y realizar cálculos matemáticos según la información ingresada por el usuario.</p>
          <p>TuCap no valida la legalidad de tasas, contratos, garantías ni otros términos de préstamo. Sus registros no constituyen por sí solos prueba legal de una deuda.</p>
          <p>El usuario es responsable de cumplir la legislación aplicable y de obtener asesoría profesional cuando corresponda.</p>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button auth-submit" disabled={saving} type="button" onClick={accept}>{saving ? "Guardando…" : "Entiendo y deseo continuar"}</button>
        <button className="text-button logout-link" type="button" onClick={onLogout}>Cerrar sesión</button>
      </section>
    </main>
  );
}

export default DisclaimerPage;
