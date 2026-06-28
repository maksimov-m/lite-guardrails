import React, { useEffect, useState } from "react";
import * as api from "./api.js";
import Login from "./Login.jsx";
import RulesTab from "./RulesTab.jsx";
import LogsTab from "./LogsTab.jsx";
import DemoTab from "./DemoTab.jsx";

const NAV = [
  { key: "rules", label: "Правила" },
  { key: "logs", label: "Логи" },
  { key: "demo", label: "Демо" },
];

export default function App() {
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState("rules");
  const [error, setError] = useState("");
  const [theme, setTheme] = useState(localStorage.getItem("gr_theme") || "light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("gr_theme", theme);
  }, [theme]);

  const logout = () => {
    localStorage.removeItem("gr_token");
    setAuthed(false);
  };

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
        {tab === "rules" && <><h2>Настройка правил</h2><p className="muted">Добавляйте, включайте и выключайте правила детекции, затем «Применить».</p></>}
        {tab === "logs" && <><h2>Логи прогонов</h2><p className="muted">Вход, выход и время обработки каждого запроса.</p></>}
        {tab === "demo" && <><h2>Демо</h2><p className="muted">Проверка детекторов и анонимизации.</p></>}

        {error && <div className="err" style={{ margin: "10px 0" }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {tab === "rules" && <RulesTab onError={setError} />}
          {tab === "logs" && <LogsTab onError={setError} />}
          {tab === "demo" && <DemoTab onError={setError} />}
        </div>
      </main>
    </div>
  );
}
