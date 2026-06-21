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
