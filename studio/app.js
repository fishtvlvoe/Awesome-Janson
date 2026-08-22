(() => {
  "use strict";
  const state = { mode: "mixed", fileUrl: null };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const toast = (message) => { const el = $("#toast"); el.textContent = message; el.classList.add("is-visible"); window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => el.classList.remove("is-visible"), 2600); };

  function setMode(mode) {
    state.mode = mode;
    $$(".choice-card").forEach((card) => { const selected = card.dataset.mode === mode; card.classList.toggle("is-selected", selected); card.setAttribute("aria-checked", String(selected)); });
    $("#mixed-options").hidden = !["mixed", "people"].includes(mode);
    const labels = { talking: "本人為主", cards: "圖卡說明", people: "人物情境", mixed: "混合安排" };
    $("#timeline-label").textContent = labels[mode];
    if (mode === "talking") $$(".segment-people, .segment-cards").forEach((el) => { el.style.display = "none"; });
    else $$(".segment-people, .segment-cards").forEach((el) => { el.style.display = "flex"; });
  }

  $$(".choice-card").forEach((card) => card.addEventListener("click", () => setMode(card.dataset.mode)));
  $("#source-file").addEventListener("change", (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    $("#source-name").textContent = file.name; $("#source-help").textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB · 僅在本機預覽`;
    $("#source-status").textContent = "已選擇"; $("#source-status").classList.add("accent");
    if (state.fileUrl) URL.revokeObjectURL(state.fileUrl); state.fileUrl = URL.createObjectURL(file); $("#preview-video").src = state.fileUrl; $("#preview-empty").hidden = true; toast("影片已載入，可以開始設定。");
  });
  const dropzone = $("#dropzone");
  ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add("is-dragging"); }));
  ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove("is-dragging"); }));
  dropzone.addEventListener("drop", (event) => { const file = event.dataTransfer.files?.[0]; if (!file || !file.type.startsWith("video/")) return toast("請放入影片檔案。"); const input = $("#source-file"); const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; input.dispatchEvent(new Event("change")); });
  $("#advanced-toggle").addEventListener("click", () => { const panel = $("#advanced-panel"); const open = panel.hidden; panel.hidden = !open; $("#advanced-toggle").setAttribute("aria-expanded", String(open)); $("#advanced-toggle span:last-child").textContent = open ? "−" : "＋"; });
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => { $$(".nav-item").forEach((nav) => nav.classList.remove("is-active")); item.classList.add("is-active"); const target = document.querySelector(`[data-section="${item.dataset.nav}"]`); if (target) target.scrollIntoView({ behavior: "smooth", block: "start" }); else toast("這個步驟會在產生分鏡後開啟。"); }));
  $("#make-storyboard").addEventListener("click", () => { if (!$("#source-file").files?.length) return toast("先選一支影片，再產生分鏡。"); $(".preview-badge").textContent = "草稿準備中"; toast("已建立分鏡草稿入口；下一步接上現有剪輯引擎。"); setTimeout(() => { $(".preview-badge").textContent = "分鏡待確認"; }, 1100); });
  $("#reset-project").addEventListener("click", () => { $("#source-file").value = ""; $("#source-name").textContent = "選一支影片"; $("#source-help").textContent = "支援 MP4、MOV；檔案只留在這台電腦"; $("#source-status").textContent = "等待選擇"; $("#source-status").classList.remove("accent"); $("#preview-video").removeAttribute("src"); $("#preview-video").load(); $("#preview-empty").hidden = false; setMode("mixed"); toast("設定已清除。"); });
  setMode("mixed");
})();
