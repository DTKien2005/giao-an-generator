/* Front-end behaviour: submit → SSE progress → document view → downloads. */
"use strict";

const $ = (sel) => document.querySelector(sel);

const GRADES = 12;
const SUBJECT_LABEL = {
  toan: "Toán", tieng_viet: "Tiếng Việt", khoa_hoc: "Khoa học",
  lich_su: "Lịch sử - Địa lí", dao_duc: "Đạo đức", ta: "Tiếng Anh",
};
const TYPE_LABEL = { lesson_plan: "Giáo án", worksheet: "Phiếu bài tập" };

let currentDoc = null;   // {document, versions, messages}
let currentVersion = null;

// ---------------------------------------------------------------- setup
function fillGrades() {
  for (let i = 1; i <= GRADES; i++) {
    const opt = document.createElement("option");
    opt.value = `grade_${i}`;
    opt.textContent = `Lớp ${i}`;
    $("#grade").appendChild(opt);
  }
}

function bindUI() {
  fillGrades();

  // week field only applies to worksheets
  document.querySelectorAll("input[name=doc_type]").forEach((el) =>
    el.addEventListener("change", () => {
      $("#week-field").hidden = !$("#dt-sheet").checked;
    })
  );

  $("#file").addEventListener("change", (e) => {
    $("#file-name").textContent = e.target.files.length ? `Đã chọn: ${e.target.files[0].name}` : "";
  });

  $("#request-form").addEventListener("submit", onSubmit);

  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      $("#tab-doc").hidden = tab.dataset.tab !== "doc";
      $("#tab-history").hidden = tab.dataset.tab !== "history";
      $("#tab-settings").hidden = tab.dataset.tab !== "settings";
      if (tab.dataset.tab === "history") loadHistory();
      if (tab.dataset.tab === "settings") loadSettings();
    })
  );

  $("#version-select").addEventListener("change", async (e) => {
    const id = Number(e.target.value);
    const v = currentDoc.versions.find((x) => x.id === id);
    if (v) await showVersion(v);
  });

  $("#edit-form").addEventListener("submit", onEditSubmit);
  $("#btn-diff").addEventListener("click", onToggleDiff);
  $("#settings-form").addEventListener("submit", onSettingsSubmit);
  $("#login-form").addEventListener("submit", onLoginSubmit);
  $("#account-form").addEventListener("submit", onAccountSubmit);
  $("#btn-logout").addEventListener("click", onLogout);

  // provider badge in the masthead; login state decides the overlay
  fetch("/api/settings").then((r) => r.json()).then((s) => {
    $("#provider-badge").textContent =
      ({ gemini: "Gemini", openai: "OpenAI", anthropic: "Claude",
         local: "Cục bộ", mock: "Mock" })[s.default_provider] || s.default_provider;
  });
  refreshLoginState();
}

// ---------------------------------------------------------------- auth UI
function showLogin() {
  $("#login-overlay").hidden = false;
  $("#login-hint").textContent = "";
  $("#login-name").focus();
}

async function refreshLoginState() {
  const me = await (await fetch("/api/me")).json();
  const overlay = $("#login-overlay");
  if (me.auth_enabled && !me.name) {
    overlay.hidden = false;
  } else {
    overlay.hidden = true;
  }
  $("#account-open").hidden = me.auth_enabled;
  $("#account-logged").hidden = !me.auth_enabled;
  $("#account-who").textContent = me.name
    ? `Đã đăng nhập: ${me.name}` : "";
}

async function onLoginSubmit(ev) {
  ev.preventDefault();
  const resp = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: $("#login-name").value, password: $("#login-password").value,
    }),
  });
  if (resp.ok) {
    location.reload();
  } else {
    $("#login-hint").textContent = "Sai tên đăng nhập hoặc mật khẩu.";
  }
}

async function onAccountSubmit(ev) {
  ev.preventDefault();
  const resp = await fetch("/api/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: $("#acc-name").value, password: $("#acc-password").value,
    }),
  });
  const body = await resp.json().catch(() => ({}));
  $("#account-status").textContent = resp.ok
    ? "Đã bật đăng nhập — tài khoản này sở hữu toàn bộ dữ liệu hiện có."
    : (body.detail || `Lỗi HTTP ${resp.status}`);
  if (resp.ok) refreshLoginState();
}

async function onLogout() {
  await fetch("/api/logout", { method: "POST" });
  location.reload();
}

function unauthorized(resp) {
  if (resp.status === 401) {
    showLogin();
    return true;
  }
  return false;
}

// ---------------------------------------------------------------- settings
async function loadSettings() {
  const s = await (await fetch("/api/settings")).json();
  $("#set-provider").value = s.default_provider;
  for (const role of s.roles) {
    const input = document.querySelector(`#set-model-${role}`);
    if (input) input.value = s.models[role] || "";
  }
  $("#set-url-local").value = (s.base_urls.local || "").replace("http://localhost:11434/v1", "");
  const notes = Object.entries(s.keys_set).filter(([, v]) => v).map(([p]) => p);
  $("#settings-status").textContent = notes.length
    ? `Khoá đã lưu (mã hoá): ${notes.join(", ")}`
    : "Chưa có khoá API nào được lưu.";
}

async function onSettingsSubmit(ev) {
  ev.preventDefault();
  const payload = {
    default_provider: $("#set-provider").value,
    models: {},
    api_keys: {},
    base_urls: {},
  };
  for (const role of ["writer", "reviewer", "reviser", "intake"]) {
    const v = document.querySelector(`#set-model-${role}`).value.trim();
    if (v) payload.models[role] = v;
  }
  for (const p of ["gemini", "openai", "anthropic"]) {
    const v = document.querySelector(`#set-key-${p}`).value.trim();
    if (v) payload.api_keys[p] = v;
  }
  const localUrl = $("#set-url-local").value.trim();
  if (localUrl) payload.base_urls.local = localUrl;

  const resp = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await resp.json().catch(() => ({}));
  for (const p of ["gemini", "openai", "anthropic"]) {
    document.querySelector(`#set-key-${p}`).value = "";
  }
  await loadSettings();  // refresh stored state first…
  // …then show the save result (loadSettings rewrites the status line)
  $("#settings-status").textContent = resp.ok
    ? "Đã lưu. Khoá API mới (nếu có) đã được mã hoá và lưu."
    : (body.detail || `Lỗi HTTP ${resp.status}`);
  $("#provider-badge").textContent =
    ({ gemini: "Gemini", openai: "OpenAI", anthropic: "Claude",
       local: "Cục bộ", mock: "Mock" })[body.default_provider] || body.default_provider || "";
}

// ---------------------------------------------------------------- submit + SSE
async function onSubmit(ev) {
  ev.preventDefault();
  const form = ev.target;
  const btn = $("#btn-generate");
  btn.disabled = true;
  btn.textContent = "Đang gửi…";
  resetProgress();
  try {
    const resp = await fetch("/api/generate", { method: "POST", body: new FormData(form) });
    if (unauthorized(resp)) return;
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      addProgress(err.detail || `Lỗi HTTP ${resp.status}`, "error");
      return;
    }
    const { run_id } = await resp.json();
    followRun(run_id);
  } catch (e) {
    addProgress(`Không gửi được yêu cầu: ${e}`, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Soạn tài liệu";
  }
}

function followRun(runId) {
  const es = new EventSource(`/api/runs/${runId}/events`);
  es.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "progress") {
      addProgress(data.label);
    } else if (data.type === "done") {
      markLastDone();
      addProgress("Hoàn tất!", "done");
      es.close();
      openDocument(data.result.document_id, data.result.version_id);
    } else if (data.type === "error") {
      addProgress(data.error, "error");
      es.close();
    }
  };
  es.onerror = () => es.close();
}

// ---------------------------------------------------------------- progress UI
function resetProgress() {
  $("#progress-card").hidden = false;
  $("#progress-lines").innerHTML = "";
}
function addProgress(label, cls = "") {
  const li = document.createElement("li");
  li.textContent = label;
  if (cls) li.classList.add(cls);
  $("#progress-lines").appendChild(li);
  li.scrollIntoView({ block: "nearest" });
}
function markLastDone() {
  const items = $("#progress-lines").querySelectorAll("li:not(.done):not(.error)");
  if (items.length) items[items.length - 1].classList.add("done");
}

// ---------------------------------------------------------------- follow-up edits
async function onEditSubmit(ev) {
  ev.preventDefault();
  const input = $("#edit-input");
  const instruction = input.value.trim();
  if (!instruction || !currentDoc) return;
  input.value = "";
  appendChat("user", instruction);
  $("#btn-generate").disabled = true;
  resetProgress();
  try {
    const body = new FormData();
    body.append("instruction", instruction);
    const resp = await fetch(`/api/documents/${currentDoc.document.id}/edit`,
      { method: "POST", body });
    if (unauthorized(resp)) return;
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      appendChat("assistant", err.detail || `Lỗi HTTP ${resp.status}`);
      return;
    }
    const { run_id } = await resp.json();
    followEditRun(run_id);
  } catch (e) {
    appendChat("assistant", `Không gửi được: ${e}`);
  } finally {
    $("#btn-generate").disabled = false;
  }
}

function followEditRun(runId) {
  const es = new EventSource(`/api/runs/${runId}/events`);
  es.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "progress") {
      addProgress(data.label);
    } else if (data.type === "done") {
      markLastDone();
      addProgress("Hoàn tất!", "done");
      es.close();
      appendChat("assistant", data.result.review_summary || "Đã chỉnh sửa xong.");
      openDocument(data.result.document_id, data.result.version_id);
    } else if (data.type === "error") {
      addProgress(data.error, "error");
      appendChat("assistant", data.error);
      es.close();
    }
  };
  es.onerror = () => es.close();
}

function renderChat() {
  const ul = $("#chat-messages");
  ul.innerHTML = "";
  for (const m of currentDoc.messages || []) {
    appendChat(m.role, m.content);
  }
  ul.scrollTop = ul.scrollHeight;
}

function appendChat(role, content) {
  const li = document.createElement("li");
  li.className = role;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? "Bạn" : "Trợ lý";
  li.appendChild(who);
  li.appendChild(document.createTextNode(content));
  const ul = $("#chat-messages");
  ul.appendChild(li);
  ul.scrollTop = ul.scrollHeight;
}

// ---------------------------------------------------------------- diff
async function onToggleDiff() {
  const view = $("#diff-view");
  if (!view.hidden) {
    view.hidden = true;
    view.innerHTML = "";
    return;
  }
  const versions = currentDoc.versions; // sorted desc
  if (versions.length < 2) return;
  const newer = versions.find((v) => v.id === currentVersion.id) || versions[0];
  const older = versions.filter((v) => v.version < newer.version)
    .sort((a, b) => b.version - a.version)[0];
  if (!older) return;

  const resp = await fetch(
    `/api/documents/${currentDoc.document.id}/diff?from_version=${older.version}&to_version=${newer.version}`);
  if (!resp.ok) {
    view.hidden = false;
    view.textContent = "Không tạo được so sánh.";
    return;
  }
  const sections = await resp.json();
  view.innerHTML = "";
  if (!sections.length) {
    view.innerHTML = "<p>Không có khác biệt nào giữa hai phiên bản.</p>";
  }
  for (const sec of sections) {
    const h = document.createElement("h4");
    h.textContent = `${sec.label} (v${older.version} → v${newer.version})`;
    view.appendChild(h);
    for (const line of sec.lines) {
      const span = document.createElement("span");
      span.className = `diff-line ${line.op}`;
      span.textContent = line.text;
      view.appendChild(span);
    }
  }
  view.hidden = false;
}

// ---------------------------------------------------------------- document view
async function openDocument(documentId, preferredVersionId = null) {
  const resp = await fetch(`/api/documents/${documentId}`);
  if (unauthorized(resp) || !resp.ok) return;
  currentDoc = await resp.json();
  currentDoc.versions.sort((a, b) => b.version - a.version);

  const d = currentDoc.document;
  $("#doc-empty").hidden = true;
  $("#doc-view").hidden = false;
  $("#doc-title").textContent = d.title;
  $("#doc-meta").textContent =
    `${TYPE_LABEL[d.doc_type] || d.doc_type} · ${d.grade.replace("grade_", "Lớp ")}`
    + ` · ${SUBJECT_LABEL[d.subject] || d.subject}`
    + (d.format_spec && d.format_spec.includes('"user_upload"') ? " · Định dạng của bạn" : "");

  const sel = $("#version-select");
  sel.innerHTML = "";
  for (const v of currentDoc.versions) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = `v${v.version} — ${v.created_at.slice(0, 16).replace("T", " ")}`;
    sel.appendChild(opt);
  }
  const target = preferredVersionId
    ? currentDoc.versions.find((v) => v.id === preferredVersionId) || currentDoc.versions[0]
    : currentDoc.versions[0];
  sel.value = target.id;
  await showVersion(target);
  renderChat();

  $("#btn-diff").hidden = currentDoc.versions.length < 2;
  $("#diff-view").hidden = true;
  $("#diff-view").innerHTML = "";

  document.querySelector('[data-tab="doc"]').click();
}

async function showVersion(v) {
  currentVersion = v;
  const resp = await fetch(`/api/versions/${v.id}/preview`);
  if (unauthorized(resp)) return;
  if (!resp.ok) {
    $("#doc-content").textContent = "Không tải được nội dung phiên bản này.";
    return;
  }
  const document = await resp.json();
  $("#doc-content").innerHTML = renderDocument(document);
  $("#doc-note").textContent = v.note || "";

  const base = `/api/versions/${v.id}/download?fmt=`;
  $("#dl-docx").href = base + "docx";
  $("#dl-pdf").href = base + "pdf";
  $("#dl-docx").style.display = v.file_docx ? "" : "none";
  $("#dl-pdf").style.display = v.file_pdf ? "" : "none";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderDocument(doc) {
  const sec = doc.sections || {};
  let html = "";

  if (sec.objectives?.length) {
    html += "<h3>I. Mục tiêu</h3><ul>" +
      sec.objectives.map((o) => `<li>${esc(o)}</li>`).join("") + "</ul>";
  }
  if (sec.materials?.length) {
    html += "<h3>II. Đồ dùng dạy học</h3><ul>" +
      sec.materials.map((o) => `<li>${esc(o)}</li>`).join("") + "</ul>";
  }
  if (sec.activities?.length) {
    html += "<h3>III. Các hoạt động dạy học</h3><table>" +
      "<tr><th>Hoạt động</th><th>Giáo viên / Học sinh</th><th>Phút</th></tr>" +
      sec.activities.map((a) =>
        `<tr><td><b>${esc(a.name)}</b></td>` +
        `<td>GV: ${esc(a.teacher)}<br/>HS: ${esc(a.students)}</td>` +
        `<td>${esc(a.minutes)}</td></tr>`).join("") +
      "</table>";
  }
  if (sec.assessment) {
    html += `<h3>IV. Đánh giá</h3><p>${esc(sec.assessment)}</p>`;
  }
  if (sec.exercises?.length) {
    html += "<h3>Bài tập</h3><ol>" +
      sec.exercises.map((ex) => `<li><p>${esc(ex.content)}</p></li>`).join("") + "</ol>";
  }
  if (sec.answers) {
    html += `<h3>Đáp án</h3><pre style="white-space:pre-wrap;font-family:inherit">${esc(sec.answers)}</pre>`;
  }
  if (sec.appendix) {
    html += `<h3>Phụ lục</h3><p>${esc(sec.appendix)}</p>`;
  }
  return html || "<p>(Nội dung trống)</p>";
}

// ---------------------------------------------------------------- history
async function loadHistory() {
  const resp = await fetch("/api/conversations");
  if (unauthorized(resp)) return;
  const rows = await resp.json();
  const ul = $("#history-list");
  ul.innerHTML = "";
  if (!rows.length) {
    ul.innerHTML = "<li style='padding:14px;color:var(--ink-soft)'>Chưa có cuộc trò chuyện nào.</li>";
    return;
  }
  for (const c of rows) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.innerHTML = `<span><span class="badge">${c.documents} tài liệu</span>${esc(c.title)}</span>` +
      `<span class="when">${esc(c.updated_at)}</span>`;
    btn.addEventListener("click", async () => {
      const r = await fetch(`/api/conversations/${c.id}/documents`);
      const docs = await r.json();
      if (docs.length) openDocument(docs[0].id);
    });
    li.appendChild(btn);
    ul.appendChild(li);
  }
}

// ---------------------------------------------------------------- boot
bindUI();
