import { state } from './state.js';
import { els, stepsConfig } from './elements.js';
import { showError } from './helpers.js';
import { renderActiveFilters } from './ui.js';
import { fetchApplicableMethods, fetchApplicablePlots } from './api.js';

// Navigate to a specific step panel
export function navigateToStep(stepKey) {
    state.currentStep = stepKey;

    let activeIndex = stepsConfig.findIndex(s => s.key === stepKey);
    if (activeIndex === -1) activeIndex = 0;

    stepsConfig.forEach((step, idx) => {
        const navEl = document.getElementById(step.navId);
        const panelEl = document.getElementById(step.panelId);

        // Manage Panel Views
        if (idx === activeIndex) {
            panelEl.classList.add('active');
            navEl.className = 'step-nav-item active';
        } else {
            panelEl.classList.remove('active');
            if (idx < activeIndex) {
                navEl.className = 'step-nav-item completed';
            } else {
                navEl.className = 'step-nav-item';
            }
        }

        // Remove old click listeners by cloning
        const newNavEl = navEl.cloneNode(true);
        navEl.parentNode.replaceChild(newNavEl, navEl);

        // Add click handler for completed steps
        if (idx < activeIndex) {
            newNavEl.addEventListener('click', () => {
                goToStep(step.key);
            });
        }
    });

    updateSidebarButtons();
}

// Update state and appearance of sidebar Back/Next buttons based on current step
export function updateSidebarButtons() {
    if (!els.btnSidebarBack || !els.btnSidebarNext) return;

    const activeIndex = stepsConfig.findIndex(s => s.key === state.currentStep);

    // Back button visibility
    if (activeIndex === 0) {
        els.btnSidebarBack.style.display = 'none';
    } else {
        els.btnSidebarBack.style.display = 'block';
    }

    // Reset next button state
    els.btnSidebarNext.disabled = false;
    els.btnSidebarNext.innerHTML = '&rarr;';
    els.btnSidebarNext.title = 'Continue';

    // Step-specific logic for Next button disabled state
    switch (state.currentStep) {
        case 'dataset_selection':
            // Logic handled by validateStep1Next in ui.js
            import('./ui.js').then(ui => ui.validateStep1Next());
            break;
        case 'filters':
            els.btnSidebarNext.disabled = false; // Filters are optional
            break;
        case 'stat_method':
            if (!state.selectedMethod && !state.selectedDiscreteMethod) {
                els.btnSidebarNext.disabled = true;
            }
            break;
        case 'results':
            els.btnSidebarNext.disabled = false;
            break;
        case 'plot_selection':
            if (state.selectedPlots.length === 0) {
                els.btnSidebarNext.disabled = true;
            }
            break;
        case 'export':
            els.btnSidebarNext.innerHTML = '&darr;'; // Download icon
            els.btnSidebarNext.title = 'Download Report';
            break;
    }
}

// Navigate back to a previously completed step via backend
export async function goToStep(stepKey) {
    try {
        const response = await fetch(`/wizard/sessions/${state.sessionId}/go-to/${stepKey}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to navigate to step.');
        }

        const data = await response.json();

        // Update local state from server response
        state.currentStep = data.current_step;
        state.selectedMethod = data.selected_method || '';
        state.activeFilters = data.filters_config || [];
        state.selectedPlots = data.selected_plots || [];

        // Re-render UI for the target step
        navigateToStep(data.current_step);

        // Restore step-specific UI state
        if (stepKey === 'filters') {
            renderActiveFilters();
        } else if (stepKey === 'stat_method') {
            await fetchApplicableMethods();
            // Re-select previously selected method if it's still there
            if (state.selectedMethod) {
                const card = document.querySelector(`.method-card[data-name="${state.selectedMethod}"]`);
                if (card) {
                    card.classList.add('selected');
                }
            }
            updateSidebarButtons(); // Re-evaluate after method re-selection
        } else if (stepKey === 'plot_selection') {
            await fetchApplicablePlots();
        }
    } catch (err) {
        showError(err.message);
    }
}
