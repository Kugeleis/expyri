const THEME_STORAGE_KEY = 'expyri-theme';
const THEME_COOKIE_KEY = 'expyri_theme';
const THEMES = {
    dark: {
        next: 'light',
        label: 'Switch to light mode'
    },
    light: {
        next: 'dark',
        label: 'Switch to dark mode'
    }
};

function currentTheme() {
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function syncThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) {
        return;
    }

    const theme = currentTheme();
    toggle.setAttribute('aria-label', THEMES[theme].label);
    toggle.setAttribute('title', THEMES[theme].label);
}

function syncThemeCookie(theme) {
    document.cookie = `${THEME_COOKIE_KEY}=${theme}; path=/; max-age=31536000; SameSite=Lax`;
}

function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    syncThemeCookie(theme);
    try {
        window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
        // The visual toggle should still work if storage is unavailable.
    }
    syncThemeToggle();
}

document.addEventListener('DOMContentLoaded', () => {
    syncThemeCookie(currentTheme());
    syncThemeToggle();

    const toggle = document.getElementById('theme-toggle');
    if (!toggle) {
        return;
    }

    toggle.addEventListener('click', () => {
        setTheme(THEMES[currentTheme()].next);
    });
});
