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
  let activeViewMode = "dual"; // 'dual', 'schematic', 'schemdraw', 'annotated'
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

  const sketchImageWrapper = document.getElementById("sketchImageWrapper");
  const cadImageWrapper = document.getElementById("cadImageWrapper");
  const sketchCanvasViewport = document.getElementById("sketchCanvasViewport");
  const cadCanvasViewport = document.getElementById("cadCanvasViewport");
  const mainDisplayImg = document.getElementById("mainDisplayImg");
  const sketchDisplayImg = document.getElementById("sketchDisplayImg");
  const sketchBboxSvg = document.getElementById("sketchBboxSvg");
  const compPopover = document.getElementById("compPopover");
  const popoverCloseBtn = document.getElementById("popoverCloseBtn");
  const popoverEditBtn = document.getElementById("popoverEditBtn");
  const selectionBox = document.getElementById("selectionBox");
  const dualViewportGrid = document.getElementById("dualViewportGrid");
  
  const btnShowDual = document.getElementById("btnShowDual");
  const btnShowSchematic = document.getElementById("btnShowSchematic");
  const btnShowSchemdraw = document.getElementById("btnShowSchemdraw");
  const btnShowAnnotated = document.getElementById("btnShowAnnotated");
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

  // Cached components for highlighting
  let loadedComponentsMap = {};

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

      // Auto-load circuit data into all panels
      loadPresetCircuit(currentSample);
    });
  });

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
  function switchTab(targetId) {
    if (!targetId) return;
    document.querySelectorAll(".tab-btn").forEach(b => {
      if (b.getAttribute("data-tab") === targetId) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
    document.querySelectorAll(".tab-pane").forEach(p => {
      if (p.id === targetId) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });
  }

  const dashboardTabs = document.querySelector(".dashboard-tabs");
  if (dashboardTabs) {
    dashboardTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (btn) {
        e.preventDefault();
        const tid = btn.getAttribute("data-tab");
        switchTab(tid);
      }
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute("data-tab");
      switchTab(targetId);
    });
  });

  // --------------------------------------------------------------------------
  // Zoom & View Controls & Interactive Marking
  // --------------------------------------------------------------------------
  let cachedInspectorComponents = [];

  function updateViewModeButtons() {
    [btnShowDual, btnShowSchematic, btnShowSchemdraw, btnShowAnnotated].forEach(b => b && b.classList.remove("active"));
    const cards = document.querySelectorAll(".viewport-card");
    const jobId = currentJobId || currentSample || "cir1";

    if (activeViewMode === "dual") {
      if (btnShowDual) btnShowDual.classList.add("active");
      if (dualViewportGrid) dualViewportGrid.style.gridTemplateColumns = "1fr 1fr";
      if (cards[0]) cards[0].style.display = "flex";
      if (cards[1]) cards[1].style.display = "flex";
      if (cadThemeGroup) cadThemeGroup.style.display = "flex";
      if (sketchDisplayImg) sketchDisplayImg.src = `/api/samples/image/${jobId}.jpg`;
      if (mainDisplayImg) mainDisplayImg.src = `/api/jobs/${jobId}/schematic/${activeCadTheme}?t=${Date.now()}`;
      if (sketchBboxSvg) sketchBboxSvg.style.display = "block";
    } else if (activeViewMode === "schematic") {
      if (btnShowSchematic) btnShowSchematic.classList.add("active");
      if (dualViewportGrid) dualViewportGrid.style.gridTemplateColumns = "1fr";
      if (cards[0]) cards[0].style.display = "none";
      if (cards[1]) cards[1].style.display = "flex";
      if (cadThemeGroup) cadThemeGroup.style.display = "flex";
      if (mainDisplayImg) mainDisplayImg.src = `/api/jobs/${jobId}/schematic/${activeCadTheme}?t=${Date.now()}`;
    } else if (activeViewMode === "schemdraw") {
      if (btnShowSchemdraw) btnShowSchemdraw.classList.add("active");
      if (dualViewportGrid) dualViewportGrid.style.gridTemplateColumns = "1fr";
      if (cards[0]) cards[0].style.display = "none";
      if (cards[1]) cards[1].style.display = "flex";
      if (cadThemeGroup) cadThemeGroup.style.display = "none";
      if (mainDisplayImg) mainDisplayImg.src = `/api/jobs/${jobId}/schematic/schemdraw?t=${Date.now()}`;
    } else if (activeViewMode === "annotated") {
      if (btnShowAnnotated) btnShowAnnotated.classList.add("active");
      if (dualViewportGrid) dualViewportGrid.style.gridTemplateColumns = "1fr";
      if (cards[0]) cards[0].style.display = "flex";
      if (cards[1]) cards[1].style.display = "none";
      if (cadThemeGroup) cadThemeGroup.style.display = "none";
      if (sketchDisplayImg) sketchDisplayImg.src = `/api/jobs/${jobId}/annotated?t=${Date.now()}`;
      if (sketchBboxSvg) sketchBboxSvg.style.display = "block";
    }
  }

  if (btnShowDual) {
    btnShowDual.addEventListener("click", () => {
      activeViewMode = "dual";
      updateViewModeButtons();
      showToast("View: Side-by-Side Dual View");
    });
  }

  if (btnShowSchematic) {
    btnShowSchematic.addEventListener("click", () => {
      activeViewMode = "schematic";
      updateViewModeButtons();
      showToast("View: Full CAD Schematic");
    });
  }

  if (btnShowSchemdraw) {
    btnShowSchemdraw.addEventListener("click", () => {
      activeViewMode = "schemdraw";
      updateViewModeButtons();
      showToast("View: Schemdraw Schematic");
    });
  }

  if (btnShowAnnotated) {
    btnShowAnnotated.addEventListener("click", () => {
      activeViewMode = "annotated";
      updateViewModeButtons();
      showToast("View: Sketch BBoxes & Detections");
    });
  }

  if (btnThemeDark) {
    btnThemeDark.addEventListener("click", () => {
      activeCadTheme = "dark";
      btnThemeDark.classList.add("active");
      if (btnThemeLight) btnThemeLight.classList.remove("active");
      const jobId = currentJobId || currentSample || "cir1";
      if (mainDisplayImg) {
        mainDisplayImg.src = `/api/jobs/${jobId}/schematic/dark?t=${Date.now()}`;
      }
    });
  }

  if (btnThemeLight) {
    btnThemeLight.addEventListener("click", () => {
      activeCadTheme = "light";
      btnThemeLight.classList.add("active");
      if (btnThemeDark) btnThemeDark.classList.remove("active");
      const jobId = currentJobId || currentSample || "cir1";
      if (mainDisplayImg) {
        mainDisplayImg.src = `/api/jobs/${jobId}/schematic/light?t=${Date.now()}`;
      }
    });
  }

  // --------------------------------------------------------------------------
  // Interactive Component BBoxes, Identification, & Port Landmarks
  // --------------------------------------------------------------------------
  function renderInteractiveBBoxes(components) {
    if (!sketchBboxSvg || !sketchDisplayImg) return;
    cachedInspectorComponents = components || [];

    const naturalW = sketchDisplayImg.naturalWidth || 1198;
    const naturalH = sketchDisplayImg.naturalHeight || 683;

    sketchBboxSvg.setAttribute("viewBox", `0 0 ${naturalW} ${naturalH}`);
    sketchBboxSvg.setAttribute("preserveAspectRatio", "none");
    sketchBboxSvg.innerHTML = "";

    if (!components || !components.length) return;

    components.forEach(comp => {
      if (!comp.bbox || comp.bbox.length !== 4) return;
      const [x1, y1, x2, y2] = comp.bbox;
      const w = Math.max(12, x2 - x1);
      const h = Math.max(12, y2 - y1);

      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "comp-bbox-group");
      g.setAttribute("data-id", comp.id);

      // Bounding box rectangle
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "comp-bbox-rect");
      rect.setAttribute("x", x1);
      rect.setAttribute("y", y1);
      rect.setAttribute("width", w);
      rect.setAttribute("height", h);
      g.appendChild(rect);

      // Component identification label pill
      const label = `${comp.display_type || comp.type}${comp.value ? ': ' + comp.value : ''}`;
      const pillW = Math.max(50, label.length * 7.5 + 16);
      const pillH = 18;
      const pillY = Math.max(0, y1 - pillH - 2);

      const pillRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      pillRect.setAttribute("class", "comp-bbox-pill");
      pillRect.setAttribute("x", x1);
      pillRect.setAttribute("y", pillY);
      pillRect.setAttribute("width", pillW);
      pillRect.setAttribute("height", pillH);
      g.appendChild(pillRect);

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("class", "comp-bbox-text");
      text.setAttribute("x", x1 + 6);
      text.setAttribute("y", pillY + 13);
      text.textContent = label;
      g.appendChild(text);

      // Terminal port landmarks
      if (comp.terminals && Array.isArray(comp.terminals)) {
        comp.terminals.forEach((term, idx) => {
          if (term.sketch_coordinates && term.sketch_coordinates.x !== undefined) {
            const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            const termClass = (term.name || `t${idx+1}`).toLowerCase();
            dot.setAttribute("class", `comp-port-dot terminal-${termClass}`);
            dot.setAttribute("cx", term.sketch_coordinates.x);
            dot.setAttribute("cy", term.sketch_coordinates.y);
            dot.setAttribute("r", "5");

            const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
            title.textContent = `${term.name || 'Pin'} (Node ${term.connected_node_id !== null ? term.connected_node_id : 'Open'})`;
            dot.appendChild(title);

            g.appendChild(dot);
          }
        });
      }

      // Click on component box to open details and editor
      g.addEventListener("click", (e) => {
        e.stopPropagation();
        openComponentDetails(comp);
      });

      sketchBboxSvg.appendChild(g);
    });
  }

  function openComponentDetails(comp) {
    if (!comp) return;

    // 1. Mark selected in SVG overlay
    document.querySelectorAll(".comp-bbox-group").forEach(el => el.classList.remove("selected"));
    const group = document.querySelector(`.comp-bbox-group[data-id="${comp.id}"]`);
    if (group) group.classList.add("selected");

    // 2. Populate and display floating popover
    if (compPopover) {
      const popoverBadge = document.getElementById("popoverBadge");
      const popoverId = document.getElementById("popoverId");
      const popoverValue = document.getElementById("popoverValue");
      const popoverConf = document.getElementById("popoverConf");
      const popoverTerminals = document.getElementById("popoverTerminals");

      if (popoverBadge) popoverBadge.textContent = (comp.display_type || comp.type || "COMPONENT").toUpperCase();
      if (popoverId) popoverId.textContent = `#${comp.id}`;
      if (popoverValue) popoverValue.textContent = comp.value || comp.label || "Unspecified";
      if (popoverConf) popoverConf.textContent = `${Math.round((comp.confidence || 0.95) * 100)}%`;

      if (popoverTerminals) {
        popoverTerminals.innerHTML = "";
        (comp.terminals || []).forEach(t => {
          const span = document.createElement("span");
          span.className = "popover-term-badge";
          span.textContent = `${t.name}: Net ${t.connected_node_id !== null ? t.connected_node_id : 'Open'}`;
          popoverTerminals.appendChild(span);
        });
      }

      // Position popover over the component
      if (sketchDisplayImg && sketchDisplayImg.clientWidth > 0 && comp.bbox) {
        const [x1, y1, x2, y2] = comp.bbox;
        const scaleX = sketchDisplayImg.clientWidth / (sketchDisplayImg.naturalWidth || 1198);
        const scaleY = sketchDisplayImg.clientHeight / (sketchDisplayImg.naturalHeight || 683);
        const posX = Math.min(sketchDisplayImg.clientWidth - 275, Math.max(10, x1 * scaleX));
        const posY = Math.min(sketchDisplayImg.clientHeight - 190, Math.max(10, (y2 * scaleY) + 8));
        compPopover.style.left = `${posX}px`;
        compPopover.style.top = `${posY}px`;
      }
      compPopover.style.display = "block";
    }

    // 3. Highlight corresponding table row in Inspector and scroll into view
    document.querySelectorAll("#inspectorTableBody tr").forEach(r => r.style.background = "");
    const editBtn = document.querySelector(`.btn-edit-sm[data-id="${comp.id}"]`);
    if (editBtn && editBtn.closest("tr")) {
      const tr = editBtn.closest("tr");
      tr.style.background = "rgba(251, 191, 36, 0.2)";
      tr.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // 4. Populate inspector edit card
    currentEditingCompId = comp.id;
    if (editCompId) editCompId.textContent = `#${comp.id} (${comp.display_type || comp.type})`;
    if (editValueInput) editValueInput.value = comp.value || "";
    if (editTypeSelect) editTypeSelect.value = comp.type || "resistor";
    const termSelect = document.getElementById("editTerminalSelect");
    if (termSelect) {
      termSelect.innerHTML = '<option value="">Select Pin...</option>';
      (comp.terminals || []).forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.terminal_id !== undefined ? t.terminal_id : t.id;
        opt.textContent = `${t.name} (currently Node ${t.connected_node_id !== null ? t.connected_node_id : 'Open'})`;
        termSelect.appendChild(opt);
      });
    }

    showToast(`Identified & Opened Component #${comp.id}: ${comp.display_type || comp.type}`);
  }

  if (popoverCloseBtn) {
    popoverCloseBtn.addEventListener("click", () => {
      if (compPopover) compPopover.style.display = "none";
      document.querySelectorAll(".comp-bbox-group").forEach(el => el.classList.remove("selected"));
    });
  }

  if (popoverEditBtn) {
    popoverEditBtn.addEventListener("click", () => {
      switchTab("tab-inspector");
      if (graphEditCard) graphEditCard.style.display = "block";
      showToast(`Editing Component #${currentEditingCompId} in Inspector`);
    });
  }

  if (sketchDisplayImg) {
    sketchDisplayImg.addEventListener("load", () => {
      if (cachedInspectorComponents && cachedInspectorComponents.length) {
        renderInteractiveBBoxes(cachedInspectorComponents);
      }
    });
  }

  // --------------------------------------------------------------------------
  // Drag to Pan Viewports & Zoom
  // --------------------------------------------------------------------------
  function makeViewportDraggable(viewport) {
    if (!viewport) return;
    let isDown = false;
    let startX = 0, startY = 0, scrollLeft = 0, scrollTop = 0;

    viewport.addEventListener("mousedown", (e) => {
      if (e.target.closest(".comp-bbox-group, .comp-popover, button, select, input, a")) return;
      isDown = true;
      viewport.classList.add("is-dragging");
      startX = e.pageX - viewport.offsetLeft;
      startY = e.pageY - viewport.offsetTop;
      scrollLeft = viewport.scrollLeft;
      scrollTop = viewport.scrollTop;
    });

    viewport.addEventListener("mouseleave", () => {
      isDown = false;
      viewport.classList.remove("is-dragging");
    });

    viewport.addEventListener("mouseup", () => {
      isDown = false;
      viewport.classList.remove("is-dragging");
    });

    viewport.addEventListener("mousemove", (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - viewport.offsetLeft;
      const y = e.pageY - viewport.offsetTop;
      const walkX = (x - startX) * 1.5;
      const walkY = (y - startY) * 1.5;
      viewport.scrollLeft = scrollLeft - walkX;
      viewport.scrollTop = scrollTop - walkY;
    });
  }

  makeViewportDraggable(sketchCanvasViewport);
  makeViewportDraggable(cadCanvasViewport);

  async function loadPresetCircuit(sampleName) {
    currentJobId = sampleName;
    currentSample = sampleName;

    // 1. Set images
    if (sketchDisplayImg) sketchDisplayImg.src = `/api/samples/image/${sampleName}.jpg`;
    if (mainDisplayImg) mainDisplayImg.src = `/api/jobs/${sampleName}/schematic/${activeCadTheme}?t=${Date.now()}`;

    // 2. Fetch data in parallel
    await Promise.all([
      loadInspectorData(sampleName),
      loadValidationData(sampleName),
      loadNetlistAndJson(sampleName)
    ]);

    // 3. Show metrics
    if (metricsStrip) metricsStrip.style.display = "grid";
  }

  async function loadNetlistAndJson(circuitId) {
    try {
      const sRes = await fetch(`/api/jobs/${circuitId}/download/spice`);
      if (sRes.ok) {
        const text = await sRes.text();
        if (spiceCodeBlock) spiceCodeBlock.textContent = text;
        if (spiceFilename) spiceFilename.textContent = `${circuitId}.cir`;
        if (statNets) statNets.textContent = (text.match(/^[RCLVDIMQX]/gm) || []).length;
      }
      const jRes = await fetch(`/api/jobs/${circuitId}/download/json`);
      if (jRes.ok) {
        const jdata = await jRes.json();
        if (jsonCodeBlock) jsonCodeBlock.textContent = JSON.stringify(jdata, null, 2);
        if (statComponents) statComponents.textContent = (jdata.components || []).length;
        if (statLabels) statLabels.textContent = (jdata.texts || []).length;
        renderComponentInventory(jdata.components || []);
      }
    } catch (e) {
      console.error("Netlist load failed:", e);
    }
  }

  function highlightComponentOnSketch(comp) {
    openComponentDetails(comp);
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
    const sketchWrap = document.getElementById("sketchImageWrapper");
    const cadWrap = document.getElementById("cadImageWrapper");
    [sketchWrap, cadWrap].forEach(wrap => {
      if (!wrap) return;
      wrap.style.transform = `scale(${zoomLevel})`;
      if (zoomLevel > 1) {
        wrap.style.transformOrigin = "top left";
        const pad = `${(zoomLevel - 1) * 60}%`;
        wrap.style.marginRight = pad;
        wrap.style.marginBottom = pad;
        wrap.style.marginLeft = "0";
        wrap.style.marginTop = "0";
      } else {
        wrap.style.transformOrigin = "center center";
        wrap.style.margin = "auto";
      }
    });
  }

  // --------------------------------------------------------------------------
  // Pipeline Execution Action
  // --------------------------------------------------------------------------
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", async () => {
      if (!currentFile && !currentSample) {
        currentSample = "cir1";
      }

      // Set UI to loading state
      analyzeBtn.disabled = true;
      if (btnSpinner) btnSpinner.style.display = "inline-block";
      if (btnText) btnText.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing Diagram...';
      if (progressCard) progressCard.style.display = "block";
      updateProgress(15, "step-init");

      const formData = new FormData();
      if (currentFile) {
        formData.append("file", currentFile);
      } else if (currentSample) {
        formData.append("sample_name", currentSample);
      }
      formData.append("conf_threshold", confRange ? confRange.value : "0.35");
      formData.append("device", activeDevice || "cpu");

      logTerminal("\n---------------------------------------------------------", "cmd");
      logTerminal(`[PIPELINE] Launching PaperToCAD Engine (${(activeDevice || "CPU").toUpperCase()})...`, "cmd");

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
}

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

    // 3. Visual Viewer (Default to Side-by-Side Dual View)
    activeViewMode = "dual";
    updateViewModeButtons();
    cadThemeGroup.style.display = "flex";

    if (sketchDisplayImg && data.images) {
      sketchDisplayImg.src = data.images.annotated || data.images.original;
    }
    if (mainDisplayImg && data.images) {
      mainDisplayImg.src = activeCadTheme === "dark" 
        ? data.images.schematic_cad_dark 
        : data.images.schematic_cad_light;
    }
    zoomLevel = 1.0;
    applyZoom();

    // 4. Component Inventory
    if (inventoryBadge) inventoryBadge.textContent = data.components.length;
    renderComponentInventory(data.components);

    // 5. SPICE Netlist
    if (spiceFilename) spiceFilename.textContent = `${data.image_name}.cir`;
    if (spiceCodeBlock) spiceCodeBlock.textContent = data.spice_netlist;

    // 6. JSON Graph
    if (jsonCodeBlock) jsonCodeBlock.textContent = JSON.stringify(data, null, 2);

    // 7. Load all newly added Paper2CAD components
    if (data.job_id) {
      loadInspectorData(data.job_id);
      loadValidationData(data.job_id);
    }
  }

  // --------------------------------------------------------------------------
  // Render Component Inventory
  // --------------------------------------------------------------------------
  function renderComponentInventory(components) {
    if (!inventoryGrid || !classFilterChips) return;
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
        if (componentFilter) filterComponentCards(cls, componentFilter.value.trim().toLowerCase());
      });
      classFilterChips.appendChild(chip);
    });

    components.forEach(comp => {
      const card = document.createElement("div");
      card.className = "comp-card";
      card.setAttribute("data-class", comp.cls_name);
      card.style.cursor = "pointer";

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

      card.addEventListener("click", () => {
        highlightComponentOnSketch(comp);
        showToast(`Highlighted ${comp.cls_name || 'component'} #${comp.id} on sketch`);
      });

      inventoryGrid.appendChild(card);
    });
  }

  if (componentFilter) {
    componentFilter.addEventListener("input", (e) => {
      const q = e.target.value.trim().toLowerCase();
      const activeChip = document.querySelector(".filter-chip.active");
      const activeCls = activeChip ? activeChip.getAttribute("data-class") : "all";
      filterComponentCards(activeCls, q);
    });
  }

  function filterComponentCards(cls, query) {
    if (!inventoryGrid) return;
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
  if (copySpiceBtn) {
    copySpiceBtn.addEventListener("click", () => {
      if (!currentResults) return;
      navigator.clipboard.writeText(currentResults.spice_netlist);
      showToast("SPICE netlist copied to clipboard!");
    });
  }

  if (copyJsonBtn) {
    copyJsonBtn.addEventListener("click", () => {
      if (!currentResults) return;
      navigator.clipboard.writeText(JSON.stringify(currentResults, null, 2));
      showToast("JSON graph copied to clipboard!");
    });
  }

  const downloadSchematicBtn = document.getElementById("downloadSchematicBtn");
  if (downloadSchematicBtn) {
    downloadSchematicBtn.addEventListener("click", () => {
      if (!currentJobId) return;
      window.location.href = `/api/jobs/${currentJobId}/download/schematic?theme=${activeCadTheme}`;
    });
  }

  if (downloadSpiceBtn) {
    downloadSpiceBtn.addEventListener("click", () => {
      if (!currentJobId) return;
      window.location.href = `/api/jobs/${currentJobId}/download/spice`;
    });
  }

  if (downloadJsonBtn) {
    downloadJsonBtn.addEventListener("click", () => {
      if (!currentJobId) return;
      window.location.href = `/api/jobs/${currentJobId}/download/json`;
    });
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2500);
  }

  // --------------------------------------------------------------------------
  // Paper2CAD: Connectivity Inspector, Validation, AI & Simulation
  // --------------------------------------------------------------------------
  const inspectorNodesList = document.getElementById("inspectorNodesList");
  const inspectorTableBody = document.getElementById("inspectorTableBody");
  const nodeCountLabel = document.getElementById("nodeCountLabel");
  const graphEditCard = document.getElementById("graphEditCard");
  const editCompId = document.getElementById("editCompId");
  const editValueInput = document.getElementById("editValueInput");
  const editTypeSelect = document.getElementById("editTypeSelect");
  const closeEditBtn = document.getElementById("closeEditBtn");
  const saveCompEditBtn = document.getElementById("saveCompEditBtn");

  const valErrorCount = document.getElementById("valErrorCount");
  const valWarningCount = document.getElementById("valWarningCount");
  const valInfoCount = document.getElementById("valInfoCount");
  const validationBadge = document.getElementById("validationBadge");
  const validationFindingsList = document.getElementById("validationFindingsList");

  const aiQuestionInput = document.getElementById("aiQuestionInput");
  const aiSendBtn = document.getElementById("aiSendBtn");
  const aiChatThread = document.getElementById("aiChatThread");
  const promptChips = document.querySelectorAll(".prompt-chip");

  const simAnalysisSelect = document.getElementById("simAnalysisSelect");
  const runSimBtn = document.getElementById("runSimBtn");
  const simStatusText = document.getElementById("simStatusText");
  const simVoltagesWrap = document.getElementById("simVoltagesWrap");
  const simCurrentsWrap = document.getElementById("simCurrentsWrap");
  const simConsoleOutput = document.getElementById("simConsoleOutput");

  let currentEditingCompId = null;

  async function loadInspectorData(jobId) {
    try {
      const res = await fetch(`/api/jobs/${jobId}/inspect`);
      if (!res.ok) return;
      const data = await res.json();
      renderInspectorNodes(data.nodes || []);
      renderInspectorComponents(data.components || []);
      renderInteractiveBBoxes(data.components || []);
    } catch (e) {
      console.error("Inspector load failed:", e);
    }
  }

  function renderInspectorNodes(nodes) {
    if (!inspectorNodesList) return;
    nodeCountLabel.textContent = `${nodes.length} nodes`;
    inspectorNodesList.innerHTML = "";

    if (nodes.length === 0) {
      inspectorNodesList.innerHTML = '<div class="empty-state"><p>No electrical nodes detected.</p></div>';
      return;
    }

    nodes.forEach(n => {
      const card = document.createElement("div");
      card.className = "node-item-card";
      const isGnd = n.is_ground || n.name === "0";
      card.innerHTML = `
        <div class="node-item-header">
          <span>Net #${n.node_id} (${n.name})</span>
          <span class="node-badge ${isGnd ? 'gnd' : ''}">${isGnd ? 'GROUND' : n.connections.length + ' pins'}</span>
        </div>
        <div class="node-connections-preview">
          Connected: ${n.connections.map(c => `<b>${c.component_type} #${c.component_id}</b> (${c.terminal_name})`).join(", ") || "None"}
        </div>
      `;

      card.addEventListener("click", () => {
        document.querySelectorAll(".node-item-card").forEach(c => c.classList.remove("active"));
        card.classList.add("active");
        
        // Highlight rows in table attached to this node
        document.querySelectorAll("#inspectorTableBody tr").forEach(r => r.style.background = "");
        const attachedCompIds = n.connections.map(c => c.component_id);
        attachedCompIds.forEach(cid => {
          const comp = loadedComponentsMap[cid];
          if (comp) {
            const btn = document.querySelector(`.btn-edit-sm[data-id="${cid}"]`);
            if (btn && btn.closest("tr")) {
              btn.closest("tr").style.background = "rgba(0, 240, 255, 0.15)";
            }
          }
        });
        if (attachedCompIds.length > 0 && loadedComponentsMap[attachedCompIds[0]]) {
          highlightComponentOnSketch(loadedComponentsMap[attachedCompIds[0]]);
        }
        showToast(`Highlighted ${n.connections.length} component pin(s) on Node #${n.node_id}`);
      });

      inspectorNodesList.appendChild(card);
    });
  }

  function renderInspectorComponents(components) {
    if (!inspectorTableBody) return;
    inspectorTableBody.innerHTML = "";
    loadedComponentsMap = {};

    components.forEach(comp => {
      loadedComponentsMap[comp.id] = comp;
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      const pinsHtml = comp.terminals.map(t => `<span class="pin-chip">${t.name}</span>`).join("");
      const netsHtml = comp.terminals.map(t => `<span class="net-chip">${t.connected_node_id !== null ? 'N' + t.connected_node_id : 'Open'}</span>`).join("");

      tr.innerHTML = `
        <td><strong>#${comp.id}</strong></td>
        <td><code>${comp.display_type}</code></td>
        <td><strong>${comp.value || comp.label || '<span class="text-muted">Unset</span>'}</strong></td>
        <td>${pinsHtml}</td>
        <td>${netsHtml}</td>
        <td>
          <button class="btn-edit-sm" data-id="${comp.id}" data-val="${comp.value || ''}" data-type="${comp.display_type}">
            <i class="fa-solid fa-pen"></i> Edit
          </button>
        </td>
      `;

      tr.addEventListener("click", (e) => {
        if (e.target.closest(".btn-edit-sm")) return;
        document.querySelectorAll("#inspectorTableBody tr").forEach(r => r.style.background = "");
        tr.style.background = "rgba(0, 240, 255, 0.12)";
        openComponentDetails(comp);
      });

      const editBtn = tr.querySelector(".btn-edit-sm");
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        currentEditingCompId = comp.id;
        editCompId.textContent = `#${comp.id} (${comp.display_type})`;
        editValueInput.value = comp.value || "";
        editTypeSelect.value = comp.type;

        const termSelect = document.getElementById("editTerminalSelect");
        if (termSelect) {
          termSelect.innerHTML = '<option value="">Select Pin...</option>';
          (comp.terminals || []).forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.terminal_id !== undefined ? t.terminal_id : t.id;
            opt.textContent = `${t.name} (currently Node ${t.connected_node_id !== null ? t.connected_node_id : 'Open'})`;
            termSelect.appendChild(opt);
          });
        }

        graphEditCard.style.display = "block";
        highlightComponentOnSketch(comp);
      });

      inspectorTableBody.appendChild(tr);
    });
  }

  const reconnectPinBtn = document.getElementById("reconnectPinBtn");
  const editTerminalSelect = document.getElementById("editTerminalSelect");
  const editTargetNodeSelect = document.getElementById("editTargetNodeSelect");

  if (reconnectPinBtn) {
    reconnectPinBtn.addEventListener("click", async () => {
      if (currentEditingCompId === null || !currentJobId) return;
      const termId = editTerminalSelect.value;
      const targetNode = parseInt(editTargetNodeSelect.value, 10);
      if (termId === "" || isNaN(targetNode)) {
        showToast("Please select a terminal and target node.");
        return;
      }
      try {
        reconnectPinBtn.disabled = true;
        reconnectPinBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Reconnecting...';
        const res = await fetch(`/api/jobs/${currentJobId}/correct`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            action: "reconnect_terminal",
            params: {
              comp_id: currentEditingCompId,
              terminal_id: parseInt(termId, 10),
              target_node_id: targetNode
            }
          })
        });
        const updateData = await res.json();
        if (updateData.success) {
          renderInspectorComponents(updateData.components || []);
          renderInspectorNodes(updateData.nodes || []);
          renderValidationFindings(updateData.findings || []);
          mainDisplayImg.src = `/api/jobs/${currentJobId}/schematic/${activeCadTheme}?t=${Date.now()}`;
          showToast(`Terminal reconnected to Node ${targetNode} and schematic updated!`);
          graphEditCard.style.display = "none";
        } else {
          showToast(`Reconnect failed: ${updateData.message || 'Error'}`);
        }
      } catch (err) {
        showToast(`Reconnect error: ${err.message}`);
      } finally {
        reconnectPinBtn.disabled = false;
        reconnectPinBtn.innerHTML = '<i class="fa-solid fa-link"></i> Reconnect Pin';
      }
    });
  }

  const revalidateBtn = document.getElementById("revalidateBtn");
  if (revalidateBtn) {
    revalidateBtn.addEventListener("click", async () => {
      if (!currentJobId) return;
      await loadValidationData(currentJobId);
      showToast("Domain validation checks re-evaluated!");
    });
  }

  if (closeEditBtn) {
    closeEditBtn.addEventListener("click", () => {
      graphEditCard.style.display = "none";
    });
  }

  if (saveCompEditBtn) {
    saveCompEditBtn.addEventListener("click", async () => {
      if (currentEditingCompId === null || !currentJobId) return;
      const newVal = editValueInput.value.trim();
      const newType = editTypeSelect.value;

      try {
        saveCompEditBtn.disabled = true;
        saveCompEditBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

        // 1. Update value
        if (newVal) {
          await fetch(`/api/jobs/${currentJobId}/correct`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({action: "update_value", params: {comp_id: currentEditingCompId, value: newVal}})
          });
        }

        // 2. Update type
        if (newType) {
          const res = await fetch(`/api/jobs/${currentJobId}/correct`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({action: "update_type", params: {comp_id: currentEditingCompId, type: newType}})
          });
          const updateData = await res.json();
          renderInspectorComponents(updateData.components || []);
          renderInspectorNodes(updateData.nodes || []);
          renderValidationFindings(updateData.findings || []);
        }

        // 3. Refresh display image
        mainDisplayImg.src = `/api/jobs/${currentJobId}/schematic/${activeCadTheme}?t=${Date.now()}`;
        graphEditCard.style.display = "none";
        showToast(`Component #${currentEditingCompId} updated and circuit re-rendered!`);
      } catch (err) {
        showToast(`Edit failed: ${err.message}`);
      } finally {
        saveCompEditBtn.disabled = false;
        saveCompEditBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save & Re-render';
      }
    });
  }

  async function loadValidationData(jobId) {
    if (!validationFindingsList && !validationBadge) return;
    try {
      const res = await fetch(`/api/jobs/${jobId}/validate`);
      if (!res.ok) return;
      const data = await res.json();
      renderValidationFindings(data.findings || []);
    } catch (e) {
      console.error("Validation load failed:", e);
    }
  }

  function renderValidationFindings(findings) {
    if (!validationFindingsList) return;
    const errors = findings.filter(f => f.severity === "error");
    const warnings = findings.filter(f => f.severity === "warning");
    const infos = findings.filter(f => f.severity === "info");

    if (valErrorCount) valErrorCount.textContent = errors.length;
    if (valWarningCount) valWarningCount.textContent = warnings.length;
    if (valInfoCount) valInfoCount.textContent = infos.length;
    if (validationBadge) validationBadge.textContent = findings.length;

    validationFindingsList.innerHTML = "";
    if (findings.length === 0) {
      validationFindingsList.innerHTML = `
        <div class="empty-state">
          <i class="fa-solid fa-shield-check" style="color: var(--accent-green); opacity: 0.8;"></i>
          <p><strong>Clean Schematic!</strong> No floating pins, accidental shorts, or topology errors found.</p>
        </div>
      `;
      return;
    }

    findings.forEach(f => {
      const card = document.createElement("div");
      card.className = `finding-card ${f.severity}`;
      card.innerHTML = `
        <div class="finding-header">
          <span class="finding-title">${f.title}</span>
          <span class="finding-rule-badge">${f.rule_id}</span>
        </div>
        <div class="finding-explanation">${f.explanation}</div>
        <div class="finding-evidence">Evidence: ${f.evidence}</div>
        <div class="finding-action"><strong>Recommended Action:</strong> ${f.suggested_action}</div>
      `;
      validationFindingsList.appendChild(card);
    });
  }

  // AI Assistant Chat Handlers
  promptChips.forEach(chip => {
    chip.addEventListener("click", () => {
      aiQuestionInput.value = chip.getAttribute("data-q");
      sendAIMessage();
    });
  });

  if (aiSendBtn) {
    aiSendBtn.addEventListener("click", sendAIMessage);
  }

  if (aiQuestionInput) {
    aiQuestionInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendAIMessage();
    });
  }

  async function sendAIMessage() {
    const q = aiQuestionInput.value.trim();
    if (!q || !currentJobId) {
      if (!currentJobId) showToast("Please analyze a circuit diagram first.");
      return;
    }

    // Append user message
    appendChatMessage("user", q);
    aiQuestionInput.value = "";

    // Show temporary typing bubble
    const typingId = "typing-" + Date.now();
    appendChatMessage("assistant", '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing circuit data...', typingId);

    try {
      const res = await fetch(`/api/jobs/${currentJobId}/assistant/chat`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({question: q})
      });
      const data = await res.json();
      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();

      appendChatMessage("assistant", data.answer || "No response received.");
    } catch (err) {
      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();
      appendChatMessage("assistant", `⚠️ Error communicating with assistant: ${err.message}`);
    }
  }

  function appendChatMessage(sender, htmlText, elementId = null) {
    const msg = document.createElement("div");
    msg.className = `ai-message ${sender}`;
    if (elementId) msg.id = elementId;
    const isBot = sender === "assistant";
    msg.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid ${isBot ? 'fa-robot' : 'fa-user'}"></i></div>
      <div class="msg-body">
        <strong>${isBot ? 'Paper2CAD Assistant' : 'You'}</strong>
        <div>${htmlText.replace(/\n/g, '<br>')}</div>
      </div>
    `;
    aiChatThread.appendChild(msg);
    aiChatThread.scrollTop = aiChatThread.scrollHeight;
  }

  // SPICE Simulation Handlers
  if (runSimBtn) {
    runSimBtn.addEventListener("click", async () => {
      if (!currentJobId) {
        showToast("Please analyze a circuit diagram first.");
        return;
      }

      const analysis = simAnalysisSelect.value;
      runSimBtn.disabled = true;
      runSimBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running SPICE...';
      simStatusText.textContent = "Simulating with ngspice...";

      try {
        const formData = new FormData();
        formData.append("analysis", analysis);

        const res = await fetch(`/api/jobs/${currentJobId}/simulate`, {
          method: "POST",
          body: formData
        });
        const data = await res.json();
        const r = data.result || {};

        simStatusText.textContent = r.success ? "Simulation Succeeded" : (r.available ? "Simulation Warnings" : "Simulator Unavailable");

        // Voltages table
        if (r.node_voltages && Object.keys(r.node_voltages).length > 0) {
          let vHtml = '<table class="inspector-table"><thead><tr><th>Node</th><th>Voltage (V)</th></tr></thead><tbody>';
          for (const [node, v] of Object.entries(r.node_voltages)) {
            vHtml += `<tr><td><strong>${node}</strong></td><td><code>${Number(v).toFixed(4)} V</code></td></tr>`;
          }
          vHtml += '</tbody></table>';
          simVoltagesWrap.innerHTML = vHtml;
        } else {
          simVoltagesWrap.innerHTML = '<p class="text-muted">No DC node voltages reported.</p>';
        }

        // Currents table
        if (r.branch_currents && Object.keys(r.branch_currents).length > 0) {
          let cHtml = '<table class="inspector-table"><thead><tr><th>Device / Branch</th><th>Current (A)</th></tr></thead><tbody>';
          for (const [dev, cur] of Object.entries(r.branch_currents)) {
            cHtml += `<tr><td><strong>${dev}</strong></td><td><code>${Number(cur).toExponential(3)} A</code></td></tr>`;
          }
          cHtml += '</tbody></table>';
          simCurrentsWrap.innerHTML = cHtml;
        } else {
          simCurrentsWrap.innerHTML = '<p class="text-muted">No branch currents reported.</p>';
        }

        simConsoleOutput.textContent = r.message + "\n\n" + (r.raw_stdout || "") + (r.raw_stderr || "");
        showToast(r.message || "Simulation execution finished");
      } catch (err) {
        simStatusText.textContent = "Execution Error";
        simConsoleOutput.textContent = `Error: ${err.message}`;
        showToast(`Simulation failed: ${err.message}`);
      } finally {
        runSimBtn.disabled = false;
        runSimBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run ngspice Simulation';
      }
    });
  }

  // --------------------------------------------------------------------------
  // Model Context Protocol (MCP) Hub
  // --------------------------------------------------------------------------
  const mcpToolsGrid = document.getElementById("mcpToolsGrid");
  const mcpToolSelect = document.getElementById("mcpToolSelect");
  const mcpCircuitIdInput = document.getElementById("mcpCircuitIdInput");
  const mcpExtraArgInput = document.getElementById("mcpExtraArgInput");
  const runMcpToolBtn = document.getElementById("runMcpToolBtn");
  const mcpOutputBlock = document.getElementById("mcpOutputBlock");

  async function loadMcpTools() {
    try {
      const res = await fetch("/api/mcp/tools");
      if (!res.ok) return;
      const data = await res.json();
      if (!mcpToolsGrid) return;
      mcpToolsGrid.innerHTML = "";
      (data.tools || []).forEach(tool => {
        const card = document.createElement("div");
        card.className = "mcp-tool-card";
        const paramNames = Object.keys(tool.parameters || {}).join(", ");
        card.innerHTML = `
          <div class="mcp-tool-name"><i class="fa-solid fa-cube"></i> ${tool.name}</div>
          <div class="mcp-tool-desc">${tool.description}</div>
          <div class="mcp-tool-params">Params: (${paramNames || 'none'})</div>
        `;
        card.addEventListener("click", () => {
          if (mcpToolSelect) mcpToolSelect.value = tool.name;
          if (mcpCircuitIdInput) mcpCircuitIdInput.value = currentJobId || "cir1";
          showToast(`Selected MCP tool: ${tool.name}`);
        });
        mcpToolsGrid.appendChild(card);
      });
    } catch (e) {
      console.error("Failed to load MCP tools:", e);
    }
  }

  if (runMcpToolBtn) {
    runMcpToolBtn.addEventListener("click", async () => {
      const toolName = mcpToolSelect.value;
      const circuitId = mcpCircuitIdInput.value.trim() || currentJobId || "cir1";
      const extraArg = mcpExtraArgInput.value.trim();

      const args = { circuit_id: circuitId };
      if (toolName === "inspect_circuit" && extraArg) args.component_id = extraArg;
      else if (toolName === "explain_circuit") args.question = extraArg || "Explain the circuit topology.";
      else if (toolName === "simulate_circuit" && extraArg) args.analysis_type = extraArg;
      else if (toolName === "generate_schematic" && extraArg) args.theme = extraArg;

      runMcpToolBtn.disabled = true;
      runMcpToolBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Invoking...';
      mcpOutputBlock.textContent = `Invoking ${toolName} on ${circuitId} via MCP JSON-RPC protocol...`;

      try {
        const res = await fetch("/api/mcp/invoke", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ tool_name: toolName, arguments: args })
        });
        const data = await res.json();
        mcpOutputBlock.textContent = JSON.stringify(data, null, 2);
        showToast(`MCP ${toolName} executed successfully!`);
      } catch (err) {
        mcpOutputBlock.textContent = `Error: ${err.message}`;
        showToast(`MCP invocation failed: ${err.message}`);
      } finally {
        runMcpToolBtn.disabled = false;
        runMcpToolBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Execute MCP Tool';
      }
    });
  }

  // --------------------------------------------------------------------------
  // Initialize Default State & Initial Circuit
  // --------------------------------------------------------------------------
  updateViewModeButtons();
  if (mcpToolsGrid) {
    loadMcpTools();
  }

  try {
    loadPresetCircuit(currentSample || "cir1");
  } catch (err) {
    console.error("Initial preset load error:", err);
  }
});

