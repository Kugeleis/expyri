import { initEventListeners } from './modules/events.js';
import { startNewSession } from './modules/api.js';

// Initialize application
window.addEventListener('DOMContentLoaded', async () => {
    initEventListeners();
    await startNewSession();
});
