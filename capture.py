__author__ = 'Tomasz Ksepka'

import cv2
import numpy as np
from PyQt4 import QtGui, QtCore
import dlib
import gabor_filters
import run_nn_classifier
import itertools
import rotate_image
import pickle
import video_feed
import face_recog_main

predictor_path = 'shape_predictor_68_face_landmarks.dat'
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(predictor_path)
pipeline = pickle.load(open('nnclf2.pk1', 'rb'))


gf = gabor_filters.build_filters()


class Capture(QtGui.QWidget):

    def __init__(self, video_source, videofeedwindow, on_next_frame=None):
        super(QtGui.QWidget, self).__init__()

        self.video_frame = QtGui.QLabel()
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.video_frame)
        self.setLayout(layout)
        self.video_source = video_source
        self.videofeedwindow = videofeedwindow
        self.current_frame = np.array([])
        self.current_emotions = {}
        self.on_next_frame = on_next_frame

    def get_frame(self):
        ret, frame = self.video_source.read()

        self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        ## Draw face bounding boxes and facial points on frame
        extracted_faces = []
        
        faces = run_nn_classifier.get_faces(frame)
        for face in faces:
            shape = predictor(frame, face)
            points = [(p.x, p.y) for p in shape.parts()]
            rotate_image.draw_face(self.current_frame, face)
            rotate_image.draw_points(self.current_frame, points)
            
            extracted_face = frame[face.top():face.bottom(), face.left():face.right()]
        #extracted_face = rotate_image.rotate_image(extracted_face)
            pred, conf = face_recog_main.recognizer.predict(extracted_face)
            if conf < 35:
                if pred == 20:
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.putText(self.current_frame, "Wendy", (face.left(),face.bottom() +10), font, 0.25,(0,0,255))
            else:
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(self.current_frame, "Unknown" , (face.left(),face.bottom() +10), font, 0.25,(0,0,255))

        height, width = self.current_frame.shape[:2]

        image = QtGui.QImage(self.current_frame, width, height, QtGui.QImage.Format_RGB888)
        image = QtGui.QPixmap.fromImage(image)
        self.video_frame.setPixmap(image)

        thread = GetEmotionsThread(frame, faces, self)
        self.connect(thread, thread.signal, self.update_image_with_emotions)
        #thread.return_emotions.connect(self.update)
        self.videofeedwindow.connect(thread,thread.signal2, self.videofeedwindow.update_graph)
        thread.start()

        if self.on_next_frame is not None:
            self.on_next_frame()
        # return image

    def update_emotions(self):
        self.videofeedwindow.update_table(self.current_emotions)
    
    def update_image_with_emotions(self, faces_emotion):
        font = cv2.FONT_HERSHEY_SIMPLEX
        emotion_text = {}
        emotion_text[0] = 'Neutral'
        emotion_text[1] = 'Angry/Disgusted'
        emotion_text[2] = 'Surprised/Afraid'
        emotion_text[3] = 'Happy'
        emotion_text[4] = 'Sad'
        for face,em in faces_emotion:
            cv2.putText(self.current_frame, emotion_text[em], (face.left() + 50, face.top() + 15), font, 0.4, (0,0,255))
            
        height, width = self.current_frame.shape[:2]

        image = QtGui.QImage(self.current_frame, width, height, QtGui.QImage.Format_RGB888)
        image = QtGui.QPixmap.fromImage(image)
        self.video_frame.setPixmap(image)

    def start(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.get_frame)
        self.timer.start(5)


    def stop(self):
        self.timer.stop()

    
    def scroll(self, new_value):
        self.video_source.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,new_value)


class GetEmotionsThread(QtCore.QThread):

    #return_emotions = QtCore.pyqtSignal(dict)

    def __init__(self, frame, faces, cw):
        QtCore.QThread.__init__(self)
        self.frame = frame
        self.faces = faces
        self.cw = cw
        self.signal = QtCore.SIGNAL("draw_emotions(PyQt_PyObject)")
        self.signal2 = QtCore.SIGNAL("update_graph(PyQt_PyObject)")

    def __del__(self):
        self.wait()

    def run(self):
        emotions = {}

        emotions[0] = 0
        emotions[1] = 0
        emotions[2] = 0
        emotions[3] = 0
        emotions[4] = 0

        num_faces = len(self.faces)

        if not num_faces:
            self.cw.current_emotions = emotions
            self.cw.update_emotions()
        else:
            faces_stored = []
            features_stored = []
            faces_list = []

            for face in self.faces:
                size = int(face.width()*0.2)
                if face.left() < size or (face.right() + size) > self.frame.shape[1] or face.top() < size or (face.bottom() + size > self.frame.shape[0]):
                    num_faces = num_faces - 1
                    continue
                faces_list.append(face)
                extracted_faces = rotate_image.cut_face(self.frame, face)
                extracted_faces = rotate_image.rotate_image(extracted_faces)
                faces_stored.append(extracted_faces)

                dim = extracted_faces.shape[0]
                face2 = dlib.rectangle(0, 0, dim, dim)

                features = run_nn_classifier.generate_feature_vector(extracted_faces, face2)
                features_stored.append(features)

            if num_faces:
                new_np_features = np.array([np.array(x) for x in features_stored])
                emotions_list = pipeline.predict(new_np_features)

                emotions_list = emotions_list.tolist()
                emotions_list = list(itertools.chain.from_iterable(emotions_list))

                for emotion in emotions_list:
                    emotions[emotion] += 1
                    # if emotion == 0:
                        # emotions[emotion] += 1
                    # elif emotion == 1:
                        # emotions[emotion] += 1
                    # elif emotion == 2:
                        # emotions[emotion] += 1
                    # elif emotion == 3:
                        # emotions[emotion] += 1
                    # elif emotion == 4:
                        # emotions[emotion] += 1
                #self.return_emotions.emit(emotions)
                faces_emotions = zip(faces_list, emotions_list)
                self.emit(self.signal, faces_emotions)
                self.emit(self.signal2, emotions)
                self.cw.current_emotions = emotions
                self.cw.update_emotions()

                print 'Emotions: ' + str(emotions_list)
            else:
                print "faces out of frame"






