/**
 * Odoo 17: Force the browser tab title to a custom value (or blank)
 * Place this file in your module's static/src/js/ directory and add it to web.assets_backend in your manifest.
 */
(function () {
    "use strict";
    // The title you want to force
    const FORCED_TITLE = "SplitPay"; // or "" for blank

    function setTitle() {
        if (document.title !== FORCED_TITLE) {
            document.title = FORCED_TITLE;
        }
    }

    // Set initially
    setTitle();

    // Observe changes to the <title> element and override
    const titleElement = document.querySelector('title');
    if (titleElement) {
        const observer = new MutationObserver(setTitle);
        observer.observe(titleElement, { childList: true });
    }

    // Also, listen for route changes (Odoo SPA navigation)
    window.addEventListener('hashchange', setTitle);
    window.addEventListener('popstate', setTitle);
})();