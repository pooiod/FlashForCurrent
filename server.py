import sys
import os
import shutil
import threading
import json
import time
import base64
import tempfile
import ctypes
import subprocess
from ctypes import wintypes
from tkinter import messagebox, Tk

os.environ["QT_WEBENGINE_DISABLE_TSF"] = "1"

from flask import Flask, request, jsonify
from flask_cors import CORS

from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QUrl, QCoreApplication, Qt, pyqtSignal, QObject, QPoint, QPointF, pyqtSlot, QDir, QRect
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFrame, QLabel, QPushButton,
                             QLineEdit, QVBoxLayout, QHBoxLayout, QDesktopWidget)
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QIcon, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineScript
from PyQt5.QtWebSockets import QWebSocketServer
from PyQt5.QtNetwork import QHostAddress

downloads = os.path.join(os.path.expanduser("~"), "Downloads")
exe_name = "FlashHelper.exe"
exe_path = os.path.join(downloads, exe_name)
autostart_path = os.path.join(os.getenv('APPDATA'), 'Microsoft\\Windows\\Start Menu\\Programs\\Startup', exe_name)
root = Tk()
root.withdraw()

if os.path.exists(exe_path):
    if messagebox.askyesno("Install FlashHelper", "Do you want to install FlashHelper.exe"):
        shutil.move(exe_path, autostart_path)
        subprocess.Popen(autostart_path, shell=True)
        messagebox.showinfo("Done", "Installed :D")
    else:
        messagebox.showinfo("Cancelled", "Installation cancelled")
    root.destroy()
    sys.exit()

def drop_privileges_and_restart():
    if "--sandboxed" in sys.argv:
        return

    print("Restarting in a restricted sandbox...")

    exe = sys.executable
    args = [exe] + sys.argv + ["--sandboxed"]

    p = subprocess.Popen(args)
    sys.exit(p.wait())

def apply_low_integrity():
    if sys.platform != 'win32': return
    try:
        advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
        GetCurrentProcess = ctypes.WinDLL('kernel32').GetCurrentProcess
        OpenProcessToken = advapi32.OpenProcessToken
        SetTokenInformation = advapi32.SetTokenInformation

        TOKEN_ADJUST_DEFAULT = 0x0080
        TOKEN_ADJUST_SESSIONID = 0x0100
        TOKEN_QUERY = 0x0008
        TOKEN_ADJUST_PRIVILEGES = 0x0020

        hToken = wintypes.HANDLE()
        OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(hToken))

        sid_string = ctypes.c_wchar_p("S-1-16-4096")
        pSid = ctypes.c_void_p()
        advapi32.ConvertStringSidToSidW(sid_string, ctypes.byref(pSid))

        class TOKEN_MANDATORY_LABEL(ctypes.Structure):
            _fields_ = [("Label", ctypes.c_void_p)]

        tml = TOKEN_MANDATORY_LABEL()

        advapi32.SetTokenInformation(hToken, 25, ctypes.byref(tml), ctypes.sizeof(tml))
        ctypes.WinDLL('kernel32').CloseHandle(hToken)
    except Exception as e:
        print(f"Sandbox restriction note: {e}")


if sys.platform == 'win32' and "--sandboxed" not in sys.argv:
    drop_privileges_and_restart()
elif sys.platform == 'win32':
    apply_low_integrity()

FLASH_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "pepflashplayer.dll"))
if not os.path.exists(FLASH_PATH):
    print(f"FATAL ERROR: Flash DLL not found.")
    sys.exit(1)

FLASH_VERSION = "32.0.0.371"
API_PORT = 48753
WS_PORT_STREAM = 48754
WS_PORT_INPUT = 48755

class AppBridge(QObject):
    spawn_window_signal = pyqtSignal()
    set_url_signal = pyqtSignal(str)
    set_size_signal = pyqtSignal(int, int)
    close_signal = pyqtSignal()

bridge = AppBridge()

class WebDialog(QFrame):
    def __init__(self, parent, dtype, msg, default_text=""):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame { background:
            QPushButton { background:
            QLineEdit { background:
        """)
        self.result, self.text_result = False, ""
        self.loop = QtCore.QEventLoop()
        layout = QVBoxLayout(self)
        lbl = QLabel(msg); lbl.setWordWrap(True); layout.addWidget(lbl)
        self.input_field = None
        if dtype == 'prompt':
            self.input_field = QLineEdit(default_text); layout.addWidget(self.input_field)
        btn_layout = QHBoxLayout(); btn_layout.addStretch()
        if dtype in ['confirm', 'prompt']:
            btn_c = QPushButton("Cancel"); btn_c.clicked.connect(self.reject); btn_layout.addWidget(btn_c)
        btn_ok = QPushButton("OK"); btn_ok.clicked.connect(self.accept); btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        self.resize(350, 160)
        self.move(parent.width()//2 - self.width()//2, parent.height()//2 - self.height()//2)
        self.show()
    def accept(self): self.result = True; self.text_result = self.input_field.text() if self.input_field else ""; self.loop.quit()
    def reject(self): self.result = False; self.loop.quit()

class CustomWebPage(QWebEnginePage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_cursor = -1
    def javaScriptAlert(self, securityOrigin, msg):
        dlg = WebDialog(self.view().window(), 'alert', msg); dlg.loop.exec_(); dlg.deleteLater()
    def javaScriptConfirm(self, securityOrigin, msg):
        dlg = WebDialog(self.view().window(), 'confirm', msg); dlg.loop.exec_(); res = dlg.result; dlg.deleteLater(); return res
    def javaScriptPrompt(self, securityOrigin, msg, defaultText):
        dlg = WebDialog(self.view().window(), 'prompt', msg, defaultText); dlg.loop.exec_(); res, txt = dlg.result, dlg.text_result; dlg.deleteLater(); return (True, txt) if res else (False, "")
    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        for c in active_input_handlers: c.client.sendTextMessage(json.dumps({"type": "request_upload"}))
        self.upload_loop = QtCore.QEventLoop(); self.upload_paths = []; self.upload_loop.exec_()
        return self.upload_paths

class FlashBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.resize(900, 500)
        desktop = QDesktopWidget().availableGeometry()
        self.move(desktop.width() + 100, 0)

        self.grabbing_frame = False
        self.pending_chrome_redirect = None
        self.chrome_initiated_nav = False
        self.is_loading = False
        self.active_downloads = {}
        self.browser = QWebEngineView(self)
        self.page = CustomWebPage(self.browser.page().profile(), self.browser)
        self.browser.setPage(self.page)
        self.last_full_frame_time = 0
        self.last_frame_img = None

        script = QWebEngineScript()
        script.setSourceCode("""
            (function() {
                var s = document.createElement('script');
                s.src = 'https://flashforcurrent.pages.dev/script.js';
                document.head.appendChild(s);
            })();

            (function () {
                function createOverlay() {
                    const o = document.createElement("div");
                    o.style.position = "fixed";
                    o.style.top = "0";
                    o.style.left = "0";
                    o.style.width = "100%";
                    o.style.height = "100%";
                    o.style.background = "rgba(0,0,0,0.5)";
                    o.style.display = "flex";
                    o.style.alignItems = "center";
                    o.style.justifyContent = "center";
                    o.style.zIndex = "9999";
                    return o;
                }

                function createBox() {
                    const b = document.createElement("div");
                    b.style.background = "#1e1e2f";
                    b.style.color = "#fff";
                    b.style.padding = "20px";
                    b.style.borderRadius = "12px";
                    b.style.minWidth = "280px";
                    b.style.fontFamily = "sans-serif";
                    b.style.boxShadow = "0 10px 30px rgba(0,0,0,0.3)";
                    b.style.textAlign = "center";
                    return b;
                }

                function createBtn(text) {
                    const btn = document.createElement("button");
                    btn.textContent = text;
                    btn.style.margin = "10px 5px 0";
                    btn.style.padding = "8px 16px";
                    btn.style.border = "none";
                    btn.style.borderRadius = "8px";
                    btn.style.background = "#4f46e5";
                    btn.style.color = "#fff";
                    btn.style.cursor = "pointer";

                    btn.onmouseover = () => btn.style.background = "#6366f1";
                    btn.onmouseout = () => btn.style.background = "#4f46e5";

                    return btn;
                }

                window.alert = function (msg) {
                    return new Promise((res) => {
                        const o = createOverlay();
                        const b = createBox();
                        const p = document.createElement("div");

                        p.textContent = msg;

                        const ok = createBtn("OK");

                        ok.onclick = () => {
                            document.body.removeChild(o);
                            res();
                        };

                        b.appendChild(p);
                        b.appendChild(ok);
                        o.appendChild(b);
                        document.body.appendChild(o);
                    });
                };

                window.confirm = function (msg) {
                    return new Promise((res) => {
                        const o = createOverlay();
                        const b = createBox();
                        const p = document.createElement("div");

                        p.textContent = msg;

                        const yes = createBtn("Yes");
                        const no = createBtn("No");

                        yes.onclick = () => {
                            document.body.removeChild(o);
                            res(true);
                        };

                        no.onclick = () => {
                            document.body.removeChild(o);
                            res(false);
                        };

                        b.appendChild(p);
                        b.appendChild(yes);
                        b.appendChild(no);
                        o.appendChild(b);
                        document.body.appendChild(o);
                    });
                };

                window.prompt = function (msg, def = "") {
                    return new Promise((res) => {
                        const o = createOverlay();
                        const b = createBox();
                        const p = document.createElement("div");

                        p.textContent = msg;

                        const input = document.createElement("input");
                        input.value = def;
                        input.style.width = "90%";
                        input.style.marginTop = "10px";
                        input.style.padding = "8px";
                        input.style.borderRadius = "6px";
                        input.style.border = "none";

                        const ok = createBtn("OK");
                        const cancel = createBtn("Cancel");

                        ok.onclick = () => {
                            document.body.removeChild(o);
                            res(input.value);
                        };

                        cancel.onclick = () => {
                            document.body.removeChild(o);
                            res(null);
                        };

                        b.appendChild(p);
                        b.appendChild(input);
                        b.appendChild(ok);
                        b.appendChild(cancel);
                        o.appendChild(b);
                        document.body.appendChild(o);

                        input.focus();
                    });
                };
            })();
        """)
        script.setInjectionPoint(QWebEngineScript.DocumentReady)
        script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(True)
        self.browser.page().profile().scripts().insert(script)

        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)

        self.browser.urlChanged.connect(self.on_url_changed)
        self.browser.loadStarted.connect(self.start_loading)
        self.browser.loadFinished.connect(self.stop_loading)
        self.browser.page().profile().downloadRequested.connect(self.handle_download)
        self.setCentralWidget(self.browser)
        self.cursor_timer = QtCore.QTimer(self); self.cursor_timer.timeout.connect(self.poll_cursor); self.cursor_timer.start(150)

    def handle_download(self, item):
        self.active_downloads[item] = item.suggestedFileName()
        path = os.path.join(tempfile.gettempdir(), item.suggestedFileName())
        item.setPath(path)
        item.finished.connect(lambda: self.on_download_finished(item))
        item.accept()

    def on_download_finished(self, item):
        if item.state() == 2:
            with open(item.path(), 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            msg = json.dumps({"type": "download_file", "filename": self.active_downloads[item], "data": b64})
            for handler in active_input_handlers:
                handler.client.sendTextMessage(msg)
            try:
                os.remove(item.path())
            except: pass
        if item in self.active_downloads: del self.active_downloads[item]

    def start_loading(self): self.is_loading = True
    def stop_loading(self, ok): self.is_loading = False

    def on_url_changed(self, url):
        u = url.toString()
        if not self.chrome_initiated_nav and u != "about:blank": self.pending_chrome_redirect = u
        self.chrome_initiated_nav = False

    def load_url(self, url):
        if self.browser.url().toString() != url: self.chrome_initiated_nav = True; self.browser.load(QUrl(url))

    def poll_cursor(self):
        cur = self.browser.cursor().shape()
        if cur != self.page.last_cursor:
            self.page.last_cursor = cur
            shape_map = {0: "default", 2: "crosshair", 3: "pointer", 4: "move", 10: "none", 13: "text", 14: "wait", 15: "move", 17: "not-allowed", 18: "grab"}
            msg = json.dumps({"type": "cursor", "value": shape_map.get(cur, "default")})
            for c in active_input_handlers:
                try: c.client.sendTextMessage(msg)
                except: pass

def get_diff_rect(img1, img2):
    if img1.size() != img2.size():
        return QRect(0, 0, img2.width(), img2.height())

    b1 = img1.bits().asstring(img1.byteCount())
    b2 = img2.bits().asstring(img2.byteCount())
    if b1 == b2:
        return None

    w = img1.width()
    h = img1.height()
    bpl = img1.bytesPerLine()

    min_y = 0
    for y in range(h):
        idx = y * bpl
        if b1[idx:idx+bpl] != b2[idx:idx+bpl]:
            min_y = y
            break

    max_y = h - 1
    for y in range(h - 1, min_y - 1, -1):
        idx = y * bpl
        if b1[idx:idx+bpl] != b2[idx:idx+bpl]:
            max_y = y
            break

    return QRect(0, min_y, w, max_y - min_y + 1)

class WSStreamHandler(QObject):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.client.textMessageReceived.connect(self.process_message)

    @pyqtSlot(str)
    def process_message(self, msg):
        global window
        if not window: return
        try:
            data = json.loads(msg); t = data.get('type')
            if t == 'get_frame' and not window.grabbing_frame:
                window.grabbing_frame = True
                now = time.time()
                pix = window.grab()
                img = pix.toImage().convertToFormat(QImage.Format_RGB32)

                is_full = (now - window.last_full_frame_time) >= 1.0 or window.last_frame_img is None or window.last_frame_img.size() != img.size()

                rect = None
                if not is_full:
                    rect = get_diff_rect(window.last_frame_img, img)
                    if rect is None:
                        self.client.sendTextMessage(json.dumps({"type": "no_change"}))
                        window.grabbing_frame = False
                        return
                else:
                    rect = QRect(0, 0, img.width(), img.height())
                    window.last_full_frame_time = now

                window.last_frame_img = img
                cropped = img.copy(rect)

                ba = QtCore.QByteArray()
                buf = QtCore.QBuffer(ba)
                buf.open(QtCore.QIODevice.WriteOnly)
                cropped.save(buf, "JPEG", 70)

                self.client.sendTextMessage(json.dumps({
                    "type": "frame_meta",
                    "x": rect.x(),
                    "y": rect.y()
                }))
                self.client.sendBinaryMessage(ba)
                window.grabbing_frame = False
        except Exception as e:
            if window: window.grabbing_frame = False

class WSInputHandler(QObject):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.client.textMessageReceived.connect(self.process_message)
    @pyqtSlot(str)
    def process_message(self, msg):
        global window
        if not window: return
        try:
            data = json.loads(msg); t = data.get('type')
            w, h = window.width(), window.height()
            pos = QPoint(int(data.get('x_pct', 0) * w), int(data.get('y_pct', 0) * h))
            target = QApplication.widgetAt(window.mapToGlobal(pos)) or window.browser.focusProxy()

            if t == 'mouse_move': QCoreApplication.postEvent(target, QMouseEvent(QtCore.QEvent.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
            elif t == 'mouse_click':
                btn = {0: Qt.LeftButton, 1: Qt.MiddleButton, 2: Qt.RightButton}.get(data['button'], Qt.LeftButton)
                evt = QtCore.QEvent.MouseButtonPress if data['act'] == 'mousedown' else QtCore.QEvent.MouseButtonRelease
                QCoreApplication.postEvent(target, QMouseEvent(evt, pos, pos, btn, btn, Qt.NoModifier))
            elif t == 'scroll': QCoreApplication.postEvent(target, QWheelEvent(QPointF(pos), window.mapToGlobal(pos), QPoint(0, int(data['dy'])), QPoint(0, int(data['dy'] * 1.2)), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
            elif t == 'keyboard':
                kb_target = QApplication.focusWidget() or window.browser.focusProxy()
                mods = Qt.NoModifier
                if data.get('ctrl'): mods |= Qt.ControlModifier
                if data.get('shift'): mods |= Qt.ShiftModifier
                if data.get('alt'): mods |= Qt.AltModifier
                key_map = {"Backspace": Qt.Key_Backspace, "Tab": Qt.Key_Tab, "Enter": Qt.Key_Enter, "Escape": Qt.Key_Escape, "ArrowLeft": Qt.Key_Left, "ArrowRight": Qt.Key_Right, "ArrowUp": Qt.Key_Up, "ArrowDown": Qt.Key_Down}
                k_str = data.get('key', '')
                qt_key = key_map.get(k_str, Qt.Key_unknown)
                if qt_key == Qt.Key_unknown and len(k_str) == 1: qt_key = Qt.Key(ord(k_str.upper()))
                QCoreApplication.postEvent(kb_target, QKeyEvent(QtCore.QEvent.KeyPress if data['act'] == 'keydown' else QtCore.QEvent.KeyRelease, qt_key, mods, k_str if len(k_str)==1 else "", data.get('isRepeat', False)))
            elif t == 'file_upload':
                temp_p = os.path.join(tempfile.gettempdir(), data['filename'])
                with open(temp_p, 'wb') as f: f.write(base64.b64decode(data['data']))
                if hasattr(window.page, 'upload_loop'): window.page.upload_paths = [temp_p]; window.page.upload_loop.quit()
        except: pass

window, last_heartbeat = None, time.time()
active_stream_handlers, active_input_handlers = [], []

def check_heartbeat():
    global window
    while True:
        time.sleep(5)
        if window and (time.time() - last_heartbeat > 80): bridge.close_signal.emit()

def on_new_stream_connection():
    client = ws_server_stream.nextPendingConnection()
    if client:
        handler = WSStreamHandler(client); active_stream_handlers.append(handler)
        client.disconnected.connect(lambda: active_stream_handlers.remove(handler) if handler in active_stream_handlers else None)

def on_new_input_connection():
    client = ws_server_input.nextPendingConnection()
    if client:
        handler = WSInputHandler(client); active_input_handlers.append(handler)
        client.disconnected.connect(lambda: active_input_handlers.remove(handler) if handler in active_input_handlers else None)

bridge.spawn_window_signal.connect(lambda: globals().update(window=FlashBrowser()) or window.show() if not window else None)
bridge.close_signal.connect(lambda: (window.close(), globals().update(window=None)) if window else None)
bridge.set_url_signal.connect(lambda u: window.load_url(u) if window else None)
bridge.set_size_signal.connect(lambda w, h: window.resize(w, h) if window else None)

app_flask = Flask(__name__)
CORS(app_flask)
@app_flask.route('/status')
def api_status():
    global last_heartbeat; last_heartbeat = time.time()
    if not window: return jsonify({"url": "about:blank", "is_loading": False})
    return jsonify({"url": window.browser.url().toString(), "is_loading": window.is_loading, "pending_redirect": window.pending_chrome_redirect})
@app_flask.route('/keep_alive', methods=['POST'])
def api_alive(): global last_heartbeat; last_heartbeat = time.time(); return jsonify({"status": "ok"})
@app_flask.route('/set_url', methods=['POST'])
def api_set_url(): bridge.spawn_window_signal.emit(); bridge.set_url_signal.emit(request.json['url']); return jsonify({"status": "ok"})
@app_flask.route('/set_size', methods=['POST'])
def api_set_size(): bridge.set_size_signal.emit(request.json['width'], request.json['height']); return jsonify({"status": "ok"})
@app_flask.route('/clear_redirect', methods=['POST'])
def api_clear_redirect():
    if window: window.pending_chrome_redirect = None
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    if "--sandboxed" in sys.argv: sys.argv.remove("--sandboxed")

    sys.argv.extend([f"--ppapi-flash-path={FLASH_PATH}", f"--ppapi-flash-version={FLASH_VERSION}", "--allow-outdated-plugins", "--disable-features=TextServicesFramework,TSF"])

    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.PluginsEnabled, True)

    ws_server_stream = QWebSocketServer("FlashStreamWS", QWebSocketServer.NonSecureMode)
    if ws_server_stream.listen(QHostAddress.LocalHost, WS_PORT_STREAM): ws_server_stream.newConnection.connect(on_new_stream_connection)

    ws_server_input = QWebSocketServer("FlashInputWS", QWebSocketServer.NonSecureMode)
    if ws_server_input.listen(QHostAddress.LocalHost, WS_PORT_INPUT): ws_server_input.newConnection.connect(on_new_input_connection)

    threading.Thread(target=lambda: app_flask.run(host='localhost', port=API_PORT, debug=False, use_reloader=False), daemon=True).start()
    threading.Thread(target=check_heartbeat, daemon=True).start()
    sys.exit(app.exec_())
