from PyQt6.QtWidgets import QMainWindow

from taskbridge.gui.viewmodel.ui_mainwindow import Ui_MainWindow


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.obj = obj
        self.setupUi(self)

