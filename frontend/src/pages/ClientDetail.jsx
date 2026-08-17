import { useEffect, useState } from "react";

import { createLoan, getBorrower, getCapitalSummary, getLoans } from "../api";
import NewLoanModal from "../components/NewLoanModal";
import ReceivePaymentModal from "../components/ReceivePaymentModal";

const money = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });
const shortDate = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric" });
const statusLabels = { active: "Activo", paid: "Pagado", written_off: "Castigado" };

function initials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function formatDate(value) {
  return shortDate.format(new Date(`${value}T12:00:00`));
}

function ClientDetail({ client, onBack, onClientUpdated }) {
  const [loans, setLoans] = useState([]);
  const [capitalOnHand, setCapitalOnHand] = useState(0);
  const [loadingLoans, setLoadingLoans] = useState(true);
  const [loanError, setLoanError] = useState("");
  const [showLoanForm, setShowLoanForm] = useState(false);
  const [paymentLoan, setPaymentLoan] = useState(null);

  const refreshPortfolio = async () => {
    const [loanRows, capital, refreshedClient] = await Promise.all([
      getLoans(client.id),
      getCapitalSummary(),
      getBorrower(client.id),
    ]);
    setLoans(loanRows);
    setCapitalOnHand(capital.capital_on_hand);
    onClientUpdated(refreshedClient);
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([getLoans(client.id), getCapitalSummary()])
      .then(([loanRows, capital]) => {
        if (!cancelled) {
          setLoans(loanRows);
          setCapitalOnHand(capital.capital_on_hand);
        }
      })
      .catch((error) => {
        if (!cancelled) setLoanError(error.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingLoans(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client.id]);

  const saveLoan = async (payload) => {
    await createLoan(payload);
    setShowLoanForm(false);
    setLoanError("");
    await refreshPortfolio();
  };

  const completePayment = async () => {
    setPaymentLoan(null);
    setLoanError("");
    await refreshPortfolio();
  };

  return (
    <section className="client-detail">
      <button className="back-button" type="button" onClick={onBack}>← Clientes</button>
      <div className="client-identity-card">
        <span className="client-avatar large">{initials(client.full_name)}</span>
        <div>
          <p className="eyebrow">Cliente</p>
          <h2>{client.full_name}</h2>
          <p>{client.phone || "Sin teléfono registrado"}</p>
        </div>
      </div>

      <div className="detail-metrics">
        <article>
          <span>Capital pendiente</span>
          <strong>{money.format(client.outstanding_principal || 0)}</strong>
        </article>
        <article>
          <span>Interés acumulado</span>
          <strong>{money.format(client.accrued_interest || 0)}</strong>
        </article>
        <article>
          <span>Límite de crédito</span>
          <strong>{money.format(client.credit_limit || 0)}</strong>
        </article>
      </div>

      <button className="primary-button full-action" type="button" onClick={() => setShowLoanForm(true)}>Crear nuevo préstamo</button>

      <section className="detail-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Información</p>
            <h3>Datos del cliente</h3>
          </div>
        </div>
        <dl className="contact-list">
          <div><dt>Teléfono</dt><dd>{client.phone || "—"}</dd></div>
          <div><dt>Correo</dt><dd>{client.email || "—"}</dd></div>
          <div><dt>Identificación</dt><dd>{client.government_id || "—"}</dd></div>
          <div><dt>Dirección</dt><dd>{client.address || "—"}</dd></div>
          <div><dt>Notas</dt><dd>{client.notes || "—"}</dd></div>
        </dl>
      </section>

      <section className="detail-section">
        <p className="eyebrow">Cartera</p>
        <h3>Préstamos</h3>
        {loadingLoans && <div className="empty-state compact"><p>Cargando préstamos…</p></div>}
        {loanError && <p className="form-error portfolio-error">{loanError}</p>}
        {!loadingLoans && !loanError && loans.length === 0 && (
          <div className="empty-state compact">
            <strong>Sin préstamos registrados</strong>
            <p>Los préstamos de este cliente aparecerán aquí.</p>
          </div>
        )}
        {!loadingLoans && loans.length > 0 && (
          <div className="loan-list">
            {loans.map((loan) => (
              <article className="loan-card" key={loan.id}>
                <div className="loan-card-heading">
                  <div>
                    <span className={`status-pill ${loan.status}`}>{statusLabels[loan.status] || loan.status}</span>
                    <strong>{money.format(loan.principal_outstanding)}</strong>
                  </div>
                  <span>{Number(loan.monthly_interest_rate).toLocaleString("es-SV")}% mensual</span>
                </div>
                <div className="loan-card-details">
                  <span>Prestado <strong>{money.format(loan.original_principal)}</strong></span>
                  <span>Interés acumulado <strong>{money.format(loan.accrued_interest)}</strong></span>
                  <span>Próximo interés <strong>{formatDate(loan.next_interest_date)}</strong></span>
                </div>
                {loan.status === "active" && (
                  <button className="receive-payment-button" type="button" onClick={() => setPaymentLoan(loan)}>
                    Recibir pago
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      {showLoanForm && (
        <NewLoanModal
          capitalOnHand={capitalOnHand}
          client={client}
          onClose={() => setShowLoanForm(false)}
          onSave={saveLoan}
        />
      )}
      {paymentLoan && (
        <ReceivePaymentModal
          client={client}
          loan={paymentLoan}
          onClose={() => setPaymentLoan(null)}
          onComplete={completePayment}
        />
      )}
    </section>
  );
}

export default ClientDetail;
