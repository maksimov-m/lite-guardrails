import React, { useState } from "react";
import GroupedRules from "./GroupedRules.jsx";
import NsfwDicts from "./NsfwDicts.jsx";

const MODULES = [
  { key: "pii", label: "PII" },
  { key: "nsfw", label: "NSFW" },
  { key: "relevant", label: "Relevant" },
];

export default function RulesTab({ onError }) {
  const [module, setModule] = useState("pii");

  return (
    <div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div className="segment">
          {MODULES.map((m) => (
            <button key={m.key} className={m.key === module ? "active" : ""}
                    onClick={() => { setModule(m.key); onError(""); }}>
              {m.label}
            </button>
          ))}
        </div>
        <span className="muted">изменения применяются сразу</span>
      </div>

      {module === "pii" && (
        <GroupedRules module="pii" valueLabel="regex" labelName="тег (EMAIL, PHONE…)" onError={onError} />
      )}
      {module === "nsfw" && <NsfwDicts onError={onError} />}
      {module === "relevant" && (
        <GroupedRules module="relevant" valueLabel="фраза" labelName="категория (greeting…)" onError={onError} />
      )}
    </div>
  );
}
