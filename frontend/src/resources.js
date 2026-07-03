// Адаптеры для DictionaryManager: описывают, как работать с конкретным ресурсом.
// Инкапсулируют разницу между NSFW (слова через пробел, есть экспорт, текст
// грузится отдельным запросом) и Relevant (фразы по строкам, текст уже в списке).

import * as api from "./api.js";

const nonEmptyLines = (text) =>
  text.split(/\r?\n/).filter((s) => s.trim()).length;

export const nsfwResource = {
  id: "nsfw",
  addPlaceholder: "новый словарь — имя",
  textPlaceholder: "слова: через пробел или с новой строки",
  countNoun: "слов",
  emptyText: "словарей нет",
  fetch: async () => {
    const { dicts } = await api.listDicts();
    return dicts.map((d) => ({
      id: d.id, title: d.name, enabled: d.enabled, count: d.word_count,
    }));
  },
  create: (name) => api.createDict(name),
  loadText: async (item) => (await api.getDict(item.id)).text,
  saveText: (id, text) => api.patchDict(id, { text }),
  toggle: (item) => api.patchDict(item.id, { enabled: !item.enabled }),
  remove: (id) => api.deleteDict(id),
  onExport: (item) => api.downloadDict(item.id, item.title),
};

export const relevantResource = {
  id: "relevant",
  addPlaceholder: "новая категория — тип (greeting…)",
  textPlaceholder: "по одной фразе на строку",
  countNoun: "фраз",
  emptyText: "категорий нет",
  fetch: async () => {
    const { categories } = await api.listCats();
    return categories.map((c) => ({
      id: c.id, title: c.type, enabled: c.enabled, count: nonEmptyLines(c.text), text: c.text,
    }));
  },
  create: (type) => api.createCat(type),
  loadText: async (item) => item.text,
  saveText: (id, text) => api.patchCat(id, { text }),
  toggle: (item) => api.patchCat(item.id, { enabled: !item.enabled }),
  remove: (id) => api.deleteCat(id),
};
