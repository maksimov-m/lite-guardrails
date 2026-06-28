// Тонкая обёртка над API. Базовый URL и admin-токен хранятся в localStorage
// и настраиваются в шапке UI.

export function getConfig() {
  return {
    base: localStorage.getItem("gr_base") || "http://localhost:8000",
    token: localStorage.getItem("gr_token") || "admin",
  };
}

export function setConfig(base, token) {
  localStorage.setItem("gr_base", base);
  localStorage.setItem("gr_token", token);
}

async function request(method, path, { body, admin } = {}) {
  const { base, token } = getConfig();
  const headers = { "Content-Type": "application/json" };
  if (admin) headers["X-Admin-Token"] = token;
  const res = await fetch(base + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText;
    throw new Error(`${res.status}: ${detail}`);
  }
  return data;
}

// --- детекция / демо ---
export const detect = (module, text, metadata) =>
  request("POST", `/detect/${module}`, {
    body: metadata ? { text, metadata } : { text },
  });
export const anonymize = (text) =>
  request("POST", "/anonymize", { body: { text } });
export const deanonymize = (id, text) =>
  request("POST", "/deanonymize", { body: { id, text } });

// --- админ: правила ---
export const listRules = (module, label) =>
  request(
    "GET",
    `/admin/rules?module=${module}` +
      (label != null ? `&label=${encodeURIComponent(label)}` : ""),
    { admin: true }
  );
export const createRule = (rule) =>
  request("POST", "/admin/rules", { body: rule, admin: true });
export const patchRule = (id, patch) =>
  request("PATCH", `/admin/rules/${id}`, { body: patch, admin: true });
export const deleteRule = (id) =>
  request("DELETE", `/admin/rules/${id}`, { admin: true });
export const getVersion = () => request("GET", "/admin/version", { admin: true });

// --- админ: словари NSFW ---
export const listDicts = () => request("GET", "/admin/dicts", { admin: true });
export const createDict = (name) =>
  request("POST", "/admin/dicts", { body: { name }, admin: true });
export const patchDict = (id, patch) =>
  request("PATCH", `/admin/dicts/${id}`, { body: patch, admin: true });
export const deleteDict = (id) =>
  request("DELETE", `/admin/dicts/${id}`, { admin: true });

// Скачивание словаря в .txt: тянем blob с admin-токеном и кликаем по ссылке.
export async function downloadDict(id, name) {
  const { base, token } = getConfig();
  const res = await fetch(`${base}/admin/dicts/${id}/export`, {
    headers: { "X-Admin-Token": token },
  });
  if (!res.ok) throw new Error(`${res.status}: не удалось скачать`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(name || "dict").replace(/[^\w.-]+/g, "_")}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- админ: логи ---
export const getLogs = (module, limit = 100, metaKey, metaValue) => {
  let path = `/admin/logs?limit=${limit}`;
  if (module) path += `&module=${module}`;
  if (metaKey) path += `&meta_key=${encodeURIComponent(metaKey)}`;
  if (metaValue) path += `&meta_value=${encodeURIComponent(metaValue)}`;
  return request("GET", path, { admin: true });
};
export const getMetaKeys = () =>
  request("GET", "/admin/logs/meta-keys", { admin: true });
