import webview
import time
import os
import urllib.request
import shutil
import threading
import ctypes

def get_loading_html(message="Loading Releases..."):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                background-color: #ffffff;
                color: #333333;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin-bottom: 20px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="spinner"></div>
        <div style="font-weight: 500;">{message}</div>
    </body>
    </html>
    """

INJECTED_JS = """
if (!document.getElementById('custom-hide-style')) {
    const style = document.createElement('style');
    style.id = 'custom-hide-style';
    style.innerHTML = `
        header,
        footer,
        #repository-container-header,
        .header-wrapper.js-header-wrapper {
            display: none !important;
        }
    `;
    document.head.appendChild(style);
}

function cleanGitHubUI() {
    const selectors = [
        'header',
        'footer',
        '#repository-container-header',
        '.header-wrapper.js-header-wrapper'
    ];

    selectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(el => el.remove());
    });

    document.querySelectorAll('li').forEach(li => {
        if (li.textContent.includes('Source')) {
            li.remove();
        }
    });

    document.querySelectorAll('a[href$=".exe"]').forEach(a => {
        if (!a.dataset.intercepted) {
            a.dataset.intercepted = "true";
            a.addEventListener('click', function(e) {
                e.preventDefault();

                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.download_and_install(this.href);
                }
            });
        }
    });
}

cleanGitHubUI();
setInterval(cleanGitHubUI, 1000);
"""

class Api:
    def download_and_install(self, url):
        t = threading.Thread(target=self._download_flow, args=(url,))
        t.start()

    def _download_flow(self, url):
        time.sleep(0.2)

        window = webview.windows[0]
        window.load_html(get_loading_html("Downloading and Installing..."))

        try:
            appdata = os.getenv('APPDATA')
            startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

            os.makedirs(startup_dir, exist_ok=True)

            filename = url.split('/')[-1]
            target_path = os.path.join(startup_dir, filename)

            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)

            os.startfile(target_path)

            js_finish = "alert('FlashForCurrent Installed'); window.pywebview.api.close_app();"
            window.evaluate_js(js_finish)

        except Exception as e:
            window.evaluate_js(f"alert('Installation failed: {str(e)}');")
            window.load_url("https://github.com/pooiod/FlashForCurrent/releases/latest")

    def close_app(self):
        webview.windows[0].destroy()

def on_loaded():
    if webview.windows:
        webview.windows[0].evaluate_js(INJECTED_JS)

def load_logic(window):
    time.sleep(2.5)
    target_url = "https://github.com/pooiod/FlashForCurrent/releases/latest"
    window.load_url(target_url)

if __name__ == "__main__":
    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    window_width = screen_width // 2
    window_height = screen_height // 2

    window_x = (screen_width - window_width) // 2
    window_y = (screen_height - window_height) // 2

    api = Api()

    window = webview.create_window(
        title='FlashHelper Installer',
        html=get_loading_html(),
        width=window_width,
        height=window_height,
        x=window_x,
        y=window_y,
        js_api=api
    )

    window.events.loaded += on_loaded

    webview.start(load_logic, window)
