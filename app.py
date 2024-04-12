import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
import darkdetect

from view.viewmodel import trayicon
from view.viewmodel.taskbridgeapp import TaskBridgeApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tb = TaskBridgeApp()
    icon_path = "view/assets/bridge_white.png" if darkdetect.isDark() else "view/assets/bridge_white.png"
    trayIcon = trayicon.TaskBridgeTray(QIcon(icon_path), tb)
    tb.tray_icon = trayIcon
    app.exec()
