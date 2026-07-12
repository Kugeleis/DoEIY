// DoEIY Application Logic

// --- Application State ---
const state = {
  factors: [],       // Array of { name, type, levels }
  designData: [],    // Array of objects (rows) representing the generated design
  designType: '',    // Current design type
  columnSpecs: [],   // Column headers
  modelFit: null,    // Results from fit API (coefficients, anova, residuals)
  hotInstance: null, // Handsontable instance
  theme: 'dark'
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initTheme();
  initFactorTable();
  initDesignControls();
  initResultsToolbar();
  initAnalysisControls();
  initOptimizer();
  loadVersion();

  // Set initial design dropdown state
  updateDesignInputs();
});

async function loadVersion() {
  try {
    const response = await fetch('/api/version');
    const data = await response.json();
    document.getElementById('app-version').innerText = `v${data.version}`;
  } catch (err) {
    console.error('Error fetching version:', err);
  }
}

// --- UI Utility: Toasts ---
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  // Auto remove after 4 seconds
  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease reverse forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- UI Utility: Spinner ---
function showSpinner(show) {
  const spinner = document.getElementById('global-spinner');
  if (show) {
    spinner.classList.add('active');
  } else {
    spinner.classList.remove('active');
  }
}

// --- Theme Toggle ---
function initTheme() {
  const toggle = document.getElementById('theme-toggle');

  // Match saved theme or system preference
  const savedTheme = localStorage.getItem('theme') || 'dark';
  state.theme = savedTheme;
  document.documentElement.setAttribute('data-theme', savedTheme);
  toggle.checked = (savedTheme === 'dark');

  toggle.addEventListener('change', (e) => {
    const newTheme = e.target.checked ? 'dark' : 'light';
    state.theme = newTheme;
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    // Update handsontable if it exists
    if (state.hotInstance) {
      state.hotInstance.render();
    }
  });
}

// --- Tab Navigation ---
function initTabs() {
  const menuItems = document.querySelectorAll('.nav-menu .nav-item');
  const panels = document.querySelectorAll('.tab-panel');

  menuItems.forEach(item => {
    item.querySelector('a').addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = item.getAttribute('data-tab');

      // Update sidebar active class
      menuItems.forEach(mi => mi.classList.remove('active'));
      item.classList.add('active');

      // Update visible panels
      panels.forEach(p => p.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');

      // Hook: Refresh Handsontable when entering Results tab
      if (tabId === 'enter-results' && state.hotInstance) {
        setTimeout(() => {
          state.hotInstance.refreshDimensions();
          state.hotInstance.render();
        }, 100);
      }
    });
  });
}

// --- Tab Switch Helper ---
function switchToTab(tabId) {
  const tabLink = document.querySelector(`.nav-menu .nav-item[data-tab="${tabId}"] a`);
  if (tabLink) {
    tabLink.click();
  }
}

// --- Make a Design: Factor Rows ---
let factorCount = 2;

function initFactorTable() {
  const tbody = document.getElementById('factors-tbody');
  const addBtn = document.getElementById('add-factor-btn');

  addBtn.addEventListener('click', (e) => {
    e.preventDefault();
    factorCount++;
    const row = document.createElement('tr');
    row.setAttribute('data-factor-idx', factorCount - 1);
    row.innerHTML = `
      <td><input type="text" class="factor-name" value="Factor_${factorCount}" placeholder="e.g. Flow" required></td>
      <td>
        <select class="factor-type">
          <option value="Continuous" selected>Continuous</option>
          <option value="Discrete">Discrete</option>
          <option value="Categorical">Categorical</option>
        </select>
      </td>
      <td><input type="text" class="factor-levels" value="0, 100" placeholder="Min, Max limit" required></td>
      <td style="text-align: center;">
        <button class="btn-icon btn-danger-outline remove-factor-btn" type="button" title="Remove factor">×</button>
      </td>
    `;
    tbody.appendChild(row);
    attachFactorRowEvents(row);
  });

  // Attach events to default rows
  document.querySelectorAll('#factors-tbody tr').forEach(row => {
    attachFactorRowEvents(row);
  });
}

function attachFactorRowEvents(row) {
  const typeSelect = row.querySelector('.factor-type');
  const levelsInput = row.querySelector('.factor-levels');
  const removeBtn = row.querySelector('.remove-factor-btn');

  typeSelect.addEventListener('change', (e) => {
    const type = e.target.value;
    if (type === 'Continuous') {
      levelsInput.value = '0, 100';
      levelsInput.placeholder = 'Min, Max limit';
    } else if (type === 'Discrete') {
      levelsInput.value = '1, 2, 3, 4';
      levelsInput.placeholder = 'Comma-separated values';
    } else if (type === 'Categorical') {
      levelsInput.value = 'Low, Med, High';
      levelsInput.placeholder = 'Comma-separated tags';
    }
  });

  removeBtn.addEventListener('click', () => {
    if (document.querySelectorAll('#factors-tbody tr').length <= 1) {
      showToast('You must have at least one factor defined.', 'error');
      return;
    }
    row.remove();
  });
}

// --- Make a Design: Design Types & Option Containers ---
function initDesignControls() {
  const designSelect = document.getElementById('design-type');
  designSelect.addEventListener('change', updateDesignInputs);

  const generateBtn = document.getElementById('generate-design-btn');
  generateBtn.addEventListener('click', handleGenerateDesign);
}

function updateDesignInputs() {
  const designType = document.getElementById('design-type').value;
  const runsContainer = document.getElementById('dynamic-runs-container');
  const blocksContainer = document.getElementById('dynamic-blocks-container');
  const ccdContainer = document.getElementById('ccd-type-container');
  const runsSelect = document.getElementById('design-runs');
  const runsLabel = document.getElementById('runs-label');

  // Reset visibility
  runsContainer.style.display = 'none';
  blocksContainer.style.display = 'none';
  ccdContainer.style.display = 'none';

  const numFactors = document.querySelectorAll('#factors-tbody tr').length;

  if (designType === 'Fractional Factorial') {
    runsContainer.style.display = 'block';
    blocksContainer.style.display = 'block';
    runsLabel.innerText = 'Number of Runs (Power of 2)';

    // Fractional factorial options
    // Clear & populate runs select dynamically based on factors
    runsSelect.innerHTML = '';
    const minRuns = Math.pow(2, Math.ceil(Math.log2(numFactors + 1)));
    const runOptions = [8, 16, 32, 64, 128].filter(r => r >= minRuns);
    runOptions.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.innerText = r;
      runsSelect.appendChild(opt);
    });

    updateBlocksDropdown();
    runsSelect.onchange = updateBlocksDropdown;

  } else if (designType === 'Latin Hypercube Sampling') {
    runsContainer.style.display = 'block';
    runsLabel.innerText = 'Number of Runs';
    runsSelect.innerHTML = `
      <option value="10" selected>10</option>
      <option value="15">15</option>
      <option value="20">20</option>
      <option value="30">30</option>
      <option value="50">50</option>
    `;
  } else if (designType === 'D-Optimal') {
    runsContainer.style.display = 'block';
    runsLabel.innerText = 'Number of Runs';
    // Minimally need runs >= n_factors + 1
    runsSelect.innerHTML = '';
    const minRuns = numFactors + 2;
    for (let r = minRuns; r <= minRuns + 20; r++) {
      const opt = document.createElement('option');
      opt.value = r;
      opt.innerText = r;
      if (r === minRuns + 4) opt.selected = true;
      runsSelect.appendChild(opt);
    }
  } else if (designType === 'Central Composite') {
    ccdContainer.style.display = 'block';
  }
}

function updateBlocksDropdown() {
  const runs = parseInt(document.getElementById('design-runs').value) || 16;
  const blocksSelect = document.getElementById('design-blocks');
  blocksSelect.innerHTML = '';

  const blockOptions = [1];
  if (runs >= 16) blockOptions.push(2);
  if (runs >= 32) blockOptions.push(4);
  if (runs >= 64) blockOptions.push(8);

  blockOptions.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b;
    opt.innerText = b === 1 ? '1 (No Blocking)' : `${b} Blocks`;
    blocksSelect.appendChild(opt);
  });
}

// --- API: Generate Design ---
async function handleGenerateDesign() {
  const designType = document.getElementById('design-type').value;
  const randomize = document.getElementById('randomize-design').checked;

  // Extract factors
  const factorRows = document.querySelectorAll('#factors-tbody tr');
  const factors = [];
  const nameRegex = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

  for (let row of factorRows) {
    const name = row.querySelector('.factor-name').value.trim();
    const type = row.querySelector('.factor-type').value;
    const levelsStr = row.querySelector('.factor-levels').value.trim();

    if (!name) {
      showToast('All factor names are required.', 'error');
      return;
    }
    if (!nameRegex.test(name)) {
      showToast(`Invalid factor name "${name}". Names must start with a letter and contain only letters, numbers, and underscores.`, 'error');
      return;
    }
    if (!levelsStr) {
      showToast(`Levels are required for factor "${name}".`, 'error');
      return;
    }

    factors.push({ name, type, levels: levelsStr });
  }

  // Gather other params
  let numRuns = null;
  let numBlocks = null;

  if (designType === 'Fractional Factorial') {
    numRuns = parseInt(document.getElementById('design-runs').value);
    numBlocks = parseInt(document.getElementById('design-blocks').value);
  } else if (designType === 'Latin Hypercube Sampling' || designType === 'D-Optimal') {
    numRuns = parseInt(document.getElementById('design-runs').value);
  }

  const payload = {
    design_type: designType,
    factors: factors,
    num_runs: numRuns,
    num_blocks: numBlocks
  };

  showSpinner(true);
  try {
    const response = await fetch('/api/design/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Failed to generate design.');
    }

    // Save design to state
    state.factors = factors;
    state.designType = designType;
    state.designData = result.data.map((row, idx) => ({ Run: idx + 1, ...row }));

    // Add default Response column (filled with nulls)
    state.designData.forEach(row => {
      if (row.Response === undefined) {
        row.Response = null;
      }
    });

    // Setup Column Specs
    const columns = Object.keys(state.designData[0]);
    state.columnSpecs = columns;

    showToast(`Successfully generated ${designType} design with ${result.data.length} runs.`);

    // Init spreadsheet and jump to Results tab
    initSpreadsheet();
    updateAnalyzeResponseDropdowns();
    switchToTab('enter-results');

  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    showSpinner(false);
  }
}

// --- Handsontable Integration ---
function initSpreadsheet() {
  const container = document.getElementById('hot-container');

  // Destroy existing if it exists
  if (state.hotInstance) {
    state.hotInstance.destroy();
  }

  // Format columns list for handsontable
  const columns = state.columnSpecs.map(col => {
    const isRun = col === 'Run';
    const isBlock = col === 'Block';
    // Find if it's a categorical factor
    const factorDef = state.factors.find(f => f.name === col);
    const isCategorical = factorDef && factorDef.type === 'Categorical';

    const spec = {
      data: col,
      readOnly: isRun, // Keep 'Run' column read-only
      className: isRun ? 'htCenter htDimmed' : 'htCenter'
    };

    if (isRun) {
      spec.type = 'numeric';
    } else if (isCategorical) {
      spec.type = 'dropdown';
      // Parse levels
      spec.source = factorDef.levels.split(',').map(s => s.trim());
    } else if (col === 'Response' || isBlock) {
      spec.type = 'numeric';
      spec.numericFormat = { pattern: '0.000' };
    }

    return spec;
  });

  state.hotInstance = new Handsontable(container, {
    data: state.designData,
    colHeaders: state.columnSpecs,
    columns: columns,
    rowHeaders: true,
    height: '450px',
    width: '100%',
    stretchH: 'all',
    contextMenu: ['row_above', 'row_below', 'remove_row'],
    licenseKey: 'non-commercial-and-evaluation',
    afterChange: (changes, source) => {
      // Sync Handsontable data back to state
      if (source !== 'loadData') {
        state.designData = state.hotInstance.getSourceData();
      }
    }
  });
}

// --- Enter/Edit Results: Toolbar Actions ---
function initResultsToolbar() {
  const saveBtn = document.getElementById('save-csv-btn');
  const loadBtn = document.getElementById('load-csv-btn');
  const fileInput = document.getElementById('csv-file-input');
  const addColBtn = document.getElementById('add-col-btn');
  const removeColBtn = document.getElementById('remove-col-btn');

  saveBtn.addEventListener('click', exportToCSV);

  loadBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', handleCSVLoad);

  addColBtn.addEventListener('click', () => {
    if (!state.hotInstance) {
      showToast('Please generate or load a design first.', 'error');
      return;
    }
    const colName = prompt('Enter name for the new column (e.g. Yield):');
    if (!colName) return;

    const cleanName = colName.trim().replace(/[^a-zA-Z0-9_]/g, '');
    if (!cleanName) {
      showToast('Invalid column name.', 'error');
      return;
    }
    if (state.columnSpecs.includes(cleanName)) {
      showToast('Column already exists.', 'error');
      return;
    }

    // Add to state
    state.columnSpecs.push(cleanName);
    state.designData.forEach(row => {
      row[cleanName] = null;
    });

    // Re-init spreadsheet
    initSpreadsheet();
    updateAnalyzeResponseDropdowns();
    showToast(`Added column "${cleanName}".`);
  });

  removeColBtn.addEventListener('click', () => {
    if (!state.hotInstance) {
      showToast('Please generate or load a design first.', 'error');
      return;
    }
    const cols = state.columnSpecs.filter(c => c !== 'Run');
    if (cols.length === 0) {
      showToast('No columns left to remove.', 'error');
      return;
    }
    const colName = prompt(`Which column would you like to remove?\nOptions: ${cols.join(', ')}`);
    if (!colName) return;

    const cleanName = colName.trim();
    if (!state.columnSpecs.includes(cleanName)) {
      showToast(`Column "${cleanName}" not found.`, 'error');
      return;
    }
    if (cleanName === 'Run') {
      showToast('Cannot remove the Run index.', 'error');
      return;
    }

    // Remove from state
    state.columnSpecs = state.columnSpecs.filter(c => c !== cleanName);
    state.designData.forEach(row => {
      delete row[cleanName];
    });

    // Remove from factors if matches
    state.factors = state.factors.filter(f => f.name !== cleanName);

    // Re-init spreadsheet
    initSpreadsheet();
    updateAnalyzeResponseDropdowns();
    showToast(`Removed column "${cleanName}".`);
  });
}

function exportToCSV() {
  if (!state.hotInstance) {
    showToast('Nothing to export yet. Generate a design first.', 'error');
    return;
  }

  const headers = state.columnSpecs;
  let csvContent = headers.join(',') + '\n';

  state.designData.forEach(row => {
    const line = headers.map(head => {
      const val = row[head];
      if (val === null || val === undefined) return '';
      return typeof val === 'string' && val.includes(',') ? `"${val}"` : val;
    });
    csvContent += line.join(',') + '\n';
  });

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `doeiy_design_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function handleCSVLoad(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(evt) {
    const text = evt.target.result;
    const lines = text.split(/\r?\n/).filter(line => line.trim() !== '');
    if (lines.length < 2) {
      showToast('CSV is empty or invalid.', 'error');
      return;
    }

    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
    const rows = [];

    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
      if (parts.length !== headers.length) continue;

      const row = {};
      headers.forEach((h, idx) => {
        const val = parts[idx];
        // Guess type
        if (val === '') {
          row[h] = null;
        } else if (!isNaN(val)) {
          row[h] = parseFloat(val);
        } else {
          row[h] = val;
        }
      });
      rows.push(row);
    }

    if (rows.length === 0) {
      showToast('No valid rows found in CSV.', 'error');
      return;
    }

    // Sync state
    state.columnSpecs = headers;
    state.designData = rows;

    // Attempt to rebuild state.factors from CSV headers
    state.factors = [];
    headers.forEach(h => {
      if (h === 'Run' || h === 'Block' || h === 'Response') return;

      // Determine type based on column contents
      const uniqueVals = [...new Set(rows.map(r => r[h]).filter(v => v !== null))];
      const isNum = uniqueVals.every(v => typeof v === 'number');

      if (isNum) {
        state.factors.push({
          name: h,
          type: 'Continuous',
          levels: `${Math.min(...uniqueVals)}, ${Math.max(...uniqueVals)}`
        });
      } else {
        state.factors.push({
          name: h,
          type: 'Categorical',
          levels: uniqueVals.join(', ')
        });
      }
    });

    initSpreadsheet();
    updateAnalyzeResponseDropdowns();
    showToast(`Loaded ${rows.length} runs successfully.`);
    switchToTab('enter-results');
  };

  reader.readAsText(file);
  e.target.value = ''; // Reset input
}

// --- Analyze tab logic ---
function updateAnalyzeResponseDropdowns() {
  const select = document.getElementById('analyze-response-col');
  select.innerHTML = '';

  if (state.columnSpecs.length === 0) {
    select.innerHTML = '<option value="">-- No Design Generated --</option>';
    return;
  }

  // Find potential numeric response columns (e.g. not Run, Block or factor variables unless continuous)
  const nonFactors = state.columnSpecs.filter(col => {
    if (col === 'Run' || col === 'Block') return false;
    return true;
  });

  nonFactors.forEach(col => {
    const opt = document.createElement('option');
    opt.value = col;
    opt.innerText = col;
    if (col === 'Response') opt.selected = true;
    select.appendChild(opt);
  });

  updateFormulaPreset();
}

function initAnalysisControls() {
  const preset = document.getElementById('model-preset');
  preset.addEventListener('change', updateFormulaPreset);

  const runBtn = document.getElementById('run-analysis-btn');
  runBtn.addEventListener('click', handleRunAnalysis);
}

function updateFormulaPreset() {
  const response = document.getElementById('analyze-response-col').value;
  const preset = document.getElementById('model-preset').value;
  const formulaInput = document.getElementById('model-formula');

  if (!response || state.factors.length === 0) {
    formulaInput.value = '';
    return;
  }

  const factorNames = state.factors.map(f => f.name);
  let terms = [];

  if (preset === 'Main Effects') {
    terms = [...factorNames];
  } else if (preset === 'Main Effects + Interactions') {
    // Main effects
    terms = [...factorNames];
    // 2-Way interactions
    for (let i = 0; i < factorNames.length - 1; i++) {
      for (let j = i + 1; j < factorNames.length; j++) {
        terms.push(`${factorNames[i]}:${factorNames[j]}`);
      }
    }
  } else if (preset === 'Response Surface') {
    terms = [...factorNames];
    // Interactions
    for (let i = 0; i < factorNames.length - 1; i++) {
      for (let j = i + 1; j < factorNames.length; j++) {
        terms.push(`${factorNames[i]}:${factorNames[j]}`);
      }
    }
    // Quadratics (only for Continuous/Discrete factors)
    state.factors.forEach(f => {
      if (f.type === 'Continuous' || f.type === 'Discrete') {
        terms.push(`I(${f.name}**2)`);
      }
    });
  }

  if (preset !== 'Custom') {
    formulaInput.value = `${response} ~ ${terms.join(' + ')}`;
  }
}

// --- API: Fit Model ---
async function handleRunAnalysis() {
  const responseCol = document.getElementById('analyze-response-col').value;
  const formula = document.getElementById('model-formula').value.trim();

  if (!responseCol) {
    showToast('Please select a response column.', 'error');
    return;
  }
  if (!formula) {
    showToast('Please define a regression formula.', 'error');
    return;
  }

  // Filter out designData rows where response is null/undefined/empty string
  const cleanData = state.designData.filter(row => {
    const val = row[responseCol];
    return val !== null && val !== undefined && val !== '';
  });

  if (cleanData.length < 3) {
    showToast('You must fill in at least 3 experimental responses to fit a model.', 'error');
    return;
  }

  const payload = {
    data: cleanData,
    formula: formula
  };

  showSpinner(true);
  try {
    const response = await fetch('/api/analysis/fit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Model fitting failed. Check your formula or response variables.');
    }

    state.modelFit = {
      ...result,
      formula: formula,
      responseCol: responseCol,
      fittedData: cleanData
    };

    showToast('Model fitted successfully!');

    // Render outputs
    renderFitMetrics();
    renderANOVATable();
    renderEstimatesTable();
    drawParityPlot();

    // Unlock and set up model explorer
    initExplorerPanel();

    document.getElementById('analysis-results-section').style.display = 'block';

  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    showSpinner(false);
  }
}

function renderFitMetrics() {
  const r2 = state.modelFit.r_squared;
  const adjR2 = state.modelFit.adj_r_squared;

  document.getElementById('val-r2').innerText = r2.toFixed(4);
  document.getElementById('val-adj-r2').innerText = adjR2.toFixed(4);
}

function renderANOVATable() {
  const tbody = document.querySelector('#anova-table tbody');
  tbody.innerHTML = '';

  state.modelFit.anova.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${row.term_clean}</strong></td>
      <td>${row.df}</td>
      <td>${row.sum_sq.toFixed(3)}</td>
      <td>${row.mean_sq.toFixed(3)}</td>
      <td>${row.f_value !== null ? row.f_value.toFixed(2) : '-'}</td>
      <td>${row.p_value !== null ? row.p_value.toFixed(4) : '-'}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderEstimatesTable() {
  const tbody = document.querySelector('#estimates-table tbody');
  tbody.innerHTML = '';

  state.modelFit.coefficients.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><code>${row.term}</code></td>
      <td><strong>${row.term_clean}</strong></td>
      <td>${row.estimate.toFixed(4)}</td>
      <td>${row.std_error.toFixed(4)}</td>
      <td>${row.t_value.toFixed(2)}</td>
      <td>${row.p_value.toFixed(4)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function drawParityPlot() {
  const container = document.getElementById('parity-plot');
  const responseCol = state.modelFit.responseCol;

  // Actual values
  const actuals = state.modelFit.fittedData.map(r => r[responseCol]);
  // Predicted values
  const predicted = state.modelFit.fitted_values;

  // Ideal diagonal line
  const minVal = Math.min(...actuals, ...predicted);
  const maxVal = Math.max(...actuals, ...predicted);

  const diagonal = {
    x: [minVal, maxVal],
    y: [minVal, maxVal],
    mode: 'lines',
    name: 'Ideal Fit',
    line: { color: 'rgba(255, 255, 255, 0.4)', dash: 'dash', width: 2 }
  };

  const points = {
    x: actuals,
    y: predicted,
    mode: 'markers',
    name: 'Runs',
    type: 'scatter',
    marker: {
      size: 10,
      color: '#6366f1',
      line: { color: 'rgba(255, 255, 255, 0.3)', width: 1 }
    }
  };

  const layout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 45, r: 15, t: 15, b: 35 },
    xaxis: {
      title: { text: `Observed ${responseCol}`, font: { size: 12, color: 'var(--text-muted)' } },
      gridcolor: 'rgba(255, 255, 255, 0.08)',
      tickfont: { color: 'var(--text-muted)' }
    },
    yaxis: {
      title: { text: `Predicted ${responseCol}`, font: { size: 12, color: 'var(--text-muted)' } },
      gridcolor: 'rgba(255, 255, 255, 0.08)',
      tickfont: { color: 'var(--text-muted)' }
    },
    showlegend: false,
    hovermode: 'closest'
  };

  Plotly.newPlot(container, [diagonal, points], layout, { responsive: true, displayModeBar: false });
}

// --- Model Explorer Tab ---
function initExplorerPanel() {
  document.getElementById('explorer-warning').style.display = 'none';
  document.getElementById('explorer-content').style.display = 'block';

  const container = document.getElementById('sliders-container');
  container.innerHTML = '';

  // We construct sliders/dropdowns for all factors defined in the design
  state.factors.forEach(f => {
    const card = document.createElement('div');
    card.className = 'slider-card';

    // Find min and max boundaries in design data
    const values = state.designData.map(r => r[f.name]).filter(v => v !== null && v !== undefined);

    if (f.type === 'Continuous') {
      const minVal = Math.min(...values);
      const maxVal = Math.max(...values);
      const meanVal = (minVal + maxVal) / 2.0;

      card.innerHTML = `
        <div class="slider-header">
          <span class="slider-name">${f.name}</span>
          <span class="slider-val" id="val-label-${f.name}">${meanVal.toFixed(2)}</span>
        </div>
        <input type="range" class="factor-slider" id="slider-${f.name}"
               min="${minVal}" max="${maxVal}" step="${((maxVal - minVal) / 100).toFixed(4)}" value="${meanVal}">
      `;
    } else if (f.type === 'Discrete') {
      const sortedUnique = [...new Set(values)].sort((a,b) => a-b);
      const idx = Math.floor(sortedUnique.length / 2);
      const defaultVal = sortedUnique[idx];

      card.innerHTML = `
        <div class="slider-header">
          <span class="slider-name">${f.name}</span>
          <span class="slider-val" id="val-label-${f.name}">${defaultVal}</span>
        </div>
        <input type="range" class="factor-slider discrete-slider" id="slider-${f.name}"
               min="0" max="${sortedUnique.length - 1}" step="1" value="${idx}">
      `;
      // Save unique values array on element
      card.querySelector('input')._discreteValues = sortedUnique;
    } else if (f.type === 'Categorical') {
      const sortedUnique = [...new Set(values)].sort();
      const defaultVal = sortedUnique[0];

      let selectOptions = sortedUnique.map(v => `<option value="${v}">${v}</option>`).join('');

      card.innerHTML = `
        <div class="slider-header" style="margin-bottom: 0.25rem;">
          <span class="slider-name">${f.name}</span>
        </div>
        <select class="factor-dropdown" id="dropdown-${f.name}">
          ${selectOptions}
        </select>
      `;
    }

    container.appendChild(card);
  });

  // Attach change listeners to update predictions real-time
  document.querySelectorAll('.factor-slider, .factor-dropdown').forEach(elem => {
    elem.addEventListener('input', triggerPredictionUpdate);
    elem.addEventListener('change', triggerPredictionUpdate);
  });

  // Initial run
  triggerPredictionUpdate();
}

function getExplorerCoordinates() {
  const coords = {};
  state.factors.forEach(f => {
    if (f.type === 'Continuous') {
      coords[f.name] = parseFloat(document.getElementById(`slider-${f.name}`).value);
    } else if (f.type === 'Discrete') {
      const slider = document.getElementById(`slider-${f.name}`);
      const idx = parseInt(slider.value);
      coords[f.name] = slider._discreteValues[idx];
    } else if (f.type === 'Categorical') {
      coords[f.name] = document.getElementById(`dropdown-${f.name}`).value;
    }
  });
  return coords;
}

function updateExplorerInputs(coords) {
  state.factors.forEach(f => {
    if (f.type === 'Continuous') {
      const val = coords[f.name];
      const slider = document.getElementById(`slider-${f.name}`);
      slider.value = val;
      document.getElementById(`val-label-${f.name}`).innerText = val.toFixed(2);
    } else if (f.type === 'Discrete') {
      const val = coords[f.name];
      const slider = document.getElementById(`slider-${f.name}`);
      const idx = slider._discreteValues.indexOf(val);
      if (idx !== -1) {
        slider.value = idx;
        document.getElementById(`val-label-${f.name}`).innerText = val;
      }
    } else if (f.type === 'Categorical') {
      const val = coords[f.name];
      document.getElementById(`dropdown-${f.name}`).value = val;
    }
  });
  triggerPredictionUpdate();
}

async function triggerPredictionUpdate() {
  if (!state.modelFit) return;

  const coords = getExplorerCoordinates();

  // Update numerical slider labels
  state.factors.forEach(f => {
    if (f.type === 'Continuous') {
      document.getElementById(`val-label-${f.name}`).innerText = coords[f.name].toFixed(2);
    } else if (f.type === 'Discrete') {
      document.getElementById(`val-label-${f.name}`).innerText = coords[f.name];
    }
  });

  // Request prediction from API
  const payload = {
    coefficients: state.modelFit.coefficients.map(c => ({ term: c.term, estimate: c.estimate })),
    factors: coords
  };

  try {
    const response = await fetch('/api/analysis/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (response.ok && result.status === 'success') {
      document.getElementById('explorer-pred-val').innerText = result.prediction.toFixed(4);

      // Update Sensitivity Curves
      drawSensitivityCurves(coords);
    }
  } catch (err) {
    console.error('Real-time prediction error:', err);
  }
}

// --- Dynamic Sensitivity Curves ---
async function drawSensitivityCurves(currentCoords) {
  const container = document.getElementById('sensitivity-plot');
  const coefficients = state.modelFit.coefficients.map(c => ({ term: c.term, estimate: c.estimate }));

  const traces = [];

  // Loop through continuous/discrete factors and generate curves
  for (let f of state.factors) {
    if (f.type === 'Categorical') continue;

    // Find min and max bounds for factor
    const values = state.designData.map(r => r[f.name]).filter(v => v !== null);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);

    // Generate 25 points along range
    const steps = 25;
    const testPoints = [];
    for (let i = 0; i <= steps; i++) {
      testPoints.push(minVal + (i / steps) * (maxVal - minVal));
    }

    // Call batch predict local evaluations
    const predictions = [];
    for (let pt of testPoints) {
      // Copy current coords and swap factor value
      const testCoords = { ...currentCoords, [f.name]: pt };

      // Local evaluation (equivalent to endpoint math)
      let pred = 0.0;
      coefficients.forEach(c => {
        pred += c.estimate * evaluateTermJS(c.term, testCoords);
      });
      predictions.push(pred);
    }

    // Add trace
    traces.push({
      x: testPoints,
      y: predictions,
      mode: 'lines',
      name: f.name,
      line: { width: 3 }
    });
  }

  const layout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 45, r: 10, t: 15, b: 35 },
    xaxis: {
      title: { text: 'Factor Value (Range Scale)', font: { size: 12, color: 'var(--text-muted)' } },
      gridcolor: 'rgba(255, 255, 255, 0.08)',
      tickfont: { color: 'var(--text-muted)' }
    },
    yaxis: {
      title: { text: state.modelFit.responseCol, font: { size: 12, color: 'var(--text-muted)' } },
      gridcolor: 'rgba(255, 255, 255, 0.08)',
      tickfont: { color: 'var(--text-muted)' }
    },
    legend: {
      font: { color: 'var(--text-muted)', size: 10 },
      orientation: 'h',
      y: -0.2
    },
    hovermode: 'closest'
  };

  Plotly.newPlot(container, traces, layout, { responsive: true, displayModeBar: false });
}

// --- JS Implementation of patsy term evaluation ---
// This enables real-time client-side curves drawing without blasting the backend with 100 HTTP requests
function evaluateTermJS(term, factors) {
  if (term === 'Intercept') return 1.0;

  // Categorical level match: e.g. C(Var2)[T.Medium] or Var2[T.Medium]
  const catMatch = term.match(/(?:C\()?([a-zA-Z0-9_]+)\)?\[T\.(.*?)\]/);
  if (catMatch) {
    const col = catMatch[1];
    const level = catMatch[2];
    return String(factors[col]) === level ? 1.0 : 0.0;
  }

  // Interactions: A:B
  if (term.includes(':')) {
    const parts = term.split(':');
    let val = 1.0;
    parts.forEach(p => {
      val *= evaluateTermJS(p, factors);
    });
    return val;
  }

  // Quadratic wrap: I(A**2)
  const quadMatch = term.match(/I\((.*?)\*\*(\d+)\)/);
  if (quadMatch) {
    const col = quadMatch[1];
    const power = parseInt(quadMatch[2]);
    return Math.pow(parseFloat(factors[col]) || 0, power);
  }

  // Direct variable
  return parseFloat(factors[term]) || 0.0;
}

// --- Mathematical Optimizer ---
function initOptimizer() {
  const optSelect = document.getElementById('opt-type');
  const targetContainer = document.getElementById('opt-target-container');

  optSelect.addEventListener('change', (e) => {
    if (e.target.value === 'Find Target') {
      targetContainer.style.display = 'block';
    } else {
      targetContainer.style.display = 'none';
    }
  });

  const runOptBtn = document.getElementById('run-optimizer-btn');
  runOptBtn.addEventListener('click', handleRunOptimization);
}

async function handleRunOptimization() {
  if (!state.modelFit) return;

  const optType = document.getElementById('opt-type').value;
  const targetVal = optType === 'Find Target' ? parseFloat(document.getElementById('opt-target').value) : null;

  const factorTypes = {};
  state.factors.forEach(f => {
    factorTypes[f.name] = f.type;
  });

  const payload = {
    data: state.modelFit.fittedData,
    factor_types: factorTypes,
    opt_type: optType,
    target_response: targetVal,
    formula: state.modelFit.formula
  };

  showSpinner(true);
  try {
    const response = await fetch('/api/analysis/optimize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Optimization solver failed.');
    }

    // Success: Update sliders to optimal coordinates
    updateExplorerInputs(result.optimal_factors);

    // Display results
    document.getElementById('opt-resolved-pred').innerText = result.optimal_response.toFixed(4);

    const badgesContainer = document.getElementById('opt-resolved-factors');
    badgesContainer.innerHTML = '';

    Object.keys(result.optimal_factors).forEach(key => {
      const val = result.optimal_factors[key];
      const badge = document.createElement('div');
      badge.className = 'opt-factor-badge';
      badge.innerHTML = `${key}: <strong>${typeof val === 'number' ? val.toFixed(2) : val}</strong>`;
      badgesContainer.appendChild(badge);
    });

    document.getElementById('optimizer-results-badge').style.display = 'block';
    showToast('Optimization complete. Navigation sliders updated to resolved coordinates.');

  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    showSpinner(false);
  }
}

// Expose state globally for testing and debugging
window.appState = state;
