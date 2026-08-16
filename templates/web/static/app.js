(function batteryTable() {
  const sortState = new Map();
  const filterState = new Map();
  const translations = {
    en: {
      action: "Action",
      actions: "Actions",
      admitted_candidates_intro: "Admitted candidates only",
      all: "All",
      ask_codex: "Ask Codex to operate this topic",
      assets: "Assets",
      authors: "Authors",
      bootstrap_chat_intro: "Create a topic first. Model and effort will be used for initialization; after creation I will enter the new topic.",
      bootstrap_intro: "Start a clean-room literature topic under",
      candidate_queue: "Candidate Queue",
      candidate_search_placeholder: "Search title, authors, abstract",
      candidates: "Candidates",
      candidates_lower: "candidates",
      chat_next_placeholder: "Tell Codex the next step, for example: download PDFs for candidates with score > 0.45 and add them to the library.",
      chat_placeholder: "Search for new papers, score candidates, read a paper, summarize status, or rebuild the report.",
      clear_view: "Clear view",
      clean_room_note: "Do not inspect sibling topics. This workbench creates a new topic from built-in templates and your inputs only.",
      codex_console: "Codex Console",
      codex_model: "Model",
      create_topic: "Create Topic",
      candidate_count: "Candidate",
      dashboard: "Overview",
      direction_placeholder: "Describe the papers to collect, preferred scope, and exclusions.",
      dismiss: "Dismiss",
      downloaded: "Downloaded",
      download_pdf: "Download PDF",
      downloading_selected_pdfs: "Downloading selected PDFs",
      download_selected_pdfs: "Download Selected PDFs",
      effort: "Effort",
      failed: "failed",
      health: "Health",
      health_check: "Health Check",
      has_pdf: "Has PDF",
      irrelevant: "Irrelevant",
      irrelevant_papers: "Irrelevant Papers",
      job_failed: "Last job failed",
      knowledge: "Knowledge",
      knowledge_pending: "Knowledge pending",
      language: "Language",
      library: "Library",
      list: "List",
      library_search_placeholder: "Search title, bibkey, venue",
      metadata: "Metadata",
      missing_pdf: "Missing PDF",
      new_candidates: "New candidates",
      new_topic: "New Topic",
      no_pdf: "No PDF",
      no_active_job: "No active job",
      no_completed_jobs: "No completed jobs yet",
      no_papers_yet: "No papers yet",
      ok: "ok",
      papers: "Papers",
      papers_lower: "papers",
      pdfs: "PDFs",
      query: "Query",
      query_placeholder: "optional search query",
      queue: "Queue",
      read_paper: "Read Paper",
      read_paper_count: "Read Paper",
      reading_selected_papers: "Codex is reading selected papers",
      read_selected_papers: "Read Paper",
      rebuild_html: "Rebuild HTML",
      recent_jobs: "Recent Jobs",
      relevant: "Relevant",
      relevant_papers: "Relevant Papers",
      research_direction: "Research direction",
      running: "Running",
      score: "Score",
      score_candidates: "Score Candidates",
      score_threshold: "Score threshold",
      search: "Search",
      search_30: "Search +30",
      seed_paper: "Seed paper",
      seed_paper_placeholder: "optional paper title",
      select: "Select",
      send: "Send",
      send_to_codex: "Send to Codex",
      selected_count: "selected",
      set_relevance: "Set relevance",
      score_queue: "Score queue",
      status: "Status",
      stop: "Stop",
      summary: "Summary",
      title_col: "Title",
      title_label: "Title",
      topic_title_placeholder: "test-time guided generative model",
      topic_chat_intro: "I have entered the current topic. Tell me the next step, or use the quick commands below.",
      topic_scope: "Topic",
      total_paper: "Total Paper",
      unscored: "Unscored",
      venue: "Venue",
      year: "Year",
      research_modules: "Research Modules",
      module_scope_note: "The review is limited to the following four modules.",
      module_candidates: "Candidates",
      module_library: "Library",
      module_read: "Read",
      strict_scope: "Strict scope",
      module_coverage: "Reading coverage",
      research_chain: "Research Chain",
      research_chain_note: "The four modules form a progression from material architecture to mechanisms, coupled models, and system validation.",
      cross_module_papers: "Cross-Module Papers",
      no_cross_module_papers: "No cross-module papers have been classified yet.",
      module_filter: "Research module",
    },
    zh: {
      action: "操作",
      actions: "操作",
      admitted_candidates_intro: "仅显示已入队候选",
      all: "全部",
      ask_codex: "让 Codex 操作当前 topic",
      assets: "资产",
      authors: "作者",
      bootstrap_chat_intro: "先创建 topic。模型和强度会用于初始化任务；创建完成后我会进入新 topic。",
      bootstrap_intro: "在此目录下创建 clean-room 文献 topic",
      candidate_queue: "候选队列",
      candidate_search_placeholder: "检索题目、作者、摘要",
      candidates: "候选",
      candidates_lower: "篇候选",
      chat_next_placeholder: "告诉 Codex 下一步，例如：把 score > 0.45 的候选下载 PDF 并入库。",
      chat_placeholder: "检索新论文、评分候选、解读论文、总结状态或重建报告。",
      clear_view: "清空视图",
      clean_room_note: "不要读取兄弟 topic。本 workbench 只使用内置模板和你的输入创建新 topic。",
      codex_console: "Codex 控制台",
      codex_model: "模型",
      create_topic: "创建 Topic",
      candidate_count: "待筛选",
      dashboard: "总览",
      direction_placeholder: "描述要收集的论文、研究范围和排除项。",
      dismiss: "移除",
      downloaded: "下载论文",
      download_pdf: "下载 PDF",
      downloading_selected_pdfs: "正在下载所选 PDF",
      download_selected_pdfs: "下载所选 PDF",
      effort: "强度",
      failed: "失败",
      health: "健康状态",
      health_check: "健康检查",
      has_pdf: "已有 PDF",
      irrelevant: "不相关",
      irrelevant_papers: "不相关论文",
      job_failed: "上一个任务失败",
      knowledge: "知识卡片",
      knowledge_pending: "知识卡片待生成",
      language: "语言",
      library: "文件库",
      list: "文献列表",
      library_search_placeholder: "检索题目、Bibkey、Venue",
      metadata: "元数据",
      missing_pdf: "缺少 PDF",
      new_candidates: "新增候选数",
      new_topic: "新 Topic",
      no_pdf: "无 PDF",
      no_active_job: "当前没有运行任务",
      no_completed_jobs: "暂无已完成任务",
      no_papers_yet: "暂无入库论文",
      ok: "成功",
      papers: "论文",
      papers_lower: "篇论文",
      pdfs: "PDF",
      query: "检索词",
      query_placeholder: "可选检索词",
      queue: "候选队列",
      read_paper: "解读论文",
      read_paper_count: "已解读",
      reading_selected_papers: "Codex 正在解读所选论文",
      read_selected_papers: "解读论文",
      rebuild_html: "重建 HTML",
      recent_jobs: "最近任务",
      relevant: "相关",
      relevant_papers: "相关论文",
      research_direction: "研究方向",
      running: "运行中",
      score: "分数",
      score_candidates: "候选评分",
      score_threshold: "分数阈值",
      search: "检索",
      search_30: "检索 +30",
      seed_paper: "种子论文",
      seed_paper_placeholder: "可选论文标题",
      select: "选择",
      send: "发送",
      send_to_codex: "发送给 Codex",
      selected_count: "已选择",
      set_relevance: "设置相关性",
      score_queue: "候选打分",
      status: "状态",
      stop: "停止",
      summary: "摘要",
      title_col: "题目",
      title_label: "标题",
      topic_title_placeholder: "test-time guided generative model",
      topic_chat_intro: "我已进入当前 topic。你可以直接说下一步，也可以点击下面的快捷命令。",
      topic_scope: "主题范围",
      total_paper: "总文章数",
      unscored: "未打分",
      venue: "Venue",
      year: "年份",
      research_modules: "研究模块",
      module_scope_note: "当前调研严格限定为以下四个模块。",
      module_candidates: "候选",
      module_library: "入库",
      module_read: "已解读",
      strict_scope: "严格范围",
      module_coverage: "精读覆盖率",
      research_chain: "研究链路",
      research_chain_note: "四个模块从材料结构出发，逐步连接相变机理、耦合模型与系统验证。",
      cross_module_papers: "跨模块论文",
      no_cross_module_papers: "尚未完成跨模块论文分类。",
      module_filter: "研究模块",
    },
  };

  function language() {
    return localStorage.getItem("battery_language") || "zh";
  }

  function t(key) {
    return translations[language()]?.[key] || translations.en[key] || key;
  }

  function applyLanguage() {
    const lang = language();
    document.documentElement.lang = lang === "zh" ? "zh" : "en";
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
    });
    document.querySelectorAll("[data-module-option]").forEach((option) => {
      option.textContent = lang === "zh" ? option.dataset.titleZh : option.dataset.titleEn;
    });
    const select = document.querySelector("[data-language-select]");
    if (select) select.value = lang;
    updateSelectionState();
  }

  const DEFAULT_CODEX_MODEL = "gpt-5.6-sol";
  const DEFAULT_CODEX_EFFORT = "medium";

  function codexSelectValue(selector, storageKey, fallback) {
    const select = document.querySelector(selector);
    if (!select) return fallback;
    const allowed = new Set(Array.from(select.options, (option) => option.value));
    const stored = localStorage.getItem(storageKey);
    const candidate = stored || select.value || fallback;
    const value = allowed.has(candidate) ? candidate : fallback;
    select.value = value;
    if (stored !== value) localStorage.setItem(storageKey, value);
    return value;
  }

  function initWorkbenchControls() {
    const langSelect = document.querySelector("[data-language-select]");
    const modelSelect = document.querySelector("[data-codex-model]");
    const effortSelect = document.querySelector("[data-codex-effort]");
    codexSelectValue("[data-codex-model]", "battery_codex_model", DEFAULT_CODEX_MODEL);
    codexSelectValue("[data-codex-effort]", "battery_codex_effort", DEFAULT_CODEX_EFFORT);
    if (langSelect) {
      langSelect.value = language();
      langSelect.addEventListener("change", () => {
        localStorage.setItem("battery_language", langSelect.value || "en");
        applyLanguage();
      });
    }
    if (modelSelect) {
      modelSelect.addEventListener("change", () => localStorage.setItem("battery_codex_model", modelSelect.value || "default"));
    }
    if (effortSelect) {
      effortSelect.addEventListener("change", () => localStorage.setItem("battery_codex_effort", effortSelect.value || "default"));
    }
    applyLanguage();
  }

  function appendCodexOptions(params) {
    const model = codexSelectValue("[data-codex-model]", "battery_codex_model", DEFAULT_CODEX_MODEL);
    const effort = codexSelectValue("[data-codex-effort]", "battery_codex_effort", DEFAULT_CODEX_EFFORT);
    params.set("codex_model", model);
    params.set("codex_effort", effort);
    return params;
  }

  function codexOptionsPayload() {
    return {
      codex_model: codexSelectValue("[data-codex-model]", "battery_codex_model", DEFAULT_CODEX_MODEL),
      codex_effort: codexSelectValue("[data-codex-effort]", "battery_codex_effort", DEFAULT_CODEX_EFFORT),
    };
  }

  let sessionCursor = 0;
  let activeAssistantMessage = null;
  let transcriptLoaded = false;
  let transcriptLoadPromise = null;
  let sessionPollInFlight = false;
  const MAX_SESSION_MESSAGES = 100;

  async function startSession() {
    if (!document.querySelector("[data-session-events]")) return;
    try {
      const response = await fetch("/api/session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(codexOptionsPayload()),
      });
      const data = await response.json();
      renderSessionState(data);
      if (!response.ok || data.ok === false) appendSessionMessage("system", data.error || data.blocker || "Session unavailable");
    } catch (error) {
      appendSessionMessage("system", error.message || "Session unavailable");
    }
  }

  async function refreshSessionState() {
    if (!document.querySelector("[data-session-status]")) return;
    try {
      const response = await fetch("/api/session/state");
      renderSessionState(await response.json());
    } catch (error) {
      renderSessionState({ status: "blocked", blocker: error.message || "Session state unavailable" });
    }
  }

  async function loadSessionTranscript() {
    const transcript = document.querySelector("[data-session-events]");
    if (!transcript) return;
    if (transcriptLoaded) return;
    if (transcriptLoadPromise) {
      await transcriptLoadPromise;
      return;
    }
    transcriptLoadPromise = (async () => {
      try {
        const response = await fetch("/api/session/transcript");
        const data = await response.json();
        if (Array.isArray(data.messages)) {
          transcript.innerHTML = "";
          activeAssistantMessage = null;
          data.messages.forEach((message) => appendSessionMessage(message.author || "system", message.message || ""));
        }
        if (typeof data.cursor === "number") sessionCursor = data.cursor;
        transcriptLoaded = true;
      } catch (error) {
        transcriptLoaded = true;
        appendSessionMessage("system", error.message || "Session transcript unavailable");
      } finally {
        transcriptLoadPromise = null;
      }
    })();
    await transcriptLoadPromise;
  }

  async function pollSessionEvents() {
    const transcript = document.querySelector("[data-session-events]");
    if (!transcript) return;
    if (sessionPollInFlight) return;
    sessionPollInFlight = true;
    try {
      if (!transcriptLoaded) await loadSessionTranscript();
      let hasMore = true;
      while (hasMore) {
        const response = await fetch(`/api/session/events?cursor=${sessionCursor}&limit=200`);
        const data = await response.json();
        if (!Array.isArray(data.events)) return;
        data.events.forEach(renderSessionEvent);
        if (typeof data.next_cursor === "number") sessionCursor = data.next_cursor;
        hasMore = Boolean(data.has_more);
      }
    } catch (error) {
      appendSessionMessage("system", error.message || "Session event polling failed");
    } finally {
      sessionPollInFlight = false;
    }
  }

  async function sendSessionMessage(message) {
    const response = await fetch("/api/session/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...codexOptionsPayload(), message }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) appendSessionMessage("system", data.error || data.blocker || "Message failed");
    await refreshSessionState();
    await pollSessionEvents();
    return response.ok && data.ok !== false;
  }

  async function sendSessionAction(action, payload = {}) {
    const response = await fetch("/api/session/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...codexOptionsPayload(), action, payload }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) appendSessionMessage("system", data.error || data.blocker || "Action failed");
    await refreshSessionState();
    await pollSessionEvents();
    return response.ok && data.ok !== false;
  }

  async function postSessionAction(action, payload = {}) {
    const response = await fetch("/api/session/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...codexOptionsPayload(), action, payload }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) appendSessionMessage("system", data.error || data.blocker || "Action failed");
    await refreshSessionState();
    await pollSessionEvents();
    return { response, data };
  }

  async function stopSessionTurn() {
    const response = await fetch("/api/session/stop", { method: "POST" });
    const data = await response.json();
    if (!response.ok || data.ok === false) appendSessionMessage("system", data.error || data.blocker || "Stop failed");
    await refreshSessionState();
  }

  function renderSessionState(data) {
    const target = document.querySelector("[data-session-status]");
    if (!target) return;
    const status = data.status || (data.ok === false ? "blocked" : "idle");
    target.textContent = status;
    target.dataset.status = status;
  }

  function renderSessionEvent(event) {
    if (event.kind === "session_started") return;
    if (event.kind === "user_message") {
      activeAssistantMessage = null;
      appendSessionMessage("you", event.message || "");
    } else if (event.kind === "assistant_message") {
      activeAssistantMessage = null;
      if (!isRoutineCodexProgress(event.message || "")) appendSessionMessage("codex", event.message || "");
    } else if (event.kind === "action") {
      activeAssistantMessage = null;
      appendSessionMessage("you", event.action || "action");
    } else if (event.kind === "item/agentMessage/delta") {
      appendAssistantDelta(event);
    } else if (event.kind === "turn/completed" || event.kind === "turn/failed" || event.kind === "turn_stopped") {
      activeAssistantMessage = null;
    } else if (event.kind === "blocker" || event.kind === "error") {
      activeAssistantMessage = null;
      appendSessionMessage("system", event.error || event.message || "blocked");
    }
  }

  function appendAssistantDelta(event) {
    const delta = event.delta || "";
    if (!delta) return;
    const key = `${event.turnId || "turn"}:${event.itemId || "assistant"}`;
    if (!activeAssistantMessage || activeAssistantMessage.key !== key) {
      const node = appendSessionMessage("codex", "", { empty: true });
      activeAssistantMessage = { key, node, text: "" };
    }
    activeAssistantMessage.text += delta;
    const paragraph = activeAssistantMessage.node?.querySelector("p");
    if (paragraph) paragraph.textContent = activeAssistantMessage.text;
    if (isRoutineCodexProgress(activeAssistantMessage.text)) {
      activeAssistantMessage.node?.remove();
      activeAssistantMessage.node = null;
    }
    const transcript = document.querySelector("[data-session-events]");
    if (transcript) transcript.scrollTop = transcript.scrollHeight;
  }

  function isRoutineCodexProgress(message) {
    const text = String(message || "").trim().toLowerCase().replace(/\s+/g, " ");
    if (!text) return false;
    return [
      "checking the project and topic operating files",
      "checking policy/status",
      "i have the operating constraints",
      "topic-local skill is older",
      "using the project-root contract",
      "project-root contract as requested",
      "sandbox cannot start commands",
      "sandbox wrapper cannot create",
      "user namespaces are unavailable",
      "rerunning the required file reads outside the sandbox",
      "routine file reads",
    ].some((pattern) => text.includes(pattern));
  }

  function appendSessionMessage(author, message, options = {}) {
    const transcript = document.querySelector("[data-session-events]");
    if (!transcript || (!message && !options.empty)) return null;
    const node = document.createElement("article");
    node.className = `chat-message ${author === "you" ? "user" : author === "codex" ? "assistant" : "system"}`;
    node.innerHTML = `<span>${escapeHtml(author)}</span><p>${escapeHtml(message)}</p>`;
    transcript.appendChild(node);
    trimSessionMessages();
    transcript.scrollTop = transcript.scrollHeight;
    return node;
  }

  function trimSessionMessages() {
    const transcript = document.querySelector("[data-session-events]");
    if (!transcript) return;
    const messages = Array.from(transcript.querySelectorAll("article.chat-message"));
    const extra = messages.length - MAX_SESSION_MESSAGES;
    if (extra <= 0) return;
    messages.slice(0, extra).forEach((node) => {
      if (activeAssistantMessage?.node === node) activeAssistantMessage = null;
      node.remove();
    });
  }

  function initSessionWorkbench() {
    const form = document.querySelector("[data-session-message-form]");
    const hasSessionAction = document.querySelector("[data-session-action]");
    const hasSessionSurface = document.querySelector("[data-session-events]") || document.querySelector("[data-session-status]");
    if (!form && !hasSessionAction && !hasSessionSurface) return;
    if (document.querySelector("[data-session-disabled]")) return;
    if (hasSessionSurface) {
      startSession().then(loadSessionTranscript).then(pollSessionEvents);
      window.setInterval(refreshSessionState, 3000);
      window.setInterval(pollSessionEvents, 2000);
    }
    if (form) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const input = document.querySelector("[data-session-message-input]");
        const message = (input?.value || "").trim();
        if (!message) return;
        input.value = "";
        await sendSessionMessage(message);
      });
    }
    document.querySelectorAll("[data-session-action]:not([data-bulk-action])").forEach((button) => {
      button.addEventListener("click", async () => {
        const ok = await sendSessionAction(button.dataset.sessionAction || "", payloadForSessionAction(button));
        if (ok) applySessionActionVisual(button);
      });
    });
    document.querySelector("[data-session-stop]")?.addEventListener("click", stopSessionTurn);
    document.querySelector("[data-session-clear]")?.addEventListener("click", () => {
      const transcript = document.querySelector("[data-session-events]");
      if (transcript) transcript.innerHTML = "";
    });
  }

  function rowsFor(name) {
    const table = document.querySelector(`[data-battery-table="${name}"]`);
    if (!table) return [];
    return Array.from(table.querySelectorAll("tbody tr"));
  }

  function applyFilters(name) {
    const search = (document.querySelector(`[data-search-table="${name}"]`)?.value || "").toLowerCase();
    const filters = { ...(filterState.get(name) || {}) };
    document.querySelectorAll(`select[data-filter-table="${name}"]`).forEach((select) => {
      if (select.dataset.filterField) filters[select.dataset.filterField] = select.value || "";
    });
    rowsFor(name).forEach((row) => {
      const text = (row.dataset.search || row.textContent || "").toLowerCase();
      const matchesSearch = !search || text.includes(search);
      const matchesFilter = Object.entries(filters).every(([field, filterValue]) => {
        if (!filterValue) return true;
        const values = String(filterValue).split(",").map((value) => value.trim()).filter(Boolean);
        const rowValues = String(row.dataset[field] || "").split(",").map((value) => value.trim()).filter(Boolean);
        return values.length === 0 || values.some((value) => rowValues.includes(value));
      });
      row.hidden = !(matchesSearch && matchesFilter);
    });
    if (name === "candidates") updateCandidateTabView();
    updateSelectionState();
  }

  function updateCandidateTabView() {
    const activeTab = document.querySelector("[data-tab-filter].active");
    const showAll = !activeTab || activeTab.dataset.tabFilter === "all";
    document.querySelectorAll(".relevance-column").forEach((node) => {
      node.hidden = showAll;
    });
  }

  function sortTable(name, key) {
    const table = document.querySelector(`[data-battery-table="${name}"]`);
    if (!table) return;
    const tbody = table.querySelector("tbody");
    const stateKey = `${name}:${key}`;
    const nextDirection = sortState.get(stateKey) === "asc" ? "desc" : "asc";
    sortState.set(stateKey, nextDirection);
    const rows = rowsFor(name);
    rows.sort((a, b) => compare(a.dataset[key] || "", b.dataset[key] || "", nextDirection));
    rows.forEach((row) => tbody.appendChild(row));
    applyFilters(name);
  }

  function compare(a, b, direction) {
    const an = Number(a);
    const bn = Number(b);
    const value = Number.isFinite(an) && Number.isFinite(bn)
      ? an - bn
      : a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
    return direction === "asc" ? value : -value;
  }

  document.querySelectorAll("[data-search-table]").forEach((input) => {
    input.addEventListener("input", () => applyFilters(input.dataset.searchTable));
  });
  document.querySelectorAll("[data-filter-table]").forEach((select) => {
    if (select.tagName === "SELECT") {
      select.addEventListener("change", () => applyFilters(select.dataset.filterTable));
    } else {
      select.addEventListener("click", () => {
        const field = select.dataset.filterField;
        const value = select.dataset.filterValue || "";
        const tableName = select.dataset.filterTable;
        const filters = filterState.get(tableName) || {};
        filters[field] = value;
        filterState.set(tableName, filters);
        document.querySelectorAll(`[data-filter-table="${tableName}"][data-filter-field="${field}"]`).forEach((control) => {
          control.classList.toggle("active", control === select);
        });
        applyFilters(select.dataset.filterTable);
      });
    }
  });
  document.querySelectorAll("[data-sort-table]").forEach((button) => {
    button.addEventListener("click", () => sortTable(button.dataset.sortTable, button.dataset.sortKey));
  });

  function visibleCheckboxes(tableName) {
    return Array.from(document.querySelectorAll(`table[data-battery-table="${tableName}"] tbody input[type="checkbox"]`))
      .filter((input) => !input.closest("tr")?.hidden);
  }

  function selectedCheckboxes(tableName) {
    return visibleCheckboxes(tableName).filter((input) => input.checked);
  }

  function updateSelectionState() {
    const selected = selectedCheckboxes("candidates").length;
    document.querySelectorAll("[data-selected-count]").forEach((node) => {
      node.textContent = `${selected} ${t("selected_count")}`;
    });
    document.querySelectorAll('[data-bulk-action="candidate-download"]').forEach((button) => {
      button.disabled = selected === 0;
    });
    document.querySelectorAll('[data-select-all="candidates"]').forEach((input) => {
      const visible = visibleCheckboxes("candidates");
      input.checked = visible.length > 0 && selected === visible.length;
      input.indeterminate = selected > 0 && selected < visible.length;
    });
    const librarySelected = selectedCheckboxes("library").length;
    document.querySelectorAll("[data-library-selected-count]").forEach((node) => {
      node.textContent = `${librarySelected} ${t("selected_count")}`;
    });
    document.querySelectorAll('[data-bulk-action="library-read"]').forEach((button) => {
      button.disabled = librarySelected === 0;
    });
    document.querySelectorAll('[data-select-all="library"]').forEach((input) => {
      const visible = visibleCheckboxes("library");
      input.checked = visible.length > 0 && librarySelected === visible.length;
      input.indeterminate = librarySelected > 0 && librarySelected < visible.length;
    });
  }

  document.querySelectorAll("[data-select-all]").forEach((input) => {
    input.addEventListener("change", () => {
      visibleCheckboxes(input.dataset.selectAll).forEach((checkbox) => {
        checkbox.checked = input.checked;
      });
      updateSelectionState();
    });
  });
  document.querySelectorAll('table[data-battery-table="candidates"] tbody input[type="checkbox"], table[data-battery-table="library"] tbody input[type="checkbox"]').forEach((input) => {
    input.addEventListener("change", updateSelectionState);
  });

  async function refreshJobs() {
    const status = document.querySelector("[data-job-status]");
    const recent = document.querySelector("[data-recent-jobs]");
    if (!status && !recent) return false;
    const response = await fetch("/api/jobs");
    const data = await response.json();
    if (status) {
      if (data.active_job) {
        status.innerHTML = `<p class="job active">${escapeHtml(t("running"))}: ${escapeHtml(data.active_job.action)} · ${escapeHtml(data.active_job.job_id)}</p>`;
        setActionDisabled(true);
      } else {
        const latest = Array.isArray(data.recent_jobs) ? data.recent_jobs[0] : null;
        if (latest && latest.ok === false) {
          const summary = latest.error || latest.summary || "";
          status.innerHTML = `<p class="warn">${escapeHtml(t("job_failed"))}: ${escapeHtml(summary)}</p>`;
        } else {
          status.innerHTML = `<p class="muted">${escapeHtml(t("no_active_job"))}</p>`;
        }
        setActionDisabled(false);
      }
    }
    if (recent && Array.isArray(data.recent_jobs)) {
      recent.innerHTML = renderRecentJobs(data.recent_jobs);
    }
    if (data.redirect) {
      window.location.href = data.redirect;
      return true;
    }
    return false;
  }

  function setActionDisabled(disabled) {
    document.querySelectorAll("[data-async-action] button[type='submit']").forEach((button) => {
      button.disabled = disabled;
    });
  }

  function showStatus(html) {
    const status = document.querySelector("[data-job-status]");
    if (status) status.innerHTML = html;
  }

  function showActionResponse(response, data) {
    if (data.redirect) {
      showStatus(`<p class="job active">${escapeHtml(t("ok"))}: ${escapeHtml(data.action || "")}</p>`);
      window.location.href = data.redirect;
      return;
    }
    if (response.status === 202) {
      showStatus(`<p class="job active">${escapeHtml(t("running"))}: ${escapeHtml(data.action)} · ${escapeHtml(data.job_id)}</p>`);
    } else {
      showStatus(`<p class="warn">${escapeHtml(data.error || "Action failed")}</p>`);
      setActionDisabled(false);
    }
  }

  function showActionError(error) {
    showStatus(`<p class="warn">${escapeHtml(error.message || "Action failed")}</p>`);
    setActionDisabled(false);
  }

  function summarizeCandidateDownload(data) {
    const results = Array.isArray(data.results) ? data.results : [];
    const promoted = [];
    const manual = [];
    const failed = [];
    results.forEach((result) => {
      const candidateId = result.candidate_id || "";
      const promote = result.promote || {};
      const acquire = result.acquire || {};
      if (promote.ok && promote.bibkey) {
        promoted.push(promote.bibkey);
      } else if (acquire.status === "manual_pdf_needed") {
        manual.push(candidateId);
      } else {
        failed.push(candidateId);
      }
    });
    const parts = [];
    if (promoted.length) parts.push(`PDF ok: ${promoted.map(escapeHtml).join(", ")}`);
    if (manual.length) parts.push(`manual PDF needed: ${manual.map(escapeHtml).join(", ")}`);
    if (failed.length) parts.push(`${escapeHtml(t("failed"))}: ${failed.map(escapeHtml).join(", ")}`);
    return parts.length ? parts.join(" · ") : escapeHtml(data.error || "No PDFs downloaded");
  }

  function renderRecentJobs(jobs) {
    if (!jobs.length) return `<p class="muted">${escapeHtml(t("no_completed_jobs"))}</p>`;
    const rows = jobs.map((job) => {
      const status = job.ok ? t("ok") : t("failed");
      const summary = job.summary || job.error || "";
      return `<tr><td>${escapeHtml(job.action || "")}</td><td>${escapeHtml(status)}</td><td>${escapeHtml(summary)}</td></tr>`;
    }).join("");
    return `<table><thead><tr><th>${escapeHtml(t("action"))}</th><th>${escapeHtml(t("status"))}</th><th>${escapeHtml(t("summary"))}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  document.querySelectorAll("form[data-async-action]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setActionDisabled(true);
      try {
        const params = appendCodexOptions(new URLSearchParams(new FormData(form)));
        const response = await fetch(form.action, {
          method: form.method || "POST",
          body: params,
        });
        const data = await response.json();
        showActionResponse(response, data);
        if (response.status === 202) {
          await refreshJobs();
        }
      } catch (error) {
        showActionError(error);
      }
    });
  });

  document.querySelectorAll("[data-page-refresh]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const redirected = await refreshJobs();
        if (!redirected) window.location.reload();
      } catch (error) {
        showActionError(error);
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-bulk-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.bulkAction;
      let sessionAction = "";
      let payload = {};
      if (action === "candidate-download") {
        sessionAction = "candidate_download_selected";
        payload = {
          candidate_ids: selectedCheckboxes("candidates").map((input) => input.value),
        };
      } else if (action === "library-read") {
        sessionAction = "library_read_selected";
        payload = {
          bibkeys: Array.from(document.querySelectorAll('table[data-battery-table="library"] input[name="bibkey"]:checked')).map((input) => input.value),
        };
      }
      const count = Object.values(payload)[0]?.length || 0;
      if (!sessionAction || count === 0) {
        showStatus('<p class="warn">Select at least one item first.</p>');
        return;
      }
      const originalText = button.textContent;
      button.disabled = true;
      if (action === "candidate-download") {
        showStatus(`<p class="job active">${escapeHtml(t("downloading_selected_pdfs"))}: ${count}</p>`);
        button.textContent = t("downloading_selected_pdfs");
      } else if (action === "library-read") {
        showStatus(`<p class="job active">${escapeHtml(t("reading_selected_papers"))}: ${count}</p>`);
        button.textContent = t("reading_selected_papers");
      }
      try {
        const { response, data } = await postSessionAction(sessionAction, payload);
        if (action === "candidate-download") {
          if (response.ok && data.ok !== false) {
            showStatus(`<p class="job active">${summarizeCandidateDownload(data)}</p>`);
            window.setTimeout(() => window.location.reload(), 900);
          } else {
            showStatus(`<p class="warn">${escapeHtml(data.error || summarizeCandidateDownload(data))}</p>`);
          }
        } else if (action === "library-read") {
          if (response.ok && data.ok !== false) {
            showStatus(`<p class="job active">${escapeHtml(t("reading_selected_papers"))}: ${count}</p>`);
          } else {
            showStatus(`<p class="warn">${escapeHtml(data.error || data.blocker || "Action failed")}</p>`);
          }
        }
        await refreshJobs();
      } catch (error) {
        showActionError(error);
      } finally {
        button.textContent = originalText;
        updateSelectionState();
      }
    });
  });

  function payloadForSessionAction(button) {
    const candidateId = button.dataset.candidateId;
    const bibkey = button.dataset.bibkey;
    if (candidateId) return { candidate_id: candidateId };
    if (bibkey) return { bibkey };
    return {};
  }

  function applySessionActionVisual(button) {
    const candidateId = button.dataset.candidateId;
    const decision = button.dataset.decision;
    if (!candidateId || !decision) return;
    const row = button.closest("tr");
    if (!row) return;
    row.dataset.decision = decision;
    row.dataset.status = decision === "dismissed" ? "dismissed" : decision;
    row.querySelectorAll(".relevance-button").forEach((item) => {
      item.classList.remove("active", "relevant", "irrelevant", "dismissed");
    });
    button.classList.add("active", decision);
    const activeTab = document.querySelector('[data-tab-filter="new"].active');
    if (activeTab && row.dataset.status !== "new") row.hidden = true;
  }

  if (document.querySelector("[data-job-status]") || document.querySelector("[data-recent-jobs]")) {
    initWorkbenchControls();
    initSessionWorkbench();
    updateCandidateTabView();
    updateSelectionState();
    refreshJobs();
    window.setInterval(refreshJobs, 3000);
  } else {
    initWorkbenchControls();
    initSessionWorkbench();
    updateCandidateTabView();
    updateSelectionState();
  }
  document.documentElement.dataset.batteryAppReady = "true";
})();
