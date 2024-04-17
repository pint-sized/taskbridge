"""
Main application entry point. Creates system tray icon and displays main window.
"""

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
import darkdetect

from taskbridge.gui.viewmodel import trayicon
from taskbridge.gui.viewmodel.taskbridgeapp import TaskBridgeApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tb = TaskBridgeApp()
    icon_path = "taskbridge/gui/assets/tray/bridge_black.png" if darkdetect.isDark() else \
        "taskbridge/gui/assets/tray/bridge_white.png"
    trayIcon = trayicon.TaskBridgeTray(QIcon(icon_path), tb)
    tb.tray_icon = trayIcon
    app.exec()
