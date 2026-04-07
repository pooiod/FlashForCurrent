// ==UserScript==
// @name         FlashForCurrent
// @namespace    http://tampermonkey.net/
// @version      2026-04-04
// @description  Native flash in modern browsers
// @author       pooiod7
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function() {
    const loader = document.createElement('div');
    loader.id = 'dynamic-script-loader-34924';
    loader.innerHTML = '<div class="spin-4534ner-28420249"></div>';

    function isFlash() {
        const FLASH_DOMAINS = ["scratchflash.pages.dev", "flashloader.pages.dev"];
        if (FLASH_DOMAINS.includes(window.location.hostname)) return true;
        return !!document.querySelector('object, embed[type*="flash"], img[alt*="Get Flash" i]');
    }

    window.HasFlashForCurrent = true;

    const style = document.createElement('style');
    style.textContent = `
        #dynamic-script-loader-34924 {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 99999;
            padding: 12px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: opacity 0.4s ease;
            opacity: ${isFlash()?"1":"0"}
        }
        .spin-4534ner-28420249 {
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-top: 3px solid #0066ff;
            border-radius: 50%;
            animation: spin-4534 0.8s linear infinite;
        }
        @keyframes spin-4534 {
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
    document.body.appendChild(loader);

    const script = document.createElement('script');
    script.src = 'https://flashforcurrent.pages.dev/main.js';

    const hideLoader = () => {
        loader.style.opacity = '0';
        setTimeout(() => loader.remove(), 400);
    };

    script.onload = () => {
        setTimeout(function() {
            hideLoader();
        }, 1000);
    };

    script.onerror = () => {
        if (!isFlash()) return;
        hideLoader();

        const n = document.createElement('div');
        n.id = 'flash-prompt';
        n.style = "position:fixed;top:20px;right:20px;background:#2c3e50;color:#ecf0f1;padding:20px;z-index:999999;font-family:sans-serif;width:280px;";
        n.innerHTML = `
            <div style='font-weight:bold;margin-bottom:8px;font-size:15px;'>Unable to load flash content</div>
            <div style='font-size:13px;line-height:1.4;margin-bottom:15px;'>The FlashForCurrent library was unable to load</div>
        `;
        document.body.appendChild(n);

        setTimeout(()=>{
            n.remove();
        }, 2000)
    };

    document.head.appendChild(script);
})();
