import sys
import os
import threading
import json
import time
import base64
import tempfile

os.environ["QT_WEBENGINE_DISABLE_TSF"] = "1"

from flask import Flask, request, jsonify
from flask_cors import CORS

from PyQt5 import QtCore
from PyQt5.QtCore import QUrl, QCoreApplication, Qt, pyqtSignal, QObject, QPoint, QPointF, pyqtSlot, QDir
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFrame, QLabel, QPushButton, 
                             QLineEdit, QVBoxLayout, QHBoxLayout, QDesktopWidget)
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QWheelEvent, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
from PyQt5.QtWebSockets import QWebSocketServer
from PyQt5.QtNetwork import QHostAddress

FLASH_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "pepflashplayer.dll"))
if not os.path.exists(FLASH_PATH):
    print(f"FATAL ERROR: Flash DLL not found.")
    sys.exit(1)

FLASH_VERSION = "32.0.0.371"
API_PORT = 48753
WS_PORT = 48754

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
            QFrame { background: #2c3e50; color: white; border-radius: 8px; border: 2px solid #34495e; }
            QPushButton { background: #3498db; color: white; border-radius: 4px; padding: 6px 15px; font-weight: bold; min-width: 60px;}
            QLineEdit { background: #1a252f; color: white; border: 1px solid #7f8c8d; border-radius: 4px; padding: 6px; }
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
        for c in active_handlers: c.client.sendTextMessage(json.dumps({"type": "request_upload"}))
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
            for handler in active_handlers:
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
            for c in active_handlers:
                try: c.client.sendTextMessage(msg)
                except: pass

class WSClientHandler(QObject):
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
            if t == 'get_frame' and not window.grabbing_frame:
                window.grabbing_frame = True
                pix = window.grab(); ba = QtCore.QByteArray(); buf = QtCore.QBuffer(ba); buf.open(QtCore.QIODevice.WriteOnly)
                pix.save(buf, "JPEG", 70); self.client.sendBinaryMessage(ba); window.grabbing_frame = False
            elif t == 'mouse_move': QCoreApplication.postEvent(target, QMouseEvent(QtCore.QEvent.MouseMove, pos, pos, Qt.NoButton, Qt.NoButton, Qt.NoModifier))
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
        except:
            if window: window.grabbing_frame = False

window, last_heartbeat, active_handlers = None, time.time(), []
def check_heartbeat():
    global window
    while True:
        time.sleep(5)
        if window and (time.time() - last_heartbeat > 60): bridge.close_signal.emit()
def on_new_connection():
    client = ws_server.nextPendingConnection()
    if client:
        handler = WSClientHandler(client); active_handlers.append(handler)
        client.disconnected.connect(lambda: active_handlers.remove(handler) if handler in active_handlers else None)

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
    sys.argv.extend([f"--ppapi-flash-path={FLASH_PATH}", f"--ppapi-flash-version={FLASH_VERSION}", "--no-sandbox", "--allow-outdated-plugins", "--disable-features=TextServicesFramework,TSF"])
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    QWebEngineSettings.globalSettings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    ws_server = QWebSocketServer("FlashSyncWS", QWebSocketServer.NonSecureMode)
    if ws_server.listen(QHostAddress.LocalHost, WS_PORT): ws_server.newConnection.connect(on_new_connection)
    threading.Thread(target=lambda: app_flask.run(host='localhost', port=API_PORT, debug=False, use_reloader=False), daemon=True).start()
    threading.Thread(target=check_heartbeat, daemon=True).start()
    sys.exit(app.exec_())
