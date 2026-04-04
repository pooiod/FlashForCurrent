(function () {
    'use strict';
    const API_BASE = "http://localhost:48753", WS_URL = "ws://localhost:48754";
    const FLASH_DOMAINS = ["scratchflash.pages.dev", "flashloader.pages.dev"];
    var hasPrompted = false;

    let isFlashMode = false, ws = null, imgElement = null, miniLoader = null, fullPageLoader = null, firstSyncDone = false;

    function isFlash() {
        if (FLASH_DOMAINS.includes(window.location.hostname)) return true;
        return !!document.querySelector('object, embed[type*="flash"], img[alt*="Get Flash" i]');
    }

    function norm(url) { return url.replace(/\/$/, "").toLowerCase(); }

    function initStreaming() {
        isFlashMode = true; document.body.innerHTML = "";
        document.body.style = "margin:0;background:#fff;overflow:hidden;user-select:none;-webkit-user-select:none;";

        imgElement = document.createElement('img');
        imgElement.style = "width:100vw;height:100vh;object-fit:fill;transition:filter 0.3s ease;pointer-events:none;";

        fullPageLoader = document.createElement('div');
        fullPageLoader.style = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:#fff;z-index:99999;display:none;flex-direction:column;justify-content:center;align-items:center;font-family:sans-serif;";
        fullPageLoader.innerHTML = `<div class='spinner'></div><div style='margin-top:20px;color:#333'>Loading page...</div>`;

        miniLoader = document.createElement('div');
        miniLoader.className = 'spinner mini';
        miniLoader.style = "position:fixed;bottom:20px;right:20px;z-index:99998;display:none;";

        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes s { to { transform: rotate(360deg); } }
            .spinner { width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: s 1s linear infinite; }
            .spinner.mini { width: 25px; height: 25px; border-width: 3px; }
        `;
        document.head.appendChild(style);
        document.body.append(imgElement, fullPageLoader, miniLoader);

        setupWebSocket(); setupInputs(); syncUrl();
    }

    function syncUrl() {
        fetch(`${API_BASE}/set_url`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: window.location.href }) })
            .then(() => {
                firstSyncDone = true;
                fetch(`${API_BASE}/set_size`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ width: window.innerWidth, height: window.innerHeight }) });
            });
    }

    function setupWebSocket() {
        if (ws) ws.close();
        ws = new WebSocket(WS_URL); ws.binaryType = "blob";
        ws.onmessage = (e) => {
            if (e.data instanceof Blob) {
                const url = URL.createObjectURL(e.data);
                imgElement.src = url;
                imgElement.onload = () => { URL.revokeObjectURL(url); if (document.hasFocus()) ws.send(JSON.stringify({ type: 'get_frame' })); };
            } else {
                const data = JSON.parse(e.data);
                if (data.type === 'cursor') document.body.style.cursor = data.value;
                if (data.type === 'download_file') {
                    if (!document.hasFocus()) return;
                    const link = document.createElement('a');
                    link.style.display = 'none';
                    link.href = "data:application/octet-stream;base64," + data.data;
                    link.download = data.filename;
                    document.body.appendChild(link);
                    link.click();
                    setTimeout(() => link.remove(), 100);
                }
                if (data.type === 'request_upload') {
                    const input = document.createElement('input'); input.type = 'file';
                    input.onchange = () => {
                        if (!input.files[0]) return;
                        const r = new FileReader();
                        r.onload = () => ws.send(JSON.stringify({ type: 'file_upload', filename: input.files[0].name, data: r.result.split(',')[1] }));
                        r.readAsDataURL(input.files[0]);
                    };
                    input.click();
                }
            }
        };
        ws.onopen = () => ws.send(JSON.stringify({ type: 'get_frame' }));
        ws.onclose = () => { if (isFlashMode) setTimeout(setupWebSocket, 1000); };
    }

    function setupInputs() {
        const getPct = (e) => ({ x_pct: e.clientX / window.innerWidth, y_pct: e.clientY / window.innerHeight });
        window.addEventListener('mousemove', (e) => { if (ws?.readyState === 1 && document.hasFocus()) ws.send(JSON.stringify({ type: 'mouse_move', ...getPct(e) })); });
        window.addEventListener('wheel', (e) => { if (ws?.readyState === 1 && document.hasFocus()) { e.preventDefault(); ws.send(JSON.stringify({ type: 'scroll', ...getPct(e), dx: e.deltaX * -0.5, dy: e.deltaY * -0.5 })); } }, { passive: false });
        const sendR = (o) => { if (ws?.readyState === 1 && document.hasFocus()) ws.send(JSON.stringify(o)); };
        window.addEventListener('mousedown', (e) => sendR({ type: 'mouse_click', act: 'mousedown', button: e.button, ...getPct(e) }));
        window.addEventListener('mouseup', (e) => sendR({ type: 'mouse_click', act: 'mouseup', button: e.button, ...getPct(e) }));
        window.addEventListener('keydown', (e) => { if (e.ctrlKey && (e.key === 'w' || e.key === 'r')) return; e.preventDefault(); sendR({ type: 'keyboard', act: 'keydown', key: e.key, ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey, isRepeat: e.repeat }); }, true);
        window.addEventListener('keyup', (e) => { e.preventDefault(); sendR({ type: 'keyboard', act: 'keyup', key: e.key, ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey, isRepeat: false }); }, true);
        document.addEventListener('contextmenu', e => e.preventDefault());
    }

    function showPrompt() {
        if (hasPrompted) return;
        hasPrompted = true;
        const n = document.createElement('div');
        n.id = 'flash-prompt';
        n.style = "position:fixed;top:20px;right:20px;background:#2c3e50;color:#ecf0f1;padding:20px;z-index:999999;font-family:sans-serif;width:280px;";
        n.innerHTML = `
            <div style='font-weight:bold;margin-bottom:8px;font-size:15px;'>Unable to load flash content</div>
            <div style='font-size:13px;line-height:1.4;margin-bottom:15px;'>Please install the flash helper to view flash content on this page.</div>
            <a href='https://github.com/pooiod/FlashForCurrent/releases/latest' target='_blank' style='display:inline-block;background:#3498db;color:#fff;text-decoration:none;padding:8px 12px;font-size:12px;font-weight:bold;border-radius:2px;'>Download helper</a>
            <button onclick="document.getElementById('flash-prompt')?.remove();clearInterval(fetchinterval85025);" style='display:inline-block;border:none;background:#3498db;color:#fff;text-decoration:none;padding:8px 12px;font-size:12px;font-weight:bold;border-radius:2px;'>Nah, I'm good</button>
        `;
        document.body.appendChild(n);
    }

    window.onfocus = () => { if (isFlashMode) { syncUrl(); if (ws?.readyState === 1) ws.send(JSON.stringify({ type: 'get_frame' })); } };

    window.fetchinterval85025 = setInterval(() => {
        if (!isFlashMode) {
            if (isFlash() && document.hasFocus()) fetch(`${API_BASE}/status`).then(initStreaming).catch(() => showPrompt());
        } else {
            fetch(`${API_BASE}/keep_alive`, { method: 'POST' }).catch(() => { });
            imgElement.style.filter = document.hasFocus() ? "none" : "invert(10%) blur(5px)";
            if (document.hasFocus()) {
                fetch(`${API_BASE}/status`).then(r => r.json()).then(data => {
                    miniLoader.style.display = data.is_loading ? "block" : "none";
                    fullPageLoader.style.display = (norm(data.url) !== norm(window.location.href) && data.url !== "about:blank") ? "flex" : "none";

                    if (data.pending_redirect && firstSyncDone) {
                        fetch(`${API_BASE}/clear_redirect`, { method: 'POST' }); window.location.href = data.pending_redirect;
                    } else if (norm(data.url) !== norm(window.location.href) && data.url !== "about:blank") { syncUrl(); }
                });
            }
        }
    }, 500);

    window.addEventListener('resize', () => { if (isFlashMode) syncUrl(); });
})();
