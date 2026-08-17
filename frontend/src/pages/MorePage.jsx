import { useEffect, useState } from "react";

import { getCapitalSummary } from "../api";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

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

function MorePage({ user, onQuickAction, onOpenDashboard, onLogout }) {
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
          <button className="more-menu-row" type="button" onClick={() => setSheet("legal")}><span className="more-menu-icon">i</span><span><strong>Aviso legal</strong><small>Alcance y responsabilidad de la plataforma</small></span><span className="row-chevron" aria-hidden="true">›</span></button>
        </div>
      </section>

      <button className="more-logout-button" type="button" onClick={() => setSheet("logout")}><span>⇥</span>Cerrar sesión</button>
      <p className="more-footer">TuCap · Herramienta privada de control de cartera</p>

      {sheet && <InformationSheet type={sheet} user={user} onClose={() => setSheet(null)} onLogout={onLogout} />}
    </section>
  );
}

export default MorePage;
