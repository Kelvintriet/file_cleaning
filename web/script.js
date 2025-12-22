window.addEventListener("pywebviewready", function () {
  refreshStats();

  // Ensure modal is hidden on load
  document.getElementById("settings-modal").classList.add("hidden");
  document.getElementById("history-modal").classList.add("hidden");
  document.getElementById("rules-modal").classList.add("hidden");
  document.getElementById("edit-rule-modal").classList.add("hidden");
  document.getElementById("ai-modal").classList.add("hidden");
});

// AI Logic
const aiModal = document.getElementById("ai-modal");
const aiBtn = document.getElementById("ai-trigger");
const closeAiBtn = document.getElementById("close-ai");
const startAiScanBtn = document.getElementById("start-ai-scan-btn");
const aiBackBtn = document.getElementById("ai-back-btn");
const applyAiBtn = document.getElementById("apply-ai-btn");
const aiApiKeyInput = document.getElementById("ai-api-key");
const aiModeSelect = document.getElementById("ai-mode");
const aiInstructionsInput = document.getElementById("ai-instructions");
const aiPrioritizeRules = document.getElementById("ai-prioritize-rules");
const aiRespectIgnore = document.getElementById("ai-respect-ignore");
const aiResultsList = document.getElementById("ai-results-list");
const aiRiskAck = document.getElementById("ai-risk-ack");
const aiSelectAll = document.getElementById("ai-select-all");

let currentAiResults = [];

aiBtn.addEventListener("click", function () {
  // Load config
  window.pywebview.api.get_ai_config().then((config) => {
    if (config.api_key) aiApiKeyInput.value = config.api_key;
    if (config.mode) aiModeSelect.value = config.mode;
    if (config.instructions) aiInstructionsInput.value = config.instructions;
    if (config.prioritize_rules !== undefined)
      aiPrioritizeRules.checked = config.prioritize_rules;
    if (config.respect_ignore !== undefined)
      aiRespectIgnore.checked = config.respect_ignore;
  });

  // Reset state
  document.getElementById("ai-step-config").classList.remove("hidden");
  document.getElementById("ai-step-scanning").classList.add("hidden");
  document.getElementById("ai-step-review").classList.add("hidden");
  aiModal.classList.remove("hidden");
});

closeAiBtn.addEventListener("click", function () {
  aiModal.classList.add("hidden");
});

startAiScanBtn.addEventListener("click", function () {
  const apiKey = aiApiKeyInput.value.trim();
  if (!apiKey) {
    alert("API Key is required!");
    return;
  }

  // Save config
  const config = {
    api_key: apiKey,
    mode: aiModeSelect.value,
    instructions: aiInstructionsInput.value,
    prioritize_rules: aiPrioritizeRules.checked,
    respect_ignore: aiRespectIgnore.checked,
  };
  window.pywebview.api.save_ai_config(config);

  // Switch to scanning
  document.getElementById("ai-step-config").classList.add("hidden");
  document.getElementById("ai-step-scanning").classList.remove("hidden");

  // Run scan
  window.pywebview.api.run_ai_scan(config).then((response) => {
    document.getElementById("ai-step-scanning").classList.add("hidden");

    if (response.error) {
      alert("Error: " + response.error);
      document.getElementById("ai-step-config").classList.remove("hidden");
      return;
    }

    if (!response.results || response.results.length === 0) {
      alert("No suggestions returned from AI.");
      document.getElementById("ai-step-config").classList.remove("hidden");
      return;
    }

    // Show results
    currentAiResults = response.results;
    renderAiResults(currentAiResults);
    document.getElementById("ai-step-review").classList.remove("hidden");
  });
});

function renderAiResults(results) {
  aiResultsList.innerHTML = "";
  results.forEach((item, index) => {
    const tr = document.createElement("tr");
    tr.style.borderBottom = "1px solid #f0f0f0";
    tr.innerHTML = `
            <td style="padding: 10px;"><input type="checkbox" class="ai-file-check" data-index="${index}" checked></td>
            <td style="padding: 10px; font-weight: 500;">${item.file}</td>
            <td style="padding: 10px; color: #0071e3;">${item.folder}</td>
            <td style="padding: 10px; font-size: 12px; color: #666;">${
              item.reason || "N/A"
            }</td>
        `;
    aiResultsList.appendChild(tr);
  });

  updateAiApplyButton();
}

aiSelectAll.addEventListener("change", function () {
  const checks = document.querySelectorAll(".ai-file-check");
  checks.forEach((c) => (c.checked = this.checked));
  updateAiApplyButton();
});

// Update button state based on selection and risk ack
function updateAiApplyButton() {
  const checkedCount = document.querySelectorAll(
    ".ai-file-check:checked"
  ).length;
  const isAck = aiRiskAck.checked;
  applyAiBtn.disabled = !(checkedCount > 0 && isAck);
  applyAiBtn.innerText =
    checkedCount > 0 ? `Apply ${checkedCount} Changes` : "Apply Changes";
}

aiResultsList.addEventListener("change", function (e) {
  if (e.target.classList.contains("ai-file-check")) {
    updateAiApplyButton();
  }
});

aiRiskAck.addEventListener("change", updateAiApplyButton);

aiBackBtn.addEventListener("click", function () {
  document.getElementById("ai-step-review").classList.add("hidden");
  document.getElementById("ai-step-config").classList.remove("hidden");
});

applyAiBtn.addEventListener("click", function () {
  const checks = document.querySelectorAll(".ai-file-check:checked");
  const toApply = [];
  checks.forEach((c) => {
    const idx = parseInt(c.dataset.index);
    toApply.push(currentAiResults[idx]);
  });

  this.disabled = true;
  this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Moving...';

  window.pywebview.api.apply_ai_changes(toApply).then((res) => {
    aiModal.classList.add("hidden");
    refreshStats();
    alert(
      `AI Sort Complete!\nMoved: ${res.moved} files\nErrors: ${res.errors}`
    );
    this.disabled = false;
    this.innerText = "Apply Selected Changes";
    aiRiskAck.checked = false; // Reset
  });
});

// Rules Logic
let currentRules = [];
let editingRuleIndex = -1;

const rulesModal = document.getElementById("rules-modal");
const rulesBtn = document.getElementById("rules-trigger");
const closeRulesBtn = document.getElementById("close-rules");
const addRuleBtn = document.getElementById("add-rule-btn");

const editRuleModal = document.getElementById("edit-rule-modal");
const closeEditRuleBtn = document.getElementById("close-edit-rule");
const saveRuleBtn = document.getElementById("save-rule-btn");
const deleteRuleBtn = document.getElementById("delete-rule-btn");

// Inputs
const ruleNameInput = document.getElementById("rule-name");
const ruleExtInput = document.getElementById("rule-extensions");
const ruleFolderInput = document.getElementById("rule-folder");
const rulePatternInput = document.getElementById("rule-pattern");

rulesBtn.addEventListener("click", function () {
  loadRules();
  rulesModal.classList.remove("hidden");
});

closeRulesBtn.addEventListener("click", function () {
  rulesModal.classList.add("hidden");
});

addRuleBtn.addEventListener("click", function () {
  editingRuleIndex = -1;
  document.getElementById("edit-rule-title").innerText = "Add New Rule";
  ruleNameInput.value = "";
  ruleExtInput.value = "";
  ruleFolderInput.value = "";
  rulePatternInput.value = "";
  deleteRuleBtn.style.display = "none";
  editRuleModal.classList.remove("hidden");
});

closeEditRuleBtn.addEventListener("click", function () {
  editRuleModal.classList.add("hidden");
});

function loadRules() {
  window.pywebview.api.get_rules().then((rules) => {
    currentRules = rules;
    const list = document.getElementById("rules-list");
    list.innerHTML = "";

    rules.forEach((rule, index) => {
      const div = document.createElement("div");
      div.className = "rule-item";
      div.onclick = () => openEditRule(index);

      const exts = rule.extensions.join(", ");
      const pattern = rule.filename_pattern
        ? ` | Pattern: ${rule.filename_pattern}`
        : "";

      div.innerHTML = `
                <div class="rule-info">
                    <div class="rule-name">${rule.name}</div>
                    <div class="rule-detail">Folder: ${rule.folder}</div>
                    <div class="rule-detail">Exts: ${exts}${pattern}</div>
                </div>
                <i class="fas fa-chevron-right" style="color: #ccc;"></i>
            `;
      list.appendChild(div);
    });
  });
}

function openEditRule(index) {
  editingRuleIndex = index;
  const rule = currentRules[index];

  document.getElementById("edit-rule-title").innerText = "Edit Rule";
  ruleNameInput.value = rule.name;
  ruleExtInput.value = rule.extensions.join(", ");
  ruleFolderInput.value = rule.folder;
  rulePatternInput.value = rule.filename_pattern || "";

  deleteRuleBtn.style.display = "block";
  editRuleModal.classList.remove("hidden");
}

saveRuleBtn.addEventListener("click", function () {
  const name = ruleNameInput.value.trim();
  const folder = ruleFolderInput.value.trim();
  if (!name || !folder) {
    alert("Name and Folder are required!");
    return;
  }

  const exts = ruleExtInput.value
    .split(",")
    .map((e) => e.trim())
    .filter((e) => e);
  const pattern = rulePatternInput.value.trim();

  const newRule = {
    name: name,
    extensions: exts,
    folder: folder,
    filename_pattern: pattern,
  };

  if (editingRuleIndex === -1) {
    currentRules.push(newRule);
  } else {
    currentRules[editingRuleIndex] = newRule;
  }

  window.pywebview.api.save_rules(currentRules).then(() => {
    editRuleModal.classList.add("hidden");
    loadRules();
  });
});

// Browse Folder for Rules
document
  .getElementById("browse-folder-btn")
  .addEventListener("click", function () {
    window.pywebview.api.select_destination_folder().then((result) => {
      if (result) {
        if (result.error) {
          alert(result.error);
        } else if (result.path) {
          document.getElementById("rule-folder").value = result.path;
        }
      }
    });
  });

deleteRuleBtn.addEventListener("click", function () {
  if (editingRuleIndex === -1) return;
  if (!confirm("Delete this rule?")) return;

  currentRules.splice(editingRuleIndex, 1);
  window.pywebview.api.save_rules(currentRules).then(() => {
    editRuleModal.classList.add("hidden");
    loadRules();
  });
});

// Settings Modal Logic
const modal = document.getElementById("settings-modal");
const settingsBtn = document.getElementById("settings-trigger");
const closeBtn = document.getElementById("close-settings");
const saveBtn = document.getElementById("save-settings");
const textarea = document.getElementById("ignore-list-input");
const excludeBtn = document.getElementById("filter-mode-exclude");
const includeBtn = document.getElementById("filter-mode-include");
const filterDesc = document.getElementById("filter-desc");

let currentFilterMode = "exclude"; // exclude | include

function updateFilterUI(mode) {
  currentFilterMode = mode;

  // Update Buttons
  if (mode === "exclude") {
    excludeBtn.classList.add("active");
    excludeBtn.style.background = "#fff";
    excludeBtn.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
    excludeBtn.style.color = "#000";

    includeBtn.classList.remove("active");
    includeBtn.style.background = "transparent";
    includeBtn.style.boxShadow = "none";
    includeBtn.style.color = "#666";

    filterDesc.innerHTML =
      "Files matching these patterns will be <strong>IGNORED</strong> (skipped).";
    textarea.placeholder = "*.tmp\n*.crdownload\n~*\ndesktop.ini";

    // Load Ignore List
    window.pywebview.api.get_ignore_list().then((list) => {
      textarea.value = list.join("\n");
    });
  } else {
    includeBtn.classList.add("active");
    includeBtn.style.background = "#fff";
    includeBtn.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
    includeBtn.style.color = "#000";

    excludeBtn.classList.remove("active");
    excludeBtn.style.background = "transparent";
    excludeBtn.style.boxShadow = "none";
    excludeBtn.style.color = "#666";

    filterDesc.innerHTML =
      "<strong>ONLY</strong> files matching these patterns will be cleaned. All others are ignored.";
    textarea.placeholder = "*.pdf\n*.docx\nProject_*\n*.jpg";

    // Load Include List
    window.pywebview.api.get_include_list().then((list) => {
      textarea.value = list.join("\n");
    });
  }
}

excludeBtn.addEventListener("click", () => updateFilterUI("exclude"));
includeBtn.addEventListener("click", () => updateFilterUI("include"));

settingsBtn.addEventListener("click", function () {
  modal.classList.remove("hidden");
  // Get current mode from backend
  window.pywebview.api.get_filter_mode().then((mode) => {
    updateFilterUI(mode);
  });
});

closeBtn.addEventListener("click", function () {
  modal.classList.add("hidden");
});

saveBtn.addEventListener("click", function () {
  const text = textarea.value;
  const patterns = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line);

  // Save Mode
  window.pywebview.api.set_filter_mode(currentFilterMode);

  // Save List
  if (currentFilterMode === "exclude") {
    window.pywebview.api.save_ignore_list(patterns).then(() => {
      modal.classList.add("hidden");
    });
  } else {
    window.pywebview.api.save_include_list(patterns).then(() => {
      modal.classList.add("hidden");
    });
  }
});

// History Modal Logic
const historyModal = document.getElementById("history-modal");
const historyBtn = document.getElementById("history-btn");
const closeHistoryBtn = document.getElementById("close-history");

historyBtn.addEventListener("click", function () {
  loadHistory();
  historyModal.classList.remove("hidden");
});

closeHistoryBtn.addEventListener("click", function () {
  historyModal.classList.add("hidden");
});

function loadHistory() {
  window.pywebview.api.get_history().then((history) => {
    const list = document.getElementById("history-list");
    list.innerHTML = "";

    if (history.length === 0) {
      list.innerHTML = '<div class="empty-state">No history found.</div>';
      return;
    }

    history.forEach((session) => {
      const div = document.createElement("div");
      div.className = "history-item";
      div.innerHTML = `
                <div class="history-info">
                    <div class="history-date">${session.date}</div>
                    <div class="history-path">${session.path}</div>
                    <div class="history-count">${session.count} files moved</div>
                </div>
                <button onclick="restoreSession(${session.id})" class="btn-restore">
                    <i class="fas fa-undo"></i> Restore
                </button>
            `;
      list.appendChild(div);
    });
  });
}

window.restoreSession = function (id) {
  if (!confirm("Are you sure you want to restore this session?")) return;

  historyModal.classList.add("hidden");
  document.getElementById("clean-btn").disabled = true;
  document.getElementById("history-btn").disabled = true;
  document.getElementById("progress-container").classList.remove("hidden");
  document.getElementById("log-list").innerHTML = "";

  window.pywebview.api.restore_session(id);
};

window.addEventListener("click", function (event) {
  if (event.target == modal) {
    modal.classList.add("hidden");
  }
  if (event.target == historyModal) {
    historyModal.classList.add("hidden");
  }
  if (event.target == rulesModal) {
    rulesModal.classList.add("hidden");
  }
  if (event.target == editRuleModal) {
    editRuleModal.classList.add("hidden");
  }
  if (event.target == aiModal) {
    aiModal.classList.add("hidden");
  }
});

// Add escape key listener
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    if (!modal.classList.contains("hidden")) modal.classList.add("hidden");
    if (!historyModal.classList.contains("hidden"))
      historyModal.classList.add("hidden");
    if (!rulesModal.classList.contains("hidden"))
      rulesModal.classList.add("hidden");
    if (!editRuleModal.classList.contains("hidden"))
      editRuleModal.classList.add("hidden");
    if (!aiModal.classList.contains("hidden")) aiModal.classList.add("hidden");
  }
});

function refreshStats() {
  window.pywebview.api.scan_downloads().then((data) => {
    // Always update path if available, even on error
    if (data.path) {
      const display = data.display_path || data.path;
      document.getElementById("target-path").innerText = display;
      document.getElementById("target-path").title = data.path;
    }

    if (data.error) {
      document.getElementById("file-count").innerText = "Error scanning";
      return;
    }
    document.getElementById("file-count").innerText = `${data.count} Files`;
  });
}

document
  .getElementById("change-folder-btn")
  .addEventListener("click", function () {
    window.pywebview.api.select_folder().then((path) => {
      if (path) {
        refreshStats(); // Update UI with new path
      }
    });
  });

document.getElementById("clean-btn").addEventListener("click", function () {
  this.disabled = true;
  document.getElementById("history-btn").disabled = true;
  this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cleaning...';

  document.getElementById("progress-container").classList.remove("hidden");
  document.getElementById("log-list").innerHTML = ""; // Clear log

  window.pywebview.api.organize_files();
});

// Callbacks
window.updateProgress = function (percent) {
  document.getElementById("progress-fill").style.width = percent + "%";
  document.getElementById("progress-text").innerText =
    Math.round(percent) + "%";
};

window.logAction = function (dataStr) {
  let data;
  if (typeof dataStr === "string") {
    data = JSON.parse(dataStr);
  } else {
    data = dataStr;
  }

  const list = document.getElementById("log-list");

  // Remove empty state if present
  const empty = list.querySelector(".empty-state");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = "log-item";

  let icon = '<i class="fas fa-check"></i>';
  let statusClass = "log-status";

  if (data.status === "Error") {
    icon = '<i class="fas fa-times"></i>';
    statusClass = "log-status error";
  } else if (data.status === "Undo") {
    icon = '<i class="fas fa-undo"></i>';
    statusClass = "log-status"; // Use same green for success
  }

  div.innerHTML = `
        <span class="log-file" title="${data.file}">${data.file}</span>
        <div class="log-details">
            <span class="log-category">${data.category}</span>
            <span class="${statusClass}">${icon} ${data.status}</span>
        </div>
    `;

  // Add to top
  list.insertBefore(div, list.firstChild);
};

window.cleaningComplete = function (moved, errors) {
  const btn = document.getElementById("clean-btn");
  btn.disabled = false;
  document.getElementById("history-btn").disabled = false;

  btn.innerHTML = '<i class="fas fa-check"></i> Done!';

  setTimeout(() => {
    btn.innerHTML = '<i class="fas fa-magic"></i> Clean Now';
    document.getElementById("progress-container").classList.add("hidden");
    refreshStats(); // Update file count
  }, 2000);

  alert(`Cleaning Complete!\nMoved: ${moved} files\nErrors: ${errors}`);
};

window.undoComplete = function (restored) {
  const btn = document.getElementById("history-btn");
  const cleanBtn = document.getElementById("clean-btn");

  btn.disabled = false;
  cleanBtn.disabled = false;

  alert(`Restore Complete!\nRestored: ${restored} files`);

  document.getElementById("progress-container").classList.add("hidden");
  refreshStats();
};

window.cleaningError = function (msg) {
  alert("Critical Error: " + msg);
  document.getElementById("clean-btn").disabled = false;
  document.getElementById("history-btn").disabled = false;

  document.getElementById("clean-btn").innerText = "Clean Now";
};
