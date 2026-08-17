import { useState } from "react";

import BottomNav from "./components/BottomNav";
import ClientsPage from "./pages/ClientsPage";
import Dashboard from "./pages/Dashboard";
import PlaceholderPage from "./pages/PlaceholderPage";

function App() {
  const [activePage, setActivePage] = useState("dashboard");

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
        <button className="avatar-button" type="button" aria-label="Cuenta de usuario">AF</button>
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
