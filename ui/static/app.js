/**
 * PaperToCAD Studio - Client Application Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentFile = null;
  let currentSample = "cir1";
  let currentJobId = null;
  let currentResults = null;
  let zoomLevel = 1.0;
  let activeViewMode = "schematic"; // 'schematic', 'schemdraw', 'annotated', 'original'
  let activeCadTheme = "dark";      // 'dark' or 'light'
  let activeDevice = "cpu";

  // Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const browseBtn = document.getElementById("browseBtn");
  const dropzonePrompt = document.getElementById("dropzonePrompt");
  const dropzonePreview = document.getElementById("dropzonePreview");
  const previewImg = document.getElementById("previewImg");
  const previewFilename = document.getElementById("previewFilename");
  const removeImgBtn = document.getElementById("removeImgBtn");

  const sampleChips = document.querySelectorAll(".sample-chip");
  const confRange = document.getElementById("confRange");
  const confVal = document.getElementById("confVal");
  const deviceToggleBtns = document.querySelectorAll("#deviceToggleGroup .toggle-btn");
  const currentDeviceLabel = document.getElementById("currentDeviceLabel");

  const analyzeBtn = document.getElementById("analyzeBtn");
  const btnSpinner = document.getElementById("btnSpinner");
  const btnText = document.getElementById("btnText");

  const progressCard = document.getElementById("progressCard");
  const progressPct = document.getElementById("progressPct");
  const progressBarFill = document.getElementById("progressBarFill");

  const metricsStrip = document.getElementById("metricsStrip");
  const statComponents = document.getElementById("statComponents");
  const statLabels = document.getElementById("statLabels");
  const statNets = document.getElementById("statNets");
  const statTime = document.getElementById("statTime");

  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  const viewportPlaceholder = document.getElementById("viewportPlaceholder");
  const imageWrapper = document.getElementById("imageWrapper");
  const mainDisplayImg = document.getElementById("mainDisplayImg");
  
  const btnShowSchematic = document.getElementById("btnShowSchematic");
  const btnShowSchemdraw = document.getElementById("btnShowSchemdraw");
  const btnShowAnnotated = document.getElementById("btnShowAnnotated");
  const btnShowOriginal = document.getElementById("btnShowOriginal");
  const btnThemeDark = document.getElementById("btnThemeDark");
  const btnThemeLight = document.getElementById("btnThemeLight");
  const cadThemeGroup = document.getElementById("cadThemeGroup");

  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomResetBtn = document.getElementById("zoomResetBtn");

  const inventoryGrid = document.getElementById("inventoryGrid");
  const inventoryBadge = document.getElementById("inventoryBadge");
  const componentFilter = document.getElementById("componentFilter");
  const classFilterChips = document.getElementById("classFilterChips");


  const spiceCodeBlock = document.getElementById("spiceCodeBlock");
  const spiceFilename = document.getElementById("spiceFilename");
  const jsonCodeBlock = document.getElementById("jsonCodeBlock");
  const terminalBody = document.getElementById("terminalBody");

  const copySpiceBtn = document.getElementById("copySpiceBtn");
  const copyJsonBtn = document.getElementById("copyJsonBtn");
  const clearLogsBtn = document.getElementById("clearLogsBtn");
  const downloadSpiceBtn = document.getElementById("downloadSpiceBtn");
  const downloadJsonBtn = document.getElementById("downloadJsonBtn");
  const toast = document.getElementById("toast");

  // --------------------------------------------------------------------------
  // Sample Selection Handlers
  // --------------------------------------------------------------------------
  sampleChips.forEach(chip => {
    chip.addEventListener("click", () => {
      sampleChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentSample = chip.getAttribute("data-sample");
      currentFile = null;

      // Update preview to sample
      previewImg.src = `/api/samples/image/${currentSample}.jpg`;
      previewFilename.textContent = `${currentSample}.jpg`;
      dropzonePrompt.style.display = "none";
      dropzonePreview.style.display = "block";
      logTerminal(`[SAMPLE] Selected preset diagram: ${currentSample}.jpg`, "cmd");
    });
  });

  // Load default sample preview on start
  if (currentSample) {
    previewImg.src = `/api/samples/image/${currentSample}.jpg`;
    previewFilename.textContent = `${currentSample}.jpg`;
    dropzonePrompt.style.display = "none";
    dropzonePreview.style.display = "block";
  }

  // --------------------------------------------------------------------------
  // Drag and Drop / File Input
  // --------------------------------------------------------------------------
  browseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener("click", () => {
    if (!currentFile && !currentSample) {
      fileInput.click();
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    if (!file.type.startsWith("image/")) {
      showToast("Please select a valid image file (JPG, PNG, WebP).");
      return;
    }
    currentFile = file;
    currentSample = null;
    sampleChips.forEach(c => c.classList.remove("active"));

    const reader = new FileReader();
    reader.onload = (ev) => {
      previewImg.src = ev.target.result;
      previewFilename.textContent = file.name;
      dropzonePrompt.style.display = "none";
      dropzonePreview.style.display = "block";
      logTerminal(`[UPLOAD] Loaded local diagram: ${file.name} (${Math.round(file.size / 1024)} KB)`, "cmd");
    };
    reader.readAsDataURL(file);
  }

  removeImgBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    currentFile = null;
    currentSample = null;
    fileInput.value = "";
    previewImg.src = "";
    dropzonePreview.style.display = "none";
    dropzonePrompt.style.display = "block";
    sampleChips.forEach(c => c.classList.remove("active"));
  });

  // --------------------------------------------------------------------------
  // Sliders and Options
  // --------------------------------------------------------------------------
  confRange.addEventListener("input", (e) => {
    confVal.textContent = parseFloat(e.target.value).toFixed(2);
  });

  deviceToggleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      deviceToggleBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeDevice = btn.getAttribute("data-device");
      currentDeviceLabel.textContent = activeDevice.toUpperCase() + (activeDevice === "cuda" ? " Accelerated" : " Mode");
      logTerminal(`[DEVICE] Compute device set to ${activeDevice.toUpperCase()}`, "info");
    });
  });

  // --------------------------------------------------------------------------
  // Tab Switching
  // --------------------------------------------------------------------------
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(targetId).classList.add("active");
    });
  });

  // --------------------------------------------------------------------------
  // Zoom & View Controls
  // --------------------------------------------------------------------------
  // Zoom & View Controls
  // --------------------------------------------------------------------------
  btnShowSchematic.addEventListener("click", () => {
    if (!currentResults) return;
    activeViewMode = "schematic";
    updateViewModeButtons();
    cadThemeGroup.style.display = "flex";
    mainDisplayImg.src = activeCadTheme === "dark" 
      ? currentResults.images.schematic_cad_dark 
      : currentResults.images.schematic_cad_light;
  });

  btnShowSchemdraw.addEventListener("click", () => {
    if (!currentResults) return;
    activeViewMode = "schemdraw";
    updateViewModeButtons();
    cadThemeGroup.style.display = "none";
    mainDisplayImg.src = currentResults.images.schematic_schemdraw;
  });

  btnShowAnnotated.addEventListener("click", () => {
    if (!currentResults) return;
    activeViewMode = "annotated";
    updateViewModeButtons();
    cadThemeGroup.style.display = "none";
    mainDisplayImg.src = currentResults.images.annotated;
  });

  btnShowOriginal.addEventListener("click", () => {
    if (!currentResults) return;
    activeViewMode = "original";
    updateViewModeButtons();
    cadThemeGroup.style.display = "none";
    mainDisplayImg.src = currentResults.images.original;
  });

  btnThemeDark.addEventListener("click", () => {
    activeCadTheme = "dark";
    btnThemeDark.classList.add("active");
    btnThemeLight.classList.remove("active");
    if (activeViewMode === "schematic" && currentResults) {
      mainDisplayImg.src = currentResults.images.schematic_cad_dark;
    }
  });

  btnThemeLight.addEventListener("click", () => {
    activeCadTheme = "light";
    btnThemeLight.classList.add("active");
    btnThemeDark.classList.remove("active");
    if (activeViewMode === "schematic" && currentResults) {
      mainDisplayImg.src = currentResults.images.schematic_cad_light;
    }
  });

  function updateViewModeButtons() {
    [btnShowSchematic, btnShowSchemdraw, btnShowAnnotated, btnShowOriginal].forEach(b => b.classList.remove("active"));
    if (activeViewMode === "schematic") btnShowSchematic.classList.add("active");
    else if (activeViewMode === "schemdraw") btnShowSchemdraw.classList.add("active");
    else if (activeViewMode === "annotated") btnShowAnnotated.classList.add("active");
    else if (activeViewMode === "original") btnShowOriginal.classList.add("active");
  }

  zoomInBtn.addEventListener("click", () => {
    zoomLevel = Math.min(zoomLevel + 0.25, 3.0);
    applyZoom();
  });

  zoomOutBtn.addEventListener("click", () => {
    zoomLevel = Math.max(zoomLevel - 0.25, 0.5);
    applyZoom();
  });

  zoomResetBtn.addEventListener("click", () => {
    zoomLevel = 1.0;
    applyZoom();
  });

  function applyZoom() {
    imageWrapper.style.transform = `scale(${zoomLevel})`;
  }

  // --------------------------------------------------------------------------
  // Pipeline Execution Action
  // --------------------------------------------------------------------------
  analyzeBtn.addEventListener("click", async () => {
    if (!currentFile && !currentSample) {
      showToast("Please choose a sample circuit or upload an image first.");
      return;
    }

    // Set UI to loading state
    analyzeBtn.disabled = true;
    btnSpinner.style.display = "inline-block";
    btnText.innerHTML = "Processing Diagram...";
    progressCard.style.display = "block";
    updateProgress(15, "step-init");

    const formData = new FormData();
    if (currentFile) {
      formData.append("file", currentFile);
    } else if (currentSample) {
      formData.append("sample_name", currentSample);
    }
    formData.append("conf_threshold", confRange.value);
    formData.append("device", activeDevice);

    logTerminal("\n---------------------------------------------------------", "cmd");
    logTerminal(`[PIPELINE] Launching PaperToCAD Engine (${activeDevice.toUpperCase()})...`, "cmd");

    const timerInterval = setInterval(() => {
      const curPct = parseInt(progressPct.textContent) || 15;
      if (curPct < 85) {
        let step = "step-yolo";
        if (curPct > 35) step = "step-crops";
        if (curPct > 55) step = "step-parseq";
        if (curPct > 70) step = "step-spice";
        updateProgress(curPct + 10, step);
      }
    }, 450);

    try {
      const response = await fetch("/api/process", {
        method: "POST",
        body: formData
      });

      clearInterval(timerInterval);

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Server error occurred");
      }

      const data = await response.json();
      currentResults = data;
      currentJobId = data.job_id;

      updateProgress(100, "step-spice");
      setTimeout(() => {
        progressCard.style.display = "none";
      }, 1200);

      renderResults(data);
      showToast("Circuit converted to SPICE successfully!");
    } catch (err) {
      clearInterval(timerInterval);
      progressCard.style.display = "none";
      logTerminal(`[ERROR] Execution failed: ${err.message}`, "warn");
      showToast(`Error: ${err.message}`);
    } finally {
      analyzeBtn.disabled = false;
      btnSpinner.style.display = "none";
      btnText.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Convert to SPICE Netlist';
    }
  });

  // --------------------------------------------------------------------------
  // Progress & Terminal Logging
  // --------------------------------------------------------------------------
  function updateProgress(pct, activeStepId) {
    progressPct.textContent = `${pct}%`;
    progressBarFill.style.width = `${pct}%`;

    const steps = ["step-init", "step-yolo", "step-crops", "step-parseq", "step-spice"];
    const activeIdx = steps.indexOf(activeStepId);

    steps.forEach((sId, idx) => {
      const el = document.getElementById(sId);
      if (idx < activeIdx) {
        el.className = "step-item done";
        el.querySelector("i").className = "fa-solid fa-circle-check";
      } else if (idx === activeIdx) {
        el.className = "step-item active";
        el.querySelector("i").className = "fa-solid fa-circle-dot";
      } else {
        el.className = "step-item";
        el.querySelector("i").className = "fa-solid fa-circle-dot";
      }
    });
  }

  function logTerminal(msg, type = "normal") {
    const line = document.createElement("div");
    line.className = `log-line ${type === "cmd" ? "log-cmd" : type === "ok" ? "log-ok" : type === "warn" ? "log-warn" : ""}`;
    line.textContent = msg;
    terminalBody.appendChild(line);
    terminalBody.scrollTop = terminalBody.scrollHeight;
  }

  clearLogsBtn.addEventListener("click", () => {
    terminalBody.innerHTML = '<div class="log-line log-info">[SYSTEM] Terminal logs cleared.</div>';
  });

  // --------------------------------------------------------------------------
  // Render Results Dashboard
  // --------------------------------------------------------------------------
  function renderResults(data) {
    // 1. Logs
    if (data.logs) {
      data.logs.forEach(l => {
        let type = "normal";
        if (l.includes("[OK]") || l.includes("[DONE]")) type = "ok";
        else if (l.includes("[WARN]")) type = "warn";
        else if (l.startsWith(">>>") || l.startsWith("[")) type = "cmd";
        logTerminal(l, type);
      });
    }

    // 2. Metrics strip
    statComponents.textContent = data.stats.total_components;
    statLabels.textContent = data.stats.total_labels;
    statNets.textContent = (data.spice_netlist.match(/^[RCLVDIMQX]/gm) || []).length;
    statTime.textContent = data.stats.processing_time;
    metricsStrip.style.display = "grid";

    // 3. Visual Viewer (Default to Computerized CAD Schematic!)
    viewportPlaceholder.style.display = "none";
    imageWrapper.style.display = "inline-block";
    activeViewMode = "schematic";
    updateViewModeButtons();
    cadThemeGroup.style.display = "flex";
    mainDisplayImg.src = activeCadTheme === "dark" 
      ? data.images.schematic_cad_dark 
      : data.images.schematic_cad_light;
    zoomLevel = 1.0;
    applyZoom();

    // 4. Component Inventory
    inventoryBadge.textContent = data.components.length;
    renderComponentInventory(data.components);

    // 5. SPICE Netlist
    spiceFilename.textContent = `${data.image_name}.cir`;
    spiceCodeBlock.textContent = data.spice_netlist;

    // 6. JSON Graph
    jsonCodeBlock.textContent = JSON.stringify(data, null, 2);
  }

  // --------------------------------------------------------------------------
  // Render Component Inventory
  // --------------------------------------------------------------------------
  function renderComponentInventory(components) {
    inventoryGrid.innerHTML = "";
    
    // Extract unique classes for filter chips
    const uniqueClasses = ["all", ...new Set(components.map(c => c.cls_name))];
    classFilterChips.innerHTML = "";
    uniqueClasses.forEach(cls => {
      const chip = document.createElement("button");
      chip.className = `filter-chip ${cls === "all" ? "active" : ""}`;
      chip.setAttribute("data-class", cls);
      chip.textContent = cls === "all" ? "All" : cls;
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        filterComponentCards(cls, componentFilter.value.trim().toLowerCase());
      });
      classFilterChips.appendChild(chip);
    });

    components.forEach(comp => {
      const card = document.createElement("div");
      card.className = "comp-card";
      card.setAttribute("data-class", comp.cls_name);

      const colorHex = comp.color || "#00f0ff";
      const badgeStyle = `background: ${colorHex}25; color: ${colorHex}; border: 1px solid ${colorHex}40;`;

      card.innerHTML = `
        <div class="comp-card-top">
          <span class="comp-badge" style="${badgeStyle}">
            ${comp.cls_name}
          </span>
          <span class="comp-conf">${Math.round(comp.confidence * 100)}% conf</span>
        </div>
        <div class="comp-thumb-box">
          <img src="${comp.crop_url || ''}" alt="${comp.cls_name}" onerror="this.style.display='none'">
        </div>
        <div class="comp-details">
          ${comp.text_label ? `<div class="comp-val-tag">${comp.text_label}</div>` : ''}
          <div class="comp-bbox-meta">
            BBox: [${comp.bbox.join(", ")}]
          </div>
        </div>
      `;
      inventoryGrid.appendChild(card);
    });
  }

  componentFilter.addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    const activeChip = document.querySelector(".filter-chip.active");
    const activeCls = activeChip ? activeChip.getAttribute("data-class") : "all";
    filterComponentCards(activeCls, q);
  });

  function filterComponentCards(cls, query) {
    const cards = inventoryGrid.querySelectorAll(".comp-card");
    cards.forEach(card => {
      const cardCls = card.getAttribute("data-class");
      const matchCls = (cls === "all" || cardCls === cls);
      const matchQuery = (!query || cardCls.toLowerCase().includes(query) || card.textContent.toLowerCase().includes(query));
      card.style.display = (matchCls && matchQuery) ? "flex" : "none";
    });
  }

  // --------------------------------------------------------------------------
  // Copy & Export Handlers
  // --------------------------------------------------------------------------
  copySpiceBtn.addEventListener("click", () => {
    if (!currentResults) return;
    navigator.clipboard.writeText(currentResults.spice_netlist);
    showToast("SPICE netlist copied to clipboard!");
  });

  copyJsonBtn.addEventListener("click", () => {
    if (!currentResults) return;
    navigator.clipboard.writeText(JSON.stringify(currentResults, null, 2));
    showToast("JSON graph copied to clipboard!");
  });

  const downloadSchematicBtn = document.getElementById("downloadSchematicBtn");
  if (downloadSchematicBtn) {
    downloadSchematicBtn.addEventListener("click", () => {
      if (!currentJobId) return;
      window.location.href = `/api/jobs/${currentJobId}/download/schematic?theme=${activeCadTheme}`;
    });
  }

  downloadSpiceBtn.addEventListener("click", () => {
    if (!currentJobId) return;
    window.location.href = `/api/jobs/${currentJobId}/download/spice`;
  });

  downloadJsonBtn.addEventListener("click", () => {
    if (!currentJobId) return;
    window.location.href = `/api/jobs/${currentJobId}/download/json`;
  });

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2500);
  }
});
