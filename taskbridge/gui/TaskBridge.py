"""
Main application entry point. Creates system tray icon and displays main window.
"""
import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
import darkdetect

from taskbridge.gui.viewmodel import trayicon
from taskbridge.gui.viewmodel.taskbridgeapp import TaskBridgeApp

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # noinspection PyProtectedMember
        assets_path = sys._MEIPASS + "/taskbridge/gui/assets"
    else:
        assets_path = os.path.dirname(os.path.abspath(__file__)) + "/assets"

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tb = TaskBridgeApp(assets_path)
    icon_path = assets_path + "/tray/bridge_black.png" if darkdetect.isDark() else \
        assets_path + "/tray/bridge_white.png"
    trayIcon = trayicon.TaskBridgeTray(QIcon(icon_path), tb)
    tb.tray_icon = trayIcon
    app.exec()
