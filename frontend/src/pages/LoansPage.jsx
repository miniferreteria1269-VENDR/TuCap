import { useEffect, useMemo, useState } from "react";

import { getBorrowers, getLoans } from "../api";
import LoanDetailModal from "../components/LoanDetailModal";
import ReceivePaymentModal from "../components/ReceivePaymentModal";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });
const shortDate = new Intl.DateTimeFormat("es-SV", { day: "numeric", month: "short", year: "numeric" });

const filters = [
  { id: "active", label: "Activos" },
  { id: "paid", label: "Cerrados" },
  { id: "written_off", label: "Castigados" },
];

const statusLabels = { active: "Activo", paid: "Pagado", written_off: "Castigado" };

function formatDate(value) {
  if (!value) return "—";
  return shortDate.format(new Date(`${value.slice(0, 10)}T12:00:00`));
}

function LoansPage({ onNewLoan }) {
  const [loans, setLoans] = useState([]);
  const [borrowers, setBorrowers] = useState([]);
  const [filter, setFilter] = useState("active");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detailLoan, setDetailLoan] = useState(null);
  const [paymentLoan, setPaymentLoan] = useState(null);

  const loadPortfolio = async () => {
    setError("");
    try {
      const [loanRows, borrowerRows] = await Promise.all([getLoans(), getBorrowers()]);
      setLoans(loanRows);
      setBorrowers(borrowerRows);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([getLoans(), getBorrowers()])
      .then(([loanRows, borrowerRows]) => {
        if (!cancelled) {
          setLoans(loanRows);
          setBorrowers(borrowerRows);
        }
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const borrowerById = useMemo(
    () => new Map(borrowers.map((borrower) => [borrower.id, borrower])),
    [borrowers],
  );

  const activeLoans = useMemo(() => loans.filter((loan) => loan.status === "active"), [loans]);
  const activePrincipal = activeLoans.reduce((total, loan) => total + Number(loan.principal_outstanding || 0), 0);
  const activeInterest = activeLoans.reduce((total, loan) => total + Number(loan.accrued_interest || 0), 0);
  const counts = useMemo(() => Object.fromEntries(filters.map((item) => [item.id, loans.filter((loan) => loan.status === item.id).length])), [loans]);

  const visibleLoans = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("es");
    return loans.filter((loan) => {
      if (loan.status !== filter) return false;
      if (!normalized) return true;
      const borrower = borrowerById.get(loan.borrower_id);
      return [borrower?.full_name, borrower?.phone, borrower?.government_id, loan.collateral_description]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("es").includes(normalized));
    });
  }, [borrowerById, filter, loans, query]);

  const clientFor = (loan) => borrowerById.get(loan.borrower_id) || { full_name: "Cliente no disponible" };

  const completePayment = async () => {
    setPaymentLoan(null);
    await loadPortfolio();
  };

  return (
    <section className="loans-page">
      <div className="page-heading loans-page-heading">
        <div><p className="eyebrow">Cartera</p><h2>Préstamos</h2><p>{loans.length} registrados</p></div>
        <button className="primary-button small-action" type="button" onClick={onNewLoan}>+ Nuevo</button>
      </div>

      <section className="portfolio-summary">
        <div className="portfolio-summary-total"><span>Cartera activa total</span><strong>{currency.format(activePrincipal + activeInterest)}</strong><small>Capital pendiente más interés acumulado</small></div>
        <div className="portfolio-summary-grid">
          <div><span>Capital</span><strong>{currency.format(activePrincipal)}</strong></div>
          <div><span>Interés</span><strong>{currency.format(activeInterest)}</strong></div>
          <div><span>Activos</span><strong>{activeLoans.length}</strong></div>
        </div>
      </section>

      <label className="search-box loans-search">
        <span aria-hidden="true">⌕</span>
        <input aria-label="Buscar préstamos" onChange={(event) => setQuery(event.target.value)} placeholder="Buscar cliente, DUI o garantía" value={query} />
        {query && <button type="button" onClick={() => setQuery("")} aria-label="Limpiar búsqueda">×</button>}
      </label>

      <div className="loan-filter-tabs" role="tablist" aria-label="Estado del préstamo">
        {filters.map((item) => (
          <button aria-selected={filter === item.id} className={filter === item.id ? "active" : ""} key={item.id} onClick={() => setFilter(item.id)} role="tab" type="button">
            <span>{item.label}</span><strong>{counts[item.id] || 0}</strong>
          </button>
        ))}
      </div>

      {loading && <div className="list-message"><span className="quick-loader" /><p>Cargando cartera…</p></div>}
      {error && <div className="list-message error-message"><strong>No pudimos cargar los préstamos.</strong><p>{error}</p><button className="text-button" type="button" onClick={loadPortfolio}>Intentar de nuevo</button></div>}
      {!loading && !error && visibleLoans.length === 0 && (
        <div className="list-message">
          <span className="empty-icon" aria-hidden="true">$</span>
          <strong>{query ? "No encontramos coincidencias" : filter === "active" ? "No hay préstamos activos" : filter === "paid" ? "No hay préstamos pagados" : "No hay préstamos castigados"}</strong>
          <p>{query ? "Prueba con otro nombre, DUI o descripción de garantía." : filter === "active" ? "Los préstamos abiertos aparecerán aquí con sus saldos actuales." : "Los préstamos aparecerán aquí al cerrar su ciclo."}</p>
          {!query && filter === "active" && <button className="primary-button" type="button" onClick={onNewLoan}>Nuevo préstamo</button>}
        </div>
      )}

      {!loading && !error && visibleLoans.length > 0 && (
        <div className="portfolio-loan-list">
          {visibleLoans.map((loan) => {
            const client = clientFor(loan);
            const totalPending = Number(loan.principal_outstanding || 0) + Number(loan.accrued_interest || 0);
            return (
              <article className={`portfolio-loan-card ${loan.status}`} key={loan.id}>
                <div className="portfolio-loan-heading">
                  <div><strong>{client.full_name}</strong><small>{formatDate(loan.start_date)} · {Number(loan.monthly_interest_rate).toLocaleString("es-SV")}% mensual</small></div>
                  <span className={`status-pill ${loan.status}`}>{statusLabels[loan.status]}</span>
                </div>

                <div className="portfolio-loan-balance">
                  <span>{loan.status === "active" ? "Saldo pendiente" : "Capital original"}</span>
                  <strong>{currency.format(loan.status === "active" ? totalPending : loan.original_principal)}</strong>
                </div>

                {loan.status === "active" ? (
                  <div className="portfolio-loan-breakdown">
                    <div><span>Capital</span><strong>{currency.format(loan.principal_outstanding)}</strong></div>
                    <div><span>Interés</span><strong>{currency.format(loan.accrued_interest)}</strong></div>
                    <div><span>Próximo cargo</span><strong>{formatDate(loan.next_interest_date)}</strong></div>
                  </div>
                ) : (
                  <div className="portfolio-closed-details"><span>Cerrado el <strong>{formatDate(loan.closed_at)}</strong></span><span>{loan.status === "written_off" ? "Consulta el resultado económico en el detalle." : "Préstamo completado contractualmente."}</span></div>
                )}

                {loan.collateral_description && <p className="portfolio-collateral"><span>Garantía</span>{loan.collateral_description}</p>}
                <div className="loan-card-actions">
                  <button className="loan-detail-button" type="button" onClick={() => setDetailLoan(loan)}>Ver detalle</button>
                  {loan.status === "active" && <button className="receive-payment-button" type="button" onClick={() => setPaymentLoan(loan)}>Recibir pago</button>}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {paymentLoan && <ReceivePaymentModal client={clientFor(paymentLoan)} loan={paymentLoan} onClose={() => setPaymentLoan(null)} onComplete={completePayment} />}
      {detailLoan && (
        <LoanDetailModal
          client={clientFor(detailLoan)}
          loan={detailLoan}
          onClose={() => setDetailLoan(null)}
          onReceivePayment={(loan) => { setDetailLoan(null); setPaymentLoan(loan); }}
          onMutated={loadPortfolio}
        />
      )}
    </section>
  );
}

export default LoansPage;
