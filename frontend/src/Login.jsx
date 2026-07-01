import React, { useState } from "react";
import * as api from "./api.js";

export default function Login({ onLogin }) {
  const cfg = api.getConfig();
  const [token, setToken] = useState(cfg.token === "admin" ? "" : cfg.token);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    api.setConfig({ token });
    try {
      await api.getVersion(); // проверка пароля: 401 -> неверный токен
      onLogin();
    } catch (err) {
      setError(
        String(err.message).startsWith("401")
          ? "Неверный пароль"
          : "Сервер недоступен"
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>🛡️ lite-guardrails</h1>
        <p className="muted" style={{ margin: 0 }}>Админка. Введите пароль.</p>

        <label>Пароль</label>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="••••••"
          autoFocus
        />

        {error && <p className="err" style={{ marginBottom: 0 }}>{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
