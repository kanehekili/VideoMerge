#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# copyright (c) 2022 kanehekili (mat.wegmann@gmail.com)
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
from PyQt5 import QtGui,QtWidgets,QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal,pyqtSlot
from DragnDropTableWidget import DragList,IconDelegate,PathDelegate,ProgressStatusBar

import mimetypes
import subprocess
import datetime
import re
import FFMPEGTools
from FFMPEGTools import FFStreamProbe,OSTools
from fractions import Fraction
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
        self._generateStatusIcons()
        self.init_ui()
        self.merger=None
        self.settings=SettingsModel()
    
    def init_ui(self):
        self.setWindowTitle("VideoMerge")
        self.init_toolbar()
     
        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        
        dlgBox = QtWidgets.QVBoxLayout() 
        dlgBox.setContentsMargins(2, 1, 3, 1) #left top right bottom
        btnHBox = QtWidgets.QHBoxLayout()
        
        self.listWidget = DragList(self)
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.onDropURL.connect(self.addURL)
        
        self.listWidget.setHeaders(["File", "Progress"])
        self.listWidget.setItemDelegateForColumn(0,PathDelegate(self))
        self.listWidget.setItemDelegateForColumn(1,IconDelegate(self.statusIcons))
        self.listWidget.setSectionResizeMode(0,QtWidgets.QHeaderView.Stretch)
        self.listWidget.setSectionResizeMode(1,QtWidgets.QHeaderView.ResizeToContents)
        self.listWidget.setToolTip("Drag files with SAME codec here")
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
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
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
        self.startAction = QtWidgets.QAction(QtGui.QIcon('./icons/start-icon.png'), 'Start Concat', self)
        self.startAction.setShortcut('Ctrl+M')
        self.startAction.triggered.connect(self.startMerge)

        self.stopAction = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'), 'Stop', self)
        self.stopAction.setShortcut('Ctrl+H')
        self.stopAction.triggered.connect(self.stopMerge)
        self.stopAction.setEnabled(False)
        
        self.mediaSettings = QtWidgets.QAction(QtGui.QIcon('./icons/settings.png'), "Settings", self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self.openMediaSettings)
        
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.startAction)
        self.toolbar.addAction(self.stopAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.mediaSettings)
    
  
    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def getMessageDialog(self, text, infoText):
        # dlg = DialogBox(self)
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Information)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Notice")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        #dlg.standardButtons.accepted.connect(self.accept)
        # Workaround to resize a qt dialog. WTF!
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
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
        ok = self.mimeHelper.isValidUrl(mimeData)
        if not ok:
            return False
        #self._displayHomogeniousState()  
        return True    

    def _onRemove(self,anIndex):
        if anIndex==None:
            return self._endMergeUI()

        self._displayHomogeniousState()
    
    def _onMergeProgress(self,percent):
        QtCore.QCoreApplication.processEvents()
        curr= self.statusProgress.value()
        if percent > curr:
            self.statusProgress.setValue(percent)
        else:
            print("Progress: %d now: %d"%(percent,curr))
    
    def _displayHomogeniousState(self):
        pathItems=self.listWidget.allColumnItems(0)
        listOfUrls=(entry.text() for entry in pathItems) #that genrator only works once
        #TODO TEST 
        #for eintrag in listOfUrls:
        #    print("#2",eintrag)
        self.mimeHelper.checkListIfHomogenious(listOfUrls)
        
        if not self.mimeHelper.homogenious:
            self._showStatus("Inhomogenious - merge by reencoding")
        else:
            self._showStatus("Homogenious - fast merge ")          
                
    def startMerge(self):
        cnt = range(self.listWidget.count())
        if len(cnt)==0:
            self.getMessageDialog("<b>Clumsy fingers</b>", "No files added?").show()
            return
        mel=[]
        #create MergeEntry for each row
        for indx in cnt:
            me = MergeEntry(self.listWidget.items(indx))
            mel.append(me)
            
        self.merger = Merger(mel,self.mimeHelper.homogenious,self.settings)
        self.merger.onProgress.connect(self._onMergeProgress)
        self.merger.onStatus.connect(self._showStatus)
        targetFile = self.getTargetFile(self.merger)
        if targetFile is None:
            return
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
        result = QtWidgets.QFileDialog.getSaveFileName(parent=self, directory=targetPath, caption="Save Video");
        if result[0]:
            fn = result[0]
            return fn
        return None
    
    def stopMerge(self):
        if not self.merger:
            self._showStatus("Invalid condition, process not found")
            return
        self.merger.interrupt()
    
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
        self._displayHomogeniousState()
    
  
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
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle("Settings")

        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
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
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
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
        self.model.reencode = QtCore.Qt.Checked == reencode

    def on_rotationChanged(self, rotation):
        self.model.noRotation = QtCore.Qt.Checked == rotation

        
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
 evaluates if the path is valid and the file can be processed. If homogenious-fast merge possible, else a reencode is needed
'''           
class MimeHelper():
    def __init__(self):
        mimetypes.init()
        mimetypes.add_type("video/mp2t",".m2t",True)
        mimetypes.add_type("video/mp2t",".m2ts",True)
        mimetypes.add_type("video/mp2t",".ts",True)
        mimetypes.add_type("video/mp2t",".mts",True)
        self.reset()
        self.homogenious=True
        self.referenceMimeString=None
        
    def isValidUrl(self,mimeData):
        if not mimeData:
            self.reset()
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

    #check after sth has been removed - we do not know whats in that list...
    def checkListIfHomogenious(self,listofUrls):
        self.referenceMimeString=None
        for url in listofUrls:
            log.debug("mimehelper testing %s:",url)
            self._evaluateFile(url)
                
        '''
        refMime=None
        for url in listofUrls:
            mimeType = mimetypes.guess_type(url)
            if refMime is None:
                refMime=mimeType
            if not mimeType == refMime:
                return False
        return True
        '''    
    
    def _evaluateMime(self,aQUrl):
        if aQUrl.isLocalFile() and len(aQUrl.fileName())>0:
            return self._evaluateFile(aQUrl.fileName())
        return False

    def _evaluateFile(self,urlString):
        types = mimetypes.guess_type(urlString)
        log.debug("mime:%s",types[0])
        if types[0] is not None and "video" in types[0]:
            if self.referenceMimeString is None:
                self.referenceMimeString = types[0]
            if types[0] == self.referenceMimeString:  
                self.homogenious=True
            else:
                self.homogenious=False
            return True
        return False


    def reset(self):
        self.singleMimeString=None;

class VideoAttributes():
    #WIDTH=0
    #HEIGHT=1
    #FPS=2
    #ROTATION=3
    #NAMES={"WIDTH":0,"HEIGHT":1,"FPS":2,"ROTATION":3}
    NAMES=["WIDTH","HEIGHT","FPS","ROTATION"]
    
    def __init__(self,path,frameProbe):
        self.probe=frameProbe
        self.video = frameProbe.getVideoStream()
        self.audio = frameProbe.getAudioStream() #might be None
        self.info = frameProbe.formatInfo
        self.src=path    
        '''
        self.src=src
        self.width=w
        self.height=h
        self.fps=fps
        self.rotation=rot
        self.needTS=tsInfo
        self.isTS=isTS
    
    #video.getWidth(),video.getHeight(),video.saneFPS(),video.getRotation(),needsTS,isTS
                isTS= fmt.isTransportStream()
            needsTS = fmt.isMP4Container() #TODO To be tested with mkv - maybe h264 is the quesiton
            if needsTS:
                print("File needs to be TS!")

    '''
            
    def homogenious(self,otherCA):
        if self.width() != otherCA.width():
            return self.NAMES[0]
        if self.height() != otherCA.height():
            return self.NAMES[1]
        
        noTS= not(self.isTS() or otherCA.isTS())
        if noTS and self.fps() != otherCA.fps(): #ignore fps on TS streams
            #if self.fps<100 and otherCA<100:
            return self.NAMES[2]
        #if self.rotation != otherCA.rotation:
        #    return self.NAMES[3]
        return None
    
    def hasCompatibleRotation(self,otherCA):
        delta = abs(self.rotation() - otherCA.rotation())
        return delta != 90 
    
    def fps(self):
        return self.video.saneFPS()

    def rotation(self):
        return self.video.getRotation()

    def needsTS(self):
        return self.probe.isMP4Container()
    
    def isTS(self):
        return self.probe.isTransportStream()
    
    def height(self):
        return self.video.getHeight()
    
    def width(self):
        return self.video.getWidth()

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
    
    def __init__(self,mergeEntryList,fastMode,settings):
        super(Merger, self).__init__()
        self.runningProcess=None
        self.mergeList=mergeEntryList
        #self.currentMergeEntry=None
        self.timeGen=None
        self.timeMark=None
        self.processed=0
        #self.fastMode=fastMode #either fast or needs to reencode
        self.conversionMode=self.MODE_FAST if fastMode and not settings.reencode else self.MODE_REENCODE
        self.errors=[]
        self.videoList=[]
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
            fmt = FFStreamProbe(src)
            info = fmt.formatInfo
            video = fmt.getVideoStream()
            #audio = fmt.getAudioStream() 
            culm=culm+int(info.getDuration())
            self.cumulatedSums.append(culm) 
            log.debug("Checking file %s",src)
            log.debug("Info dur %s",info.getDuration())
            log.debug("Info br %s",info.getBitRate())
            log.debug("Info size %s",info.getSizeKB())
            log.debug("Info formats %s",info.formatNames())
            log.debug("Video size: %s @ %s"%(video.getWidth(),video.getHeight()))
            log.debug("Video fps: %d"%(video.saneFPS()))
            log.debug("Video rot: %d"%(video.getRotation()))
  
            #TODO: pass streamProbe data - CA should do the rest
            cid = VideoAttributes(src,fmt)
            self.videoList.append(cid)
            
        log.info("---Total dur: %d",culm)
        self.totalTime=culm
        self.timeGen=iter(self.cumulatedSums)
        self.timeMark=(next(self.timeGen),0) #tuple: time and merge entry index.
        self._refineMuxing()

    def isImpossible(self):
        return self.conversionMode == self.MODE_IMPOSSIBLE

    def _refineMuxing(self):
        #on ts we might have an fps drop!
        if self.conversionMode==self.MODE_REENCODE:
            self.onStatus.emit("Reencoding")
            return #different containers..
        #TODO: does the target support the codecs?? astra and moebius do not fit into mkv as example
        if len(self.videoList)<2:
            return
        for i,ca in enumerate(self.videoList[:-1]):
            adjacent=self.videoList[i+1]
            val= ca.homogenious(adjacent)
            if val is not None:
                log.info("Invalid stream value %s : %s - ignoring file %s"%(val,adjacent,adjacent.src)) #TODO cal.value(key)
                
                if not ca.hasCompatibleRotation(adjacent) and self.autoRotate():
                    self.errors.append("Portrait and Landscape can't be joined")
                    self.validateDone()
                    break
                
                self.conversionMode=self.MODE_REENCODE #brute force. take the first videoList
                self.onStatus.emit("Different formats - will reencode all")
                break

            if ca.needsTS():
                self.conversionMode=self.MODE_TS
                self.onStatus.emit("Merging with TS filters")
                break

    def autoRotate(self):
        return not self.settings.noRotation 
    
    def healFPS(self,ref,instance):
        pass #iterate throught the fps and get the most sane one
    
    def saveTo(self,targetFile):
           
        targetDir= os.path.dirname(targetFile)
        mergeFile=targetDir+'content.txt'
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
        self.validateDone()

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
        log.info('Reencoding mp4- searching sane FPS')
        prim=self.videoList[0]
        darMode=Fraction(int(prim.width()),int(prim.height()))
        cmd1=['ffmpeg', "-hide_banner", "-y"]
        #for mergeEntry in self.mergeList:
        for ca in self.videoList:
            cmd1.append("-i")
            cmd1.append(ca.src)
        cmd1.append('-filter_complex')
        indx=0
        cmdString=[]
        cmdString.append('')
        #for mergeEntry in self.mergeList:
        #data must be same on all streams!
        for ca in self.videoList:
            cmdString.append("[")
            cmdString.append(str(indx))
            cmdString.append(":v]")
            cmdString.append("scale="+prim.width()+":"+prim.height())
            cmdString.append(",setdar="+str(darMode.numerator)+"/"+str(darMode.denominator)+",")
            cmdString.append("fps="+str(prim.fps())+",")
            rot = str(prim.rotation()) if self.autoRotate() else "0"
            cmdString.append("rotate="+rot)
            cmdString.append("[v")
            cmdString.append(str(indx))
            cmdString.append("]; ")
            indx=indx+1
        #build the mapping
        for indx in range(len(self.mergeList)):
            cmdString.append("[v")
            cmdString.append(str(indx))
            cmdString.append("][")
            cmdString.append(str(indx))
            cmdString.append(":a] ")

        cmdString.append("concat=n="+str(len(self.mergeList))+':v=1:a=1 [outv] [outa]')#"
        cmd1.append(''.join(cmdString))
        cmd1.append("-map")
        cmd1.append('[outv]')
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
        for ca in self.videoList:
            tempFile=self.TMP_FILE+str(fnr)+".ts"
            rotFile=self.ROT_FILE+str(fnr)+".mp4"
            tmpFiles.append(tempFile)
            fnr+=1
            srcFile =ca.src
            if ca.rotation()!=0 and self.autoRotate():
                cmd=['ffmpeg', "-hide_banner", "-y",'-i',ca.src,"-vf","rotate=0",rotFile]
                self._runCommand(cmd, "Rotate",self.timeCursor)# 
                srcFile=rotFile
            
            cmd=['ffmpeg', "-hide_banner", "-y",'-i',srcFile,"-c","copy","-bsf:v","h264_mp4toannexb","-f","mpegts",tempFile]
            self._runCommand(cmd, "To transport stream",0)#??? no count % because intermediate

        targetDir= os.path.dirname(targetFile)                    
        mergeFile=targetDir+'content.txt'       
        with open(mergeFile,'w') as aFile:
            aFile.write('ffconcat version 1.0\n') 
            for tmpEntry in tmpFiles:
                aFile.write("file '"+ tmpEntry+"'\n")
        self._commandMuxing(mergeFile, targetFile)
        os.remove(mergeFile)
         
    def _runCommand(self,cmd,stage,advanceCount):
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
    
    #flickering problem
    #same time=ignore
    #time<prevTime = index+1
    #time == index-1: ignore
    '''TODO:
    > frame= 5619 fps=239 q=-1.0 Lsize=   23551kB time=00:03:07.30 bitrate=1030.0kbits/s dup=1 drop=2 speed=7.96x  total: [187, 206]
T: 00:03:07.30 index:0 cursor: 187 END:187 list:187,206 proz:90

> frame=    1 fps=0.0 q=-1.0 size=       0kB time=00:00:00.00 bitrate=N/A speed=N/A  total: [187, 206]
T: 00:00:00.00 index:0 cursor: 0 END:187 list:187,206 proz:0

> frame= 5619 fps=0.0 q=-1.0 Lsize=   25472kB time=00:03:07.30 bitrate=1114.0kbits/s speed=3.33e+03x  total: [187, 206]
T: 00:03:07.30 index:0 cursor: 187 END:187 list:187,206 proz:90

> frame=    1 fps=0.0 q=0.0 size=       0kB time=00:00:00.23 bitrate=   1.6kbits/s speed=10.4x  total: [187, 206]
T: 00:00:00.23 index:0 cursor: 0 END:187 list:187,206 proz:0

> frame=  121 fps=0.0 q=29.0 size=     256kB time=00:00:04.07 bitrate= 514.8kbits/s speed=7.79x  total: [187, 206]
T: 00:00:04.07 index:0 cursor: 4 END:187 list:187,206 proz:1

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
                    
    
    #invoked by stop button, kill the process...
    def interrupt(self):
        if self.runningProcess is None:
            self.onStatus.emit("Can't stop ffmpeg - Proeces not found = Error!")
        else:
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
        app.setWindowIcon(getAppIcon())
        res = parseOptions(sys.argv)
        win = VideoMerge(res)
        
        win.show()
        code = app.exec_()
        log.info("Close Session")
        return code
    except:
        traceback.print_exc(file=sys.stdout)

if __name__ == '__main__':
    sys.exit(main())
    
