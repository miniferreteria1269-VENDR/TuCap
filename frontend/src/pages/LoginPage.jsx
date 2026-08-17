import { useState } from "react";

import { login, setAccessToken } from "../api";

function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const session = await login(email, password);
      setAccessToken(session.access_token);
      onLogin(session.user);
    } catch (loginError) {
      setError(loginError.message);
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark auth-logo">T</span>
          <div><h1>TuCap</h1><p>Tu capital, bajo control</p></div>
        </div>
        <div className="auth-copy">
          <p className="eyebrow">Acceso seguro</p>
          <h2>Bienvenido</h2>
          <p>Ingresa para consultar y administrar únicamente tu cartera.</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <label className="field full-width">
            <span>Correo electrónico</span>
            <input autoComplete="username" autoFocus inputMode="email" onChange={(event) => setEmail(event.target.value)} placeholder="tu@correo.com" required type="email" value={email} />
          </label>
          <label className="field full-width">
            <span>Contraseña</span>
            <input autoComplete="current-password" minLength="12" onChange={(event) => setPassword(event.target.value)} placeholder="••••••••••••" required type="password" value={password} />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button auth-submit" disabled={submitting} type="submit">{submitting ? "Ingresando…" : "Ingresar"}</button>
        </form>
        <p className="auth-security-note">La sesión expira automáticamente y el acceso está separado por cuenta.</p>
      </section>
    </main>
  );
}

export default LoginPage;
