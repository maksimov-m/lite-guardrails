import React, { useEffect, useState } from "react";
import * as api from "./api.js";
import Login from "./Login.jsx";
import DashboardTab from "./DashboardTab.jsx";
import RulesTab from "./RulesTab.jsx";
import ApiKeysTab from "./ApiKeysTab.jsx";
import LogsTab from "./LogsTab.jsx";
import DemoTab from "./DemoTab.jsx";

const NAV = [
  { key: "dashboard", label: "Дашборд" },
  { key: "rules", label: "Правила" },
  { key: "keys", label: "Ключи" },
  { key: "logs", label: "Логи" },
  { key: "demo", label: "Демо" },
];

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [checking, setChecking] = useState(true); // восстанавливаем сессию из localStorage
  const [tab, setTab] = useState("dashboard");
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(localStorage.getItem("gr_theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gr_theme", theme);
  }, [theme]);

  // При загрузке страницы: если токен уже был сохранён — валидируем его и не
  // требуем повторный вход. Невалидный (напр. сменили на сервере) — чистим.
  useEffect(() => {
    if (!localStorage.getItem("gr_token")) { setChecking(false); return; }
    api.getVersion()
      .then(() => setAuthed(true))
      .catch(() => localStorage.removeItem("gr_token"))
      .finally(() => setChecking(false));
  }, []);

  const logout = () => {
    localStorage.removeItem("gr_token");
    setAuthed(false);
  };

  if (checking) return <div className="login-wrap"><div className="muted">Загрузка…</div></div>;
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">🛡️ guardrails</div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={"nav-btn" + (n.key === tab ? " active" : "")}
            onClick={() => { setTab(n.key); setError(""); }}
          >
            {n.label}
          </button>
        ))}

        <div className="spacer" />

        <button className="nav-btn" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          {theme === "light" ? "🌙 Тёмная тема" : "☀️ Светлая тема"}
        </button>
        <button className="nav-btn" onClick={logout}>⎋ Выйти</button>
      </aside>

      <main className="main">
        {tab === "dashboard" && <><h2>Дашборд</h2><p className="muted">Сводка по работе гуарда за выбранный период.</p></>}
        {tab === "rules" && <><h2>Настройка правил</h2><p className="muted">Добавляйте словари/категории и правила — изменения применяются сразу.</p></>}
        {tab === "keys" && <><h2>API-ключи</h2><p className="muted">Выдача и отзыв ключей клиентов для детекшн-ручек.</p></>}
        {tab === "logs" && <><h2>Логи прогонов</h2><p className="muted">Вход, выход и время обработки каждого запроса.</p></>}
        {tab === "demo" && <><h2>Демо</h2><p className="muted">Проверка детекторов и анонимизации.</p></>}

        {error && <div className="err" style={{ margin: "10px 0" }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {tab === "dashboard" && <DashboardTab onError={setError} />}
          {tab === "rules" && <RulesTab onError={setError} />}
          {tab === "keys" && <ApiKeysTab onError={setError} />}
          {tab === "logs" && <LogsTab onError={setError} />}
          {tab === "demo" && <DemoTab onError={setError} />}
        </div>
      </main>
    </div>
  );
}
