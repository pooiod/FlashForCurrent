# This script will tell you if pyqt5 is 64 bit or 32 bit so you can use the correct pepper flash

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

app = QApplication(sys.argv)
view = QWebEngineView()

def check_real_bitness(res):
    print(f"Reported Platform: {res}")
    view.page().runJavaScript("Number.MAX_SAFE_INTEGER > 2**32", lambda val: print(f"Confirmed 64-bit Engine: {val}"))

view.page().runJavaScript("navigator.platform", check_real_bitness)
app.exec_()
