import React, { useEffect, useState } from "react";

// Переиспользуемый менеджер «коллекция записей с текстовым содержимым».
// NSFW-словари и Relevant-категории устроены одинаково (ключ + text-блок),
// различия инкапсулированы в `resource` (см. resources.js): как грузить/сохранять
// текст, как считать элементы, есть ли экспорт и какие подписи показывать.
export default function DictionaryManager({ resource, onError }) {
  const [items, setItems] = useState([]);
  const [newKey, setNewKey] = useState("");

  const load = async () => {
    try { setItems(await resource.fetch()); onError(""); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(); }, [resource.id]);

  const add = async () => {
    const key = newKey.trim();
    if (!key) return;
    try { await resource.create(key); setNewKey(""); load(); }
    catch (e) { onError(e.message); }
  };
  const toggle = async (item) => {
    try { await resource.toggle(item); load(); }
    catch (e) { onError(e.message); }
  };
  const remove = async (item) => {
    if (!confirm(`Удалить «${item.title}»?`)) return;
    try { await resource.remove(item.id); load(); }
    catch (e) { onError(e.message); }
  };

  return (
    <div>
      <div className="card">
        <div className="row">
          <input placeholder={resource.addPlaceholder} value={newKey}
                 onChange={(e) => setNewKey(e.target.value)} style={{ flex: 1 }}
                 onKeyDown={(e) => e.key === "Enter" && add()} />
          <button className="primary" onClick={add}>+ Добавить</button>
        </div>
      </div>

      {items.map((item) => (
        <ItemBlock key={item.id} item={item} resource={resource}
                   onToggle={toggle} onRemove={remove} onSaved={load} onError={onError} />
      ))}
      {items.length === 0 && <p className="muted">{resource.emptyText}</p>}
    </div>
  );
}

function ItemBlock({ item, resource, onToggle, onRemove, onSaved, onError }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);

  const openEditor = async () => {
    if (open) { setOpen(false); return; }
    try {
      setText(await resource.loadText(item));
      setDirty(false);
      setOpen(true);
    } catch (e) { onError(e.message); }
  };

  const save = async () => {
    setBusy(true);
    try {
      await resource.saveText(item.id, text);
      setDirty(false);
      onSaved();
      onError("");
    } catch (e) { onError(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="card">
      <div className="rule-row">
        <input type="checkbox" checked={item.enabled} onChange={() => onToggle(item)} />
        <span className="rule-val">
          <b>{item.title}</b>{" "}
          <span className="muted">· {item.count} {resource.countNoun}</span>
        </span>
        {resource.onExport && (
          <button className="ghost" onClick={() => resource.onExport(item).catch((e) => onError(e.message))}>
            Скачать
          </button>
        )}
        <button className="ghost" onClick={openEditor}>{open ? "Свернуть" : "Открыть"}</button>
        <button className="danger" title="удалить" onClick={() => onRemove(item)}>✕</button>
      </div>

      {open && (
        <div style={{ marginTop: 10 }}>
          <textarea rows={8} className="mono" value={text}
                    onChange={(e) => { setText(e.target.value); setDirty(true); }}
                    placeholder={resource.textPlaceholder} style={{ width: "100%" }} />
          <div className="row" style={{ marginTop: 8 }}>
            <span className="muted">{resource.textPlaceholder}</span>
            <div className="spacer" style={{ flex: 1 }} />
            <button className="primary" onClick={save} disabled={busy || !dirty}>
              {busy ? "Сохранение…" : dirty ? "Сохранить" : "Сохранено"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
