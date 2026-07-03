import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// Настройки модуля relevant, не привязанные к отдельным категориям.
// Пока один флаг — этап детекции «мусора» (gibberish: текст без букв и цифр).
// Категории (в т.ч. prompt-injection) включаются/выключаются ниже, в списке.
export default function RelevantSettings({ onError }) {
  const [gibberish, setGibberish] = useState(null); // null = ещё грузим
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const s = await api.getRelevantSettings();
      setGibberish(s.gibberish_enabled);
      onError("");
    } catch (e) {
      onError(e.message);
    }
  };
  useEffect(() => { load(); }, []);

  const toggleGibberish = async () => {
    const next = !gibberish;
    setBusy(true);
    setGibberish(next); // оптимистично
    try {
      const s = await api.patchRelevantSettings({ gibberish_enabled: next });
      setGibberish(s.gibberish_enabled);
      onError("");
    } catch (e) {
      setGibberish(!next); // откат
      onError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="rule-row">
        <input
          type="checkbox"
          checked={!!gibberish}
          disabled={gibberish === null || busy}
          onChange={toggleGibberish}
        />
        <span className="rule-val">
          <b>Детекция мусора (gibberish)</b>{" "}
          <span className="muted">
            · блокирует ввод без букв и цифр (напр. «!!! ???»)
          </span>
        </span>
      </div>
      <p className="muted" style={{ margin: "8px 0 0" }}>
        Категории смолтока и prompt-injection включаются по отдельности в списке ниже.
      </p>
    </div>
  );
}
