"""
Contains the ``MainWindow`` class.
"""

from PyQt6.QtWidgets import QMainWindow

from taskbridge.gui.viewmodel.ui_mainwindow import Ui_MainWindow


class MainWindow(QMainWindow, Ui_MainWindow):
    """
    Subclasses ``QMainWindow`` and ``Ui_MainWindow`` to carry out initial set up for the main window.
    """

    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.obj = obj
        self.setupUi(self)
