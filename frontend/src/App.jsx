import { useCallback, useEffect, useState } from "react";

import {
  clearAccessToken,
  getAccessToken,
  getCurrentUser,
  getLastSessionActivity,
  revokeSession,
} from "./api";
import BottomNav from "./components/BottomNav";
import QuickActions from "./components/QuickActions";
import ClientsPage from "./pages/ClientsPage";
import Dashboard from "./pages/Dashboard";
import DisclaimerPage from "./pages/DisclaimerPage";
import LoginPage from "./pages/LoginPage";
import LoansPage from "./pages/LoansPage";
import PlaceholderPage from "./pages/PlaceholderPage";

function initials(name) {
  return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

const IDLE_TIMEOUT_MS = 5 * 60 * 1000;

function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(() => Boolean(getAccessToken()));
  const [showAccount, setShowAccount] = useState(false);
  const [sessionNotice, setSessionNotice] = useState("");
  const [quickAction, setQuickAction] = useState(null);
  const [dataVersion, setDataVersion] = useState(0);
  const [actionNotice, setActionNotice] = useState("");

  const lockSession = useCallback((notice = "") => {
    clearAccessToken();
    setUser(null);
    setShowAccount(false);
    setQuickAction(null);
    setActivePage("dashboard");
    setSessionNotice(notice);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (getAccessToken()) await revokeSession();
    } catch {
      // Clearing the local token still locks the device if the server session already expired.
    } finally {
      lockSession();
    }
  }, [lockSession]);

  useEffect(() => {
    const unauthorized = () => lockSession("Tu sesión expiró. Ingresa nuevamente.");
    window.addEventListener("tucap:unauthorized", unauthorized);
    if (!getAccessToken()) {
      return () => window.removeEventListener("tucap:unauthorized", unauthorized);
    }
    getCurrentUser().then(setUser).catch(() => lockSession("Tu sesión expiró. Ingresa nuevamente.")).finally(() => setCheckingSession(false));
    return () => window.removeEventListener("tucap:unauthorized", unauthorized);
  }, [lockSession]);

  useEffect(() => {
    if (!user) return undefined;
    let timeoutId;

    const scheduleLock = () => {
      window.clearTimeout(timeoutId);
      const remaining = IDLE_TIMEOUT_MS - (Date.now() - getLastSessionActivity());
      if (remaining <= 0) {
        lockSession("Sesión cerrada después de 5 minutos sin actividad.");
        return;
      }
      timeoutId = window.setTimeout(
        () => lockSession("Sesión cerrada después de 5 minutos sin actividad."),
        remaining,
      );
    };

    const checkVisibility = () => {
      if (document.visibilityState === "visible") scheduleLock();
    };

    window.addEventListener("tucap:activity", scheduleLock);
    document.addEventListener("visibilitychange", checkVisibility);
    scheduleLock();
    return () => {
      window.clearTimeout(timeoutId);
      window.removeEventListener("tucap:activity", scheduleLock);
      document.removeEventListener("visibilitychange", checkVisibility);
    };
  }, [lockSession, user]);

  useEffect(() => {
    if (!actionNotice) return undefined;
    const timeoutId = window.setTimeout(() => setActionNotice(""), 3200);
    return () => window.clearTimeout(timeoutId);
  }, [actionNotice]);

  const completeQuickAction = (notice) => {
    setQuickAction(null);
    setDataVersion((current) => current + 1);
    setActionNotice(notice);
  };

  if (checkingSession) {
    return <main className="auth-shell"><div className="session-loader"><span className="brand-mark">T</span><p>Protegiendo tu cartera…</p></div></main>;
  }
  if (!user) {
    return (
      <LoginPage
        notice={sessionNotice}
        onLogin={(authenticatedUser) => {
          setSessionNotice("");
          setUser(authenticatedUser);
        }}
      />
    );
  }
  if (user.disclaimer_required) return <DisclaimerPage onAccepted={setUser} onLogout={logout} />;

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand-lockup">
          <span className="brand-mark">T</span>
          <div>
            <h1>TuCap</h1>
            <p>Tu capital, bajo control</p>
          </div>
        </div>
        <button className="avatar-button" type="button" aria-label="Cuenta de usuario" onClick={() => setShowAccount((value) => !value)}>{initials(user.full_name)}</button>
        {showAccount && (
          <section className="account-popover">
            <strong>{user.full_name}</strong>
            <span>{user.email}</span>
            <small>Tenant {user.tenant_number}</small>
            <button type="button" onClick={logout}>Cerrar sesión</button>
          </section>
        )}
      </header>

      <main>
        {activePage === "dashboard" && <Dashboard key={`dashboard-${dataVersion}`} />}
        {activePage === "borrowers" && <ClientsPage key={`borrowers-${dataVersion}`} />}
        {activePage === "loans" && <LoansPage key={`loans-${dataVersion}`} onNewLoan={() => setQuickAction("new-loan")} />}
        {activePage === "more" && <PlaceholderPage page={activePage} />}
      </main>

      {actionNotice && <div className="action-toast" role="status">✓ {actionNotice}</div>}
      <button
        aria-expanded={Boolean(quickAction)}
        aria-label={quickAction ? "Cerrar acciones rápidas" : "Abrir acciones rápidas"}
        className={quickAction ? "floating-action open" : "floating-action"}
        onClick={() => setQuickAction((current) => current ? null : "menu")}
        type="button"
      >+</button>
      <BottomNav active={activePage} onChange={setActivePage} />
      {quickAction && (
        <QuickActions
          initialAction={quickAction === "menu" ? null : quickAction}
          onClose={() => setQuickAction(null)}
          onCompleted={completeQuickAction}
        />
      )}
    </div>
  );
}

export default App;
