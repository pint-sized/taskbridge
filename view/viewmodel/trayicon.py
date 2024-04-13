from __future__ import annotations

from PyQt6.QtGui import QIcon, QAction, QMovie
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu

from view.viewmodel.taskbridgeapp import TaskBridgeApp


# noinspection PyUnresolvedReferences
class TaskBridgeTray(QSystemTrayIcon):

    def __init__(self, icon: QIcon, parent: TaskBridgeApp, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setIcon(icon)
        self.parent = parent
        self.show()
        self.animated_icon: QMovie | None = None

        menu = QMenu()
        self.mnu_show = QAction("Show TaskBridge")
        self.mnu_show.triggered.connect(self.parent.ui.show)
        menu.addAction(self.mnu_show)
        self.mnu_quit = QAction("Quit TaskBridge")
        self.mnu_quit.triggered.connect(self.parent.quit_gracefully)
        menu.addAction(self.mnu_quit)
        self.setContextMenu(menu)

    def set_animated_icon(self, path: str):
        self.animated_icon = QMovie(path)
        self.animated_icon.start()
        self.animated_icon.frameChanged.connect(self._update_animated_icon)

    def _update_animated_icon(self):
        icon = QIcon()
        icon.addPixmap(self.animated_icon.currentPixmap())
        self.setIcon(icon)
