import React, { useEffect, useState } from "react";
import * as api from "./api.js";

// Слова берутся из словарей. Словарь целиком вкл/выкл (галочка), внутри —
// добавление/удаление слов. Встроенный словарь только переключается.
export default function NsfwDicts({ onError }) {
  const [dicts, setDicts] = useState([]);
  const [newName, setNewName] = useState("");

  const load = async () => {
    try { setDicts((await api.listDicts()).dicts); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { load(); }, []);

  const toggle = async (d) => {
    try { await api.patchDict(d.id, { enabled: !d.enabled }); load(); }
    catch (e) { onError(e.message); }
  };
  const removeDict = async (d) => {
    if (!confirm(`Удалить словарь «${d.name}» со всеми словами?`)) return;
    try { await api.deleteDict(d.id); load(); }
    catch (e) { onError(e.message); }
  };
  const addDict = async () => {
    if (!newName.trim()) return;
    try { await api.createDict(newName); setNewName(""); load(); onError(""); }
    catch (e) { onError(e.message); }
  };

  return (
    <div>
      <div className="card">
        <div className="row">
          <input placeholder="новый словарь (имя)" value={newName}
                 onChange={(e) => setNewName(e.target.value)} style={{ flex: 1 }}
                 onKeyDown={(e) => e.key === "Enter" && addDict()} />
          <button className="primary" onClick={addDict}>+ Словарь</button>
        </div>
      </div>

      {dicts.map((d) => (
        <DictBlock key={d.id} d={d} onToggle={toggle} onRemove={removeDict} onError={onError} />
      ))}
    </div>
  );
}

function DictBlock({ d, onToggle, onRemove, onError }) {
  const [open, setOpen] = useState(false);
  const [words, setWords] = useState([]);
  const [newWord, setNewWord] = useState("");

  const loadWords = async () => {
    try { setWords((await api.listRules("nsfw", d.name)).rules); }
    catch (e) { onError(e.message); }
  };
  useEffect(() => { if (open && !d.builtin) loadWords(); }, [open]);

  const addWord = async () => {
    if (!newWord.trim()) return;
    try { await api.createRule({ module: "nsfw", label: d.name, value: newWord }); setNewWord(""); loadWords(); }
    catch (e) { onError(e.message); }
  };
  const delWord = async (w) => {
    try { await api.deleteRule(w.id); loadWords(); }
    catch (e) { onError(e.message); }
  };
  const download = async () => {
    try { await api.downloadDict(d.id, d.name); }
    catch (e) { onError(e.message); }
  };

  return (
    <div className="card">
      <div className="rule-row">
        <input type="checkbox" checked={d.enabled} onChange={() => onToggle(d)} />
        <span className="rule-val">
          <b>{d.name}</b>{" "}
          <span className="muted">
            {d.builtin ? "· встроенный, ~4900 слов" : `· ${d.word_count} слов`}
          </span>
        </span>
        <button className="ghost" onClick={download}>Скачать</button>
        {!d.builtin && (
          <button className="ghost" onClick={() => setOpen(!open)}>{open ? "Свернуть" : "Открыть"}</button>
        )}
        {!d.builtin && <button className="danger" onClick={() => onRemove(d)}>✕</button>}
      </div>

      {open && !d.builtin && (
        <div style={{ marginTop: 10, paddingLeft: 26 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <input placeholder="новое слово" value={newWord}
                   onChange={(e) => setNewWord(e.target.value)} style={{ flex: 1 }}
                   onKeyDown={(e) => e.key === "Enter" && addWord()} />
            <button onClick={addWord}>+ Слово</button>
          </div>
          <div className="words">
            {words.map((w) => (
              <span className="word-chip" key={w.id}>
                {w.value}
                <button className="danger" onClick={() => delWord(w)}>✕</button>
              </span>
            ))}
            {words.length === 0 && <span className="muted">слов нет</span>}
          </div>
        </div>
      )}
    </div>
  );
}
