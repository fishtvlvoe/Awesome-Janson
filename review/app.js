(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const state = {
    edit: null,
    selectedCueId: null,
    filter: "all",
    search: "",
    approvedWordIds: new Set(),
    approvedCueIds: new Set(),
    decisions: new Map(),
    videoUrl: null,
    playbackEnd: null,
    subtitleStyle: {
      zh_font_size: 50,
      en_font_size: 30,
      show_english: true,
    },
  };

  const elements = {
    editFile: $("#edit-file"),
    videoFile: $("#video-file"),
    editName: $("#edit-name"),
    videoName: $("#video-name"),
    sourceMeta: $("#source-meta"),
    cueCount: $("#cue-count"),
    search: $("#search"),
    cueList: $("#cue-list"),
    preview: $("#preview"),
    videoStage: $("#video-stage"),
    videoEmpty: $("#video-empty"),
    subtitleOverlay: $("#subtitle-overlay"),
    subtitleZh: $("#preview-subtitle-zh"),
    subtitleEn: $("#preview-subtitle-en"),
    previewTime: $("#preview-time"),
    previewRange: $("#preview-range"),
    playCue: $("#play-cue"),
    enableAudio: $("#enable-audio"),
    selectedTitle: $("#selected-title"),
    selectedStatus: $("#selected-status"),
    selectedTime: $("#selected-time"),
    selectedZh: $("#selected-zh"),
    selectedEn: $("#selected-en"),
    wordStrip: $("#word-strip"),
    wordHelper: $("#word-helper"),
    keepCue: $("#keep-cue"),
    approveFillers: $("#approve-fillers"),
    deleteCue: $("#delete-cue"),
    resetCue: $("#reset-cue"),
    statSuggested: $("#stat-suggested"),
    statApproved: $("#stat-approved"),
    statDuration: $("#stat-duration"),
    reviewDot: $("#review-dot"),
    approveAll: $("#approve-all"),
    keepAll: $("#keep-all"),
    resetAll: $("#reset-all"),
    exportReview: $("#export-review"),
    exportEdit: $("#export-edit"),
    saveStatus: $("#save-status"),
    themeToggle: $("#theme-toggle"),
    zhFontSize: $("#zh-font-size"),
    zhFontSizeValue: $("#zh-font-size-value"),
    enFontSize: $("#en-font-size"),
    enFontSizeValue: $("#en-font-size-value"),
    showEnglish: $("#show-english"),
    resetSubtitleStyle: $("#reset-subtitle-style"),
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function asId(value) {
    return String(value);
  }

  function cues() {
    return Array.isArray(state.edit?.cues) ? state.edit.cues : [];
  }

  function words() {
    return Array.isArray(state.edit?.words) ? state.edit.words : [];
  }

  function wordsById() {
    return new Map(words().map((word) => [asId(word.id), word]));
  }

  function cueById(id) {
    return cues().find((cue) => asId(cue.id) === asId(id)) || null;
  }

  function cueWordIds(cue) {
    return (cue?.word_ids || []).map(asId);
  }

  function baseDropIds(cue) {
    return new Set((cue?.drop_word_ids || []).map(asId));
  }

  function formatTime(seconds, includeHours = false) {
    const total = Math.max(0, Number(seconds) || 0);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (includeHours || hours > 0) {
      return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${secs.toFixed(2).padStart(5, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${secs.toFixed(2).padStart(5, "0")}`;
  }

  function setStatus(message, tone = "") {
    elements.saveStatus.textContent = message;
    elements.saveStatus.dataset.tone = tone;
  }

  function setEnabled(enabled) {
    [
      elements.playCue,
      elements.enableAudio,
      elements.keepCue,
      elements.approveFillers,
      elements.deleteCue,
      elements.resetCue,
      elements.approveAll,
      elements.keepAll,
      elements.resetAll,
      elements.exportReview,
      elements.exportEdit,
    ].forEach((element) => {
      element.disabled = !enabled;
    });
  }

  function getCueStatus(cue) {
    const id = asId(cue.id);
    if (state.approvedCueIds.has(id)) return "delete";
    const approvedCount = cueWordIds(cue).filter((wordId) => state.approvedWordIds.has(wordId)).length;
    if (approvedCount > 0) return "filler";
    const decision = state.decisions.get(id);
    if (decision === "keep") return "keep";
    if (decision === "pending") return "pending";
    if (baseDropIds(cue).size > 0) return "suggested";
    return "pending";
  }

  function statusLabel(status) {
    return {
      delete: "刪除整句",
      filler: "已核准贅詞",
      suggested: "AI 建議",
      keep: "已保留",
      pending: "待確認",
    }[status] || "待確認";
  }

  function statusClass(status) {
    return `status-${status}`;
  }

  function currentCue() {
    return state.selectedCueId == null ? null : cueById(state.selectedCueId);
  }

  function normaliseSubtitleStyle(style = {}) {
    const numberInRange = (value, fallback, min, max) => {
      const number = Number(value);
      return Number.isFinite(number) ? Math.min(max, Math.max(min, Math.round(number))) : fallback;
    };
    return {
      zh_font_size: numberInRange(style.zh_font_size, 50, 24, 64),
      en_font_size: numberInRange(style.en_font_size, 30, 14, 42),
      show_english: style.show_english !== false,
    };
  }

  function applySubtitleStyle() {
    state.subtitleStyle = normaliseSubtitleStyle(state.subtitleStyle);
    const width = elements.videoStage?.clientWidth || 1280;
    const scale = Math.min(1, width / 1280);
    elements.videoStage?.style.setProperty("--preview-zh-size", `${Math.round(state.subtitleStyle.zh_font_size * scale)}px`);
    elements.videoStage?.style.setProperty("--preview-en-size", `${Math.round(state.subtitleStyle.en_font_size * scale)}px`);
    elements.zhFontSize.value = String(state.subtitleStyle.zh_font_size);
    elements.zhFontSizeValue.textContent = `${state.subtitleStyle.zh_font_size}px`;
    elements.enFontSize.value = String(state.subtitleStyle.en_font_size);
    elements.enFontSizeValue.textContent = `${state.subtitleStyle.en_font_size}px`;
    elements.showEnglish.checked = state.subtitleStyle.show_english;
  }

  function cueAtTime(seconds) {
    const time = Number(seconds);
    if (!Number.isFinite(time)) return null;
    return cues().find((cue) => time >= Number(cue.source_start) && time < Number(cue.source_end)) || null;
  }

  function renderSubtitleOverlay(cue = cueAtTime(elements.preview.currentTime)) {
    if (!cue) {
      elements.subtitleOverlay.hidden = true;
      elements.subtitleZh.textContent = "";
      elements.subtitleEn.textContent = "";
      return;
    }
    elements.subtitleZh.textContent = cue.zh || "";
    elements.subtitleEn.textContent = cue.en || "";
    elements.subtitleEn.hidden = !cue.en || !state.subtitleStyle.show_english;
    elements.subtitleOverlay.hidden = !cue.zh && (!cue.en || !state.subtitleStyle.show_english);
  }

  function syncCueToVideo() {
    const cue = cueAtTime(elements.preview.currentTime);
    renderSubtitleOverlay(cue);
    if (!cue) {
      elements.previewRange.textContent = `原始時間 ${formatTime(elements.preview.currentTime)} · 尚未載入這段字幕`;
      return;
    }
    if (asId(cue.id) === asId(state.selectedCueId)) return;
    state.selectedCueId = asId(cue.id);
    renderCueList();
    renderSelectedCue();
  }

  function enableAudio() {
    elements.preview.muted = false;
    elements.preview.volume = 1;
    elements.enableAudio.textContent = "聲音已開啟";
    // 綠色按鈕同時是使用者手勢；若目前暫停，直接播放目前句子，避免只解除靜音卻仍沒有聲音。
    if (currentCue() && elements.preview.paused) playSelectedCue();
    setStatus("已解除靜音並播放目前句子；若仍聽不到，請檢查系統輸出音量。", "success");
  }

  function filteredCues() {
    const query = state.search.trim().toLowerCase();
    return cues().filter((cue) => {
      const status = getCueStatus(cue);
      if (state.filter === "suggested" && status !== "suggested") return false;
      if (state.filter === "approved" && !["delete", "filler"].includes(status)) return false;
      if (state.filter === "keep" && status !== "keep") return false;
      if (!query) return true;
      const haystack = [
        cue.zh,
        cue.en,
        formatTime(cue.source_start),
        formatTime(cue.source_end),
        cueWordIds(cue).join(" "),
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }

  function renderCueList() {
    const visible = filteredCues();
    if (!visible.length) {
      elements.cueList.innerHTML = `<div class="empty-state compact"><span class="empty-icon">⌕</span><strong>找不到符合的句子</strong><p>換一個搜尋字詞或清除篩選條件。</p></div>`;
      return;
    }
    elements.cueList.innerHTML = visible.map((cue) => {
      const id = asId(cue.id);
      const status = getCueStatus(cue);
      const selected = id === asId(state.selectedCueId) ? " is-selected" : "";
      const rowStatus = status === "delete" ? " is-deleted" : status === "filler" ? " is-filler" : "";
      return `
        <button class="cue-row${selected}${rowStatus}" type="button" data-cue-id="${escapeHtml(id)}" aria-label="第 ${escapeHtml(id)} 句：${escapeHtml(cue.zh)}">
          <span class="cue-row-head">
            <span class="cue-time">${formatTime(cue.source_start)} — ${formatTime(cue.source_end)}</span>
            <span class="cue-status ${statusClass(status)}">${statusLabel(status)}</span>
          </span>
          <span class="cue-preview">${escapeHtml(cue.zh || cue.en || "（無字幕文字）")}</span>
        </button>`;
    }).join("");
  }

  function renderStats() {
    const suggested = cues().reduce((total, cue) => total + baseDropIds(cue).size, 0);
    const approvedWords = state.approvedWordIds.size;
    const approvedCues = state.approvedCueIds.size;
    const duration = mergedIntervals(approvedIntervals()).reduce((total, interval) => total + interval.end - interval.start, 0);
    elements.cueCount.textContent = String(cues().length);
    elements.statSuggested.textContent = String(suggested);
    elements.statApproved.textContent = `${approvedWords}／${approvedCues}`;
    elements.statDuration.textContent = `${duration.toFixed(2)} 秒`;
    elements.reviewDot.classList.toggle("is-active", approvedWords > 0 || approvedCues > 0);
  }

  function approvedIntervals() {
    const byId = wordsById();
    const intervals = [];
    state.approvedWordIds.forEach((wordId) => {
      const word = byId.get(wordId);
      if (word) intervals.push({ start: Number(word.start), end: Number(word.end) });
    });
    state.approvedCueIds.forEach((cueId) => {
      const cue = cueById(cueId);
      if (cue && Number(cue.source_end) > Number(cue.source_start)) {
        intervals.push({ start: Number(cue.source_start), end: Number(cue.source_end) });
      }
    });
    return intervals.filter((interval) => interval.end > interval.start);
  }

  function mergedIntervals(intervals) {
    const sorted = [...intervals].sort((a, b) => a.start - b.start || a.end - b.end);
    const result = [];
    sorted.forEach((interval) => {
      const previous = result[result.length - 1];
      if (previous && interval.start <= previous.end) {
        previous.end = Math.max(previous.end, interval.end);
      } else {
        result.push({ ...interval });
      }
    });
    return result;
  }

  function renderSelectedCue() {
    const cue = currentCue();
    const hasEdit = Boolean(state.edit);
    const actionButtons = [elements.playCue, elements.keepCue, elements.approveFillers, elements.deleteCue, elements.resetCue];
    actionButtons.forEach((button) => { button.disabled = !cue; });
    if (!cue) {
      elements.selectedTitle.textContent = hasEdit ? "選取左側句子開始審核" : "請先載入語意 JSON";
      elements.selectedStatus.className = "status-badge status-empty";
      elements.selectedStatus.textContent = "未選取";
      elements.selectedTime.textContent = "—";
      elements.selectedZh.textContent = "—";
      elements.selectedEn.textContent = "—";
      elements.wordStrip.innerHTML = "";
      elements.wordHelper.textContent = hasEdit ? "紅色標籤是譯神提出的贅詞候選；點選標籤可以單獨核准或取消。" : "載入 semantic_edit.json 後，這裡會顯示逐字稿與時間碼。";
      elements.previewRange.textContent = "尚未選取句子";
      return;
    }

    const status = getCueStatus(cue);
    elements.selectedTitle.textContent = `第 ${cue.id} 句`;
    elements.selectedStatus.className = `status-badge ${statusClass(status)}`;
    elements.selectedStatus.textContent = statusLabel(status);
    elements.selectedTime.textContent = `${formatTime(cue.source_start, true)} — ${formatTime(cue.source_end, true)} · ${Math.max(0, Number(cue.source_end) - Number(cue.source_start)).toFixed(2)} 秒`;
    elements.selectedZh.textContent = cue.zh || "（無繁中字幕）";
    elements.selectedEn.textContent = cue.en || "（無英文翻譯）";
    elements.previewRange.textContent = `第 ${cue.id} 句 · ${formatTime(cue.source_start)} — ${formatTime(cue.source_end)}`;

    const dropIds = baseDropIds(cue);
    const byId = wordsById();
    elements.wordStrip.innerHTML = cueWordIds(cue).map((wordId) => {
      const word = byId.get(wordId);
      if (!word) return "";
      const isSuggested = dropIds.has(wordId);
      const isApproved = state.approvedWordIds.has(wordId);
      const classes = ["word-chip", isApproved ? "is-approved" : isSuggested ? "is-suggested" : "is-content"].join(" ");
      const action = isSuggested ? " title=\"點擊切換這個贅詞的核准狀態\"" : " title=\"內容詞預設不提供自動刪除\"";
      return `<button class="${classes}" type="button" data-word-id="${escapeHtml(wordId)}"${action}>${escapeHtml(word.text)} <small>${formatTime(word.start)}</small></button>`;
    }).join("");
    elements.wordHelper.textContent = dropIds.size
      ? "橘色是 AI 建議，尚未剪除；點擊橘色詞或按「採用贅詞建議」後，才會進入匯出的 EDL。"
      : "這句沒有 AI 贅詞建議。若確定整句不需要，可選擇「刪除整句」。";
  }

  function render() {
    renderCueList();
    renderSelectedCue();
    renderStats();
  }

  function selectCue(id, shouldPlay = false) {
    const cue = cueById(id);
    if (!cue) return;
    state.selectedCueId = asId(id);
    render();
    const row = elements.cueList.querySelector(`[data-cue-id="${CSS.escape(asId(id))}"]`);
    row?.scrollIntoView({ block: "nearest" });
    if (elements.preview.src && Number.isFinite(Number(cue.source_start))) {
      elements.preview.currentTime = Number(cue.source_start);
      renderSubtitleOverlay(cue);
    }
    if (shouldPlay) playSelectedCue();
  }

  function setCueDecision(cue, decision) {
    if (!cue) return;
    const id = asId(cue.id);
    const ids = new Set(cueWordIds(cue));
    ids.forEach((wordId) => state.approvedWordIds.delete(wordId));
    state.approvedCueIds.delete(id);
    if (decision === "delete") {
      state.approvedCueIds.add(id);
    } else if (decision === "filler") {
      baseDropIds(cue).forEach((wordId) => state.approvedWordIds.add(wordId));
    }
    state.decisions.set(id, decision);
    render();
    setStatus(`已更新第 ${id} 句：${statusLabel(getCueStatus(cue))}`, "success");
  }

  function toggleWord(wordId) {
    const cue = currentCue();
    if (!cue || !baseDropIds(cue).has(asId(wordId))) return;
    const id = asId(wordId);
    state.approvedCueIds.delete(asId(cue.id));
    if (state.approvedWordIds.has(id)) {
      state.approvedWordIds.delete(id);
    } else {
      state.approvedWordIds.add(id);
    }
    const approvedInCue = cueWordIds(cue).some((item) => state.approvedWordIds.has(item));
    state.decisions.set(asId(cue.id), approvedInCue ? "filler" : "pending");
    render();
    setStatus(approvedInCue ? `已核准第 ${cue.id} 句的部分贅詞` : `已取消第 ${cue.id} 句的贅詞核准`, "success");
  }

  function playSelectedCue() {
    const cue = currentCue();
    if (!cue || !elements.preview.src) return;
    const start = Number(cue.source_start) || 0;
    state.playbackEnd = Number(cue.source_end) || null;
    elements.preview.currentTime = start;
    elements.preview.play().catch(() => {});
  }

  function loadEdit(payload, fileName = "semantic_edit.json") {
    if (!payload || !Array.isArray(payload.words) || !Array.isArray(payload.cues)) {
      throw new Error("這不是可審核的 semantic_edit.json：需要 words 與 cues 陣列。請載入譯神輸出的完整語意編輯檔。 ");
    }
    state.edit = payload;
    state.selectedCueId = cues()[0] ? asId(cues()[0].id) : null;
    state.subtitleStyle = normaliseSubtitleStyle(payload.subtitle_style || payload.review?.subtitle_style || {});
    state.approvedWordIds = new Set((payload.review?.approved_word_ids || []).map(asId));
    state.approvedCueIds = new Set((payload.review?.approved_cue_ids || []).map(asId));
    state.decisions = new Map(Object.entries(payload.review?.decision_by_cue || {}).map(([id, value]) => [asId(id), String(value)]));
    cues().forEach((cue) => {
      const id = asId(cue.id);
      if (!state.decisions.has(id)) state.decisions.set(id, baseDropIds(cue).size ? "suggested" : "pending");
    });
    elements.editName.textContent = fileName;
    elements.sourceMeta.textContent = `${cues().length} cues · ${words().length} words · ${formatTime(payload.source_start, true)} — ${formatTime(payload.source_end, true)}`;
    setEnabled(true);
    applySubtitleStyle();
    render();
    renderSubtitleOverlay();
    setStatus("已載入語意編輯；AI 建議尚未剪除，請逐句核准。", "success");
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function makeReviewState() {
    return {
      schema_version: 1,
      tool: "awesome-janson",
      kind: "awesome-janson-review",
      mode: "manual-review",
      source_start: state.edit?.source_start ?? null,
      source_end: state.edit?.source_end ?? null,
      subtitle_style: { ...state.subtitleStyle },
      approved_word_ids: [...state.approvedWordIds],
      approved_cue_ids: [...state.approvedCueIds],
      decision_by_cue: Object.fromEntries(state.decisions.entries()),
    };
  }

  function makeReviewedEdit() {
    const result = cloneJson(state.edit);
    const review = makeReviewState();
    result.review = review;
    result.subtitle_style = { ...state.subtitleStyle };
    const byId = wordsById();
    const fullCueIds = new Set(review.approved_cue_ids.map(asId));
    const approvedWords = new Set(review.approved_word_ids.map(asId));
    result.cues = result.cues.map((cue) => {
      const ids = cueWordIds(cue);
      const deleted = fullCueIds.has(asId(cue.id)) ? ids : ids.filter((id) => approvedWords.has(id));
      return {
        ...cue,
        drop_word_ids: deleted,
        kept_word_ids: ids.filter((id) => !deleted.includes(id)),
      };
    });
    result.deletions = review.approved_word_ids
      .map((wordId) => byId.get(asId(wordId)))
      .filter(Boolean)
      .map((word) => ({
        word_id: asId(word.id),
        start: word.start,
        end: word.end,
        text: word.text,
        reason: "manual-review",
        confidence: 1,
      }));
    result.stats = {
      ...(result.stats || {}),
      word_count: words().length,
      cue_count: cues().length,
      deletion_count: result.deletions.length,
      deleted_duration_s: Number(mergedIntervals(approvedIntervals()).reduce((total, interval) => total + interval.end - interval.start, 0).toFixed(3)),
      manual_deleted_cue_count: review.approved_cue_ids.length,
    };
    return result;
  }

  function downloadJson(payload, filename) {
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function baseName() {
    return (elements.editName.textContent || "semantic_edit.json").replace(/\.json$/i, "");
  }

  function exportReview() {
    if (!state.edit) return;
    downloadJson(makeReviewState(), `${baseName()}_review.json`);
    setStatus("已匯出審核檔；可用 apply_review.py 套用到原始語意 JSON。", "success");
  }

  function exportEdit() {
    if (!state.edit) return;
    downloadJson(makeReviewedEdit(), `${baseName()}_reviewed.json`);
    setStatus("已匯出可直接交給 render_semantic.py 的 reviewed edit JSON。", "success");
  }

  function resetAll(decision = "pending") {
    state.approvedWordIds.clear();
    state.approvedCueIds.clear();
    cues().forEach((cue) => state.decisions.set(asId(cue.id), decision));
    render();
    setStatus(decision === "keep" ? "已全部標記為保留；沒有 AI 建議會被剪除。" : "已清除人工審核，所有建議回到待確認。", "success");
  }

  function loadVideo(file) {
    if (!file) return;
    if (state.videoUrl) URL.revokeObjectURL(state.videoUrl);
    state.videoUrl = URL.createObjectURL(file);
    elements.preview.src = state.videoUrl;
    elements.preview.muted = false;
    elements.preview.volume = 1;
    elements.preview.load();
    elements.videoName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    elements.videoEmpty.hidden = true;
    renderSubtitleOverlay();
    setStatus("影片已載入；點選逐字稿句子或拖曳時間軸，字幕會跟著時間走。", "success");
  }

  elements.editFile.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      loadEdit(JSON.parse(await file.text()), file.name);
    } catch (error) {
      setStatus(error.message || "語意 JSON 載入失敗。", "error");
      alert(error.message || "語意 JSON 載入失敗。 ");
    }
    event.target.value = "";
  });

  elements.videoFile.addEventListener("change", (event) => {
    loadVideo(event.target.files?.[0]);
    event.target.value = "";
  });

  elements.cueList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-cue-id]");
    // 點逐字稿不只選取，也直接跳到並播放對應句子。
    if (row) selectCue(row.dataset.cueId, true);
  });

  elements.wordStrip.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-word-id]");
    if (chip) toggleWord(chip.dataset.wordId);
  });

  elements.search.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderCueList();
  });

  document.querySelectorAll(".filter-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.filter = tab.dataset.filter;
      document.querySelectorAll(".filter-tab").forEach((item) => item.classList.toggle("is-active", item === tab));
      renderCueList();
    });
  });

  elements.playCue.addEventListener("click", playSelectedCue);
  elements.enableAudio.addEventListener("click", enableAudio);
  elements.keepCue.addEventListener("click", () => setCueDecision(currentCue(), "keep"));
  elements.approveFillers.addEventListener("click", () => setCueDecision(currentCue(), "filler"));
  elements.deleteCue.addEventListener("click", () => setCueDecision(currentCue(), "delete"));
  elements.resetCue.addEventListener("click", () => setCueDecision(currentCue(), "pending"));
  elements.approveAll.addEventListener("click", () => {
    state.approvedCueIds.clear();
    cues().forEach((cue) => {
      baseDropIds(cue).forEach((wordId) => state.approvedWordIds.add(wordId));
      if (baseDropIds(cue).size) state.decisions.set(asId(cue.id), "filler");
    });
    render();
    setStatus("已採用全部 AI 贅詞建議；內容詞仍然保留。", "success");
  });
  elements.keepAll.addEventListener("click", () => resetAll("keep"));
  elements.resetAll.addEventListener("click", () => resetAll("pending"));
  elements.exportReview.addEventListener("click", exportReview);
  elements.exportEdit.addEventListener("click", exportEdit);
  elements.zhFontSize.addEventListener("input", (event) => {
    state.subtitleStyle.zh_font_size = Number(event.target.value);
    applySubtitleStyle();
    renderSubtitleOverlay();
  });
  elements.enFontSize.addEventListener("input", (event) => {
    state.subtitleStyle.en_font_size = Number(event.target.value);
    applySubtitleStyle();
    renderSubtitleOverlay();
  });
  elements.showEnglish.addEventListener("change", (event) => {
    state.subtitleStyle.show_english = event.target.checked;
    applySubtitleStyle();
    renderSubtitleOverlay();
  });
  elements.resetSubtitleStyle.addEventListener("click", () => {
    state.subtitleStyle = normaliseSubtitleStyle();
    applySubtitleStyle();
    renderSubtitleOverlay();
    setStatus("已恢復字幕預設大小與英文顯示。", "success");
  });
  window.addEventListener("resize", applySubtitleStyle);

  elements.preview.addEventListener("timeupdate", () => {
    elements.previewTime.textContent = formatTime(elements.preview.currentTime);
    syncCueToVideo();
    if (state.playbackEnd != null && elements.preview.currentTime >= state.playbackEnd) {
      elements.preview.pause();
      state.playbackEnd = null;
    }
  });
  elements.preview.addEventListener("seeked", syncCueToVideo);
  elements.preview.addEventListener("volumechange", () => {
    const muted = elements.preview.muted || elements.preview.volume === 0;
    elements.enableAudio.textContent = muted ? "開啟聲音" : "聲音已開啟";
  });
  elements.preview.addEventListener("loadedmetadata", () => {
    elements.videoEmpty.hidden = true;
    elements.preview.muted = false;
    elements.preview.volume = 1;
    renderSubtitleOverlay();
  });
  elements.preview.addEventListener("error", () => {
    elements.videoEmpty.hidden = false;
    setStatus("影片無法在瀏覽器預覽，但仍可繼續審核 JSON。", "error");
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea, select")) return;
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      playSelectedCue();
      return;
    }
    if (!state.edit || !cues().length) return;
    const currentIndex = cues().findIndex((cue) => asId(cue.id) === asId(state.selectedCueId));
    if (event.key === "ArrowDown" && currentIndex < cues().length - 1) {
      event.preventDefault();
      selectCue(cues()[currentIndex + 1].id);
    }
    if (event.key === "ArrowUp" && currentIndex > 0) {
      event.preventDefault();
      selectCue(cues()[currentIndex - 1].id);
    }
  });

  elements.themeToggle.addEventListener("click", () => {
    const next = document.body.dataset.theme === "dark" ? "light" : "dark";
    document.body.dataset.theme = next;
    elements.themeToggle.textContent = next === "dark" ? "☼" : "☾";
  });

  setEnabled(false);
})();
