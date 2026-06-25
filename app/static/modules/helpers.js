import { els } from './elements.js';

// Show Error Toast UI
export function showError(message) {
    if (!els.toastMsg || !els.errorToast) return;
    els.toastMsg.textContent = message;
    els.errorToast.classList.remove('hidden');

    // Automatically hide after 5 seconds
    setTimeout(() => {
        els.errorToast.classList.add('hidden');
    }, 5000);
}

// Set session status bar state
export function setSessionStatus(text, type) {
    if (!els.sessionInfo) return;
    const textEl = els.sessionInfo.querySelector('.text');
    const dotEl = els.sessionInfo.querySelector('.dot');
    if (textEl) textEl.textContent = text;

    if (dotEl) {
        dotEl.style.backgroundColor =
            type === 'active' ? 'var(--success-green)' :
            type === 'waiting' ? 'orange' : 'red';
    }
}

// Dtype checkers
export function isNumericDtype(col) {
    if (!col || !col.dtype) return false;
    const dt = col.dtype.toLowerCase();
    return dt.startsWith('int') || dt.startsWith('float');
}

export function isDiscreteDtype(col) {
    if (!col || !col.dtype) return false;
    const dt = col.dtype.toLowerCase();
    return dt === 'object' || dt === 'category' || dt === 'bool';
}

export function formatMethodName(name) {
    if (!name) return '';
    const prettyNames = {
        'anova': 'One-way ANOVA',
        'chi_square': 'Chi-Square Test',
        'cluster_mean_anova': 'Cluster Mean ANOVA',
        'cluster_mean_kruskal_wallis': 'Cluster Mean Kruskal-Wallis',
        'linear_mixed_model': 'Linear Mixed Model (LMM)',
        'proportion_kruskal_wallis': 'Proportion Kruskal-Wallis',
        'grubbs_cluster_outlier': 'Grubbs Cluster Outlier',
        'levene_cluster_uniformity': "Levene's Cluster Uniformity",
        'kruskal_wallis': 'Kruskal-Wallis H Test',
        'mann_whitney': 'Mann-Whitney U Test',
        'ttest_ind': 'Independent Two-Sample t-Test'
    };
    if (name in prettyNames) {
        return prettyNames[name];
    }
    // Fallback: title case replacement for any future custom method name
    return name
        .split('_')
        .map(word => {
            if (word.toLowerCase() === 'anova') return 'ANOVA';
            if (word.toLowerCase() === 'lmm') return 'LMM';
            if (word.toLowerCase() === 'ttest') return 't-Test';
            return word.charAt(0).toUpperCase() + word.slice(1);
        })
        .join(' ');
}
