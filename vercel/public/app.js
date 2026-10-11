"use strict";
/* PolisDiff AI web UI. All analysis happens in the API (same engine as the Streamlit app).
   Reviewed interface copy comes from /api/i18n/<lang> (Russian source string -> translation).
   Strings in NEW below exist only in this web UI and are unreviewed drafts. */
const NEW = {
  samplesTitle: ["Или попробуйте образец.", "Or try a sample.", "Yoki namunani sinab ko‘ring.", "Ёки намунани синаб кўринг."],
  samplesNote: ["Синтетические тестовые оферты команды.", "Synthetic test offers made by the team.", "Jamoaning sintetik test takliflari.", "Жамоанинг синтетик тест таклифлари."],
  dropLabel: ["Выберите PDF или перетащите его сюда", "Choose a PDF or drop it here", "PDF tanlang yoki shu yerga tashlang", "PDF танланг ёки шу ерга ташланг"],
  hint: ["Текстовый PDF · до {mb} МиБ в этом развертывании · до 80 страниц. Русский, узбекская латиница и кириллица. Сканы без текстового слоя не поддерживаются: OCR отсутствует.",
         "Text PDF · up to {mb} MiB on this deployment · up to 80 pages. Russian, Uzbek Latin and Cyrillic. Scans without a text layer are not supported: no OCR.",
         "Matnli PDF · bu serverda {mb} MiB gacha · 80 sahifagacha. Rus, o‘zbek lotin va kirill. Matn qatlamisiz skanlar qo‘llab-quvvatlanmaydi: OCR yo‘q.",
         "Матнли PDF · бу серверда {mb} МиБ гача · 80 саҳифагача. Рус, ўзбек лотин ва кирилл. Матн қатламисиз сканлар қўллаб-қувватланмайди: OCR йўқ."],
  tooBig: ["Файл превышает лимит этого развертывания: {mb} МиБ.", "The file exceeds this deployment's limit of {mb} MiB.", "Fayl bu server limitidan oshdi: {mb} MiB.", "Файл бу сервер лимитидан ошди: {mb} МиБ."],
  notPdf: ["Выберите файл PDF.", "Please choose a PDF file.", "PDF faylni tanlang.", "PDF файлни танланг."],
  demoTrust: ["Демо-развертывание: PDF обрабатывается в памяти серверной функции и не сохраняется; внешние AI API не вызываются. В периметре банка система работает полностью локально.",
              "Demo deployment: the PDF is processed in the memory of a server function and is not stored; no external AI API is called. Inside a bank perimeter the system runs fully locally.",
              "Demo server: PDF server funksiyasi xotirasida qayta ishlanadi va saqlanmaydi; tashqi AI API chaqirilmaydi. Bank perimetrida tizim to‘liq lokal ishlaydi.",
              "Демо сервер: PDF сервер функцияси хотирасида қайта ишланади ва сақланмайди; ташқи AI API чақирилмайди. Банк периметрида тизим тўлиқ локал ишлайди."],
  demoChip: ["Демо", "Demo", "Demo", "Демо"],
  aiBackendNote: ["AI-поиск выполнен на отдельном сервере модели.", "AI search ran on the separate model server.", "AI qidiruvi alohida model serverida bajarildi.", "AI қидируви алоҳида модел серверида бажарилди."],
  keepPdf: ["Для просмотра страниц держите этот файл выбранным.", "Keep this file selected to preview pages.", "Sahifalarni ko‘rish uchun faylni tanlangan holda qoldiring.", "Саҳифаларни кўриш учун файлни танланган ҳолда қолдиринг."],
  language: ["Язык", "Language", "Til", "Тил"],
  skip: ["К содержимому", "Skip to content", "Mazmunga o‘tish", "Мазмунга ўтиш"],
};
const LANGS = ["ru", "en", "uz-Latn", "uz-Cyrl"];
const $ = (id) => document.getElementById(id);
const state = { lang: "ru", dict: {}, config: null, file: null, result: null, report: null, samples: [], tab: "results", busy: false };

function idx() { return LANGS.indexOf(state.lang); }
function fmt(s, vars) { return s.replace(/\{(\w+)\}/g, (_, k) => (vars && k in vars ? vars[k] : `{${k}}`)); }
function T(ru, vars) { const s = state.dict[ru] ?? ru; return fmt(s, vars); }
function N(key, vars) { return fmt(NEW[key][idx()], vars); }
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v; else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
async function api(path, opts) {
  const res = await fetch("/api" + path, opts);
  if (!res.ok) { let code = ""; try { code = (await res.json()).detail; } catch { /* ignore */ } const e = new Error(code || res.statusText); e.status = res.status; e.code = code; throw e; }
  return res;
}
function download(name, type, content) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = h("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/* ---------- static labels ---------- */
function applyLabels() {
  document.documentElement.lang = state.lang === "uz-Latn" ? "uz-Latn" : state.lang === "uz-Cyrl" ? "uz-Cyrl" : state.lang;
  $("lang-label").textContent = N("language");
  document.querySelector(".skip").textContent = N("skip");
  $("chip-demo").textContent = N("demoChip");
  $("eyebrow").textContent = T("POLISDIFF AI / ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА");
  $("title").textContent = T("Условия полиса, с доказательствами");
  $("lead").textContent = T("Найдите три ключевых условия ОСАГО, сравните их с критериями для выбранной даты и проверьте цитаты в оригинале.");
  $("scope").textContent = T("Доступны только выбранные три проверки ОСАГО. Результаты требуют правовой проверки.");
  $("step1").textContent = T("1. Документ и даты");
  $("drop-label").textContent = N("dropLabel");
  $("drop-file").textContent = state.file ? state.file.name : "";
  $("drop").setAttribute("aria-label", T("Загрузить PDF ОСАГО"));
  $("drop-hint").textContent = N("hint", { mb: Math.round((state.config?.max_upload_bytes || 4194304) / 1048576) });
  $("samples-title").textContent = N("samplesTitle");
  $("samples-note").textContent = N("samplesNote");
  $("date-title").textContent = T("Когда применялся договор?");
  $("date-help").textContent = T("Дата применимости — дата, для которой проверяются условия договора и редакция нормы. Установите ее по договору или оферте; дата загрузки и дата, найденная на странице, ее не заменяют.");
  $("date-confirm-label").textContent = T("Я подтверждаю дату применимости договора");
  $("applicable-label").textContent = T("Дата применимости договора");
  $("audit-label").textContent = T("Дата аудита");
  $("audit-help").textContent = T("Дата аудита — когда выполняется проверка. Она не определяет, какая редакция нормы применима к договору.");
  $("adv-title").textContent = T("Дополнительные настройки поиска");
  $("mode-legend").textContent = T("Поиск доказательств");
  $("mode-help").textContent = T("По умолчанию — локальная модель вместе с поиском по словам. Малый тестовый набор не устанавливает преимущество AI в точности. При отсутствии модели используется явно обозначенный поиск по словам.");
  $("analyze").textContent = T("Анализировать документ");
  $("clear").textContent = T("Очистить сессию");
  $("foot-trust").textContent = N("demoTrust");
  $("foot-legal").textContent = T("Не юридическое заключение. Интерпретации ожидают проверки юристом: PENDING_LEGAL_REVIEW.");
  if (state.config) $("foot-version").textContent = `v${state.config.version} · catalogue ${state.config.catalogue_version} · ${state.config.catalogue_sha256.slice(0, 8)}`;
  renderModes(); renderSamples(); updateReadiness();
}
function renderModes() {
  const labels = { hybrid: T("AI + лексический поиск"), semantic: T("AI поиск"), lexical: T("Лексический поиск") };
  const current = document.querySelector("input[name=mode]:checked")?.value || "hybrid";
  const box = $("modes"); box.replaceChildren();
  for (const m of state.config?.modes || ["hybrid", "semantic", "lexical"])
    box.append(h("label", {}, h("input", { type: "radio", name: "mode", value: m, checked: m === current }), labels[m]));
}
function renderSamples() {
  const box = $("sample-list"); box.replaceChildren();
  for (const s of state.samples)
    box.append(h("button", { class: "chipbtn", type: "button", onclick: () => useSample(s), title: s.applicable_date }, `${s.language} · ${s.case.replace(/_/g, " ")}`));
}

/* ---------- inputs ---------- */
function mode() { return document.querySelector("input[name=mode]:checked")?.value || "hybrid"; }
function setFile(file) {
  hideError();
  if (!file) { state.file = null; }
  else if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") { showError(N("notPdf")); return; }
  else if (file.size > (state.config?.max_upload_bytes || 4194304)) { showError(N("tooBig", { mb: Math.round(state.config.max_upload_bytes / 1048576) })); return; }
  else state.file = file;
  $("drop-file").textContent = state.file ? state.file.name : "";
  $("analyze").disabled = !state.file || state.busy;
  invalidate();
}
async function useSample(s) {
  const res = await fetch(s.file); const blob = await res.blob();
  setFile(new File([blob], s.file.split("/").pop(), { type: "application/pdf" }));
  $("date-confirm").checked = true; $("applicable").disabled = false; $("applicable").value = s.applicable_date;
  updateReadiness(); analyze();
}
function updateReadiness() {
  const box = $("readiness"), confirmed = $("date-confirm").checked, value = $("applicable").value, audit = $("audit").value;
  const range = state.config?.supported_date_range;
  let msg = "";
  if (!confirmed || !value) msg = T("Дата не подтверждена: доступен только поиск положений. Числовое сравнение с нормами не выполнено. Установите дату по договору или оферте, подтвердите ее и повторите анализ.");
  else if ((audit && value > audit) || (range && (value < range[0] || value > range[1])))
    msg = T("Дата вне подтвержденного диапазона каталога или позже даты аудита. Система воздержится от сравнения; проверьте даты и редакцию нормы.");
  box.hidden = !msg; box.textContent = msg;
}
function invalidate() { if (state.result) { state.result = null; state.report = null; $("results").hidden = true; } }
function hideError() { $("error").hidden = true; }
function showError(msg) { const e = $("error"); e.textContent = msg; e.hidden = false; }

async function analyze(keepReviews) {
  if (!state.file || state.busy) return;
  hideError(); state.busy = true; $("analyze").disabled = true;
  $("busy").hidden = false; $("busy").textContent = T("Подготовка локального поиска…");
  const form = new FormData();
  form.append("file", state.file);
  form.append("applicable_date", $("date-confirm").checked ? $("applicable").value : "");
  form.append("audit_date", $("audit").value);
  form.append("mode", mode()); form.append("language", state.lang);
  try {
    const res = await api("/analyze", { method: "POST", body: form });
    const previous = keepReviews === true && state.report ? state.report.reviews : [];
    state.result = await res.json(); state.report = state.result.report; state.report.reviews = previous; if (!keepReviews) { state.page = null; state.tab = "results"; }
    renderResults();
    $("results").hidden = false; $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    if (e.status === 429) showError(T("Сервер сейчас выполняет другой анализ. Повторите запрос после его завершения."));
    else if (e.status === 422) showError(T("PDF не удалось прочитать безопасно: проверьте формат, шифрование, размер и число страниц. Это проблема обработки файла, а не вывод об условиях договора."));
    else if (e.status === 413) showError(N("tooBig", { mb: Math.round(state.config.max_upload_bytes / 1048576) }));
    else showError(T("Обработка не завершена; отчет не создан. Попробуйте поиск по словам или другой текстовый PDF. Это не означает нарушение в договоре."));
  } finally { state.busy = false; $("busy").hidden = true; $("analyze").disabled = !state.file; }
}

/* ---------- results ---------- */
function renderResults() {
  const v = state.result.view, r = state.report;
  $("summary-text").textContent = v.summary;
  $("summary-meta").textContent = T("Документ: {name} · страниц: {pages} · {languages}", { name: state.file?.name || "", pages: r.page_count, languages: r.detected_languages.join(", ") }) + " · " +
    T("Дата договора: {applicable} · дата аудита: {audit} · проверок: {checks}", { applicable: r.applicable_date || T("не подтверждена"), audit: r.audit_date, checks: r.findings.length });
  const labels = [T("Проверено условий"), T("Согласуются с критерием"), T("Возможные несоответствия"), T("Не найдены"), T("Недостаточно данных")];
  const c = v.counts, values = [r.findings.length, c.MATCH_FOUND, c.POTENTIAL_CONFLICT, c.NOT_FOUND, c.UNVERIFIABLE];
  $("metrics").replaceChildren(...labels.map((l, i) => h("div", { class: "metric" }, h("b", {}, String(values[i])), h("span", {}, l))));
  const warn = $("result-warnings"); warn.replaceChildren();
  if (v.unreadable_pages.length) warn.append(h("div", { class: "notice warn" }, T("Проблема обработки: текст не читается надежно на страницах {pages}. Это ограничение PDF, а не страхового условия.", { pages: v.unreadable_pages.join(", ") })));
  if (v.detected_dates.length) warn.append(h("div", { class: "notice info" }, T("Найденные на первой странице даты — только подсказки: {dates}", { dates: v.detected_dates.join(", ") })));
  if (v.ai_fallback) warn.append(h("div", { class: "notice warn" }, T("AI-модель недоступна. Анализ выполнен поиском по словам, без AI. Фактический режим указан в отчете.")));
  warn.append(h("p", { class: "muted small" }, T("Фактический поиск: {mode}", { mode: v.retrieval_label }) + (v.mode_note === "ai_backend" ? " · " + N("aiBackendNote") : "")));
  renderTabs(); renderTab();
}
const TABS = [["results", "Результаты"], ["pages", "Доказательства документа"], ["review", "Решение аналитика"], ["sources", "Источники и ограничения"]];
function renderTabs() {
  const box = $("tabs"); box.replaceChildren();
  TABS.forEach(([id, ru], i) => box.append(h("button", { role: "tab", id: "t-" + id, "aria-selected": String(state.tab === id), "aria-controls": "tab-" + id, tabindex: state.tab === id ? "0" : "-1",
    onclick: () => { state.tab = id; renderTabs(); renderTab(); },
    onkeydown: (e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const n = (i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length; state.tab = TABS[n][0]; renderTabs(); renderTab(); $("t-" + state.tab).focus(); } } }, T(ru))));
}
function renderTab() {
  for (const [id] of TABS) $("tab-" + id).hidden = id !== state.tab;
  ({ results: renderFindings, pages: renderPages, review: renderReview, sources: renderSources })[state.tab]();
}
function kv(title, ...body) { return h("div", { class: "kv" }, h("h4", {}, title), ...body.map((b) => (typeof b === "string" ? h("p", {}, b) : b))); }
function renderFindings() {
  const box = $("tab-results"); box.replaceChildren();
  for (const f of state.result.view.findings) {
    const d = f.details, first = f.evidence[0];
    const evidenceCol = h("div", {}, h("h3", {}, T("Доказательства из документа")));
    if (!f.evidence.length) evidenceCol.append(h("p", {}, T("Подходящее доказательство не найдено. Цитата и страница отсутствуют.")));
    f.evidence.forEach((ev, i) => {
      evidenceCol.append(h("p", { class: "muted small" }, T("Страница PDF {page}", { page: ev.page }) + " · " + ev.section_label),
        h("blockquote", { html: ev.quote_html }));
      if (ev.image) evidenceCol.append(h("img", { class: "pageimg", alt: T("Страница PDF {page}", { page: ev.page }), src: "data:image/png;base64," + ev.image }));
      else if (state.file) evidenceCol.append(h("button", { class: "btn small", type: "button", onclick: () => { state.tab = "pages"; state.page = ev.page; renderTabs(); renderTab(); } }, T("Открыть в PDF · стр. {page}", { page: ev.page })));
    });
    const refCol = h("div", {},
      h("h3", {}, T("Официальный текст и редакция")),
      kv(T("Что проверяли"), d.checked), h("p", {}, d.found),
      kv(T("Официальный текст и редакция"), d.reference,
        d.source_quote ? h("code", { class: "src" }, d.source_quote) : h("p", { class: "muted" }, T("Цитата применимой версии не выбрана. Не используйте текущий текст как основание для неизвестной даты.")),
        h("p", { class: "muted small" }, `${d.provision_reference} · ${d.period}`),
        h("a", { href: d.source_url, rel: "noreferrer", target: "_blank" }, T("Официальный источник · LexUZ")),
        h("p", { class: "muted small" }, d.date_note)),
      kv(T("Почему получен результат"), d.reason),
      kv(T("Проверка перед исправлением"), h("p", { class: "muted small" }, d.remediation_kind), h("ul", { class: "tight" }, d.verification.map((c) => h("li", {}, c)))),
      kv(T("Условное действие"), d.remediation),
      h("p", { class: "muted small" }, T("Юридическая проверка необходима · PENDING_LEGAL_REVIEW")));
    const tech = h("details", { class: "sub" }, h("summary", {}, T("Технические детали · ") + f.rule_id), h("pre", { class: "src" }, JSON.stringify(state.report.findings.find((x) => x.rule_id === f.rule_id), null, 2)));
    box.append(h("article", { class: `card finding ${f.status}` },
      h("div", { class: "f-head" },
        h("div", {}, h("h3", {}, f.name), h("p", { class: "muted small" }, f.pending_date ? T("Ожидает подтверждения даты") : d.found)),
        h("span", { class: `badge ${f.status}` }, `${f.icon} ${f.status_label}`)),
      h("div", { class: "f-body" }, evidenceCol, refCol), h("div", { class: "f-body" }, tech)));
    void first;
  }
  box.append(h("div", { class: "row" },
    h("button", { class: "btn", type: "button", onclick: () => download("polisdiff-report.json", "application/json", JSON.stringify(state.report, null, 2)) }, T("Скачать JSON отчет")),
    h("button", { class: "btn", type: "button", onclick: exportHtml }, T("Скачать HTML отчет"))),
    h("p", { class: "muted small" }, T("HTML — читаемый отчет с цитатами и аннотациями. Для PDF откройте HTML и выберите «Печать → Сохранить как PDF». JSON сохраняет исходные статусы и метаданные.")));
}
async function exportHtml() {
  const res = await api("/export/html", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ report: state.report, language: state.lang }) });
  download("polisdiff-report.html", "text/html", await res.text());
}
async function renderPages() {
  const box = $("tab-pages"); box.replaceChildren();
  if (!state.file) { box.append(h("p", { class: "muted" }, N("keepPdf"))); return; }
  const n = state.report.page_count;
  const input = h("input", { type: "number", min: "1", max: String(n), value: String(state.page || 1), "aria-label": T("Страница документа") });
  const out = h("div", {});
  const show = async () => {
    const number = Math.min(n, Math.max(1, parseInt(input.value || "1", 10)));
    const form = new FormData(); form.append("file", state.file); form.append("number", String(number));
    out.replaceChildren(h("p", { class: "busy" }, "…"));
    try {
      const j = await (await api("/page", { method: "POST", body: form })).json();
      const meta = state.result.view.pages[number - 1];
      out.replaceChildren(h("p", { class: "muted small" }, T("Страница PDF {page} · {section} · {readability}", { page: number, section: meta.section_label, readability: T(meta.readable ? "текст читается" : "текст поврежден или отсутствует") })),
        h("img", { class: "pageimg", alt: T("Страница PDF {page}", { page: number }), src: "data:image/png;base64," + j.image }));
    } catch { out.replaceChildren(h("p", { class: "notice err" }, T("Изображение страницы недоступно. Проверьте оригинальный PDF."))); }
  };
  box.append(h("h2", {}, T("Исходный документ")), h("div", { class: "row" }, input, h("button", { class: "btn", type: "button", onclick: show }, T("Показать изображение страницы"))), out);
  if (state.page) show();
}
function renderReview() {
  const box = $("tab-review"); box.replaceChildren();
  const f = state.result.view.findings;
  const sel = h("select", { id: "rv-rule" }, f.map((x) => h("option", { value: x.rule_id }, x.name)));
  const act = h("select", { id: "rv-action" }, ["further_review", "confirm", "dismiss"].map((a) => h("option", { value: a }, state.result.view.review_labels[a])));
  const why = h("textarea", { id: "rv-why", maxlength: "2000", "aria-label": T("Обоснование") });
  const err = h("div", { class: "notice err", hidden: true, role: "alert" });
  const list = h("div", {});
  const names = Object.fromEntries(f.map((x) => [x.rule_id, x.name]));
  const paint = () => list.replaceChildren(...state.report.reviews.map((r) => h("div", { class: "review-item" },
    h("p", { class: "small" }, `${names[r.rule_id]} · ${state.result.view.review_labels[r.action]} · ${r.timestamp}`), h("p", {}, r.rationale))));
  box.append(h("h2", {}, T("Аннотация аналитика")),
    h("p", { class: "muted" }, T("Запись не меняет результат алгоритма и не является юридической сертификацией. Она хранится в этой сессии; экспортируйте ее перед очисткой.")),
    h("label", { class: "field" }, T("Проверка"), sel), h("label", { class: "field" }, T("Действие"), act), h("label", { class: "field" }, T("Обоснование"), why), err,
    h("button", { class: "btn primary", type: "button", onclick: async () => {
      err.hidden = true;
      if (why.value.trim().length < 3) { err.textContent = T("Укажите обоснование длиной от 3 до 2000 символов."); err.hidden = false; return; }
      try {
        const res = await api("/review", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ report: state.report, rule_id: sel.value, action: act.value, rationale: why.value }) });
        state.report = await res.json(); why.value = ""; paint();
      } catch { err.textContent = T("Укажите обоснование длиной от 3 до 2000 символов."); err.hidden = false; }
    } }, T("Записать решение")), list);
  paint();
}
function renderSources() {
  const box = $("tab-sources"); box.replaceChildren();
  const cfg = state.config;
  box.append(h("p", {}, T("Каталог {version} · подтвержденный диапазон: {dates}", { version: cfg.catalogue_version, dates: cfg.supported_date_range.join(" — ") })),
    h("ul", {}, state.result.view.limitations.map((t) => h("li", {}, t))));
  const w = state.result.view.warnings;
  if (w.length) box.append(h("details", { class: "sub" }, h("summary", {}, T("Предупреждения и метаданные анализа")), h("ul", {}, w.map((t) => h("li", {}, t))),
    h("pre", { class: "src" }, JSON.stringify({ ...state.report, findings: undefined, reviews: undefined }, null, 2))));
  for (const rule of cfg.rules) box.append(h("details", { class: "sub" }, h("summary", {}, state.result.view.findings.find((x) => x.rule_id === rule.id)?.name || rule.name),
    h("p", { class: "muted small" }, T("Оригинальное описание из каталога (без перевода)")), h("p", {}, rule.interpretation), h("p", { class: "muted small" }, rule.reference),
    h("a", { href: rule.official_source, rel: "noreferrer", target: "_blank" }, "LexUZ")));
}

/* ---------- boot ---------- */
async function setLanguage(lang) {
  state.lang = lang;
  try { localStorage.setItem("polisdiff-lang", lang); } catch { /* storage may be blocked */ }
  state.dict = lang === "ru" ? {} : await (await api("/i18n/" + lang)).json();
  if (lang === "ru") state.dict = await (await api("/i18n/ru")).json();
  applyLabels();
  if (state.result) { await reanalyzeForLanguage(); }
}
async function reanalyzeForLanguage() {
  // Localized finding copy is produced by the engine's presentation layer, so refresh it.
  if (state.file && !state.busy) { await analyze(true); } else { renderResults(); }
}
async function boot() {
  try { state.config = await (await api("/config")).json(); } catch { showError("API unavailable"); return; }
  const sel = $("lang");
  for (const [code, name] of Object.entries(state.config.languages)) sel.append(h("option", { value: code }, name));
  let saved = "ru"; try { saved = localStorage.getItem("polisdiff-lang") || "ru"; } catch { /* ignore */ }
  if (!LANGS.includes(saved)) saved = "ru";
  sel.value = saved; sel.addEventListener("change", () => setLanguage(sel.value));
  $("audit").value = state.config.today; $("audit").max = state.config.today;
  try { state.samples = await (await fetch("/samples/index.json")).json(); } catch { state.samples = []; }
  const drop = $("drop"), input = $("file");
  drop.addEventListener("click", () => input.click());
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
  input.addEventListener("change", () => setFile(input.files[0] || null));
  for (const ev of ["dragenter", "dragover"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
  for (const ev of ["dragleave", "drop"]) drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); });
  drop.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0] || null));
  $("date-confirm").addEventListener("change", () => { $("applicable").disabled = !$("date-confirm").checked; if (!$("date-confirm").checked) $("applicable").value = ""; updateReadiness(); invalidate(); });
  $("applicable").addEventListener("change", () => { updateReadiness(); invalidate(); });
  $("audit").addEventListener("change", () => { updateReadiness(); invalidate(); });
  $("modes").addEventListener("change", invalidate);
  $("analyze").addEventListener("click", () => analyze());
  $("clear").addEventListener("click", () => { state.file = null; input.value = ""; $("date-confirm").checked = false; $("applicable").value = ""; $("applicable").disabled = true; $("analyze").disabled = true; $("drop-file").textContent = ""; invalidate(); hideError(); updateReadiness(); });
  await setLanguage(saved);
}
boot();
