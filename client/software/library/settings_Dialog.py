import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QGraphicsSceneHoverEvent, QMainWindow, QDialog, QFileDialog
from PyQt5.QtGui import QImage
# from PyQt5.Qt import QStandardPaths
from library.settings import Ui_Dialog
import cv2
import imutils
import csv
import os
import json
import logging
from library.aws_auto_setup import AWSSetupDialog


class set_Dialog(QDialog):
    cloudConfigurationChanged = QtCore.pyqtSignal()

    def load_config(self, file_path):
        """ Load configuration values from a JSON file. """
        try:
            with open(file_path, 'r') as file:
                config = json.load(file)
                self.incisor_edge_index = config.get("incisor_edge_index")
                self.cuspid_edge_index = config.get("cuspid_edge_index")
                self.conversion_factor = config.get("conversion_factor")
                self.incisor_length = config.get("incisor_length")
        except FileNotFoundError:
            print(f"Error: The configuration file {file_path} was not found.")
        except json.JSONDecodeError:
            print("Error: JSON decode error.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def save_config(self, file_path):
        """ Save configuration values to a JSON file. """
        config = {
            "incisor_edge_index": self.incisor_edge_index,
            "cuspid_edge_index": self.cuspid_edge_index,
            "conversion_factor": self.conversion_factor,
            "incisor_length": self.incisor_length
        }
        
        try:
            with open(file_path, 'w') as file:  # Open the file in write mode
                json.dump(config, file, indent=4)  # Writing JSON data with indentation
            logging.info("Configuration saved successfully.")
        except IOError as e:
            logging.error(f"An IOError occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while saving configuration: {e}")

    def __init__(self, parent=None, cloud_manager=None):
        super().__init__(parent)  # 调用父类构造函数，self 就是一个 QMainWindow 对象
        self.ui = Ui_Dialog()  # 创建UI 对象
        self.ui.setupUi(self)  # 构造UIm
        self.resize(820, 680)
        self.setMinimumSize(600, 480)
        self.setWindowTitle("Dynasmile Settings")

        self.tabs = QtWidgets.QTabWidget()
        self.general_page = QtWidgets.QWidget()
        self.general_page.setMinimumSize(490, 524)
        self.general_scroll = QtWidgets.QScrollArea()
        self.general_scroll.setWidgetResizable(False)
        self.general_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.general_scroll.setWidget(self.general_page)
        self.tabs.addTab(self.general_scroll, "Analysis")

        general_widgets = (
            self.ui.buttonBox,
            self.ui.checkBox,
            self.ui.checkBox_2,
            self.ui.horizontalLayoutWidget,
            self.ui.verticalSlider,
            self.ui.label_2,
            self.ui.horizontalSlider,
            self.ui.label_3,
            self.ui.horizontalLayoutWidget_2,
        )
        for widget in general_widgets:
            widget.setParent(self.general_page)

        self.cloud_page = QtWidgets.QWidget()
        cloud_layout = QtWidgets.QVBoxLayout(self.cloud_page)
        cloud_layout.setContentsMargins(0, 0, 0, 0)
        cloud_scroll = QtWidgets.QScrollArea(self.cloud_page)
        cloud_scroll.setWidgetResizable(False)
        cloud_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.cloud_panel = AWSSetupDialog(cloud_scroll, cloud_manager, embedded=True)
        self.cloud_panel.setWindowFlags(QtCore.Qt.Widget)
        self.cloud_panel.setMinimumSize(760, 620)
        self.cloud_panel.resize(760, 620)
        cloud_scroll.setWidget(self.cloud_panel)
        cloud_layout.addWidget(cloud_scroll)
        self.tabs.addTab(self.cloud_page, "AWS / EC2 Server")

        dialog_layout = QtWidgets.QVBoxLayout(self)
        dialog_layout.setContentsMargins(8, 8, 8, 8)
        dialog_layout.addWidget(self.tabs)
        self.cloud_panel.configurationSaved.connect(self.cloudConfigurationChanged.emit)
        self.cloud_panel.show()

        current_path=os.path.abspath(__file__)
        current_folder=os.path.dirname(current_path)

        self.config_file=os.path.join(current_folder,'config.json')

        self.load_config(self.config_file)

        self.ui.lineEdit.setText(str(self.conversion_factor))

        self.ui.lineEdit_2.setText(str(self.incisor_length))

        self.ui.buttonBox.accepted.connect(self.ok_api)
        self.ui.checkBox.setChecked(True) 
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
        self.save_config(self.config_file)
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
    cutomUI = set_Dialog()
    cutomUI.show()
    sys.exit(app.exec_())
