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

// DRY Shared Pac-Man loader animator
export function animatePacman({ stage, textRow, pacman, pacBody, text, cycleTime = 3000, pacWidth = 20, letterFontSize = '16px' }) {
    if (!textRow || !pacman || !pacBody || !stage) return;

    const spans = [];
    textRow.innerHTML = '';
    for (const ch of text) {
        const span = document.createElement('span');
        span.className = 'letter';
        if (letterFontSize) span.style.fontSize = letterFontSize;
        span.textContent = ch;
        textRow.appendChild(span);
        spans.push(span);
    }

    function setX(x) {
        if (pacman) pacman.style.left = x + 'px';
    }

    function setEatingMode() {
        if (pacman && pacBody) {
            pacman.style.transform = 'translateY(-50%) scaleX(1)';
            pacBody.className = 'pac-body chomping';
        }
    }

    function setPoopingMode() {
        if (pacman && pacBody) {
            pacman.style.transform = 'translateY(-50%) scaleX(-1)';
            pacBody.className = 'pac-body pooping';
        }
    }

    function runCycle() {
        if (!pacman || !pacman.isConnected) return;
        spans.forEach(s => s.classList.remove('eaten'));
        setEatingMode();

        const stageRect = stage.getBoundingClientRect();
        const textRowRect = textRow.getBoundingClientRect();

        const textLeft = textRowRect.left - stageRect.left;
        const textRight = textRowRect.right - stageRect.left;

        const startX = textLeft - pacWidth - 10;
        const endX = textRight + 10;
        const halfCycle = cycleTime / 2;

        let startTime = null;
        let phase = 'forward';
        let pauseStart = null;

        function tick(ts) {
            if (!pacman || !pacman.isConnected) return;
            if (!startTime) startTime = ts;
            const elapsed = ts - startTime;

            if (phase === 'forward') {
                const t = Math.min(elapsed / halfCycle, 1);
                const x = startX + (endX - startX) * t;
                setX(x);

                const mouthX = x + pacWidth;
                spans.forEach(span => {
                    const r = span.getBoundingClientRect();
                    const mid = r.left - stageRect.left + r.width / 2;
                    if (mid < mouthX) span.classList.add('eaten');
                });

                if (t >= 1) {
                    phase = 'pause';
                    pauseStart = ts;
                    setPoopingMode();
                }

            } else if (phase === 'pause') {
                if (ts - pauseStart > 350) {
                    phase = 'backward';
                    startTime = ts;
                }

            } else if (phase === 'backward') {
                const t = Math.min(elapsed / halfCycle, 1);
                const x = endX + (startX - endX) * t;
                setX(x);

                const buttX = x + pacWidth;
                spans.forEach(span => {
                    const r = span.getBoundingClientRect();
                    const mid = r.left - stageRect.left + r.width / 2;
                    if (mid > buttX) span.classList.remove('eaten');
                });

                if (t >= 1) {
                    setEatingMode();
                    setTimeout(() => {
                        if (pacman && pacman.isConnected) {
                            runCycle();
                        }
                    }, 400);
                    return;
                }
            }

            requestAnimationFrame(tick);
        }

        setX(startX);
        requestAnimationFrame(tick);
    }

    setTimeout(runCycle, 100);
}
