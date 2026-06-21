import { state } from './state.js';
import { els } from './elements.js';
import { showError, setSessionStatus } from './helpers.js';
import { navigateToStep } from './navigation.js';
import {
    renderResultsTable,
    updatePlotsFilter,
    updatePlotsCounter,
    validateStep1Next,
    renderSubgroupsList
} from './ui.js';

// Start a new wizard session
export async function startNewSession() {
    try {
        setSessionStatus('Initializing session...', 'waiting');

        // 1. Create a session on backend
        const response = await fetch('/wizard/sessions', { method: 'POST' });
        if (!response.ok) throw new Error('Could not create wizard session.');

        const data = await response.json();
        state.sessionId = data.session_id;
        state.currentStep = data.current_step;

        setSessionStatus(`Session: ${state.sessionId.substring(0, 8)}...`, 'active');

        // 2. Move to the step indicated by session status (usually dataset_selection)
        navigateToStep(state.currentStep);
    } catch (err) {
        showError(err.message);
        setSessionStatus('Initialization failed', 'error');
    }
}

// Fetch applicable statistical methods
export async function fetchApplicableMethods() {
    try {
        const response = await fetch(`/wizard/sessions/${state.sessionId}/methods`);
        if (!response.ok) throw new Error('Failed to retrieve applicable methods list.');

        state.applicableMethods = await response.json();
        els.methodsList.innerHTML = '';
        els.btnStep3Next.disabled = true;
        state.selectedMethod = '';

        if (state.applicableMethods.length === 0) {
            els.methodsList.innerHTML = '<p class="no-filters-msg">No statistical methods are applicable to your current dataset properties. Please check your data or adjust preprocessing filters.</p>';
            return;
        }

        state.applicableMethods.forEach(method => {
            const card = document.createElement('article');
            card.className = 'method-card';
            card.dataset.name = method.name;

            card.innerHTML = `
                <div class="method-title">${method.name}</div>
                <div class="method-desc">${method.description}</div>
            `;

            card.addEventListener('click', (e) => {
                document.querySelectorAll('.method-card').forEach(c => c.classList.remove('selected'));
                const activeCard = e.currentTarget;
                activeCard.classList.add('selected');

                state.selectedMethod = activeCard.dataset.name;
                els.btnStep3Next.disabled = false;
            });

            els.methodsList.appendChild(card);
        });
    } catch (err) {
        showError(err.message);
    }
}

// Run the evaluation endpoint
export async function executeStatisticalMethod() {
    try {
        const response = await fetch(`/wizard/sessions/${state.sessionId}/results`);
        if (!response.ok) throw new Error('Statistical evaluation run failed.');

        const data = await response.json();
        state.statResults = data;

        // Default sort: p-value asc
        state.sortColumn = 'p_value';
        state.sortAsc = true;

        // Sort initial data
        state.statResults.sort((a, b) => {
            if (a.p_value === null || a.p_value === undefined) return 1;
            if (b.p_value === null || b.p_value === undefined) return -1;
            return a.p_value - b.p_value;
        });

        // Update significance filter count & state.plotsTopN
        updatePlotsFilter();

        // Render
        renderResultsTable();
    } catch (err) {
        showError(err.message);
    }
}

// Fetch applicable plots list
export async function fetchApplicablePlots() {
    try {
        const response = await fetch(`/wizard/sessions/${state.sessionId}/plots`);
        if (!response.ok) throw new Error('Failed to fetch applicable plot generators.');

        state.applicablePlots = await response.json();
        els.plotsSelector.innerHTML = '';
        els.btnStep5Next.disabled = true;
        state.selectedPlots = [];
        els.plotsDisplay.innerHTML = '<span class="no-plots-msg">Select plot types and click Generate Plots above.</span>';

        if (state.applicablePlots.length === 0) {
            els.plotsSelector.innerHTML = '<p class="no-filters-msg">No visualizations applicable.</p>';
            if (els.plotsGenerationCounter) {
                els.plotsGenerationCounter.textContent = 'Will generate 0 plots';
            }
            if (els.btnGeneratePlots) {
                els.btnGeneratePlots.disabled = true;
            }
            return;
        }

        state.applicablePlots.forEach(plot => {
            const card = document.createElement('article');
            card.className = 'plot-select-item';
            card.dataset.name = plot.name;

            // Check if this is the boxplot and preselect it
            const isBoxplot = plot.name === 'boxplot';
            if (isBoxplot) {
                state.selectedPlots.push(plot.name);
                card.classList.add('selected');
            }

            card.innerHTML = `
                <input type="checkbox" id="chk-plot-${plot.name}" ${isBoxplot ? 'checked' : ''}>
                <div class="plot-select-info">
                    <h5>${plot.name}</h5>
                    <p>${plot.description}</p>
                </div>
            `;

            // Toggle selection logic
            const checkbox = card.querySelector('input');
            const toggleSelection = () => {
                checkbox.checked = !checkbox.checked;
                card.classList.toggle('selected', checkbox.checked);

                if (checkbox.checked) {
                    state.selectedPlots.push(plot.name);
                } else {
                    state.selectedPlots = state.selectedPlots.filter(p => p !== plot.name);
                }
                updatePlotsCounter();
            };

            card.addEventListener('click', (e) => {
                // Prevent double trigger when clicking checkbox directly
                if (e.target !== checkbox) {
                    toggleSelection();
                }
            });
            checkbox.addEventListener('change', () => {
                card.classList.toggle('selected', checkbox.checked);
                if (checkbox.checked) {
                    state.selectedPlots.push(plot.name);
                } else {
                    state.selectedPlots = state.selectedPlots.filter(p => p !== plot.name);
                }
                updatePlotsCounter();
            });

            els.plotsSelector.appendChild(card);
        });

        updatePlotsCounter();
    } catch (err) {
        showError(err.message);
    }
}

// Generate plots client side preview (updates live as they check boxes)
export async function generatePlotsPreview() {
    if (state.selectedPlots.length === 0) {
        els.plotsDisplay.innerHTML = '<span class="no-plots-msg">Select one or more plots to generate.</span>';
        return;
    }

    try {
        els.plotsDisplay.innerHTML = '<span class="no-plots-msg">Generating plots...</span>';
        els.btnGeneratePlots.disabled = true;
        els.btnStep5Next.disabled = true;

        const response = await fetch(`/wizard/sessions/${state.sessionId}/plots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                selected_plots: state.selectedPlots,
                top_n_columns: state.plotsTopN
            })
        });

        if (!response.ok) throw new Error('Plot rendering failed.');

        const data = await response.json();
        els.plotsDisplay.innerHTML = '';

        // Group plots by variable (column_name)
        const plotsByVar = {};
        data.plot_results.forEach(plot => {
            const col = plot.column_name || 'General';
            if (!plotsByVar[col]) {
                plotsByVar[col] = [];
            }
            plotsByVar[col].push(plot);
        });

        Object.entries(plotsByVar).forEach(([colName, plots]) => {
            const card = document.createElement('article');
            card.className = 'variable-plots-card';
            card.style.margin = '0 0 1rem 0';
            card.style.width = '100%';

            const header = document.createElement('header');
            header.style.padding = '0.5rem 0.75rem';
            header.style.marginBottom = '0.75rem';
            header.style.backgroundColor = 'rgba(255, 255, 255, 0.02)';
            header.style.borderBottom = '1px solid var(--pico-border-color)';

            const title = document.createElement('h4');
            title.style.margin = '0';
            title.style.fontSize = '0.95rem';
            title.style.fontWeight = '600';
            title.textContent = colName;
            header.appendChild(title);
            card.appendChild(header);

            // Grid row for plots - up to 3 columns
            const row = document.createElement('div');
            row.style.display = 'grid';
            row.style.gridTemplateColumns = 'repeat(auto-fit, minmax(200px, 1fr))';
            row.style.gap = '1rem';
            row.style.width = '100%';

            plots.forEach(plot => {
                const plotWrapper = document.createElement('div');
                plotWrapper.className = 'plot-image-wrapper';
                plotWrapper.style.textAlign = 'center';

                const img = document.createElement('img');
                img.src = `data:${plot.content_type};base64,${plot.image_base64}`;
                img.alt = `${plot.plot_type} for ${colName}`;
                img.style.maxWidth = '100%';
                img.style.height = 'auto';
                img.style.borderRadius = '8px';
                img.style.border = '1px solid var(--pico-border-color)';

                const label = document.createElement('div');
                label.style.marginTop = '0.25rem';
                label.style.fontSize = '0.75rem';
                label.style.color = 'var(--pico-muted-color)';
                label.textContent = plot.plot_type.toUpperCase();

                plotWrapper.appendChild(img);
                plotWrapper.appendChild(label);
                row.appendChild(plotWrapper);
            });

            card.appendChild(row);
            els.plotsDisplay.appendChild(card);
        });

        els.btnStep5Next.disabled = false;
    } catch (err) {
        els.plotsDisplay.innerHTML = `<span class="no-plots-msg text-error">Failed to render plots: ${err.message}</span>`;
    } finally {
        els.btnGeneratePlots.disabled = false;
    }
}

// Fetch unique values for a group column (subgroups) from the dataset
export async function updateSubgroupsList() {
    const datasetId = state.selectedDatasetId;
    const groupCol = els.groupColSelect.value;

    if (!groupCol) {
        els.subgroupsSection.classList.add('hidden');
        state.selectedGroups = new Set();
        state.availableGroups = [];
        validateStep1Next();
        return;
    }

    try {
        const response = await fetch(`/wizard/datasets/${datasetId}/columns/${groupCol}/unique`);
        if (!response.ok) throw new Error('Failed to fetch unique values for group column.');

        const groups = await response.json();

        state.availableGroups = groups;
        state.selectedGroups = new Set(groups);

        if (els.subgroupsSearch) {
            els.subgroupsSearch.value = '';
        }

        renderSubgroupsList();
    } catch (err) {
        showError(err.message);
        els.subgroupsSection.classList.add('hidden');
    }
}
