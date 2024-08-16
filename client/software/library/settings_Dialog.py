import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QGraphicsSceneHoverEvent, QMainWindow, QDialog, QFileDialog
from PyQt5.QtGui import QImage
# from PyQt5.Qt import QStandardPaths
from library.settings import Ui_Dialog
import cv2
import imutils
import csv


class CustomUI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)  # 调用父类构造函数，self 就是一个 QMainWindow 对象
        self.ui = Ui_Dialog()  # 创建UI 对象
        self.ui.setupUi(self)  # 构造UIm

        self.incisor_edge_index = 0.5

        self.cuspid_edge_index = 0.5

        self.conversion_factor = 6.5  # the distance of middle face.

        self.incisor_length = 1.0

        self.ui.lineEdit.setText(str(self.conversion_factor))

        self.ui.lineEdit_2.setText(str(self.incisor_length))

        self.ui.buttonBox.accepted.connect(self.ok_api)

        self.ui.checkBox.stateChanged.connect(self.display_slide_bars)

        self.ui.verticalSlider.valueChanged.connect(
            self.get_incisor_edge_index)

        self.ui.verticalSlider.sliderReleased.connect(
            self.change_incisor_point)

        self.ui.horizontalSlider.valueChanged.connect(
            self.get_cuspid_edge_index)

        self.ui.verticalSlider.setVisible(False)

        self.ui.horizontalSlider.setVisible(False)

        self.ui.label_2.setVisible(False)

        self.ui.label_3.setVisible(False)

        # self.ui.checkBox_2.stateChanged.connect(self.save_with_image)

    mysignal = QtCore.pyqtSignal(str)

    mysignal2 = QtCore.pyqtSignal(str)

    mysignal3 = QtCore.pyqtSignal(str)

    mysignal5 = QtCore.pyqtSignal(str)

    mysignal6 = QtCore.pyqtSignal(str)

    mysignal7 = QtCore.pyqtSignal(str)

    def get_incisor_edge_index(self):
        self.incisor_edge_index = self.ui.verticalSlider.value()/100
        self.ui.verticalSlider.setToolTip(
            str(self.ui.verticalSlider.value()/100))
        print(self.incisor_edge_index)

    def change_incisor_point(self):
        self.incisor_edge_index = self.ui.verticalSlider.value()/100
        self.ui.verticalSlider.setToolTip(
            str(self.ui.verticalSlider.value()/100))

        if self.ui.checkBox.isChecked():
            self.mysignal5.emit(str(self.incisor_edge_index))
        else:
            pass

    def get_cuspid_edge_index(self):
        self.cuspid_edge_index = self.ui.horizontalSlider.value()/100
        self.ui.horizontalSlider.setToolTip(
            str(self.ui.horizontalSlider.value()/100))
        print(self.cuspid_edge_index)

    def display_slide_bars(self):
        if self.ui.checkBox.isChecked():
            self.ui.verticalSlider.setVisible(True)
            self.ui.horizontalSlider.setVisible(True)
            self.ui.label_2.setVisible(True)
            self.ui.label_3.setVisible(True)
        else:
            self.ui.verticalSlider.setVisible(False)
            self.ui.horizontalSlider.setVisible(False)
            self.ui.label_2.setVisible(False)
            self.ui.label_3.setVisible(False)

    def send_incisor(self):
        if self.ui.checkBox.isChecked():
            self.mysignal5.emit(str(self.incisor_edge_index))
        else:
            pass

    # send the required incisor index and ask the mainwindow to change the place.
    def send_incisor(self):
        if self.ui.checkBox.isChecked():
            self.mysignal5.emit(str(self.incisor_edge_index))
        else:
            pass

    def send_cuspid(self):
        if self.ui.checkBox.isChecked():
            self.mysignal6.emit(str(self.cuspid_edge_index))
        else:
            pass

    '''This is the function used for ok button. When the button is clicked, three signals will be released.'''

    def ok_api(self):
        self.load_tooth_landmarks()
        self.save_with_image()
        self.send_incisor()
        self.send_cuspid()
        self.conv_factor()
        self.get_incisor_length()
        print("ok")
        pass

    def load_tooth_landmarks(self):
        if self.ui.checkBox.isChecked():
            self.mysignal.emit('true')
            # self.ui.pushButton_2.setVisible(True)
            # self.ui.lineEdit_2.setVisible(True)
        else:
            self.mysignal.emit('false')
            # self.ui.pushButton_2.setVisible(False)
            # self.ui.lineEdit_2.setVisible(False)

    def save_with_image(self):
        if self.ui.checkBox.isChecked():
            self.mysignal2.emit('true')
            # self.ui.pushButton_2.setVisible(True)
            # self.ui.lineEdit_2.setVisible(True)
        else:
            self.mysignal2.emit('false')
            # self.ui.pushButton_2.setVisible(False)
            # self.ui.lineEdit_2.setVisible(False)

    def conv_factor(self):
        if self.ui.lineEdit.text != '':
            try:
                # meaning that the text can be converted to float.
                self.conversion_factor = float(self.ui.lineEdit.text())
                self.mysignal3.emit(self.ui.lineEdit.text())
            finally:
                pass

    def get_incisor_length(self):
        if self.ui.lineEdit_2.text != '':
            try:
                # meaning that the text can be converted to float.
                self.incisor_length = float(self.ui.lineEdit_2.text())
                self.mysignal7.emit(self.ui.lineEdit_2.text())
            finally:
                pass


if __name__ == '__main__':
    app = QApplication(sys.argv)  # 创建app，用 QApplication 类
    cutomUI = CustomUI()
    cutomUI.show()
    sys.exit(app.exec_())
