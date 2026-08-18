import { useEffect, useState } from "react";

import { changePassword, getCapitalSummary } from "../api";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

function PasswordChangeSheet({ onClose, onPasswordChanged }) {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (form.new_password.length < 12) {
      setError("La contraseña nueva debe contener al menos 12 caracteres.");
      return;
    }
    if (form.new_password !== form.confirm_password) {
      setError("La confirmación no coincide con la contraseña nueva.");
      return;
    }
    if (form.current_password === form.new_password) {
      setError("La contraseña nueva debe ser diferente a la actual.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      await changePassword({
        current_password: form.current_password,
        new_password: form.new_password,
      });
      onPasswordChanged();
    } catch (saveError) {
      setError(saveError.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet information-sheet" role="dialog" aria-modal="true" aria-labelledby="password-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading"><div><p className="eyebrow">Cuenta y seguridad</p><h2 id="password-title">Cambiar contraseña</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
        <form className="client-form password-change-form" onSubmit={submit}>
          <label className="field full-width"><span>Contraseña actual</span><input autoComplete="current-password" autoFocus maxLength="256" onChange={update("current_password")} required type="password" value={form.current_password} /></label>
          <label className="field full-width"><span>Contraseña nueva</span><input autoComplete="new-password" maxLength="256" minLength="12" onChange={update("new_password")} required type="password" value={form.new_password} /><small>Mínimo 12 caracteres.</small></label>
          <label className="field full-width"><span>Confirmar contraseña nueva</span><input autoComplete="new-password" maxLength="256" minLength="12" onChange={update("confirm_password")} required type="password" value={form.confirm_password} /></label>
          <p className="password-security-note">Al guardar, TuCap cerrará todas las sesiones abiertas. Deberás ingresar nuevamente con la contraseña nueva.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="modal-actions"><button className="cancel-button" type="button" onClick={onClose}>Cancelar</button><button className="primary-button" disabled={saving} type="submit">{saving ? "Actualizando…" : "Cambiar contraseña"}</button></div>
        </form>
      </section>
    </div>
  );
}

function InformationSheet({ type, user, onClose, onLogout }) {
  const [loggingOut, setLoggingOut] = useState(false);

  if (type === "security") {
    return (
      <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
        <section className="sheet-modal compact-sheet information-sheet" role="dialog" aria-modal="true" aria-labelledby="security-title" onMouseDown={(event) => event.stopPropagation()}>
          <div className="sheet-handle" aria-hidden="true" />
          <div className="modal-heading"><div><p className="eyebrow">Configuración</p><h2 id="security-title">Cuenta y seguridad</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
          <dl className="settings-list">
            <div><dt>Usuario</dt><dd>{user.full_name}</dd></div>
            <div><dt>Correo</dt><dd>{user.email}</dd></div>
            <div><dt>Espacio de trabajo</dt><dd>Tenant {user.tenant_number}</dd></div>
            <div><dt>Bloqueo automático</dt><dd>5 minutos sin actividad</dd></div>
            <div><dt>Separación de datos</dt><dd>Activa por cuenta</dd></div>
          </dl>
          <p className="security-explanation">TuCap cierra la sesión automáticamente cuando el dispositivo permanece sin realizar solicitudes. Cada cuenta solo puede consultar la información de su propio espacio de trabajo.</p>
          <div className="app-version"><span>TuCap</span><strong>Versión piloto 0.1.0</strong></div>
          <button className="primary-button full-action" type="button" onClick={onClose}>Listo</button>
        </section>
      </div>
    );
  }

  if (type === "legal") {
    return (
      <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
        <section className="sheet-modal compact-sheet information-sheet" role="dialog" aria-modal="true" aria-labelledby="legal-title" onMouseDown={(event) => event.stopPropagation()}>
          <div className="sheet-handle" aria-hidden="true" />
          <div className="modal-heading"><div><p className="eyebrow">Aviso legal</p><h2 id="legal-title">Registro matemático únicamente</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
          <div className="legal-notice-copy">
            <p>TuCap está diseñado únicamente para registrar operaciones y realizar cálculos matemáticos según la información ingresada por el usuario.</p>
            <p>TuCap no valida la legalidad de tasas, contratos, garantías ni otros términos de préstamo. Sus registros no constituyen por sí solos prueba legal de una deuda.</p>
            <p>El usuario es responsable de cumplir la legislación aplicable y de obtener asesoría profesional cuando corresponda.</p>
          </div>
          <p className="legal-reminder">Este aviso también aparece después de cada inicio de sesión.</p>
          <button className="primary-button full-action" type="button" onClick={onClose}>Entendido</button>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal compact-sheet logout-confirmation" role="dialog" aria-modal="true" aria-labelledby="logout-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading"><div><p className="eyebrow">Seguridad</p><h2 id="logout-title">¿Cerrar sesión?</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
        <p>Se bloqueará el acceso a la información financiera en este dispositivo hasta que vuelvas a ingresar.</p>
        <div className="modal-actions"><button className="cancel-button" type="button" onClick={onClose}>Cancelar</button><button className="danger-button" disabled={loggingOut} type="button" onClick={async () => { setLoggingOut(true); await onLogout(); }}>{loggingOut ? "Cerrando…" : "Cerrar sesión"}</button></div>
      </section>
    </div>
  );
}

function MorePage({ user, onQuickAction, onOpenDashboard, onLogout, onPasswordChanged }) {
  const [capitalOnHand, setCapitalOnHand] = useState(null);
  const [capitalError, setCapitalError] = useState("");
  const [sheet, setSheet] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getCapitalSummary()
      .then((summary) => { if (!cancelled) setCapitalOnHand(summary.capital_on_hand); })
      .catch((error) => { if (!cancelled) setCapitalError(error.message); });
    return () => { cancelled = true; };
  }, []);

  return (
    <section className="more-page">
      <div className="page-heading more-page-heading"><div><p className="eyebrow">TuCap</p><h2>Más opciones</h2><p>Administración, informes y seguridad</p></div></div>

      <section className="more-capital-card">
        <div><span>Capital disponible</span><strong>{capitalOnHand == null ? "—" : currency.format(capitalOnHand)}</strong><small>Fondos registrados para préstamos</small></div>
        <div className="more-capital-actions">
          <button className="secondary-button" type="button" onClick={() => onQuickAction("add-capital")}>Agregar</button>
          <button className="withdraw-button" disabled={capitalOnHand == null || Number(capitalOnHand) <= 0} type="button" onClick={() => onQuickAction("withdraw-capital")}>Retirar</button>
        </div>
        {capitalError && <p className="more-capital-error">No se pudo actualizar el saldo. Las opciones restantes siguen disponibles.</p>}
      </section>

      <section className="more-section">
        <p className="more-section-label">Finanzas</p>
        <div className="more-menu-list">
          <button className="more-menu-row" type="button" onClick={() => onOpenDashboard("period-report")}><span className="more-menu-icon">▥</span><span><strong>Reportes por período</strong><small>Cobros, capital desplegado y resultados</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
          <button className="more-menu-row" type="button" onClick={() => onOpenDashboard("capital-activity")}><span className="more-menu-icon">↕</span><span><strong>Movimientos de capital</strong><small>Depósitos, retiros, recuperaciones y anulaciones</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
        </div>
      </section>

      <section className="more-section">
        <p className="more-section-label">Cuenta</p>
        <div className="more-menu-list">
          <button className="more-menu-row" type="button" onClick={() => setSheet("security")}><span className="more-menu-icon">⌾</span><span><strong>Cuenta y seguridad</strong><small>Usuario, espacio de trabajo y bloqueo automático</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
          <button className="more-menu-row" type="button" onClick={() => setSheet("password")}><span className="more-menu-icon">✱</span><span><strong>Cambiar contraseña</strong><small>Actualiza tu clave y cierra las demás sesiones</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
          <button className="more-menu-row" type="button" onClick={() => setSheet("legal")}><span className="more-menu-icon">i</span><span><strong>Aviso legal</strong><small>Alcance y responsabilidad de la plataforma</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
        </div>
      </section>

      <button className="more-logout-button" type="button" onClick={() => setSheet("logout")}><span>⇥</span>Cerrar sesión</button>
      <p className="more-footer">TuCap · Herramienta privada de control de cartera</p>

      {sheet === "password" && <PasswordChangeSheet onClose={() => setSheet(null)} onPasswordChanged={onPasswordChanged} />}
      {sheet && sheet !== "password" && <InformationSheet type={sheet} user={user} onClose={() => setSheet(null)} onLogout={onLogout} />}
    </section>
  );
}

export default MorePage;
