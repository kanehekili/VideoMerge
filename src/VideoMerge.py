#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# copyright (c) 2022-2024 kanehekili (kanehekili.media@gmail.com)
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License,
# as published by the Free Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the  GNU General Public License for more
# details.
#
# You should have received a copy of the  GNU General Public License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
'''
Created on Apr 16, 2020

@author: kanehekili
'''
import sys,traceback,os,getopt
from PyQt6 import QtGui,QtWidgets,QtCore
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import pyqtSignal,pyqtSlot

from DragnDropTableWidget import DragList,IconDelegate,PathDelegate,ProgressStatusBar

import mimetypes
import subprocess
import datetime
import re
import FFMPEGTools
from FFMPEGTools import FFStreamProbe,OSTools,FORMATS
import glob


log=FFMPEGTools.Log

#log = logging.getLogger("VideoMerge")
#####################################################
Version = "@xxx@"
#####################################################

class VideoMerge(QtWidgets.QMainWindow):
    def __init__(self,debugOptions):
        log.info("Start")
        super(VideoMerge, self).__init__()
        FFMPEGTools.setupRotatingLogger("VideoMerge",debugOptions["logConsole"])
        FFMPEGTools.setLogLevel(debugOptions["level"])  
        log.info("Start session")             
        self.setWindowIcon(getAppIcon()) #Titlebar icon only!
        self.mimeHelper = MimeHelper()
        self.sigCache = SignatureCache()
        self.probeWorker=ProbeOperation(self,self.sigCache)
        self.probeWorker.finished.connect(self._onProbeDone)
        self.mergeMode=None
        self.mergeReason="Idle"
        self._generateStatusIcons()
        self.init_ui()
        self.merger=None
        self.worker=None
        self.settings=SettingsModel()
    
    def init_ui(self):
        self.setWindowTitle("VideoMerge")
        self.init_toolbar()
     
        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Shape.Panel | QtWidgets.QFrame.Shadow.Sunken)
        
        dlgBox = QtWidgets.QVBoxLayout() 
        dlgBox.setContentsMargins(2, 1, 3, 1) #left top right bottom
        btnHBox = QtWidgets.QHBoxLayout()
        
        self.listWidget = DragList(self)
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.onDropURL.connect(self.addURL)
        
        self.listWidget.setHeaders(["File", "Progress"])
        self.listWidget.setItemDelegateForColumn(0,PathDelegate(self))
        self.listWidget.setItemDelegateForColumn(1,IconDelegate(self.statusIcons))
        self.listWidget.setSectionResizeMode(0,QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.listWidget.setSectionResizeMode(1,QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.listWidget.setToolTip("Drag video files here - streams are analyzed automatically")
        #Filter to ensure the correct files are dragged and dropped
        self.listWidget.setDragFilter(self._onDropped)
        self.listWidget.onRemove.connect(self._onRemove)
        
        fontM = QtGui.QFontMetrics(self.listWidget.font())
        self.ITEM_HEIGHT = fontM.height() * 2
        self.ITEM_SIZE=80

        sb = ProgressStatusBar(self,"icons/stop-red-icon")
        self.statusbar=sb.statusbar
        self.statusProgress=sb.progressBar
        self.btnStop=sb.buttonStop
        self.statusbar.showMessage("Idle")
        #test
        sb.buttonStop.clicked.connect(self.stopMerge)
        
        dlgBox.addWidget(frame1)
        dlgBox.addWidget(self.listWidget)
        dlgBox.addLayout(btnHBox)
        dlgBox.addWidget(self.statusbar)

        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)        
        wid.setLayout(dlgBox)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 0)
        self.centerWindow()
    
    def _showStatus(self,text):
        log.info(text)
        self.statusbar.showMessage(text)
        self.statusbar.setToolTip(text)
    
    def _showProgress(self,isVisible):
        self.statusProgress.setRange(0, 100)
        self.statusProgress.setVisible(isVisible)    
        self.btnStop.setVisible(isVisible)
    
    def _generateStatusIcons(self):
        
        t1= QtGui.QIcon('icons/idleIcon.png')
        t2= QtGui.QIcon('icons/execIcon.png')
        t3= QtGui.QIcon('icons/doneIcon.png')
        self.statusIcons = [t1,t2,t3]
        #?self.statusIcons = [QtGui.QIcon(QtCore.QDir.current().absoluteFilePath("/icons/"+name)) for name in ["idleIcon.png", "execIcon.png","doneIcon.png"]]
    

    def init_toolbar(self):
        self.startAction = QtGui.QAction(QtGui.QIcon('./icons/start-icon.png'), 'Start Concat', self)
        self.startAction.setShortcut('Ctrl+M')
        self.startAction.triggered.connect(self.startMerge)

        self.stopAction = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'), 'Stop', self)
        self.stopAction.setShortcut('Ctrl+H')
        self.stopAction.triggered.connect(self.stopMerge)
        self.stopAction.setEnabled(False)
        
        self.mediaSettings = QtGui.QAction(QtGui.QIcon('./icons/settings.png'), "Settings", self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self.openMediaSettings)
        
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.startAction)
        self.toolbar.addAction(self.stopAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.mediaSettings)
    
  
    def centerWindow(self):
        frameGm = self.frameGeometry()
        #pyqt5 screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        #pyqt5 screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        #pyqt5 centerPoint = QApplication.desktop().screenGeometry(screen).center()
        centerPoint=QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def getMessageDialog(self, text, infoText):
        # dlg = DialogBox(self)
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dlg.setWindowTitle("Notice")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        #dlg.standardButtons.accepted.connect(self.accept)
        # Workaround to resize a qt dialog. WTF!
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        # dlg.setMinimumSize(450, 0)
        return dlg;

    def _prepareMergeUI(self):
        self._showStatus("Merging...")
        self.stopAction.setEnabled(True)
        #self.statusIcon.setVisible(True)
        #self.statusIcon.movie().start()
        self._showProgress(True)

    @pyqtSlot()
    def _endMergeUI(self):
        self.stopAction.setEnabled(False)
        self._showProgress(False)

    @pyqtSlot(str)
    def _noGood(self,error):
        self.getMessageDialog("Merge error", error).show()

    '''
    ---------- actions -------------
    '''

    def _onDropped(self,mimeData):
        return self.mimeHelper.isValidUrl(mimeData)

    def _onRemove(self,anIndex):
        if anIndex is None:
            self._endMergeUI()
        self._updateMergeMode()
    
    def _onMergeProgress(self,percent):
        QtCore.QCoreApplication.processEvents()
        curr= self.statusProgress.value()
        if percent > curr:
            self.statusProgress.setValue(percent)
        else:
            print("Progress: %d now: %d"%(percent,curr))
    
    '''
    probes the streams of all listed files (in background if not cached yet)
    and displays the resulting merge mode
    '''
    def _updateMergeMode(self):
        pathItems=self.listWidget.allColumnItems(0)
        paths=[entry.text() for entry in pathItems]
        if len(paths)==0:
            self.mergeMode=None
            self._showStatus("Idle")
            return
        missing = self.sigCache.missing(paths)
        if missing:
            self.mergeMode=None
            self._showStatus("Analyzing streams...")
            self._startProbe(missing)
            return
        broken=[os.path.basename(p) for p in paths if self.sigCache.get(p) is None]
        if broken:
            self.mergeMode=Merger.MODE_IMPOSSIBLE
            self.mergeReason="Can't probe: "+", ".join(broken)
            self._showStatus(self.mergeReason)
            return
        signatures=[self.sigCache.get(p) for p in paths]
        self.mergeMode,self.mergeReason = decideMergeMode(signatures,self.settings)
        self._showStatus(self.mergeReason)

    def _startProbe(self,paths):
        self.probeWorker.probe(paths) #ignored while busy - finished triggers a recheck

    @pyqtSlot()
    def _onProbeDone(self):
        self._updateMergeMode()

    def startMerge(self):
        cnt = range(self.listWidget.count())
        if len(cnt)==0:
            self.getMessageDialog("<b>Clumsy fingers</b>", "No files added?").show()
            return
        self._updateMergeMode() #settings may have changed - cheap, signatures are cached
        if self.mergeMode is None:
            self.getMessageDialog("Analyzing", "Still probing the files - try again in a moment").show()
            return
        if self.mergeMode == Merger.MODE_IMPOSSIBLE:
            self.getMessageDialog("Can't merge", self.mergeReason).show()
            return
        mel=[]
        #create MergeEntry for each row
        for indx in cnt:
            me = MergeEntry(self.listWidget.items(indx))
            mel.append(me)

        self.merger = Merger(mel,self.mergeMode,self.sigCache,self.settings)
        self.merger.onProgress.connect(self._onMergeProgress)
        self.merger.onStatus.connect(self._showStatus)
        targetFile = self.getTargetFile(self.merger)
        if targetFile is None:
            return
        self.merger.adaptToTarget(targetFile)
        self.worker=LongRunningOperation(self._asyncMerge,targetFile)
        self.worker.finished.connect(self._endMergeUI)
        self.worker.noGood.connect(self._noGood)
        self.worker.start()

        self._prepareMergeUI()

    def _asyncMerge(self,targetFile):
        self.merger.gatherInfos()
        self.merger.saveTo(targetFile)              
    
    def getTargetFile(self,merger):
        targetPath = merger.getTargetPath()
        firstFile = merger.mergeList[0].getText()
        ext = os.path.splitext(firstFile)[1]  #fallback: keep the source extension
        filterStr = "Video (*{});;All files (*)".format(ext) if ext else "All files (*)"
        sig = self.sigCache.get(firstFile)
        if sig is not None:
            best = sig.probe.getTargetExtension() #container that fits the codecs
            if best:
                ext = "."+best
                filterStr = "Video ({});;All files (*)".format(sig.probe.getDialogFileExtensions())
        proposal = os.path.join(targetPath,"merge"+ext)
        result = QtWidgets.QFileDialog.getSaveFileName(parent=self, directory=proposal, caption="Save Video", filter=filterStr)
        if result[0]:
            fn = result[0]
            if ext and not os.path.splitext(fn)[1]:
                fn += ext
            return fn
        return None
    
    def stopMerge(self):
        if not self.merger:
            self._showStatus("Invalid condition, process not found")
            return
        self.merger.interrupt()

    #stop ffmpeg and the worker threads before the window dies
    def closeEvent(self,event):
        if self.merger is not None:
            self.merger.interrupt()
        try:
            if self.worker is not None and self.worker.isRunning():
                self.worker.wait(5000)
        except RuntimeError:
            pass #thread object already deleted - nothing to wait for
        if self.probeWorker.isRunning():
            self.probeWorker.wait(3000)
        event.accept()
    
    def openMediaSettings(self):
        dlg = SettingsDialog(self, self.settings) 
        dlg.show()  
    
    def addURL(self,path):
        item = QtGui.QStandardItem() 
        item.setText(path)
        ''' Example for subclass. Set item prototye on views model! 
        item = PathItem()
        item.setData(path,item.ROLE)
        '''
        pb = QtGui.QStandardItem()
        #pb.setData(0,ProgressDelegate.PROGRESS_USER_ROLE)
        pb.setData(0,IconDelegate.PROGRESS_USER_ROLE)
        
#         cb = QtGui.QStandardItem()
#         cb.setData(True,CheckBoxDelegate.CHECKBOX_USER_ROLE)
        self.listWidget.addItems([item,pb])
        self._updateMergeMode()
    
  
    '''
    ---------- actions end -------------
    ''' 
     
    #Error hook  
    def raise_error(self):
        assert False
        
'''
class StatusDispatcher(QtCore.QObject):
    progressSignal = pyqtSignal(int)

    def __init__(self):
        QtCore.QObject.__init__(self)
    
    def progress(self, percent):
        self.progressSignal.emit(round(percent))
'''
class SettingsModel(QtCore.QObject):
    #trigger = pyqtSignal(object)#No save, no trigger!
    
    def __init__(self):
        # keep flags- save them later
        super(SettingsModel, self).__init__()
        self.reencode=False
        self.noRotation=False
             
        
class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent, model):
        """Init UI."""
        super(SettingsDialog, self).__init__(parent)
        self.model = model
        self.init_ui()

    def init_ui(self):
        #pyqt5 self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setWindowTitle("Settings")

        frame1 = QtWidgets.QFrame()
        #pyqt5 frame1.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame1.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Sunken)
        frame1.setLineWidth(1)

        encodeBox = QtWidgets.QVBoxLayout(frame1)
        self.check_reencode = QtWidgets.QCheckBox("Force Reencode (Slow!)")
        self.check_reencode.setToolTip("Reencode the files. Might take longer")
        self.check_reencode.setChecked(self.model.reencode)#session data .must not be saved...
        self.check_reencode.stateChanged.connect(self.on_reencodeChanged)
        encodeBox.addWidget(self.check_reencode)

        self.check_rotation = QtWidgets.QCheckBox("Ignore rotation information")
        self.check_rotation.setToolTip("Ignore the roation infos. Might lead to funny results")
        encodeBox.addWidget(self.check_rotation)
        self.check_rotation.setChecked(self.model.noRotation)
        self.check_rotation.stateChanged.connect(self.on_rotationChanged)
        outBox = QtWidgets.QVBoxLayout()
        # outBox.addStretch(1)
        #pyqt5 self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        versionBox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Version:")
        ver = QtWidgets.QLabel(Version)
        versionBox.addStretch(1)
        versionBox.addWidget(lbl)
        versionBox.addWidget(ver)
        versionBox.addStretch(1)
        
        outBox.addLayout(versionBox)
        outBox.addWidget(frame1)
        self.setLayout(outBox)
        # make it wider...
        self.setMinimumSize(400, 0)
        
    def on_reencodeChanged(self, reencode):
        self.model.reencode = QtCore.Qt.CheckState.Checked == reencode

    def on_rotationChanged(self, rotation):
        self.model.noRotation = QtCore.Qt.CheckState.Checked == rotation

        
class LongRunningOperation(QtCore.QThread):
    finished = pyqtSignal() 
    noGood= pyqtSignal(str)

    def __init__(self, func, *args):
        QtCore.QThread.__init__(self)
        self.function = func
        self.arguments = args

    def run(self):
        try:
            self.function(*self.arguments)
        except Exception as ex:
            #Log.logException("***Error in LongRunningOperation***")
            #self.msg = "Error while converting: "+str(ex)
            self.noGood.emit(str(ex))
            log.exception("Merge failure")
        finally:
            self.finished.emit()
            self.quit()
            self.deleteLater()


class MergeEntry():
    STATE_WAIT=0;
    STATE_PROCESS=1;
    STATE_DONE=2;
    def __init__(self,itemList):
        self.textItem = itemList[0]
        self.progress = itemList[1]
        
    def setText(self,text):
        self.displayName = text
        self.textItem.setText(self.displayName)
     
    def getText(self):
        return self.textItem.text()
        
    def setProgress(self,state):
        #print("Merge Progress:",state)
        self.progress.setData(state,IconDelegate.PROGRESS_USER_ROLE)

'''
 evaluates if the path may be processed at all - a cheap extension check
 before the streams are probed by the SignatureCache
'''
class MimeHelper():
    def __init__(self):
        mimetypes.init()
        mimetypes.add_type("video/mp2t",".m2t",True)
        mimetypes.add_type("video/mp2t",".m2ts",True)
        mimetypes.add_type("video/mp2t",".ts",True)
        mimetypes.add_type("video/mp2t",".mts",True)

    def isValidUrl(self,mimeData):
        if not mimeData:
            return False

        if not mimeData.hasUrls():
            return False
        urls = mimeData.urls()
        if len(urls)==0:
            return False
        for aQUrl in urls:
            if not self._evaluateMime(aQUrl):
                return False
        return True

    def _evaluateMime(self,aQUrl):
        if aQUrl.isLocalFile() and len(aQUrl.fileName())>0:
            types = mimetypes.guess_type(aQUrl.fileName())
            log.debug("mime:%s",types[0])
            return types[0] is not None and "video" in types[0]
        return False

'''
Copy-concat compatibility fingerprint of one video file. Everything that must
match for a stream-copy concat lives in "data", so comparing two files is a
loop and the mismatch report names the offending fields.
'''
class StreamSignature():
    FPS_TOLERANCE = 0.5

    def __init__(self,path,frameProbe):
        self.src=path
        self.probe=frameProbe
        video = frameProbe.getVideoStream()
        if video is None:
            raise ValueError("No video stream in "+path)
        audio = frameProbe.getAudioStream() #might be None
        vd = video.dataDict #every ffprobe field is in there
        self.data = {
            "vcodec": video.getCodec(),
            "width": int(video.getWidth()),
            "height": int(video.getHeight()),
            "pix_fmt": vd.get("pix_fmt"),
            "field_order": self._saneFieldOrder(vd),
            "sar": self._saneSAR(vd),
            "rotation": video.getRotation() % 360,
            "acodec": None, "sample_rate": None, "channels": None,
        }
        if audio is not None:
            self.data["acodec"] = audio.getCodec()
            self.data["sample_rate"] = audio.sampleRate()
            self.data["channels"] = audio.audioChannels()
        self.audio=audio
        self._fps = video.saneFPS()
        self.timeBase = video.getTimeBase()
        self.duration = frameProbe.formatInfo.getDuration()

    def _saneFieldOrder(self,dataDict):
        fo = dataDict.get("field_order")
        if fo is None or fo == "unknown":
            return "progressive"
        return fo

    #"0:1" means unspecified - same as the default 1:1
    def _saneSAR(self,dataDict):
        sar = dataDict.get("sample_aspect_ratio")
        if sar is None or sar == "0:1":
            return "1:1"
        return sar

    '''names of the fields that forbid a stream-copy concat with other. Empty list = compatible'''
    def mismatches(self,other):
        diffs = [key for key in self.data if self.data[key] != other.data[key]]
        noTS = not(self.isTS() or other.isTS()) #ignore fps on TS streams
        if noTS and abs(self._fps - other._fps) > self.FPS_TOLERANCE:
            diffs.append("fps")
        return diffs

    '''dimensions as presented to the viewer - coded dims swapped on 90/270 rotation'''
    def displayDims(self):
        if self.data["rotation"] % 180:
            return (self.data["height"],self.data["width"])
        return (self.data["width"],self.data["height"])

    def isPortraitVsLandscape(self,other):
        (w1,h1) = self.displayDims()
        (w2,h2) = other.displayDims()
        return (w1 > h1) != (w2 > h2)

    def hasAudio(self):
        return self.data["acodec"] is not None

    def audioRate(self):
        return self.data["sample_rate"] or 48000

    def audioLayout(self):
        if self.audio is not None:
            return self.audio.dataDict.get("channel_layout","stereo")
        return "stereo"

    def codec(self):
        return self.data["vcodec"]

    def fps(self):
        return self._fps

    def rotation(self):
        return self.data["rotation"]

    def needsTS(self):
        return self.probe.isMP4Container()

    def isTS(self):
        return self.probe.isTransportStream()

    def height(self):
        return str(self.data["height"])

    def width(self):
        return str(self.data["width"])

'''
Probes video files in its own thread. The built-in QThread "finished" signal
fires when a batch is done - it is emitted after run() has really returned,
so the thread may be restarted safely. One instance lives as long as its parent.
'''
class ProbeOperation(QtCore.QThread):
    def __init__(self,parent,cache):
        QtCore.QThread.__init__(self,parent)
        self.cache=cache
        self.paths=[]

    #main thread only. Ignored while busy - "finished" triggers a recheck anyway
    def probe(self,paths):
        if self.isRunning():
            return
        self.paths=paths
        self.start()

    def run(self):
        self.cache.probe(self.paths)

'''
Caches one StreamSignature per file path. probe() runs inside the
ProbeOperation thread - it must not touch any Qt UI objects.
'''
class SignatureCache():
    INVALID="invalid"

    def __init__(self):
        self._cache={}

    def probe(self,pathList):
        for path in pathList:
            if path in self._cache:
                continue
            try:
                self._cache[path] = StreamSignature(path,FFStreamProbe(path))
            except Exception:
                log.exception("Can't probe %s",path)
                self._cache[path] = self.INVALID

    '''paths that have not been probed yet'''
    def missing(self,pathList):
        return [path for path in pathList if path not in self._cache]

    '''the signature, or None if the file could not be probed'''
    def get(self,path):
        sig = self._cache.get(path)
        if sig is self.INVALID:
            return None
        return sig

#codecs that survive the mpegts intermediate route, with their bitstream filter
TS_BSF = {"h264":"h264_mp4toannexb", "hevc":"hevc_mp4toannexb"}

'''
Decides how a list of files can be merged, based on their stream signatures.
Returns a tuple (Merger.MODE_*, human readable reason)
'''
def decideMergeMode(signatures,settings):
    if len(signatures) < 2:
        return (Merger.MODE_FAST,"Single file - fast merge")
    ref = signatures[0]
    #impossibility dominates any other verdict - check all files first
    if not settings.noRotation:
        for sig in signatures[1:]:
            if ref.isPortraitVsLandscape(sig):
                return (Merger.MODE_IMPOSSIBLE,"Portrait and landscape can't be joined")
    for sig in signatures[1:]:
        diffs = ref.mismatches(sig)
        if diffs:
            reason = "%s differs in %s - reencoding"%(os.path.basename(sig.src),", ".join(diffs))
            return (Merger.MODE_REENCODE,reason)
    #all streams copy-compatible - pick the safest copy route
    timescaleDrift = any(sig.timeBase != ref.timeBase for sig in signatures)
    if ref.needsTS() or timescaleDrift:
        if ref.codec() in TS_BSF:
            return (Merger.MODE_TS,"Same streams - merging via transport stream")
        return (Merger.MODE_REENCODE,"Codec %s can't pass through mpegts - reencoding"%ref.codec())
    return (Merger.MODE_FAST,"Same streams - fast merge")

class Merger(QtCore.QObject):
    onProgress = pyqtSignal(int)
    onStatus = pyqtSignal(str) 
    REG_TIME = re.compile('(time=[ ]*)([0-9:.]+)') #2 groups!
    MODE_FAST=1
    MODE_TS=2
    MODE_REENCODE=3 #...tobe continued
    MODE_ROTATE=4
    MODE_IMPOSSIBLE=99
    TMP_FILE='/tmp/_merge'
    ROT_FILE='/tmp/_rot'
    
    def __init__(self,mergeEntryList,mergeMode,signatureCache,settings):
        super(Merger, self).__init__()
        self.runningProcess=None
        self.mergeList=mergeEntryList
        #self.currentMergeEntry=None
        self.timeGen=None
        self.timeMark=None
        self.processed=0
        self.conversionMode=self.MODE_REENCODE if settings.reencode else mergeMode
        self.interrupted=False
        self.errors=[]
        self.videoList=[] #StreamSignatures, in merge order
        self.signatureCache=signatureCache
        self.totalTime=0
        self.timeCursor=0 #for multi TS operations like rotatate & mux
        self.settings=settings

    '''
    Must be the same:
    Video resolution (e.g. -vf scale=1280x720)
    Video framerate (framerate dont need to match, but the timescale. -video_track_timescale 60000)
    Video interlacing (e.g. deinterlace using -vf yadif)
    Video pixel format (e.g. -vf format=yuv420p)
    Video codec (e.g. -c:v libx264)
    Audio samplerate (e.g. -ar 48000)
    Audio channels and track / layout (e.g. -map 0:1 -ac 2)
    Audio codec(s) (e.g. -c:a aac)
    '''
  
    def gatherInfos(self):
        culm=0
        self.cumulatedSums=[]
        for mergeEntry in self.mergeList:
            mergeEntry.setProgress(MergeEntry.STATE_WAIT)
            src= mergeEntry.getText()
            sig = self.signatureCache.get(src) #probed when the file was dropped
            if sig is None:
                raise ValueError("File can't be probed: "+src)
            culm=culm+int(sig.duration)
            self.cumulatedSums.append(culm)
            log.debug("File %s: %s %sx%s @%d fps rot:%d dur:%s",src,sig.codec(),sig.width(),sig.height(),sig.fps(),sig.rotation(),sig.duration)
            self.videoList.append(sig)

        log.info("---Total dur: %d",culm)
        self.totalTime=culm
        self.timeGen=iter(self.cumulatedSums)
        self.timeMark=(next(self.timeGen),0) #tuple: time and merge entry index.

    def autoRotate(self):
        return not self.settings.noRotation

    '''
    the user chose the target container - if it can't hold the copied codecs,
    fall back to reencoding instead of failing mid-merge
    '''
    def adaptToTarget(self,targetFile):
        if self.conversionMode==self.MODE_REENCODE:
            return
        fmtMap = FORMATS.fromFilename(targetFile)
        sig = self.signatureCache.get(self.mergeList[0].getText())
        if fmtMap is None or not fmtMap.containsCodecs(sig.codec(),sig.data["acodec"]):
            self.conversionMode=self.MODE_REENCODE
            self.onStatus.emit("Streams can't be copied into this container - reencoding")
            log.info("Target %s doesn't support %s/%s - reencode",targetFile,sig.codec(),sig.data["acodec"])

    def saveTo(self,targetFile):
           
        targetDir= os.path.dirname(targetFile)
        mergeFile=os.path.join(targetDir,'content.txt')
        #count = len(self.mergeList)
        self.markProcessStart()
        #hook for more variations
        try:
            if self.conversionMode==self.MODE_REENCODE:
                self.commandReencodeMP4Eloquent(targetFile)
            elif self.conversionMode==self.MODE_TS:
                self.processTS(targetFile)    
            else:
                with open(mergeFile,'w') as aFile:
                    aFile.write('ffconcat version 1.0\n') 
                    for mergeEntry in self.mergeList:
                        aFile.write("file '"+ mergeEntry.getText()+"'\n")
                self._commandMuxing(mergeFile, targetFile)
                os.remove(mergeFile)
                
        except Exception as error:
            self.runningProcess= None
            log.exception("SaveTo:")

        self._removeIntermediateFiles()
        if self.interrupted:
            self._removePartialTarget(targetFile)
            self.onStatus.emit("Merge stopped")
            return
        self.validateDone()

    #a stopped ffmpeg leaves an unusable torso
    def _removePartialTarget(self,targetFile):
        try:
            if os.path.exists(targetFile):
                os.remove(targetFile)
                log.info("Removed partial target %s",targetFile)
        except OSError:
            log.exception("Can't remove partial target %s",targetFile)

    '''
        this is the concat demuxer. works with mp4 or mp2, no need for intermediate ts files..
    '''
    def _commandMuxing(self,mergeFile,targetFile):
        cmd= ['ffmpeg', "-hide_banner", "-y", "-f", "concat", "-safe", "0","-segment_time_metadata","0","-noautorotate","-i", mergeFile,"-c","copy",targetFile ]
        self._runCommand(cmd, "Muxing",0)#one run, no time cumulation

    '''
    check:https://stackoverflow.com/questions/18141055/ffmpeg-commands-to-concatenate-different-type-and-resolution-videos-into-1-video
    '''
    #TODO: find first Sane FPS!
    def commandReencodeMP4Eloquent(self,targetFile):
        log.info('Reencoding')
        prim=self.videoList[0]
        if self.autoRotate():
            #ffmpeg rotates each input upright on decode - the canvas is prim's display size
            (w,h) = prim.displayDims()
        else:
            (w,h) = (int(prim.width()),int(prim.height()))
        withAudio = all(sig.hasAudio() for sig in self.videoList)
        if not withAudio:
            self.onStatus.emit("Clip without audio found - merging video only")
        cmd1=['ffmpeg', "-hide_banner", "-y"]
        for sig in self.videoList:
            if not self.autoRotate():
                cmd1.append("-noautorotate")
            cmd1.append("-i")
            cmd1.append(sig.src)
        cmd1.append('-filter_complex')
        cmdString=[]
        #normalize each stream to the "prim" canvas - concat needs equal streams.
        #the scale keeps the aspect ratio, differing formats are padded, not distorted
        scalePad = "scale=%d:%d:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1"%(w,h,w,h)
        for indx in range(len(self.videoList)):
            cmdString.append("[%d:v]"%indx)
            cmdString.append(scalePad)
            cmdString.append(",fps="+str(prim.fps()))
            cmdString.append("[v%d]; "%indx)
            if withAudio:
                cmdString.append("[%d:a]aresample=%d,aformat=channel_layouts=%s[a%d]; "%(indx,prim.audioRate(),prim.audioLayout(),indx))
        #build the mapping
        for indx in range(len(self.videoList)):
            cmdString.append("[v%d]"%indx)
            if withAudio:
                cmdString.append("[a%d]"%indx)
        if withAudio:
            cmdString.append("concat=n="+str(len(self.videoList))+':v=1:a=1 [outv] [outa]')
        else:
            cmdString.append("concat=n="+str(len(self.videoList))+':v=1:a=0 [outv]')
        cmd1.append(''.join(cmdString))
        cmd1.append("-map")
        cmd1.append('[outv]')
        if withAudio:
            cmd1.append("-map")
            cmd1.append('[outa]')
        cmd1.append(targetFile)
        self._runCommand(cmd1, "Reencoding",0)#no time slices. One process
        
    '''
    complex TS processing:
    1)rotate mp4 if necessary
    2)mux to TS 
    3)merge them
    '''
    def processTS(self,targetFile):
        log.info("Complex TS: rotate, mux & merge")
        fnr=0
        tmpFiles=[]
        for sig in self.videoList:
            tempFile=self.TMP_FILE+str(fnr)+".ts"
            rotFile=self.ROT_FILE+str(fnr)+".mp4"
            tmpFiles.append(tempFile)
            fnr+=1
            srcFile =sig.src
            if sig.rotation()!=0 and self.autoRotate():
                #bake the rotation in: the decoder rotates upright by itself, mpegts can't carry the metadata
                cmd=['ffmpeg', "-hide_banner", "-y",'-i',sig.src,rotFile]
                self._runCommand(cmd, "Rotate",self.timeCursor)#
                srcFile=rotFile

            bsf = TS_BSF.get(sig.codec(),"h264_mp4toannexb") #decideMergeMode only picks MODE_TS for these codecs
            cmd=['ffmpeg', "-hide_banner", "-y",'-i',srcFile,"-c","copy","-bsf:v",bsf,"-f","mpegts",tempFile]
            self._runCommand(cmd, "To transport stream",0)#??? no count % because intermediate

        targetDir= os.path.dirname(targetFile)
        mergeFile=os.path.join(targetDir,'content.txt')
        with open(mergeFile,'w') as aFile:
            aFile.write('ffconcat version 1.0\n') 
            for tmpEntry in tmpFiles:
                aFile.write("file '"+ tmpEntry+"'\n")
        self._commandMuxing(mergeFile, targetFile)
        os.remove(mergeFile)
         
    def _runCommand(self,cmd,stage,advanceCount):
        if self.interrupted:
            raise InterruptedError("Merge stopped")
        log.info("processing: %s",stage)
        for path in self.executeAsync(cmd,False):
            self.parseAndDispatch(path,advanceCount)

    #TODO option for audio lag?
       
    def markProcessStart(self):
        self.mergeList[0].setProgress(MergeEntry.STATE_PROCESS)

    '''
    There's some time between processing the last file and the merging of the whole file
    '''
    def validateDone(self):
        if self.processed+1 < len(self.mergeList):
            self.onStatus.emit("Error during merge")
            if len(self.errors)>0:
                dot = '\u2022'
                text =dot+dot.join(self.errors)
                raise Exception(text)
        else:
            self.mergeList[self.processed].setProgress(MergeEntry.STATE_DONE)
            self.onStatus.emit("Done")

    def executeAsync(self,cmd,shell):
        log.info(' '.join(cmd))     
        self.runningProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,shell=shell)
        for stdout_line in iter(self.runningProcess.stdout.readline, ""):
            yield stdout_line 
        self.runningProcess.stdout.close()
        return_code = self.runningProcess.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)         
    
    
    '''
    #error codes!
    Error reinitializing filters!
    Failed to inject frame into filter network: Invalid argument
    Error while processing the decoded data for stream #1:1
    Conversion failed!
    Aborted
    '''
   
    def parseAndDispatch(self,text,advanceCount):
        try:
            m= self.REG_TIME.search(text)
            if m is None:
                if re.search('error',text,flags=re.IGNORECASE):
                    self.errors.append(text)
                elif re.search('fail',text,flags=re.IGNORECASE):
                    self.errors.append(text)
                #log.debug(">> %s",text)
                return
            ts = m.group(2)
            pt = datetime.datetime.strptime(ts,'%H:%M:%S.%f')
            #that only works if you merge in one batch. No reliable info if segmented into muxing,rotate etc!  
            #totalSeconds = pt.second + pt.minute*60 + pt.hour*3600
            self.timeCursor = advanceCount + pt.second + pt.minute*60 + pt.hour*3600
            #TEST:
            print(">",text.strip())
            blob = ",".join(str(x) for x in self.cumulatedSums)
            currIndex = self.timeMark[1] #(endtime,index)
            eotChunk=self.timeMark[0] #end of the curr Video
            perc=(self.timeCursor/self.totalTime)*100
            log.debug("T: %s index:%d cursor: %d END:%d list:%s proz:%d",ts,currIndex,self.timeCursor,eotChunk, blob,perc)

            self.onProgress.emit(int(perc))
            while eotChunk < self.timeCursor:
                #print("   mark done")
                self.mergeList[currIndex].setProgress(MergeEntry.STATE_DONE)
                try:
                    timeSlice = next(self.timeGen,None)
                    if timeSlice:
                        self.timeMark=(timeSlice,currIndex+1)
                    else:
                        log.info("All marks done")
                        break;
                except StopIteration:
                    #print("End of list!")
                    log.exception("total seconds:")  
                    break
                currIndex = self.timeMark[1]
                self.processed=currIndex    
                eotChunk=self.timeMark[0] #end of the curr Video
                #print("Udate index:%d END:%d "%(currIndex,eotChunk))
                #print("   mark progress")                
                self.mergeList[currIndex].setProgress(MergeEntry.STATE_PROCESS)
                
        except:
            pass
            log.debug("?"+text)
            log.exception("Parse&dispatch:")  
            traceback.print_exc(file=sys.stdout)
    

    def getTargetPath(self):
        count = len(self.mergeList)
        lastEntry = self.mergeList[count - 1]
        return os.path.dirname(lastEntry.getText()) 
    
    def _removeIntermediateFiles(self):
        fileList = glob.glob(self.TMP_FILE+"*")
        fileList.extend(glob.glob(self.ROT_FILE+"*"))
        for filePath in fileList:
            try:
                os.remove(filePath)
                log.debug("RM:%s",filePath)
            except:
                log.exception("Error while deleting file: %s ", filePath)
                    
    
    #invoked by stop button or window close. Kills the process and prevents follow-up commands
    def interrupt(self):
        self.interrupted=True
        if self.runningProcess is not None:
            self.runningProcess.kill()
     
    #connect to ui?
    def warn(self,text):
        log.warning("Warning:%s",text) 
        

def getAppIcon():
    return QtGui.QIcon('icons/merge.png')

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.error("Application failure:\n %s", tb)
    QtWidgets.QApplication.quit()
            
def parseOptions(args):
    res={}
    res["logConsole"]=False
    res["level"]="Info"
    try:
        opts,args=getopt.getopt(args[1:], "cd", ["console","debug"])
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
    
    for o,a in opts:
        if o in ("-d","--debug"):
            #FFMPEGTools.setLogLevel("Debug")
            res["level"]="Debug"
        elif o in ("-c","--console"):
            res["logConsole"]=True
        else:
            print("Undef:",o) 
    return res            
            
             
def main():
    try:
        sys.excepthook = excepthook
        folder = OSTools().getLocalPath(__file__)
        #find your files and icons:
        OSTools().setMainWorkDir(folder)
        app = QApplication(sys.argv)
        # Set the application name (this sets WM_CLASS)
        app.setApplicationName("VideoMerge")
        # Link to your desktop file (important for GNOME)
        app.setDesktopFileName("VideoMerge.desktop")          
        
        app.setWindowIcon(getAppIcon())
        res = parseOptions(sys.argv)
        win = VideoMerge(res)
        
        win.show()
        code = app.exec()
        log.info("Close Session")
        return code
    except:
        traceback.print_exc(file=sys.stdout)

if __name__ == '__main__':
    sys.exit(main())
    
