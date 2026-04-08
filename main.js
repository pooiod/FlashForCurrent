(function () {
    'use strict';

    const API_BASE = "http://localhost:48753";
    const WS_URL_STREAM = "ws://localhost:48754";
    const WS_URL_INPUT = "ws://localhost:48755";
    const FLASH_DOMAINS = ["scratchflash.pages.dev", "flashloader.pages.dev"];
    var hasPrompted = false;

    window.HasFlashForCurrent = true;

    const getThemeColors = () => {
        let style = getComputedStyle(document.body).backgroundColor;
        if (!style || style === "transparent" || style === "rgba(0, 0, 0, 0)") {
            style = "rgb(255,255,255)";
        } else if (style.startsWith("rgba")) {
            let parts = style.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+\.?\d*)\)/);
            let r = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[1]) * parseFloat(parts[4]));
            let g = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[2]) * parseFloat(parts[4]));
            let b = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[3]) * parseFloat(parts[4]));
            style = `rgb(${r},${g},${b})`;
        }

        const bgColor = style;
        const tempElem = document.createElement("div");
        tempElem.style.color = bgColor;
        document.body.appendChild(tempElem);
        const rgbStyle = window.getComputedStyle(tempElem).color;
        document.body.removeChild(tempElem);

        const rgbValues = rgbStyle.match(/\d+/g).map(Number);
        const r = rgbValues[0] / 255;
        const g = rgbValues[1] / 255;
        const b = rgbValues[2] / 255;

        const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        const textColor = luminance > 0.5 ? "#000000" : "#ffffff";

        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0;
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        h *= 360;
        s *= 100;
        l *= 100;

        let accentHue = (h + 180) % 360;
        let accentSat = s < 10 ? 75 : Math.min(s + 20, 100);
        let accentLight;

        if (l > 70) {
            accentLight = 40;
        } else if (l < 30) {
            accentLight = 70;
        } else {
            accentLight = l > 50 ? l - 30 : l + 30;
        }

        if (s < 10) {
            accentHue = 210;
            accentSat = 80;
        }

        const accentColor = `hsl(${Math.round(accentHue)}, ${Math.round(accentSat)}%, ${Math.round(accentLight)}%)`;

        return {
            background: bgColor,
            accent: accentColor,
            text: textColor
        };
    };

    const theme = getThemeColors();

    let isFlashMode = false, ws_stream = null, ws_input = null, canvasElement = null, ctx = null, miniLoader = null, fullPageLoader = null, firstSyncDone = false;
    let nextFrameMeta = { x: 0, y: 0 };

    function isFlash() {
        if (FLASH_DOMAINS.includes(window.location.hostname)) return true;
        return !!document.querySelector('object, embed[type*="flash"], img[alt*="Get Flash" i]');
    }

    function norm(url) { return url.replace(/\/$/, "").toLowerCase(); }

    function initStreaming() {
        isFlashMode = true; document.body.innerHTML = "";
        document.body.style = `margin:0;background:${theme.background};overflow:hidden;user-select:none;-webkit-user-select:none;`;

        canvasElement = document.createElement('canvas');
        canvasElement.style = `width:100vw;height:100vh;pointer-events:none;display:block;background:${theme.background};`;
        canvasElement.width = window.innerWidth;
        canvasElement.height = window.innerHeight;

        ctx = canvasElement.getContext('2d', { alpha: false });

        ctx.fillStyle = theme.background;
        ctx.fillRect(0, 0, canvasElement.width, canvasElement.height);

        fullPageLoader = document.createElement('div');
        fullPageLoader.style = `position:fixed;top:0;left:0;width:100vw;height:100vh;background:${theme.background};z-index:99999;display:none;flex-direction:column;justify-content:center;align-items:center;font-family:sans-serif;`;
        fullPageLoader.innerHTML = `<div class='spinner'></div><div style='margin-top:20px;color:${theme.text}'>Loading page...</div>`;

        miniLoader = document.createElement('div');
        miniLoader.className = 'spinner mini';
        miniLoader.style = "position:fixed;bottom:20px;right:20px;z-index:99998;display:none;bottom:-40px;";

        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes s { to { transform: rotate(360deg); } }
            .spinner { width: 40px; height: 40px; border: 4px solid #00000000; border-top: 4px solid ${theme.accent}; border-radius: 50%; animation: s 1s linear infinite; }
            .spinner.mini { width: 25px; height: 25px; border-width: 3px; }
        `;
        document.head.appendChild(style);
        document.body.append(canvasElement, fullPageLoader, miniLoader);

        setupStreamWS();
        setupInputWS();
        setupInputs();
        syncUrl();
    }

    function syncUrl() {
        fetch(`${API_BASE}/set_url`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: window.location.href }) })
            .then(() => {
                firstSyncDone = true;
                if (canvasElement) {
                    canvasElement.width = window.innerWidth;
                    canvasElement.height = window.innerHeight;
                    ctx.fillStyle = theme.background;
                    ctx.fillRect(0, 0, canvasElement.width, canvasElement.height);
                }
                fetch(`${API_BASE}/set_size`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ width: window.innerWidth, height: window.innerHeight }) });
            });
    }

    function setupStreamWS() {
        if (ws_stream) {
            ws_stream.onclose = null;
            if (ws_stream.readyState !== WebSocket.CLOSED) ws_stream.close();
        }

        ws_stream = new WebSocket(WS_URL_STREAM);
        ws_stream.binaryType = "blob";

        ws_stream.onmessage = (e) => {
            if (typeof e.data === "string") {
                const data = JSON.parse(e.data);
                if (data.type === 'frame_meta') {
                    nextFrameMeta = { x: data.x, y: data.y };
                } else if (data.type === 'no_change') {
                    if (document.hasFocus() && ws_stream.readyState === 1) ws_stream.send(JSON.stringify({ type: 'get_frame' }));
                }
            } else if (e.data instanceof Blob) {
                const url = URL.createObjectURL(e.data);
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, nextFrameMeta.x, nextFrameMeta.y);
                    URL.revokeObjectURL(url);
                    if (document.hasFocus() && ws_stream.readyState === 1) ws_stream.send(JSON.stringify({ type: 'get_frame' }));
                };
                img.src = url;
            }
        };

        ws_stream.onopen = () => ws_stream.send(JSON.stringify({ type: 'get_frame' }));
        ws_stream.onclose = () => { if (isFlashMode) setTimeout(setupStreamWS, 1000); };
        ws_stream.onerror = () => { ws_stream.close(); };
    }

    function setupInputWS() {
        if (ws_input) {
            ws_input.onclose = null;
            if (ws_input.readyState !== WebSocket.CLOSED) ws_input.close();
        }

        ws_input = new WebSocket(WS_URL_INPUT);

        ws_input.onmessage = (e) => {
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
                    r.onload = () => {
                        if (ws_input.readyState === 1) {
                            ws_input.send(JSON.stringify({ type: 'file_upload', filename: input.files[0].name, data: r.result.split(',')[1] }));
                        }
                    };
                    r.readAsDataURL(input.files[0]);
                };
                input.click();
            }
        };

        ws_input.onclose = () => { if (isFlashMode) setTimeout(setupInputWS, 1000); };
        ws_input.onerror = () => { ws_input.close(); };
    }

    function setupInputs() {
        const getPct = (e) => ({ x_pct: e.clientX / window.innerWidth, y_pct: e.clientY / window.innerHeight });
        window.addEventListener('mousemove', (e) => { if (ws_input?.readyState === 1 && document.hasFocus()) ws_input.send(JSON.stringify({ type: 'mouse_move', ...getPct(e) })); });
        window.addEventListener('wheel', (e) => { if (ws_input?.readyState === 1 && document.hasFocus()) { e.preventDefault(); ws_input.send(JSON.stringify({ type: 'scroll', ...getPct(e), dx: e.deltaX * -1, dy: e.deltaY * -1 })); } }, { passive: false });
        const sendR = (o) => { if (ws_input?.readyState === 1 && document.hasFocus()) ws_input.send(JSON.stringify(o)); };
        window.addEventListener('mousedown', (e) => sendR({ type: 'mouse_click', act: 'mousedown', button: e.button, ...getPct(e) }));
        window.addEventListener('mouseup', (e) => sendR({ type: 'mouse_click', act: 'mouseup', button: e.button, ...getPct(e) }));
        window.addEventListener('keydown', (e) => {
            if (e.ctrlKey && (e.key === 'w' || e.key === 'r' || e.key === 'j')) return;
            e.preventDefault();
            sendR({
                type: 'keyboard',
                act: 'keydown',
                key: e.key,
                ctrl: e.ctrlKey,
                shift: e.shiftKey,
                alt: e.altKey,
                isRepeat: e.repeat
            });
        }, true);

        window.addEventListener('keyup', (e) => {
            e.preventDefault();
            sendR({
                type: 'keyboard',
                act: 'keyup',
                key: e.key,
                ctrl: e.ctrlKey,
                shift: e.shiftKey,
                alt: e.altKey,
                isRepeat: false
            });
        }, true);
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
            <a href='https://flashforcurrent.pages.dev/installer' target='_blank' style='display:inline-block;background:#3498db;color:#fff;text-decoration:none;padding:8px 12px;font-size:12px;font-weight:bold;border-radius:2px;'>Download helper</a>
            <button onclick="document.getElementById('flash-prompt')?.remove();clearInterval(fetchinterval85025);" style='display:inline-block;border:none;background:#3498db;color:#fff;text-decoration:none;padding:8px 12px;font-size:12px;font-weight:bold;border-radius:2px;'>Nah, I'm good</button>
        `;
        document.body.appendChild(n);
    }

    window.onfocus = () => { if (isFlashMode) { syncUrl(); if (ws_stream?.readyState === 1) ws_stream.send(JSON.stringify({ type: 'get_frame' })); } };

    setInterval(() => {
        if (isFlashMode) fetch(`${API_BASE}/keep_alive`, { method: 'POST' }).catch(() => { });
    }, 30000);

    var justHadNoFocus = 0;
    setInterval(()=>{
        if (justHadNoFocus > 0 || document.hidden) {
            fullPageLoader.style.display = "flex";
            justHadNoFocus -= 1;
        }
    }, 100);

    function isTheSame(txt1, txt2){
        return txt1 == txt2
            || decodeURIComponent(txt1).toLowerCase().replace(/\s+/g,'') == decodeURIComponent(txt2).toLowerCase().replace(/\s+/g,'');
    }

    window.fetchinterval85025 = setInterval(() => {
        if (!isFlashMode) {
            if (isFlash() && document.hasFocus()) fetch(`${API_BASE}/status`).then(initStreaming).catch(() => showPrompt());
        } else {
            if (canvasElement) canvasElement.style.filter = document.hasFocus() ? "none" : "invert(10%) blur(5px)";

            if (document.hasFocus()) {
                fetch(`${API_BASE}/status`).then(r => r.json()).then(data => {
                    fullPageLoader.style.display = (!isTheSame(norm(data.url),  norm(window.location.href))) ? "flex" : "none";

                    if (justHadNoFocus > 0) {
                        fullPageLoader.style.display = "flex";
                    }

                    if (data.pending_redirect && firstSyncDone) {
                        if (data.url == "about:blank") return;
                        fetch(`${API_BASE}/clear_redirect`, { method: 'POST' }); window.location.href = data.pending_redirect;
                    } else if (!isTheSame(norm(data.url), norm(window.location.href))) {
                        console.log(data.url, window.location.href);
                        syncUrl();
                    }
                });
            } else {
                justHadNoFocus = 10;
            }
        }
    }, 500);

    window.addEventListener('resize', () => { if (isFlashMode) syncUrl(); });
})();
