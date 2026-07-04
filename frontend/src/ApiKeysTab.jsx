import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// Выдача клиентских API-ключей. Полный ключ виден ТОЛЬКО один раз при создании
// (сервер хранит лишь sha256-хэш) — показываем его в баннере с кнопкой «Копировать».
// Инлайн-редактор лимита: пусто = глобальный дефолт (не переопределяем), число —
// свой лимит (0 = без ограничения). Пустое значение не сохраняем, чтобы не путать.
function LimitInput({ value, onSave }) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => { setV(value ?? ""); }, [value]);
  const save = () => {
    if (v === "") { setV(value ?? ""); return; }
    const n = Math.max(0, parseInt(v, 10) || 0);
    if (n !== value) onSave(n);
  };
  return (
    <input type="number" min="0" className="mono" style={{ width: 64 }}
           placeholder="дефолт" value={v}
           onChange={(e) => setV(e.target.value)} onBlur={save}
           onKeyDown={(e) => e.key === "Enter" && e.target.blur()} />
  );
}

export default function ApiKeysTab({ onError }) {
  const [keys, setKeys] = useState([]);
  const [name, setName] = useState("");
  const [limit, setLimit] = useState("");
  const [fresh, setFresh] = useState(null); // {name, key} — только что созданный

  const load = async () => {
    try { setKeys((await api.listKeys()).keys); onError(""); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!name.trim()) return;
    try {
      const rl = limit === "" ? null : Math.max(0, parseInt(limit, 10) || 0);
      const k = await api.createKey(name.trim(), rl);
      setFresh({ name: k.name, key: k.key });
      setName("");
      setLimit("");
      load();
    } catch (e) { onError(e.message); }
  };
  const toggle = async (k) => {
    try { await api.patchKey(k.id, { enabled: !k.enabled }); load(); }
    catch (e) { onError(e.message); }
  };
  const setLimitFor = async (k, rl) => {
    try { await api.patchKey(k.id, { rate_limit_per_min: rl }); load(); }
    catch (e) { onError(e.message); }
  };
  const remove = async (k) => {
    if (!confirm(`Отозвать ключ «${k.name}»? Клиенты с ним получат 401.`)) return;
    try { await api.deleteKey(k.id); load(); }
    catch (e) { onError(e.message); }
  };
  const copy = (text) => navigator.clipboard?.writeText(text);

  return (
    <div>
      <div className="card" style={{ borderLeft: "3px solid var(--accent)" }}>
        <b>Лимит частоты на ключ</b> — сколько запросов <b>в минуту</b> разрешено одному
        ключу. Пусто — общий дефолт сервера · <b>0 — без ограничения</b> · сверх лимита
        сервис отвечает <code className="mono">429 Too Many Requests</code>.
      </div>

      <div className="card">
        <div className="row">
          <input placeholder="имя ключа (напр. support-bot)" value={name}
                 onChange={(e) => setName(e.target.value)} style={{ flex: 1 }}
                 onKeyDown={(e) => e.key === "Enter" && create()} />
          <input type="number" min="0" placeholder="макс/мин" value={limit}
                 onChange={(e) => setLimit(e.target.value)} style={{ width: 96 }}
                 title="максимум запросов в минуту; пусто — глобальный дефолт, 0 — без лимита"
                 onKeyDown={(e) => e.key === "Enter" && create()} />
          <button className="primary" onClick={create}>+ Выдать ключ</button>
        </div>
      </div>

      {fresh && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <div className="muted">
            Ключ «{fresh.name}» создан. Скопируйте его сейчас — позже он не показывается.
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <code className="mono rule-val" style={{ wordBreak: "break-all" }}>{fresh.key}</code>
            <button onClick={() => copy(fresh.key)}>Копировать</button>
            <button className="ghost" onClick={() => setFresh(null)}>Скрыть</button>
          </div>
        </div>
      )}

      {keys.map((k) => (
        <div className="card" key={k.id}>
          <div className="rule-row">
            <input type="checkbox" checked={k.enabled} onChange={() => toggle(k)} title="вкл/выкл" />
            <span className="rule-val">
              <b>{k.name}</b>{" "}
              <span className="muted mono">· {k.prefix}… · {new Date(k.created_at).toLocaleDateString()}</span>
              {!k.enabled && <span className="muted"> · отключён</span>}
            </span>
            <span className="muted" style={{ whiteSpace: "nowrap" }}
                  title="максимум запросов в минуту (0 — без лимита)">макс. запр./мин</span>
            <LimitInput value={k.rate_limit_per_min}
                        onSave={(rl) => setLimitFor(k, rl)} />
            <button className="danger" title="отозвать" onClick={() => remove(k)}>✕</button>
          </div>
        </div>
      ))}
      {keys.length === 0 && (
        <p className="muted">Ключей пока нет. Введите имя выше и выдайте первый ключ.</p>
      )}
    </div>
  );
}
