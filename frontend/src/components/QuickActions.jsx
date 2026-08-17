import { useEffect, useMemo, useState } from "react";

import {
  addCapital,
  createBorrower,
  createLoan,
  getBorrowers,
  getCapitalSummary,
  getLoans,
  withdrawCapital,
} from "../api";
import AddCapitalModal from "./AddCapitalModal";
import ClientFormModal from "./ClientFormModal";
import NewLoanModal from "./NewLoanModal";
import ReceivePaymentModal from "./ReceivePaymentModal";
import WithdrawCapitalModal from "./WithdrawCapitalModal";

const currency = new Intl.NumberFormat("es-SV", { style: "currency", currency: "USD" });

const actions = [
  { id: "new-loan", icon: "$+", title: "Nuevo préstamo", detail: "Desembolsar capital a un cliente" },
  { id: "payment", icon: "$", title: "Registrar pago", detail: "Aplicar interés y capital" },
  { id: "new-client", icon: "+", title: "Nuevo cliente", detail: "Agregar persona y límite de crédito" },
  { id: "add-capital", icon: "↑", title: "Agregar capital", detail: "Ingresar fondos a la caja" },
  { id: "withdraw-capital", icon: "↓", title: "Retirar capital", detail: "Registrar uso personal u otro retiro" },
];

function SelectionSheet({ action, borrowers, loans, loading, error, onClose, onRetry, onSelect, onSwitch }) {
  const [query, setQuery] = useState("");
  const isLoan = action === "new-loan";
  const isWithdrawal = action === "withdraw-capital";
  const borrowerById = useMemo(
    () => new Map(borrowers.map((borrower) => [borrower.id, borrower])),
    [borrowers],
  );
  const normalized = query.trim().toLocaleLowerCase("es");
  const rows = useMemo(() => {
    if (isLoan) {
      return borrowers.filter((borrower) => (
        !normalized || [borrower.full_name, borrower.phone, borrower.government_id]
          .filter(Boolean)
          .some((value) => value.toLocaleLowerCase("es").includes(normalized))
      ));
    }
    return loans.filter((loan) => {
      if (loan.status !== "active") return false;
      const borrower = borrowerById.get(loan.borrower_id);
      return !normalized || [borrower?.full_name, borrower?.phone, borrower?.government_id]
        .filter(Boolean)
        .some((value) => value.toLocaleLowerCase("es").includes(normalized));
    });
  }, [borrowerById, borrowers, isLoan, loans, normalized]);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="sheet-modal quick-selection-sheet" role="dialog" aria-modal="true" aria-labelledby="quick-selection-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-handle" aria-hidden="true" />
        <div className="modal-heading">
          <div><p className="eyebrow">Acción rápida</p><h2 id="quick-selection-title">{isWithdrawal ? "Retirar capital" : isLoan ? "¿A quién prestarás?" : "¿Qué préstamo pagarán?"}</h2></div>
          <button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>

        {!isWithdrawal && !loading && !error && (borrowers.length > 0 || !isLoan) && (
          <label className="search-box quick-search">
            <span aria-hidden="true">⌕</span>
            <input aria-label="Buscar cliente" onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre, teléfono o DUI" value={query} />
            {query && <button type="button" onClick={() => setQuery("")} aria-label="Limpiar búsqueda">×</button>}
          </label>
        )}

        {loading && <div className="quick-state"><span className="quick-loader" /><p>Cargando información…</p></div>}
        {error && <div className="quick-state"><strong>No pudimos cargar la información.</strong><p>{error}</p><button className="primary-button" type="button" onClick={onRetry}>Intentar de nuevo</button></div>}
        {!loading && !error && rows.length === 0 && (
          <div className="quick-state">
            <strong>{normalized ? "No encontramos coincidencias" : isLoan ? "No hay clientes registrados" : "No hay préstamos activos"}</strong>
            <p>{normalized ? "Prueba con otra búsqueda." : isLoan ? "Primero agrega a la persona que recibirá el préstamo." : "Registra un préstamo antes de recibir su pago."}</p>
            {!normalized && <button className="primary-button" type="button" onClick={() => onSwitch(isLoan ? "new-client" : "new-loan")}>{isLoan ? "Nuevo cliente" : "Nuevo préstamo"}</button>}
          </div>
        )}

        {!loading && !error && rows.length > 0 && (
          <div className="quick-selection-list">
            {rows.map((row) => {
              const borrower = isLoan ? row : borrowerById.get(row.borrower_id);
              return (
                <button className="quick-selection-row" key={row.id} type="button" onClick={() => onSelect(isLoan ? { borrower: row } : { borrower, loan: row })}>
                  <span className="quick-selection-main"><strong>{borrower?.full_name || "Cliente no disponible"}</strong><small>{isLoan ? (borrower.phone || "Sin teléfono") : `${currency.format(row.principal_outstanding)} de capital pendiente`}</small></span>
                  <span className="quick-selection-value"><strong>{isLoan ? currency.format(row.outstanding_principal || 0) : currency.format(row.accrued_interest || 0)}</strong><small>{isLoan ? "exposición actual" : "interés acumulado"}</small></span>
                  <span className="row-chevron" aria-hidden="true">›</span>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function QuickActions({ onClose, onCompleted }) {
  const [action, setAction] = useState(null);
  const [borrowers, setBorrowers] = useState([]);
  const [loans, setLoans] = useState([]);
  const [capitalOnHand, setCapitalOnHand] = useState(0);
  const [selection, setSelection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadVersion, setLoadVersion] = useState(0);

  const chooseAction = (nextAction) => {
    setAction(nextAction);
    setSelection(null);
    setError("");
    setLoading(["new-loan", "payment", "withdraw-capital"].includes(nextAction));
  };

  const retryLoad = () => {
    setError("");
    setLoading(true);
    setLoadVersion((current) => current + 1);
  };

  useEffect(() => {
    if (!["new-loan", "payment", "withdraw-capital"].includes(action)) return undefined;
    let cancelled = false;

    const loaders = action === "new-loan"
      ? [getBorrowers(), getCapitalSummary()]
      : action === "payment"
        ? [getBorrowers(), getLoans()]
        : [getCapitalSummary()];

    Promise.all(loaders)
      .then((results) => {
        if (cancelled) return;
        if (action === "new-loan") {
          setBorrowers(results[0]);
          setCapitalOnHand(results[1].capital_on_hand);
        } else if (action === "payment") {
          setBorrowers(results[0]);
          setLoans(results[1]);
        } else {
          setCapitalOnHand(results[0].capital_on_hand);
        }
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [action, loadVersion]);

  if (!action) {
    return (
      <div className="modal-backdrop quick-actions-backdrop" role="presentation" onMouseDown={onClose}>
        <section className="sheet-modal quick-actions-sheet" role="dialog" aria-modal="true" aria-labelledby="quick-actions-title" onMouseDown={(event) => event.stopPropagation()}>
          <div className="sheet-handle" aria-hidden="true" />
          <div className="modal-heading"><div><p className="eyebrow">Crear o registrar</p><h2 id="quick-actions-title">Acciones rápidas</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Cerrar">×</button></div>
          <div className="quick-action-list">
            {actions.map((item) => (
              <button className="quick-action-row" key={item.id} type="button" onClick={() => chooseAction(item.id)}>
                <span className={`quick-action-icon ${item.id}`}>{item.icon}</span>
                <span><strong>{item.title}</strong><small>{item.detail}</small></span>
                <span className="row-chevron" aria-hidden="true">›</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    );
  }

  if (action === "new-client") return <ClientFormModal onClose={onClose} onSave={async (payload) => { await createBorrower(payload); onCompleted("Cliente registrado"); }} />;
  if (action === "add-capital") return <AddCapitalModal onClose={onClose} onSave={async (payload) => { await addCapital(payload); onCompleted("Capital agregado"); }} />;
  if (action === "withdraw-capital" && !loading && !error) return <WithdrawCapitalModal available={capitalOnHand} onClose={onClose} onSave={async (payload) => { await withdrawCapital(payload); onCompleted("Retiro registrado"); }} />;
  if (action === "new-loan" && selection?.borrower) return <NewLoanModal capitalOnHand={capitalOnHand} client={selection.borrower} onClose={onClose} onSave={async (payload) => { await createLoan(payload); onCompleted("Préstamo registrado"); }} />;
  if (action === "payment" && selection?.borrower && selection?.loan) return <ReceivePaymentModal client={selection.borrower} loan={selection.loan} onClose={onClose} onComplete={() => onCompleted("Pago registrado")} />;

  return (
    <SelectionSheet
      action={action}
      borrowers={borrowers}
      error={error}
      loading={loading}
      loans={loans}
      onClose={onClose}
      onRetry={retryLoad}
      onSelect={setSelection}
      onSwitch={chooseAction}
    />
  );
}

export default QuickActions;
