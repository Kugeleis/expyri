import { state } from './state.js';
import { els, stepsConfig } from './elements.js';
import { showError } from './helpers.js';
import { updateSubgroupsList } from './api.js';

// Render active filter badges in Step 2
export function renderActiveFilters() {
    if (state.activeFilters.length === 0) {
        els.activeFilters.innerHTML = '<p class="no-filters-msg">No filters configured. Click below to add a filter, or proceed directly.</p>';
        return;
    }

    els.activeFilters.innerHTML = '';
    state.activeFilters.forEach((filter, idx) => {
        const badge = document.createElement('div');
        badge.className = 'filter-badge';

        let descText = '';
        if (filter.name === 'numeric_range') {
            const hasMin = filter.params.min !== undefined;
            const hasMax = filter.params.max !== undefined;
            if (hasMin && hasMax) descText = `${filter.params.min} <= val <= ${filter.params.max}`;
            else if (hasMin) descText = `val >= ${filter.params.min}`;
            else descText = `val <= ${filter.params.max}`;
        } else {
            const categories = filter.params.categories.join(', ');
            descText = `${filter.params.exclude ? 'Exclude' : 'Include'}: [${categories}]`;
        }

        badge.innerHTML = `
            <div class="filter-info">
                <h5>${filter.params.column}</h5>
                <p>${filter.name === 'numeric_range' ? 'Numeric Range' : 'Category Filter'}: ${descText}</p>
            </div>
            <button class="btn-remove-filter" data-index="${idx}">&times;</button>
        `;

        // Remove handler
        badge.querySelector('.btn-remove-filter').addEventListener('click', (e) => {
            const removeIdx = parseInt(e.target.dataset.index);
            state.activeFilters.splice(removeIdx, 1);
            renderActiveFilters();
        });

        els.activeFilters.appendChild(badge);
    });
}

// Client-side sorting for Step 4 statistical results
export function sortResults(field) {
    if (state.sortColumn === field) {
        state.sortAsc = !state.sortAsc;
    } else {
        state.sortColumn = field;
        state.sortAsc = true;
    }

    state.statResults.sort((a, b) => {
        let valA = a[field];
        let valB = b[field];

        // Keep null/undefined values always at the bottom of the table
        if (valA === null || valA === undefined) {
            if (valB === null || valB === undefined) return 0;
            return 1;
        }
        if (valB === null || valB === undefined) {
            return -1;
        }

        if (typeof valA === 'number' && typeof valB === 'number') {
            return state.sortAsc ? valA - valB : valB - valA;
        } else {
            // String comparison
            const strA = String(valA).toLowerCase();
            const strB = String(valB).toLowerCase();
            if (strA < strB) return state.sortAsc ? -1 : 1;
            if (strA > strB) return state.sortAsc ? 1 : -1;
            return 0;
        }
    });

    renderResultsTable();
}

// Chart instance to be managed
export let chartInstance = null;

// Render the significance chart
export function renderSignificanceChart() {
    if (!els.significanceChart) return;

    if (!state.statResults || state.statResults.length === 0) {
        els.significanceChart.style.display = 'none';
        return;
    }

    const filterInput = els.plotsSigFilter;
    let limit = 0.05;
    if (filterInput) {
        limit = parseFloat(filterInput.value);
        if (isNaN(limit) || limit < 0) {
            limit = 0.05;
        }
    }
    const strictLimit = limit * 0.2;

    // Filter out null p-values and sort ascending
    const validResults = state.statResults
        .filter(res => res.p_value !== null && res.p_value !== undefined)
        .sort((a, b) => a.p_value - b.p_value);

    if (validResults.length === 0) {
        els.significanceChart.style.display = 'none';
        return;
    }

    els.significanceChart.style.display = 'block';

    const labels = validResults.map(res => res.column_name || 'Unknown');
    const data = validResults.map(res => res.p_value);

    // Color logic
    const backgroundColors = validResults.map(res => {
        if (res.p_value <= strictLimit) {
            return 'rgba(16, 185, 129, 0.8)'; // Green
        } else if (res.p_value <= limit) {
            return 'rgba(250, 204, 21, 0.8)'; // Yellow
        } else {
            return 'rgba(255, 255, 255, 0.1)'; // Default gray-ish
        }
    });

    if (chartInstance) {
        chartInstance.destroy();
    }

    const ctx = els.significanceChart.getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'p-value Limit',
                    data: labels.map(() => limit),
                    borderColor: 'rgba(250, 204, 21, 0.5)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    fill: 1,
                    backgroundColor: 'rgba(250, 204, 21, 0.12)',
                    order: 2
                },
                {
                    label: 'p-value Strict Limit',
                    data: labels.map(() => strictLimit),
                    borderColor: 'rgba(16, 185, 129, 0.5)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    fill: 'start',
                    backgroundColor: 'rgba(16, 185, 129, 0.12)',
                    order: 3
                },
                {
                    label: 'p-value',
                    data: data,
                    showLine: false,
                    pointBackgroundColor: backgroundColors,
                    pointBorderColor: 'rgba(255, 255, 255, 0.3)',
                    pointBorderWidth: 1,
                    pointRadius: 6,
                    pointHoverRadius: 9,
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Significance Chart',
                    color: '#f1f3f9'
                },
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: limit * 3,
                    title: {
                        display: true,
                        text: 'p-value',
                        color: '#9aa0a6'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#9aa0a6'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Columns (Sorted by p-value)',
                        color: '#9aa0a6'
                    },
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#9aa0a6',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// Render the results table
export function renderResultsTable() {
    const container = document.getElementById('statResultsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (!state.statResults || state.statResults.length === 0) {
        container.textContent = 'No statistical results generated.';
        return;
    }

    // Also render chart
    renderSignificanceChart();

    const wrapper = document.createElement('div');
    wrapper.className = 'overflow-auto';

    const table = document.createElement('table');
    table.className = 'results-table striped';

    const thead = document.createElement('thead');
    const tr = document.createElement('tr');

    const headers = [
        { label: 'Column', field: 'column_name' },
        { label: 'Method', field: 'method_name' },
        { label: 'Statistic', field: 'test_statistic' },
        { label: 'p-value', field: 'p_value' },
        { label: 'Effect Size', field: 'effect_size' }
    ];

    headers.forEach(h => {
        const th = document.createElement('th');
        th.setAttribute('scope', 'col');
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.dataset.field = h.field;

        let indicator = '';
        if (state.sortColumn === h.field) {
            indicator = state.sortAsc ? ' ▲' : ' ▼';
        }
        th.textContent = h.label + indicator;

        th.addEventListener('click', () => {
            sortResults(h.field);
        });

        tr.appendChild(th);
    });

    thead.appendChild(tr);
    table.appendChild(thead);

    const filterInput = els.plotsSigFilter;
    let limit = 0.05;
    if (filterInput) {
        limit = parseFloat(filterInput.value);
        if (isNaN(limit) || limit < 0) {
            limit = 0.05;
        }
    }
    const strictLimit = limit * 0.2;

    const tbody = document.createElement('tbody');
    state.statResults.forEach(res => {
        const trRow = document.createElement('tr');

        trRow.innerHTML = `
            <td>${res.column_name || ''}</td>
            <td>${res.method_name}</td>
            <td>${res.test_statistic !== null && res.test_statistic !== undefined ? Number(res.test_statistic).toFixed(4) : ''}</td>
            <td>${res.p_value !== null && res.p_value !== undefined ? Number(res.p_value).toFixed(6) : ''}</td>
            <td>${res.effect_size !== null && res.effect_size !== undefined ? Number(res.effect_size).toFixed(4) : ''}</td>
        `;

        if (res.p_value !== null && res.p_value !== undefined) {
            let bgColor = '';
            if (res.p_value <= strictLimit) {
                bgColor = 'rgba(16, 185, 129, 0.12)'; // Green matching the chart's strict limit zone
            } else if (res.p_value <= limit) {
                bgColor = 'rgba(250, 204, 21, 0.12)'; // Yellow matching the chart's limit zone
            }

            if (bgColor) {
                trRow.querySelectorAll('td').forEach(td => {
                    td.style.backgroundColor = bgColor;
                });
            }
        }

        tbody.appendChild(trRow);
    });
    table.appendChild(tbody);
    wrapper.appendChild(table);
    container.appendChild(wrapper);
}

// Calculate the number of variables with p-value <= significance threshold
export function updatePlotsFilter() {
    const filterInput = els.plotsSigFilter;
    if (!filterInput) return;

    let threshold = parseFloat(filterInput.value);
    if (isNaN(threshold) || threshold < 0) {
        threshold = 0.05;
    }

    const matchingResults = state.statResults.filter(res => res.p_value !== null && res.p_value !== undefined && res.p_value <= threshold);
    const count = matchingResults.length;

    state.plotsTopN = count;

    if (els.filteredPlotsCounter) {
        els.filteredPlotsCounter.textContent = `Matches ${count} variable${count !== 1 ? 's' : ''}`;
    }

    // Update step 5 plots count if needed
    updatePlotsCounter();
}

// Update the counter text in Step 5 plots selector
export function updatePlotsCounter() {
    const numVariables = state.plotsTopN;
    const numPlots = state.selectedPlots.length;
    const totalPlots = numVariables * numPlots;

    if (els.plotsGenerationCounter) {
        els.plotsGenerationCounter.textContent = `Will generate ${totalPlots} plot${totalPlots !== 1 ? 's' : ''} (${numVariables} variable${numVariables !== 1 ? 's' : ''} × ${numPlots} plot type${numPlots !== 1 ? 's' : ''})`;
    }

    if (els.btnGeneratePlots) {
        els.btnGeneratePlots.disabled = totalPlots === 0;
    }
}

// Render the checkbox list of value columns in Step 1
export function updateValueColumnsList() {
    const selectedGroupCol = els.groupColSelect.value;
    
    // --- Render Continuous Columns ---
    const filterText = (els.valueColSearch?.value || '').toLowerCase().trim();
    els.valueColumnsList.innerHTML = '';
    let hasColumns = false;
    let hasVisibleColumns = false;

    state.selectedDatasetColumns.forEach(col => {
        if (col.is_numeric && col.name !== selectedGroupCol) {
            hasColumns = true;

            // Check if column name matches filter text
            if (filterText && !col.name.toLowerCase().includes(filterText)) {
                return;
            }

            hasVisibleColumns = true;

            const item = document.createElement('label');
            item.className = 'value-column-item';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = col.name;
            cb.checked = state.selectedValueColumns.has(col.name);
            cb.addEventListener('change', (e) => {
                if (e.target.checked) {
                    state.selectedValueColumns.add(col.name);
                } else {
                    state.selectedValueColumns.delete(col.name);
                }
                validateStep1Next();
            });

            const span = document.createElement('span');
            span.textContent = `${col.name} (${col.dtype})`;

            item.appendChild(cb);
            item.appendChild(span);
            els.valueColumnsList.appendChild(item);
        }
    });

    if (!hasColumns) {
        els.valueColumnsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No continuous columns available.</span>';
    } else if (!hasVisibleColumns) {
        els.valueColumnsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No columns match search.</span>';
    }

    // --- Render Discrete Columns ---
    const filterDiscreteText = (els.discreteColSearch?.value || '').toLowerCase().trim();
    els.discreteColumnsList.innerHTML = '';
    let hasDiscreteColumns = false;
    let hasVisibleDiscreteColumns = false;

    state.selectedDatasetColumns.forEach(col => {
        if (col.is_discrete && col.name !== selectedGroupCol) {
            hasDiscreteColumns = true;

            // Check if column name matches filter text
            if (filterDiscreteText && !col.name.toLowerCase().includes(filterDiscreteText)) {
                return;
            }

            hasVisibleDiscreteColumns = true;

            const item = document.createElement('label');
            item.className = 'value-column-item';

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = col.name;
            cb.checked = state.selectedDiscreteColumns.has(col.name);
            cb.addEventListener('change', (e) => {
                if (e.target.checked) {
                    state.selectedDiscreteColumns.add(col.name);
                } else {
                    state.selectedDiscreteColumns.delete(col.name);
                }
                validateStep1Next();
            });

            const span = document.createElement('span');
            span.textContent = `${col.name} (${col.dtype})`;

            item.appendChild(cb);
            item.appendChild(span);
            els.discreteColumnsList.appendChild(item);
        }
    });

    if (!hasDiscreteColumns) {
        els.discreteColumnsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No discrete columns available.</span>';
    } else if (!hasVisibleDiscreteColumns) {
        els.discreteColumnsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No columns match search.</span>';
    }

    validateStep1Next();
}

// Validate if Step 1 transitions are allowed
export function validateStep1Next() {
    const selectedGroupCol = els.groupColSelect.value;
    const hasDependentCol = state.selectedValueColumns.size > 0 || state.selectedDiscreteColumns.size > 0;

    // In Step 1, update the sidebar next button instead
    if (state.currentStep === 'dataset_selection') {
        if (!selectedGroupCol || !hasDependentCol || state.selectedGroups.size === 0) {
            if (els.btnSidebarNext) els.btnSidebarNext.disabled = true;
        } else {
            if (els.btnSidebarNext) els.btnSidebarNext.disabled = false;
        }
    }
}

// Render the subgroups checkbox list in Step 1
export function renderSubgroupsList() {
    els.subgroupsList.innerHTML = '';
    const filterText = (els.subgroupsSearch?.value || '').toLowerCase().trim();

    let hasVisibleGroups = false;

    state.availableGroups.forEach(groupVal => {
        if (filterText && !groupVal.toLowerCase().includes(filterText)) {
            return;
        }

        hasVisibleGroups = true;

        const item = document.createElement('label');
        item.className = 'value-column-item';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = groupVal;
        cb.checked = state.selectedGroups.has(groupVal);
        cb.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedGroups.add(groupVal);
            } else {
                state.selectedGroups.delete(groupVal);
            }
            validateStep1Next();
        });

        const span = document.createElement('span');
        span.textContent = groupVal;

        item.appendChild(cb);
        item.appendChild(span);
        els.subgroupsList.appendChild(item);
    });

    if (state.availableGroups.length === 0) {
        els.subgroupsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No values available in this column.</span>';
    } else if (!hasVisibleGroups) {
        els.subgroupsList.innerHTML = '<span class="no-columns-msg" style="color: var(--text-secondary); font-size: 0.95rem;">No subgroups match search.</span>';
    }

    els.subgroupsSection.classList.remove('hidden');
    validateStep1Next();
}
