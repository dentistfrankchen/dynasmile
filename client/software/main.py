import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import Qt, QThread, QPointF, QPoint
from PyQt5.QtWidgets import QApplication, QGraphicsSceneHoverEvent, QMainWindow, QDialog, QFileDialog
from PyQt5.QtGui import QImage, QKeyEvent, QCursor
import cv2
import imutils
import csv

from library.cat import Ui_MainWindow
from library.read_csv_Dialog import read_Dialog
from library.write_csv_Dialog import write_Dialog
from library.settings_Dialog import set_Dialog
from library.test_batch_detections import load_model, detect_face
from library.bucket_test import upload_video, upload_video_new,get_bucket_name
from library.json_handler import append_tojson, is_item_in_json, read_from_json
from library.another import manage_item
from library.aws_connection import start_ec2_instance,stop_ec2_instance
from library.crypt import decrypt_new
from library.key_loader import load_key_api
from library.aws_auto_setup import AWSManager, AWSSetupDialog

import socket
from deepface import DeepFace
import os
import numpy as np
import matplotlib.pyplot as plt
import socketio
import json
import boto3

import subprocess
import time
import logging
import traceback
import atexit

current_path = os.path.abspath(__file__)
current_folder = os.path.dirname(current_path)
cloud_manager = None

def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.exit(0)
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


class Thread(QThread):
    def __init__(self, s3_client, filename, bucket_name):
        super(Thread, self).__init__()
        self.s3_client = s3_client
        self.filename = filename
        self.bucket_name = bucket_name

    '''View file to know more information.'''

    def run(self):
        upload_video_new(self.s3_client, self.filename, get_bucket_name())


class CloudConnectThread(QThread):
    connected = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(str)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        try:
            self.manager.open_tunnel(5000)
            self.connected.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


'''This is used to handle the situation when disconnection happens.'''


class disconnection__Thread(QThread):
    def __init__(self):
        super(disconnection__Thread, self).__init__()

    def run(self):
        # input('After the connection is recovered, press any key to resume: ')
        print('After the connection is recovered, everything is being recovered...now sending requests...')


'''This is the inner signal inside the point object. This is fired to refresh the displaying pane.'''


class inner_signal(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent=None)

    mysignal = QtCore.pyqtSignal(str)


class MyItem(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, coordinates_dict, size):
        self.coordinates_dict = coordinates_dict
        self.size = size
        print(self.coordinates_dict['name'])
        super().__init__(
            self.coordinates_dict['center_x'] -
            self.size /
            2,
            self.coordinates_dict['center_y'] -
            self.size /
            2,
            self.size,
            self.size)
        # super().setPos(QtCore.QPointF(100,100))
        self.point_name = self.coordinates_dict['name']
        self.setToolTip(self.point_name)

        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setBrush(QtGui.QBrush(QtCore.Qt.yellow))
        self.setAcceptHoverEvents(True)

        self.set_ScaleCenter()

        self.inner_signal = inner_signal()

        print(self.get_dict())
        print("done")

    # mysignal=QtCore.pyqtSignal(str)

    def mouseReleaseEvent(self, event):
        print("uu")
        print(str(self.pos().x()))
        # self.mysignal.emit('refresh')
        self.inner_signal.mysignal.emit("refresh")
        return super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        print("hovered.Now it is time to zoom.")
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable)
        self.setFocus()
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setScale(2.0)
        self.setOpacity(0.1)
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        # print("hover out.Now it is time to go back to normal.")
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable, False)
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.setScale(1.0)
        self.setOpacity(1.0)
        # self.setToolTip(self.point_name)
        return super().hoverLeaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Up:
            # print("pressed")
            if self.flags() & QtWidgets.QGraphicsItem.ItemIsMovable:
                move_distance = QPointF(0, -5)
                self.moveBy(move_distance.x(), move_distance.y())
                cursor_pos = QCursor.pos()
                move_distancea = QPoint(0, -5)
                new_cursor_pos = cursor_pos + move_distancea
                QCursor.setPos(new_cursor_pos)

        if event.key() == Qt.Key_Down:
            # print("pressed")
            if self.flags() & QtWidgets.QGraphicsItem.ItemIsMovable:
                move_distance = QPointF(0, 5)
                self.moveBy(move_distance.x(), move_distance.y())
                cursor_pos = QCursor.pos()
                move_distancea = QPoint(0, 5)
                new_cursor_pos = cursor_pos + move_distancea
                QCursor.setPos(new_cursor_pos)

        if event.key() == Qt.Key_Left:
            print("pressed")
            if self.flags() & QtWidgets.QGraphicsItem.ItemIsMovable:
                move_distance = QPointF(-5, 0)
                self.moveBy(move_distance.x(), move_distance.y())
                cursor_pos = QCursor.pos()
                move_distancea = QPoint(-5, 0)
                new_cursor_pos = cursor_pos + move_distancea
                QCursor.setPos(new_cursor_pos)

        if event.key() == Qt.Key_Right:
            print("pressed")
            if self.flags() & QtWidgets.QGraphicsItem.ItemIsMovable:
                move_distance = QPointF(5, 0)
                self.moveBy(move_distance.x(), move_distance.y())
                cursor_pos = QCursor.pos()
                move_distancea = QPoint(5, 0)
                new_cursor_pos = cursor_pos + move_distancea
                QCursor.setPos(new_cursor_pos)
        return super().keyPressEvent(event)

    def get_dict(self):  # get method,used with set method
        # the "pos" method actually calculates within the self coordinates
        # within the graphitems object. So actually it can be thought as a
        # tracker.
        self.coordinates_dict['center_x'] += self.pos().x()
        self.coordinates_dict['center_y'] += self.pos().y()
        # print(self.coordinates_dict)
        return self.coordinates_dict

    # the set method used to set new position. generated by co.
    def set_position(self, center_x, center_y):
        x = center_x - (self.coordinates_dict['center_x'])
        y = center_y - (self.coordinates_dict['center_y'])
        # no matter how you have toogles the point, it still remembers the
        # original location.
        self.setPos(x, y)
        '''no need to do the following:
        self.coordinates_dict['center_x']=center_x
        self.coordinates_dict['center_y']=center_y
        the self.pos.x() and self.pos.y() will do their job.
        '''

    # Since the default scale center is (0,0), you have to use this.
    def set_ScaleCenter(self):
        self.setTransformOriginPoint(
            QtCore.QPointF(
                self.coordinates_dict['center_x'],
                self.coordinates_dict['center_y']))


class CustomUI(QMainWindow):
    '''The signal to change the progress bar. Because of the threads, you cannot change it directly.'''
    progressChanged = QtCore.pyqtSignal(int)
    render_signal = QtCore.pyqtSignal()
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

    def __init__(self, parent=None):
        self.load_config(os.path.join(current_folder,'library','config.json'))



        # iheriting from QMainWndow
        super().__init__(parent)

        # creating UI object.
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # load the landmark list. This list is used to store Myitem objects.
        self.ui.landmark_list = {}
        #thread_checker('my func')
        self.ui.landmark_size = 10  # to do: changable size
        # load the dlib face shape predictor.
        # self.predictor = dlib.shape_predictor(os.path.abspath(os.path.join(os.getcwd(), ".."))+"\supporting_files\shape_predictor_68_face_landmarks\shape_predictor_68_face_landmarks.dat")

        # load the face detector.
        self.detector = load_model()
        self.detector.eval()  # important

        self.model = DeepFace.build_model("Emotion")
        
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # set the current frame that this program is working on.
        self.current_frame = 0  # the 0th frame.
        #self.max_frame=0  #the frame with the greatest smile intensity.
        self.slider_allow_auto_move = True

        # set the status to be needing analyze. In the loadImage() function, If
        # a video is selected. The emotion degree will first be analyzed.
        self.requires_analyze = True

        self.landmarks = []

        # In the load Image function, during the analysis process, this program
        # will create a list storing happiness mark of all frames.
        self.emotion_mark_list = []

        self.commissure_seq = []

        self.nasion_list = []

        self.conversion_list = []

        self.leftx_eye_list = []

        self.lefty_eye_list = []

        self.conversion_factor_video = 1

        self.display_tooth_landmarks = True

        self.save_img = False

        self.recognize_json=False #set to true if you want to use commissure.json to verify whether the file has been analyzed.

        # the factor used to measure distance(the distance of middle face.)[Now
        # is the distance betwwen inner canthus--in millimeters.

        self.Pause = False

        self.analyzed = False

        '''initialize the web client.'''

        # initializing the angles list, which is later used for exporting.(as
        # csv file)
        self.angles = {}

        # the flag used for setting the mode to human vs AI test.
        self.test_mode = False

        self.ready = False
        self.cloud_thread = None

        self.disconnected = False

        self.AI_dict = {}

        # self.s3_resource = boto3.resource('s3')

        #with open(os.path.join(current_folder,'library','aws_config.json')) as json_file:
        #    config = json.load(json_file)
        if cloud_manager and cloud_manager.session:
            self.s3_client = cloud_manager.session.client('s3')
        else:
            self.s3_client = None

        #self.s3_client = boto3.client('s3')
        self.gin=None
        self.ins=None
        self.lcpc=None
        self.rcpc=None

        # to ensure the label in the column has enough width.
        self.ui.gridLayout.setColumnMinimumWidth(0, 900)

        self.ui.pushButton.clicked.connect(self.pause)
        self.ui.pushButton_2.clicked.connect(self.my_slot)
        self.ui.pushButton_2.clicked.connect(self.loadImage)
        self.ui.pushButton_clear.clicked.connect(self.landmarks_clear)
        self.ui.pushButton_render.clicked.connect(self.landmarks_calculator)
        self.ui.pushButton_render.clicked.connect(self.send_info)
        self.ui.pushButton_readcsv.clicked.connect(self.readcsv)
        self.ui.pushButton_writecsv.clicked.connect(self.writecsv)
        self.ui.slider_time.sliderReleasedSignal.connect(self.time_changed)
        #self.ui.slider_time.sliderMoved.connect(self.overcome_zig)
        self.ui.time_setter.mysignal.connect(self.change_time)
        self.ui.dragdrop_widget.itemDropped.connect(self.on_item_dropped)
        self.render_signal.connect(self.landmarks_calculator)
        self.ui.lineEdit_media.textChanged.connect(self.media_monitor)

        self.ui.commandLinkButton.clicked.connect(self.open_settings)

        self.ui.comboBox.activated[str].connect(self.select_change)

        # creating a graphicsview to draw the landmark points.
        # setting the background to transparent so we can see the QLabel image.
        self.ui.graphicsView.setStyleSheet("background:transparent;")
        # needed to keep the landmarks at correct place.
        self.ui.graphicsView.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        # since we do not need scroll bar in graphicsview. we need scrollbars
        # in the outside of this widget.
        self.ui.graphicsView.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        # since the first column has enough width, the width of the pixmap is
        # accurate.
        # set the size policy to preferred!!! default is expanding, which can
        # leave a blank margin.
        self.ui.graphicsView.setGeometry(
            QtCore.QRect(
                95,
                29,
                self.ui.label.pixmap().width(),
                self.ui.label.pixmap().height()))
        self.ui.scene = QtWidgets.QGraphicsScene()

        self.ui.graphicsView.setScene(self.ui.scene)
        # the value can be any value, but keep it to be (-x,-x,2x,2x),So the
        # (0,0) point is in the correct place.
        self.ui.graphicsView.scene().setSceneRect(-200, -200, 400, 400)

        # set the 'pause' botton to not enabled.
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton_render.setEnabled(False)
        self.ui.slider_time.setEnabled(False)
        self.initial_state()
        self.tmp = None

        self.coord_offset = (0, 0)

        self.progressChanged.connect(self.ui.progressBar.setValue)

        self.server_status_label = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(self.server_status_label)
        if cloud_manager and cloud_manager.config.get('instance_id') and cloud_manager.config.get('key_path'):
            self.set_server_status("Server: configured, waiting to connect…", "#b36b00")
        else:
            self.set_server_status("Server: not configured — open Settings to configure AWS / EC2", "#b00020")

    def set_server_status(self, text, color):
        self.server_status_label.setText(text)
        self.server_status_label.setStyleSheet("font-weight: bold; color: {}; padding: 3px 8px;".format(color))

    def connect_cloud_server(self):
        if not cloud_manager or not cloud_manager.config.get('instance_id') or not cloud_manager.config.get('key_path'):
            self.set_server_status("Server: not configured — open Settings to configure AWS / EC2", "#b00020")
            return
        if self.cloud_thread and self.cloud_thread.isRunning():
            return
        self.set_server_status("Server: starting EC2 and secure tunnel…", "#b36b00")
        self.cloud_thread = CloudConnectThread(cloud_manager)
        self.cloud_thread.connected.connect(self.on_cloud_connected)
        self.cloud_thread.failed.connect(self.on_cloud_connection_failed)
        self.cloud_thread.start()

    def on_cloud_connected(self):
        try:
            self.s3_client = cloud_manager.session.client('s3')
            self.sio = self.start_client()
            self.ready = True
            self.set_server_status("Server: connected", "#16823b")
        except Exception as exc:
            self.on_cloud_connection_failed(str(exc))

    def on_cloud_connection_failed(self, message):
        self.ready = False
        self.set_server_status("Server: connection failed — {}".format(message), "#b00020")

    def start_ssh_connections(self):
        max_retries = 5
        attempts = 0
        while True:
            try:
                self.sio = self.start_client()
                self.ready = True
                logging.info('Connected successfully.')
                return  # successfully connect
            except socketio.exceptions.ConnectionError as e:
                message = self.handle_connection_error(e)
                print(f"Error message from start_ssh_connection.{message}")
                attempts += 1
                if attempts < max_retries:
                    print(f'Retry attempt {attempts} in 5 seconds...')
                    time.sleep(5)  # wait for 5 secs
                else:
                    # enough
                    prompt = input("All retry attempts failed. Do you want to try again? (yes/no): ")
                    if prompt.lower() == 'no':
                        logging.info('Exiting program as user opted not to retry.')
                        return  # exit
                    elif prompt.lower() == 'yes':
                        attempts = 0  # set attempt to  0 to restart
                    else:
                        print("Invalid input, exiting program.")
                        return  # exit

    def handle_connection_error(self, e):
        """process ssh errors."""
        error_message = str(e)
        if 'refuse' in error_message:
            message = (
                'Please check the server and the 5000 port connection. '
                'Ensure the connection is established, then rerun this program.\n'
                'Use ALT 1, ALT 2, ALT 3 to start all the programs.\n'
            )
        else:
            message = (
                'Please check the connection of port 5000. Unable to resume. '
                'Ensure the server is started first before connecting to port 5000.\n'
                'Use ALT 1, ALT 2, ALT 3 to start all the programs.\n'
            )
        logging.error(message)
        return message

    def start_client(self, arg=None):
        pass
        sio = socketio.Client()

        sio.connect('http://localhost:5000')

        @sio.on('image_evaluated')
        def image_verified(data):
            print(float(data['happiness value']))

        '''internet progress bar'''
        @sio.on('video_analyzing')
        def move_progress_bar(data: str):
            self.current_frame = int(data)
            self.progressChanged.emit(
                (self.current_frame / self.total_frame) * 100)
            # self.ui.progressBar.setValue()

        @sio.on('send_list')
        def send_list(data):
            print(type(json.loads(data)))

        @sio.on('debug_server')
        def debug_server(data):
            print(data)

        @sio.on('landmark_list')
        def recv_landmark_list(data):
            self.oral_landmarks=json.loads(data)
            self.gin=self.oral_landmarks['gin']
            self.ins=self.oral_landmarks['ins']
            self.lcpc=self.oral_landmarks['lcpc']
            self.rcpc=self.oral_landmarks['rcpc']
            self.render_signal.emit()
            self.ui.pushButton_render.setEnabled(True)

        @sio.on('emotion_list_of_video')
        def recv_emotion_list(data):
            self.AI_dict = json.loads(data)
            self.emotion_mark_list = self.AI_dict['emotion_list']
            self.commissure_seq = self.AI_dict['commissure_list']
            self.connection_list=[]
            for index, value in enumerate(self.commissure_seq):
                if value!=0:
                    self.connection_list.append(index) #还原原始视频位置
                else:
                    pass
            print("c:" + str(len(self.commissure_seq)))
            self.face_not_detected = self.AI_dict['face_not_detected']
            self.face_greater_than_one_cv2_only = self.AI_dict['face_greater_than_one_cv2_only']
            self.face_greater_than_one_mobile = self.AI_dict['face_greater_than_one_mobile']
            '''We need to document the commissure seq.'''
            self.nasion_list = self.AI_dict['nasion_list']
            self.conversion_list = self.AI_dict['conversion_list']
            self.leftx_eye_list = self.AI_dict['leftx_eye_list']
            self.lefty_eye_list = self.AI_dict['lefty_eye_list']
            export_data = {'filename': self.media_source,
                           'fps': self.fps,
                           'emotion_mark_list': self.emotion_mark_list,
                           'commissure_seq': self.commissure_seq,
                           'nasion_list': self.nasion_list,
                           'conversion_list': self.conversion_list,
                           'leftx_eye_list': self.leftx_eye_list,
                           'lefty_eye_list': self.lefty_eye_list
                           }
            self.process_seq_func()
            self.requires_analyze = False
            # now you can press the pause button.
            self.ui.pushButton.setEnabled(True)
            self.ui.pushButton_2.setEnabled(False)
            
            self.display("on peak")
            self.allow_landmarking()
            
            self.render_signal.emit()
            '''VERY IMPORTANT:Do not use self.landmarks_calculator here.
            It will cause the thread to have huge mistakes.'''
            print(json.loads(data)['name'])
            #print(json.loads(data)['emotion_list'])
            print('not detected rate: ' +
                  str(self.face_not_detected /
                      len(self.emotion_mark_list)))
            print('detected greater than one rate with cv2: ' +
                  str(self.face_greater_than_one_cv2_only /
                      len(self.emotion_mark_list)))
            print('detected greater than one rate with mobile: ' +
                  str(self.face_greater_than_one_mobile /
                      len(self.emotion_mark_list)))
            append_tojson(os.path.join(current_folder,'test.json'), export_data)  # not too early.

        @sio.event
        def disconnect():  # You don't have to manully use the disconnection, since it will disconnect automatically when the program returns.
            # sio.connect('http://localhost:5000')
            '''In the case we meet the disconnection(typically the ssh refusion error.)'''
            self.disconnected = True
            print("I'm disconnected!")

        @sio.event
        def connect():
            if self.disconnected == True and self.ready == True:
                try:
                    DThread = disconnection__Thread()
                    DThread.start()
                    DThread.wait()
                    if self.requires_analyze==True:
                        sio.emit('How s it going', {'filename': self.media_source})
                    else:
                        pass
                    # print('detecting...waiting for connection')
                    self.disconnected = False

                except BaseException:
                    raise Exception(
                        'please check the connect function. Some error is not catched.')

        return sio

    def media_monitor(self):
        if self.ui.lineEdit_media.text() == '':
            #self.ui.pushButton_2.setText('import new media')
            self.ui.dragdrop_widget.enableDragDrop()
            self.ui.dragdrop_widget.cross_image_label.show()
            self.requires_analyze = True
            self.analyzed = False  # important
            self.current_frame = 0
            self.initial_state()
            self.ui.slider_time.setEnabled(False)
        else:
            pass

    def my_slot(self):  # test function used to test slot.
        try:
            time.sleep(0.1)
            self.ui.pushButton_clear.click()
        except:
            pass
        pass

    '''The pause function works with pause button.
    '''

    def pause(self):
        # Once the pause button is hit, you cannot hit it twice unless you hit
        # start.
        self.ui.pushButton.setEnabled(False)
        if self.current_frame < self.total_frame:
            self.Pause = True
        # time setter is the line edit next to the horizontal sliding bar. it
        # displays current time.
        self.ui.time_setter.setText(str(float(self.current_frame / self.fps)))
        # When the pause button is hit, you can hit the start button.
        self.ui.pushButton_2.setEnabled(True)


    '''When you change the value of time setter and right click, the change_time function works to change the value of the horizontal sliding bar.
    It calculates the frame that needs to be calculated and bring it there by setting self.current_frame.
    It also reads that frame and renders it to the label by self.update()
    '''

    def change_time(self):
       # Set the slider value based on the given time input in relation to the total frames and fps
        #self.ui.slider_time.setValue(
        #    int(float(self.ui.time_setter.text()) *self.fps)
        #)
        self.ui.slider_time.location=int(float(self.ui.time_setter.text()) *self.fps)
        self.ui.slider_time.update()
        # Calculate the target frame based on the time input and frames per second (fps)
        frame_target = int(float(self.ui.time_setter.text()) * self.fps)
        # Update the current frame to the target frame
        self.current_frame = frame_target
        # Check if the video capture is opened and set the current frame position
        if self.vid.isOpened():
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, frame_target)
        # Update the time setter text to reflect the current frame as time in seconds
        self.ui.time_setter.setText(str(float((self.current_frame + 1) / self.fps)))
        # Read the next frame from the video capture
        img, self.image = self.vid.read()
        # Resize the captured image for display
        self.image = imutils.resize(self.image, height=618)
        # Trigger an update to refresh the UI or display the new image
        self.update()
    '''only the import_media can be used.'''

    def initial_state(self):
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_render.setEnabled(False)
        self.ui.pushButton_readcsv.setEnabled(False)
        self.ui.pushButton_writecsv.setEnabled(False)
        self.ui.pushButton_clear.setEnabled(False)

    def allow_landmarking(self):
        self.ui.pushButton_render.setEnabled(True)
        self.ui.pushButton_readcsv.setEnabled(True)
        self.ui.pushButton_writecsv.setEnabled(True)
        self.ui.pushButton_clear.setEnabled(True)

    def pic_state(self):
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_render.setEnabled(True)
        self.ui.pushButton_readcsv.setEnabled(True)
        self.ui.pushButton_writecsv.setEnabled(True)
        self.ui.pushButton_clear.setEnabled(True)
    '''This load_local_image function is used for the testing of loadimage function.
    '''

    def load_local_image(self):
        local_img = cv2.imread('OIP-C-original.jpg')
        frame = cv2.cvtColor(local_img, cv2.COLOR_BGR2RGB)
        image = QImage(
            frame,
            frame.shape[1],
            frame.shape[0],
            frame.strides[0],
            QImage.Format_RGB888)
        self.ui.label.setPixmap(QtGui.QPixmap.fromImage(image))
        self.ui.graphicsView.setGeometry(
            QtCore.QRect(
                95,
                29,
                self.ui.label.pixmap().width(),
                self.ui.label.pixmap().height()))  # set the size policy to preferred!!!
        # everything done locally.

    def send_signal(self, data):
        self.progressChanged.emit(data)

    def start_video_capture(self, reduce_fps=False):  # Add reduce_fps parameter
        self.ui.dragdrop_widget.cross_image_label.hide()
        if self.media_source:  # Check if media source is not empty
            try:
                if not self.analyzed:  # If the video has not been analyzed yet
                    video_source = self.media_source
                    self.vid = cv2.VideoCapture(video_source)  # Capture video from the given source
                    print("Ready to capture new file.")
                    # Start a new thread to upload the video
                    thread = Thread(self.s3_client, video_source, get_bucket_name())
                    thread.start()  # Start the thread
                    thread.wait()   # Use wait() to wait for the thread to finish
                else:
                    # Handle previously analyzed video
                    self.vid = cv2.VideoCapture(os.path.join(current_folder,'output','myvideo.mp4'))  # Load the default video
                # Optionally reduce the capture frame rate
                if reduce_fps:
                    original_fps = self.vid.get(cv2.CAP_PROP_FPS)
                    self.vid.set(cv2.CAP_PROP_FPS, original_fps / 2)  # Reduce the frame rate by half
                # Update the button text to indicate the next action
                self.ui.pushButton_2.setText("Start")
            except Exception as e:  # Catch a more specific exception
                print(f"An error occurred: {e}")  # Print the error message for debugging
            
            #try:
            #    self.update() #reloading can zoom to normal
            #except:pass
        else:
            print("No media source provided.")  # Provide feedback if media source is empty

    def on_item_dropped(self,media):
        self.media_source = str(media)
        self.ui.lineEdit_media.setText(self.media_source)
        self.loadImage()

    def loadImage(self):
        self.fps = 25

        """ This function will load the camera device, obtain the image
            and set it to label using the setPhoto function.
            This works as the most important function of the whole program.
            First, it connects with the import media button.
            If you hit it, it will opens up a dialog to let you choose mp4 or jpg media.
            Before it processes the media, it filters the path you enter in the dialog.
            Filter 1: If you enter nothing, it will return None. Nothing will happen.
        """
        '''Below is the IP filter
        '''

        self.start_video_capture(reduce_fps=False)


        # Get the total number of frames and frames per second (fps) from the video
        self.total_frame = int(self.vid.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = int(self.vid.get(cv2.CAP_PROP_FPS))
        self.video_duration = self.total_frame / self.fps  # Calculate total video duration
        # Reset current frame if it exceeds total frames
        if not self.current_frame < self.total_frame:
            self.current_frame = 0
        # Debug output for current frame and analysis status
        print(self.current_frame)
        print(self.requires_analyze)
        # Set the position of the video capture to the current frame
        self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        
        # Check if analysis is required
        if self.requires_analyze:
            # Disable the start button when analyzing
            self.ui.pushButton_2.setEnabled(False)
            self.ui.slider_time.setEnabled(False)
            
            # Check if the current media source is in the JSON file for recognition
            if self.recognize_json and is_item_in_json(os.path.join(current_folder,'test.json'), self.media_source):
                print('Your mp4 is being analyzed; please decide if you need it to be analyzed.')
                # Read data from JSON and update the media source and related parameters
                temp_data = read_from_json(os.path.join(current_folder,'test.json'), self.media_source)
                self.media_source = temp_data['filename']
                self.fps = temp_data['fps']
                self.emotion_mark_list = temp_data['emotion_mark_list']
                self.commissure_seq = temp_data['commissure_seq']
                self.nasion_list = temp_data['nasion_list']
                self.conversion_list = temp_data['conversion_list']
                self.leftx_eye_list = temp_data['leftx_eye_list']
                self.lefty_eye_list = temp_data['lefty_eye_list']
                # Emit progress change event
                self.progressChanged.emit(100)  # Emit progress in case of network failure
                # Mark the video as analyzed
                self.analyzed = True
                # Restart video capture from a default video source
                self.vid = cv2.VideoCapture(os.path.join(current_folder,'output','myvideo.mp4'))
                self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Set to the first frame
                # Update video properties after restarting the capture
                self.total_frame = int(self.vid.get(cv2.CAP_PROP_FRAME_COUNT))
                self.fps = int(self.vid.get(cv2.CAP_PROP_FPS))
                self.current_frame = 0
                # Update the graphics view size when the analysis has finished
                self.ui.graphicsView.setGeometry(
                    QtCore.QRect(
                        95,
                        29,
                        self.vid.get(cv2.CAP_PROP_FRAME_WIDTH) /
                        self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT) * 618,
                        618)
                )
                # Disable analysis requirement and enable pause button
                self.requires_analyze = False
                self.ui.pushButton.setEnabled(True)
                self.ui.pushButton_2.setEnabled(False)
                # Call display and state functions
                self.display()
                self.allow_landmarking()
            else:
                # Start analysis if no prior analysis is required
                self.load_first_frame()
        else:
            # Enable pause button if analysis is complete
            self.ui.pushButton.setEnabled(True)
            self.ui.pushButton_2.setEnabled(False)
            self.display()  # Update display

    def send_frame_number_pesudo(self):
        '''function to test whether the server can receive frame number.Copied from load_first_frame.'''
        try:
            self.sio.call(
                'frame_number', {
                    'frame number': -1}, timeout=5)
        except BaseException:
            pass

    def send_frame_number(self):
        '''function to test whether the server can receive frame number.Copied from load_first_frame.'''
        try:
            self.sio.call(
                'frame_number', {
                    'frame number': self.connection_list[round(self.current_frame-1)]}) #还原原始视频位置
            print("frame number sent:"+str(self.current_frame))
        except BaseException:
            pass

    def load_first_frame(self):
        '''new function. save the video. to filter the emotion.'''
        # height=self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        try:
            self.sio.call(
                'analyze_uploaded_video_and_generate_emotion_list', {
                    'filename': self.media_source}, timeout=5)
        except BaseException:
            pass

        self.vid_writer = cv2.VideoWriter(
            os.path.join(current_folder,'output','myvideo.mp4'), cv2.VideoWriter.fourcc(
                'm', 'p', '4', 'v'), self.fps, (int(
                    self.vid.get(
                        cv2.CAP_PROP_FRAME_WIDTH)), int(
                    self.vid.get(
                        cv2.CAP_PROP_FRAME_HEIGHT))))

        '''displaying the first frame.'''
        self.current_frame = 0

        self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)

        print(self.total_frame)
        print(self.media_source)
        print(self.vid)

        img, self.image = self.vid.read()
        self.image = imutils.resize(self.image, height=618)
        self.ui.graphicsView.setGeometry(
            QtCore.QRect(
                95,
                29,
                self.vid.get(
                    cv2.CAP_PROP_FRAME_WIDTH) /
                self.vid.get(
                    cv2.CAP_PROP_FRAME_HEIGHT) *
                618,
                618))  # change the graphicsview size when the analyzing has finished.

        if self.vid.get(cv2.CAP_PROP_FRAME_WIDTH) / \
                self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT) * 618 > 1351 - 50:

            self.ui.gridLayout.setGeometry(
                QtCore.QRect(95, 29, 1351 + 200, 891))

        self.requires_analyze = False
        self.update()
        self.requires_analyze = True

        self.current_frame = 0

        self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)


    def process_seq_func(self):
        self.draw_align_point = False
        self.conver_accord_karmen = False
        self.draw_align_rect = False
        # another video that labels all not happy frames with a green frame.
        self.store_not_happy_frame_but_show = True

        self.current_frame = 0
        self.conversion_list_index = 0

        self.commissure_seq_temp = []
        self.emotion_mark_list_temp = []
        self.nasion_list_temp = []

        # another video that labels all not happy frames with a green frame.
        if self.store_not_happy_frame_but_show == True:
            self.vid_writer_another = cv2.VideoWriter(
                os.path.join(current_folder,'output','myvideo_another.mp4'), cv2.VideoWriter.fourcc(
                    'm', 'p', '4', 'v'), self.fps, (int(
                        self.vid.get(
                            cv2.CAP_PROP_FRAME_WIDTH)), int(
                        self.vid.get(
                            cv2.CAP_PROP_FRAME_HEIGHT))))

        while (self.vid.isOpened()):
            img, self.image = self.vid.read()
            if self.image is None:  # not == None
                break
            self.image = imutils.resize(
                self.image, height=int(
                    self.vid.get(
                        cv2.CAP_PROP_FRAME_HEIGHT)))
            #print(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))  # necessary for debuuging, but large video may be laggy.
            #print(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))  # necessary

            # another video that labels all not happy frames with a green
            # frame.
            if self.store_not_happy_frame_but_show == True:
                img_another = self.image
                if self.emotion_mark_list[self.current_frame] > 0.9:
                    cv2.rectangle(
                        img_another, (0, 0), (img_another.shape[1], img_another.shape[0]), (0, 255, 0), 2)
                self.vid_writer_another.write(img_another)

            if self.commissure_seq[self.current_frame] != 0:
                if self.draw_align_point == True:
                    cv2.circle(self.image, (round(self.leftx_eye_list[self.conversion_list_index]), round(
                        self.lefty_eye_list[self.conversion_list_index])), 8, (0, 255, 0), -1)
                # if set to karmen filter,the video will change its size, which
                # reduces the error caused by movements, however if the person
                # do not move, it will cause extra error.
                if self.conver_accord_karmen == True:
                    self.conversion_factor_video = self.conversion_list[self.conversion_list_index]
                else:
                    # if the person is relatively static, please set to this.
                    self.conversion_factor_video = 1
                resized_img = cv2.resize(
                    self.image,
                    None,
                    fx=self.conversion_factor_video,
                    fy=self.conversion_factor_video)  # important
                new_img = np.ones_like(self.image)
                start_x = round((1 - self.conversion_factor_video)
                                * self.leftx_eye_list[self.conversion_list_index])
                start_y = round((1 - self.conversion_factor_video)
                                * self.lefty_eye_list[self.conversion_list_index])
                new_img[start_y:start_y +
                        resized_img.shape[0], start_x:start_x +
                        resized_img.shape[1]] = resized_img
                if self.draw_align_rect == True:
                    cv2.rectangle(
                        new_img,
                        (start_x,
                            start_y),
                        (start_x +
                            resized_img.shape[1],
                            start_y +
                            resized_img.shape[0]),
                        (0,
                            255,
                            0),
                        2)

                self.vid_writer.write(new_img)
                # important, we need to multiply conversion factor once since
                # we assume it is in one dimension.
                self.commissure_seq_temp.append(
                    self.commissure_seq[self.current_frame] * self.conversion_factor_video)
                self.emotion_mark_list_temp.append(
                    self.emotion_mark_list[self.current_frame])
                self.nasion_list_temp.append(
                    self.nasion_list[self.current_frame])
                self.conversion_list_index += 1
            self.current_frame += 1
            '''if self.image is None:
                break'''
        if self.store_not_happy_frame_but_show == True:  # another video that labels all not happy frames with a green frame.
            self.vid_writer_another.release()

        '''to be done next'''
        self.vid_writer.release()

        #smoothed_commissure_seq_temp = adaptive_savitzky_golay_filter(self.commissure_seq_temp, max_window_length=11, polyorder=6, threshold=0.05)
        #self.commissure_seq=scale_to_int(smoothed_commissure_seq_temp)
        self.commissure_seq=self.commissure_seq_temp
        self.emotion_mark_list = self.emotion_mark_list_temp
        self.nasion_list = self.nasion_list_temp

        y = self.commissure_seq

        pre_x = np.arange(0, len(self.commissure_seq) / self.fps, 1 / self.fps)

        # z=[ii*30 for ii in self.conversion_list]

        # print("conversion_list:"+str(z))

        x = list(pre_x)

        if len(x)>len(y):
            x=x[:-1]
        elif len(x)<len(y):
            y=y[:-1]

        plt.plot(x, y, 'g--')  # hotfix

        # plt.plot(x,z)

        ymax = max(y)
        print(ymax)

        xpos = np.where(np.array(y) == ymax)
        print(xpos)
        for i in xpos[0]:
            print(x[i])  # the time of the largest nad biggest smile.

            plt.annotate(
                'local max\n' + str(
                    round(
                        x[i], 2)), xy=(
                    x[i], ymax), xytext=(
                    0, 0), textcoords='offset points')

        self.max=round(x[i], 2)*self.fps

        plt.savefig(os.path.join(current_folder,'output','commissure.png'))

        plt.cla()
        
        #image = Image.open("commissure.png")
        #image.show()

        self.progressChanged.emit(100)  # In case the network failure.

        self.analyzed = True

        self.vid = cv2.VideoCapture(os.path.join(current_folder,'output','myvideo.mp4'))
        self.vid.set(cv2.CAP_PROP_POS_FRAMES, 0)  # set to the first frame.
        self.total_frame = int(self.vid.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = int(self.vid.get(cv2.CAP_PROP_FPS))
        self.current_frame = 0
        self.conversion_list_index = 0
        print(self.commissure_seq)
        self.ui.slider_time.update_scores(self.commissure_seq)

    def display(self,mode="from beginning"):
        self.ui.slider_time.setEnabled(True)
        if mode=="on peak":
            self.current_frame= self.max
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            img, self.image = self.vid.read()
            self.image = imutils.resize(self.image, height=618)
            self.update()
            self.Pause = False
            self.ui.pushButton.setEnabled(False)
            self.ui.pushButton_2.setEnabled(True)
            self.ui.time_setter.setText(str(float(self.current_frame / self.fps)))
            print("allow_landmarking executed.")
            self.ui.slider_time.location=self.current_frame
            print(f"DISPLAY changed slider_time.location to {self.ui.slider_time.location}")
            self.ui.slider_time.update()
            print(f"slider_time UPDATED.")
        if mode=="from beginning":
            while (self.vid.isOpened()):
                QtWidgets.QApplication.processEvents()
                img, self.image = self.vid.read()
                cv2.waitKey(33)
                # None means the video has reached its end.
                if self.current_frame == self.total_frame - 1:
                    self.current_frame = 0
                    self.vid.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                    self.ui.pushButton.click()  # hit the pause button by itself.
                # to display more clearly.
                self.image = imutils.resize(self.image, height=618)
                if self.slider_allow_auto_move == True:
                    #self.ui.slider_time.setValue(
                    #    self.current_frame)
                    self.ui.slider_time.location=self.current_frame
                    self.ui.slider_time.update()

                # self.emotion_mark_list.append(self.process_with_AI()[2])
                '''new function.'''

                self.update()

                self.current_frame += 1

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or self.Pause == True:  # detect the pause
                    self.Pause = False
                    self.ui.pushButton_2.setEnabled(True)
                    self.update()
                    break
            self.ui.pushButton_render.click()

    def setPhoto(self, image):
        """ This function will take image input and resize it
            only for display purpose and convert it to QImage
            to set at the label.
        """
        self.tmp = image
        #if self.requires_analyze == True:
        #    image = imutils.resize(image, width=640)
        #else:
        image = imutils.resize(image, height=618)
        frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = QImage(
            frame,
            frame.shape[1],
            frame.shape[0],
            frame.strides[0],
            QImage.Format_RGB888)
        self.ui.label.setPixmap(QtGui.QPixmap.fromImage(image))

    def setPhoto_with_proper_height(self, image):
        """ This function will take image input and resize it
            only for display purpose and convert it to QImage
            to set at the label.
        """
        self.tmp = image
        image = imutils.resize(image, height=618)
        frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = QImage(
            frame,
            frame.shape[1],
            frame.shape[0],
            frame.strides[0],
            QImage.Format_RGB888)
        self.ui.label.setPixmap(QtGui.QPixmap.fromImage(image))
        return (frame, frame.shape[1], frame.shape[0])

    def update(self):
        self.setPhoto(self.image)

    def landmarks_clear(self):
        self.ui.scene.clear()
        # self.ui.graphicsView.setScene(self.ui.scene)
        # if delete this,there will be a RuntimeError: wrapped C/C++ object of
        # type QGraphicsRectItem has been deleted.
        self.ui.landmark_list.clear()

        print(self.ui.scene)  # you do not have to createa new scene.

    def send_info(self):
        self.send_frame_number()
        self.ui.pushButton_render.setEnabled(False)

    def landmarks_calculator(self):
        landmarks = detect_face(self.detector, self.image)
        print('0:'+str(self.image.shape[0]))
        transformed_landmarks_dict_list = []
        if landmarks is not None:
            self.landmarks = landmarks
            '''notice:to make each append operation shorter, first we append the coordinates without offset.'''
            transformed_landmarks_dict_list.append({'center_x': landmarks[33][0],
                                                    'center_y': landmarks[33][1],
                                                    'name': 'subnasale'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[39][0],
                                                    'center_y': landmarks[39][1],
                                                    'name': 'right inner canthus'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[42][0],
                                                    'center_y': landmarks[42][1],
                                                    'name': 'left inner canthus'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[62][0],
                                                    'center_y': landmarks[62][1],
                                                    'name': 'inferior upper lip border'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[66][0],
                                                    'center_y': landmarks[66][1],
                                                    'name': 'superior lower lip border'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[36][0],
                                                    'center_y': landmarks[36][1],
                                                    'name': 'right outer canthus'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[45][0],
                                                    'center_y': landmarks[45][1],
                                                    'name': 'left outer canthus'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[48][0],
                                                    'center_y': landmarks[48][1],
                                                    'name': 'right outer smile commissure'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[54][0],
                                                    'center_y': landmarks[54][1],
                                                    'name': 'left outer smile commissure'})
            transformed_landmarks_dict_list.append({'center_x': (landmarks[21][0] + landmarks[22][0]) / 2,
                                                    'center_y': (landmarks[21][1] + landmarks[22][1]) / 2,
                                                    'name': 'soft tissue nasion'})
            transformed_landmarks_dict_list.append({'center_x': landmarks[8][0],
                                                    'center_y': landmarks[8][1],
                                                    'name': 'soft tissue pogonion'})
            if self.display_tooth_landmarks == True and self.ins!=None:
                # calculate the incisor edge point's x from the lip border
                # distance.
                if self.ins[0]!=10000: #tried to detect but not detected
                    print(self.gin[0])
                    print('48'+str(landmarks[48][0]))
                    incisor_edge_x = self.ins[0]
                    # calculate the incisor edge point's y from the lip border
                    # distance.
                    incisor_edge_y = self.ins[1]
                if self.ins[0]==10000: #the auxillary method
                    incisor_edge_x = landmarks[62][0] + self.incisor_edge_index * (
                    landmarks[66][0] - landmarks[62][0])
                    # calculate the incisor edge point's y from the lip border
                    # distance.
                    incisor_edge_y = landmarks[62][1] + self.incisor_edge_index * (
                        landmarks[66][1] - landmarks[62][1])
                transformed_landmarks_dict_list.append({'center_x': incisor_edge_x,
                                                        'center_y': incisor_edge_y,
                                                        'name': 'incisor edge'})
                dis_from_incisor_to_lip = self.dis_of_vec((incisor_edge_x, incisor_edge_y),
                                                        self.dconv(
                                                            landmarks[62]),
                                                            ((landmarks[21][0] + landmarks[22][0]) / 2,
                                                            (landmarks[21][1] + landmarks[22][1]) / 2),
                                                            self.dconv(landmarks[33]))  # the l1
                
                if self.rcpc[0]!=10000:
                    transformed_landmarks_dict_list.append({'center_x': self.rcpc[0],
                                                            'center_y': self.rcpc[1],
                                                            'name': 'left upper cuspid tip'})
                if self.rcpc[0]==10000: #the auxillary method
                    transformed_landmarks_dict_list.append({'center_x': self.cuspid_edge_index * (landmarks[64][0] - landmarks[66][0]) + landmarks[66][0] + landmarks[62][0] + self.incisor_edge_index * (landmarks[66][0] - landmarks[62][0]) - landmarks[66][0],
                                                        'center_y': (landmarks[65][1] - landmarks[66][1]) * self.cuspid_edge_index * (landmarks[64][0] - landmarks[66][0]) / (landmarks[65][0] - landmarks[66][0]) + landmarks[66][1] + landmarks[62][1] + self.incisor_edge_index * (landmarks[66][1] - landmarks[62][1]) - landmarks[66][1],
                                                        'name': 'left upper cuspid tip'})
                    
                if self.lcpc[0]!=10000:
                    transformed_landmarks_dict_list.append({'center_x': self.lcpc[0],
                                                            'center_y': self.rcpc[1],
                                                            'name': 'right upper cuspid tip'})
                if self.lcpc[0]==10000: #the auxillary method
                    transformed_landmarks_dict_list.append({'center_x': self.cuspid_edge_index * (landmarks[60][0] - landmarks[66][0]) + landmarks[66][0] + landmarks[62][0] + self.incisor_edge_index * (landmarks[66][0] - landmarks[62][0]) - landmarks[66][0],
                                                            'center_y': (landmarks[67][1] - landmarks[66][1]) * self.cuspid_edge_index * (landmarks[60][0] - landmarks[66][0]) / (landmarks[67][0] - landmarks[66][0]) + landmarks[66][1] + landmarks[62][1] + self.incisor_edge_index * (landmarks[66][1] - landmarks[62][1]) - landmarks[66][1],
                                                            'name': 'right upper cuspid tip'})
                if self.gin[0]!=10000:
                    cer_of_incisor_x = self.gin[0]
                    cer_of_incisor_y = self.gin[1]
                if self.gin[0]==10000: #the auxillary method
                    cer_of_incisor_x = incisor_edge_x - self.incisor_length / dis_from_incisor_to_lip * (incisor_edge_x - landmarks[62][0])
                    cer_of_incisor_y = incisor_edge_y - self.incisor_length / dis_from_incisor_to_lip * (incisor_edge_y - landmarks[62][1])
                transformed_landmarks_dict_list.append({'center_x': cer_of_incisor_x,
                                                            'center_y': cer_of_incisor_y,
                                                            'name': 'cervical part of incisor'})
                    #print(f"incisor_edge_index from LANDMARKS_CALCULATOR:{self.incisor_edge_index}")
            # transformed_landmarks_dict.
            '''now we add the offset and calculate.'''
            for value in transformed_landmarks_dict_list:
                value['center_x'] -= self.image.shape[1] / 2
                value['center_y'] -= self.image.shape[0] / 2
                self.landmarks_render(value)

        self.refresh()

    def cord_from_name(self, name: str):
        try:
            return (self.ui.landmark_list[name].coordinates_dict["center_x"] + self.ui.landmark_list[name].pos().x(), 
        self.ui.landmark_list[name].coordinates_dict["center_y"] + self.ui.landmark_list[name].pos().y())
        except KeyError:
            pass
            return 0
            print(self.ui.landmark_list)
       

    def refresh(self):  # calcualte smile characteristics from self.landmarks, which
        # is a list that stores all the Xs and Ys of previously detected
        # landmarks.
        landmarks = self.landmarks
        if not self.cord_from_name("right outer smile commissure")==0:
            self.angles = {'canthus and smile commissure divation(dg)': str(self.angle_between_four_points(self.cord_from_name("right outer canthus"), self.cord_from_name("left outer canthus"), self.cord_from_name("right outer smile commissure"), self.cord_from_name("left outer smile commissure"))),
                        'intercommissure width(mm)': str(self.dis_of_vec(self.cord_from_name("right outer smile commissure"),
                                                                        self.cord_from_name(
                                                                            "left outer smile commissure"),
                                                                        self.cord_from_name(
                                                                            "right inner canthus"),
                                                                        self.cord_from_name(
                                                                            "left inner canthus")
                                                                        )),
                        'interlabial gap(mm)': str(self.dis_of_vec(self.cord_from_name("inferior upper lip border"),
                                                                self.cord_from_name(
                                                                    "superior lower lip border"),
                                                                self.cord_from_name(
                                                                    "soft tissue nasion"),
                                                                self.cord_from_name(
                                                                    "subnasale")
                                                                )),
                        'philtrum height(mm)': str(self.dis_of_vec(self.cord_from_name("subnasale"),
                                                                self.cord_from_name(
                                                                    "inferior upper lip border"),
                                                                self.cord_from_name(
                                                                    "soft tissue nasion"),
                                                                self.cord_from_name(
                                                                    "subnasale")
                                                                )),
                        'transverse symmetry(mm)': str(self.rel_dis(np.abs(self.ver_dis_from_point_to_vec(self.cord_from_name("left outer smile commissure"),
                                                                                                        self.cord_from_name(
                                                                                                            "soft tissue nasion"),
                                                                                                        self.cord_from_name("soft tissue pogonion")) -
                                                                        self.ver_dis_from_point_to_vec(self.cord_from_name("right outer smile commissure"),
                                                                                                        self.cord_from_name(
                                                                                                            "soft tissue nasion"),
                                                                                                        self.cord_from_name("soft tissue pogonion"))),
                                                                self.cord_from_name(
                                                                    "soft tissue nasion"),
                                                                self.cord_from_name("subnasale"))),
                        'vertical symmetry(dg)': str(self.angle_between_four_points(self.cord_from_name("left outer smile commissure"), self.cord_from_name("right outer smile commissure"), self.cord_from_name("soft tissue nasion"), self.cord_from_name("soft tissue pogonion")))
                        }
            if self.display_tooth_landmarks == True:
                self.angles['upper dental angulation(dg)'] = str(self.angle_between_four_points(self.cord_from_name("inferior upper lip border"),
                                                                                            self.cord_from_name(
                                                                                                "incisor edge"),
                                                                                            self.cord_from_name(
                                                                                                "soft tissue nasion"),
                                                                                            self.cord_from_name("subnasale")))
                self.angles['gingival display(mm)'] = str(self.dis_of_vec(self.cord_from_name("inferior upper lip border"),
                                                                    self.cord_from_name(
                                                                        "cervical part of incisor"),
                                                                    self.cord_from_name(
                                                                        "soft tissue nasion"),
                                                                    self.cord_from_name(
                                                                        "subnasale")
                                                                    ))

            display = ''
            self.ui.comboBox.clear()
            for key, value in self.angles.items():
                display += key + ': ' + value + '\n'
                self.ui.comboBox.addItem(key)
            self.ui.textEdit_2.setPlainText(display)

    def dconv(self, a) -> (float, float):  # dlib xy converter
        return a[0], a[1]

    def mol_of_vec(self, a: (float, float), b: (float, float)) -> float:
        vec = np.array((b[0] - a[0], b[1] - a[1]))
        mol_vec = np.sqrt(vec.dot(vec))
        return mol_vec

    def dis_of_vec(self, a: (float, float), b: (float, float),
                   ref_a: (float, float), ref_b: (float, float)) -> float:
        mol_vec1 = self.mol_of_vec(a, b)
        mol_vec_ref = self.mol_of_vec(ref_a, ref_b)
        return mol_vec1 * self.conversion_factor / mol_vec_ref

    # c is the point.
    def ver_dis_from_point_to_vec(self, a: (float, float), b: (
            float, float), c: (float, float)) -> float:
        A = (b[1] - a[1]) / (a[0] - b[0])
        B = 1
        C = (b[1] - a[1]) / (b[0] - a[0]) * a[0] - a[1]
        distance = np.abs(A * c[0] + B * c[1] + C) / np.sqrt(A * A + B * B)
        return distance

    def rel_dis(self, distance: float, ref_a: (
            float, float), ref_b: (float, float)) -> float:
        mol_vec_ref = self.mol_of_vec(ref_a, ref_b)
        return distance * self.conversion_factor / mol_vec_ref

    def angle_between_four_points(self, a: (float, float), b: (
            float, float), c: (float, float), d: (float, float)) -> float:
        vec_1 = np.array((b[0] - a[0], b[1] - a[1]))
        vec_2 = np.array((d[0] - c[0], d[1] - c[1]))

        mol_vec_1 = np.sqrt(vec_1.dot(vec_1))
        mol_vec_2 = np.sqrt(vec_2.dot(vec_2))
        dot_product = vec_1.dot(vec_2)
        cos_ = dot_product / (mol_vec_1 * mol_vec_2)
        arccos_ = np.arccos(cos_)
        return arccos_ * 180 / np.pi  # angle

    def landmarks_render(self, dict_for_landmarks):
        '''dict for landmarks is a dict that stores the parameters to be passed to MyItem object.
        the structure of the dict is:{"center_x":int,"center_y":int,"name":str}
        '''
        #print(hex(id(QThread.currentThread())))
        self.ui.landmark_list[dict_for_landmarks['name']] = MyItem(
            dict_for_landmarks, self.ui.landmark_size)  # allocate like this to ensure in the middle. -25 and -25 are the upper and left most of the coordinates.
        # self.ui.landmark_list[0].setPos(QtCore.QPointF(100,100))
        # self.ui.landmark_list[0].setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.ui.landmark_list[dict_for_landmarks['name']
                              ].inner_signal.mysignal.connect(self.refresh)
        self.ui.scene.addItem(
            self.ui.landmark_list[dict_for_landmarks['name']])
        print(f"The x of {dict_for_landmarks['name']} is {self.ui.landmark_list[dict_for_landmarks['name']].transformOriginPoint().x()}"
            )


    def readcsv(self):
        # self.ui.pushButton_readcsv.setText("change_csv")
        read_dialog = read_Dialog(self)  # parent window:mainwindow
        read_dialog.csv_source = "xxx"
        # the lambda function is necessary for taking arguments.
        read_dialog.ui.buttonBox.accepted.connect(
            lambda: self.csv_loader(read_dialog.csv_source))
        read_dialog.show()

    def csv_loader(self, csv_file):
        with open(csv_file) as file:
            loader = csv.DictReader(file)
            for lines in loader:
                # pass the lines into the landmarks_render function and renders
                # the landmarks to qlabel.
                self.landmarks_render({'center_x': float(lines['center_x']), 'center_y': float(
                    lines['center_y']), 'name': lines['name']})
                print(lines)
            print(csv_file)
        pass

    def writecsv(self):
        # allocate self as the parent window.
        write_dialog = write_Dialog(self)
        write_dialog.csv_source = "xxx"
        self.identity = "AI"
        write_dialog.mysignal.connect(self.process_sig_img)
        write_dialog.identity_signal.connect(self.rec_character)
        # the lambda function is necessary for taking arguments.
        write_dialog.ui.buttonBox.accepted.connect(
            lambda: self.csv_exporter(write_dialog.csv_source))
        write_dialog.show()

    def process_sig_img(self, text):
        if text == 'true':
            self.save_img = True
        else:
            self.save_img = False

    def rec_character(self, text):
        if text == "AI":
            self.identity = "AI"
        elif text == "tester1":
            self.identity = "tester1"
        elif text == "tester2":
            self.identity = "tester2"

    def csv_exporter(self, csv_folder):

        # Extract landmark data as a list of dictionaries from the UI landmark list
        content = [i.get_dict() for i in list(self.ui.landmark_list.values())]
        # Create a new list with relevant landmark information
        content_new = [
            {
                'center_x': str(x['center_x']),
                'center_y': str(x['center_y']),
                'name': x['name']
            } for x in content
        ]
        # Determine the appropriate CSV file path based on the media source type
        media_extension = os.path.splitext(self.media_source)[-1]
        if media_extension == '.jpg':
            # If the media source is a JPG image, create a CSV file name based on the image's base name
            csv_file = os.path.join(csv_folder, os.path.basename(self.media_source) + '.csv')
        elif media_extension == '.mp4':
            # If the media source is an MP4 video, create a CSV filename for storing landmarks
            csv_file = os.path.join(csv_folder, os.path.basename(self.media_source) + '-' +
                                    str(float((self.current_frame - 1) / self.fps)) + '.csv')
            
            # Create a second CSV filename for storing measurements
            csv_file_2 = os.path.join(csv_folder, os.path.basename(self.media_source) + '-' +
                                    str(float((self.current_frame - 1) / self.fps)) + '_measurements.csv')
            # Check if images should be saved
            if self.save_img:
                try:
                    # Save the current frame as a PNG image
                    cv2.imwrite(os.path.join(csv_folder, os.path.basename(self.media_source) + '-' +
                                            str(float((self.current_frame - 1) / self.fps)) + '.png'), self.image)
                except Exception as e:
                    # Optionally, you can log the exception if needed
                    print(f"Error saving image: {e}")
        # Create a dictionary to store file information
        new_dict = {}
        new_dict['filename'] = csv_file

        if self.test_mode == True:

            if is_item_in_json("record.json", csv_file) == False:
                new_dict["content_AI"] = [
                    {'center_x': '1', 'center_y': '1', 'name': x['name']} for x in content]
                new_dict["content_tester1"] = [
                    {'center_x': '1', 'center_y': '1', 'name': x['name']} for x in content]
                new_dict["content_tester2"] = [
                    {'center_x': '1', 'center_y': '1', 'name': x['name']} for x in content]
                if self.identity == "AI":
                    new_dict["content_AI"] = content_new
                elif self.identity == "tester1":
                    new_dict["content_tester1"] = content_new
                elif self.identity == "tester2":
                    new_dict["content_tester2"] = content_new
                append_tojson("record.json", new_dict)

            else:
                with open("record.json", 'r+') as file:
                    # First we load existing data into a dict.
                    file_data = json.load(file)

                    for thing in file_data["emp_details"]:
                        try:
                            if thing['filename'] == csv_file:
                                if self.identity == "AI":
                                    thing["content_AI"] = content_new
                                elif self.identity == "tester1":
                                    thing["content_tester1"] = content_new
                                elif self.identity == "tester2":
                                    thing["content_tester2"] = content_new
                        except BaseException:
                            print('error detected')
                            pass
                    file.seek(0)

                    json.dump(file_data, file, indent=4)

        # Define the field names for the CSV files
        fields = ['center_x', 'center_y', 'name']
        fields_2 = ['item', 'value']
        try:
            # Open the main CSV file for writing
            with open(csv_file, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()  # Write the header for the main CSV
                print(content)  # Debug: print the content of landmarks
                print(content_new)  # Debug: print the new content for landmarks
                # Assuming content is a list of dictionaries; write rows to the main CSV
                writer.writerows(content)
        except PermissionError:
            print("Permission error: Unable to write to the file.")
            return
        except Exception as e:
            print(f"An error occurred while writing to {csv_file}: {e}")
            return
        try:
            # Open the second CSV file for writing
            with open(csv_file_2, 'w', newline='') as file_2:
                writer_2 = csv.DictWriter(file_2, fieldnames=fields_2)
                writer_2.writeheader()  # Write the header for the secondary CSV
                # Prepare angle data for writing
                content_angles = [{'item': key, 'value': value} for key, value in self.angles.items()]
                # Write rows to the secondary CSV
                writer_2.writerows(content_angles)
        except PermissionError:
            print("Permission error: Unable to write to the file.")
            return
        except Exception as e:
            print(f"An error occurred while writing to {csv_file_2}: {e}")
            return

    def is_ip_exist(self, ip_address):
        try:
            socket.inet_aton(ip_address)
            return True
        except socket.error:
            return False

    def time_changed(self):
        print("total frame count:"+str(self.total_frame))
        print("video fps:"+str(self.fps))
        print("current slider location:"+str(self.ui.slider_time.location))
        frame_target = self.ui.slider_time.location

        if frame_target<=0:
            pass

        else:
            self.current_frame = frame_target

        if self.vid.isOpened():
            self.vid.set(cv2.CAP_PROP_POS_FRAMES, frame_target)

        self.slider_allow_auto_move = True

        self.ui.time_setter.setText(str(float(self.current_frame / self.fps)))

        '''QtWidgets.QToolTip.showText(
            QtCore.QPoint(
                100, 100), str(
                float(
                    frame_target / self.fps)), self.ui.slider_time)'''
        print('time')

        img, self.image = self.vid.read()

        self.image = imutils.resize(self.image, height=618)

        if not self.image is None:
            self.update()

    def overcome_zig(self):  # overcoming zigzags when toggling slide bar.
        self.slider_allow_auto_move = False

    def open_settings(self):
        set_dialog = set_Dialog(self, cloud_manager)
        set_dialog.mysignal.connect(self.load_the_tooth)
        set_dialog.cloudConfigurationChanged.connect(self.on_cloud_configuration_changed)

        set_dialog.incisor_edge_index = self.incisor_edge_index

        set_dialog.cuspid_edge_index = self.cuspid_edge_index

        set_dialog.ui.lineEdit.setText(str(self.conversion_factor))

        set_dialog.ui.lineEdit_2.setText(str(self.incisor_length))

        if self.display_tooth_landmarks == True:
            set_dialog.ui.checkBox.setCheckState(1)
        else:
            set_dialog.ui.checkBox.setCheckState(0)
        if self.save_img == True:
            set_dialog.ui.checkBox_2.setCheckState(1)
        else:
            set_dialog.ui.checkBox_2.setCheckState(0)
        set_dialog.mysignal2.connect(self.save_the_image)
        set_dialog.mysignal3.connect(self.change_conversion_factor)
        set_dialog.mysignal5.connect(self.get_incisor_edge_index)
        set_dialog.mysignal6.connect(self.get_cuspid_edge_index)
        set_dialog.mysignal7.connect(self.get_incisor_length)

        set_dialog.show()

    def on_cloud_configuration_changed(self):
        os.environ['DYNASMILE_BUCKET'] = cloud_manager.config.get('bucket', 'frank--bucket')
        self.set_server_status("Server: configuration saved, connecting…", "#b36b00")
        self.connect_cloud_server()

    def select_change(self,text):
        display=''
        display += text + ': ' + self.angles[text] + '\n'
        for key, value in self.angles.items():
            if key!=text:
                display += key + ': ' + value + '\n'
        self.ui.textEdit_2.setPlainText(display)

        print("Now items in combobox are: "+text)
        print(self.ui.landmark_list['right outer smile commissure'].brush().color().name())
        print(self.measure_to_mark(text)[0])
        if self.ui.landmark_list[self.measure_to_mark(text)[0]].brush().color().name()=='#ffff00':
            for item in self.measure_to_mark(text):
                self.ui.landmark_list[item].setBrush(QtGui.QBrush(QtCore.Qt.green))
            self.ui.comboBox.clear()
            self.ui.comboBox.addItem(text)
        else:
            for item in self.measure_to_mark(text):
                self.ui.landmark_list[item].setBrush(QtGui.QBrush(QtCore.Qt.yellow))
            self.ui.comboBox.clear()
            for key, value in self.angles.items():
                self.ui.comboBox.addItem(key)

    def measure_to_mark(self,measurement):
        if measurement=='intercommissure width(mm)':
            return ['right outer smile commissure','left outer smile commissure']
        elif measurement=='canthus and smile commissure divation(dg)': 
            return ["right outer canthus","left outer canthus","right outer smile commissure","left outer smile commissure"]
        elif measurement=='interlabial gap(mm)': 
            return["inferior upper lip border","superior lower lip border"]
        elif measurement== 'philtrum height(mm)': 
            return["subnasale","inferior upper lip border"]
        elif measurement=='transverse symmetry(mm)': 
            return["left outer smile commissure","right outer smile commissure","soft tissue nasion","subnasale"]
        elif measurement=='vertical symmetry(dg)': 
            return["left outer smile commissure","right outer smile commissure","soft tissue nasion", "soft tissue pogonion"]
        elif measurement=='upper dental angulation(dg)':
            return["inferior upper lip border","incisor edge"]
        elif measurement=='gingival display(mm)':
            return["inferior upper lip border","cervical part of incisor"]

    def load_the_tooth(self, text):
        if text == 'true':
            self.display_tooth_landmarks = True
        else:
            self.display_tooth_landmarks = False

    def save_the_image(self, text):
        if text == 'true':
            self.save_img = True
        else:
            self.save_img = False

    def get_incisor_edge_index(self, text):
        try:
            self.incisor_edge_index = float(text)
            '''incisor_edge_x = int(
                self.landmarks[62][0] +
                self.incisor_edge_index *
                (
                    self.landmarks[66][0] -
                    self.landmarks[62][0]) -
                self.image.shape[1] /
                2)  # calculate the incisor edge point's x from the lip border distance.
            incisor_edge_y = int(
                self.landmarks[62][1] +
                self.incisor_edge_index *
                (
                    self.landmarks[66][1] -
                    self.landmarks[62][1]) -
                self.image.shape[0] /
                2)  # calculate the incisor edge point's y from the lip border distance.'''

            '''incisor_point = {'center_x': incisor_edge_x,
                             'center_y': incisor_edge_y,
                             'name': 'incisor edge'}'''

            '''if 'incisor edge' in self.ui.landmark_list:  # search the landmark_list
                self.ui.landmark_list['incisor edge'].set_position(
                    incisor_point['center_x'], incisor_point['center_y'])
            else:
                self.ui.landmark_list['incisor edge'] = MyItem(
                    incisor_point, self.ui.landmark_size)
                self.ui.landmark_list['incisor edge'].inner_signal.mysignal.connect(
                    self.refresh)  # connect to refresh
                self.ui.scene.addItem(self.ui.landmark_list['incisor edge'])
                print('added!!!!!!!!!!!!!!!!!!!!!!!"')
                print(incisor_edge_x, incisor_edge_y)'''
        except BaseException:
            print('incisor error')
        

    def get_cuspid_edge_index(self, text):
        try:
            self.cuspid_edge_index = float(text)
        finally:
            pass

    def get_incisor_length(self, text):
        try:
            self.incisor_length = float(text)
        finally:
            pass

    def change_conversion_factor(self, text):
        try:
            self.conversion_factor = float(text)
            if self.angles:
                print(self.angles)
                #self.refresh()
        except AttributeError:
            print("please load landmarks first.")
        finally:
            pass

    def closeEvent(self, event):
        if cloud_manager:
            cloud_manager.close()
        event.accept()


if __name__ == '__main__':
    parent_folder=os.path.dirname(current_folder)
    upper_folder=os.path.dirname(parent_folder)

    logging.basicConfig(
    filename=os.path.join(current_folder,'output','error_log.txt'),
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

    sys.excepthook = log_exception

    app = QApplication(sys.argv)
    try:
        cloud_manager = AWSManager()
        os.environ['DYNASMILE_BUCKET'] = cloud_manager.config.get('bucket', 'frank--bucket')
        cutomUI = CustomUI()
        cutomUI.show()
        QtCore.QTimer.singleShot(0, cutomUI.connect_cloud_server)
        sys.exit(app.exec_())
    except Exception as e:
        if cloud_manager:
            cloud_manager.close()
        QtWidgets.QMessageBox.critical(None, "Dynasmile cloud startup failed", str(e))
    finally:
        if cloud_manager:
            cloud_manager.close()
'''
12.10 task: write_csv dialog choose different image.
'''
'''
to do: add dlib reconizing function.
'''
'''
to do: add scroll bar.
'''
