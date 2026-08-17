import { useCallback, useEffect, useState } from "react";

import { clearAccessToken, getAccessToken, getCurrentUser } from "./api";
import BottomNav from "./components/BottomNav";
import ClientsPage from "./pages/ClientsPage";
import Dashboard from "./pages/Dashboard";
import DisclaimerPage from "./pages/DisclaimerPage";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";

function initials(name) {
  return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(() => Boolean(getAccessToken()));
  const [showAccount, setShowAccount] = useState(false);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setShowAccount(false);
    setActivePage("dashboard");
  }, []);

  useEffect(() => {
    const unauthorized = () => logout();
    window.addEventListener("tucap:unauthorized", unauthorized);
    if (!getAccessToken()) {
      return () => window.removeEventListener("tucap:unauthorized", unauthorized);
    }
    getCurrentUser().then(setUser).catch(() => logout()).finally(() => setCheckingSession(false));
    return () => window.removeEventListener("tucap:unauthorized", unauthorized);
  }, [logout]);

  if (checkingSession) {
    return <main className="auth-shell"><div className="session-loader"><span className="brand-mark">T</span><p>Protegiendo tu cartera…</p></div></main>;
  }
  if (!user) return <LoginPage onLogin={setUser} />;
  if (!user.disclaimer_accepted_at) return <DisclaimerPage onAccepted={setUser} onLogout={logout} />;

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
        {activePage === "dashboard" && <Dashboard />}
        {activePage === "borrowers" && <ClientsPage />}
        {activePage !== "dashboard" && activePage !== "borrowers" && (
          <PlaceholderPage page={activePage} />
        )}
      </main>

      <button className="floating-action" type="button" aria-label="Registrar pago">+</button>
      <BottomNav active={activePage} onChange={setActivePage} />
    </div>
  );
}

export default App;
