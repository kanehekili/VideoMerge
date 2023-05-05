'''
Created on May 24, 2020

@author: matze
'''
#from PyQt5 import QtGui,QtWidgets,QtCore
#from PyQt5.QtCore import pyqtSignal
from PyQt6 import QtGui,QtWidgets,QtCore
from PyQt6.QtCore import pyqtSignal,Qt


import os

class CheckBoxDelegate(QtWidgets.QItemDelegate):
    CHECKBOX_USER_ROLE = QtCore.Qt.ItemDataRole.UserRole+1001
    
    def createEditor(self, parent, option, index):
        """ Important, otherwise an editor is created if the user clicks in this cell.
        """
        return None 
            
    def paint(self, painter, option, index):
        checked = index.data(self.CHECKBOX_USER_ROLE)
        text=index.data(QtCore.Qt.ItemDataRole.DisplayRole)
        opts = QtWidgets.QStyleOptionButton()
        opts.state |= QtWidgets.QStyle.StateFlag.State_Active
        if index.flags() & QtCore.Qt.ItemFlag.ItemIsEditable:
            opts.state |= QtWidgets.QStyle.StateFlag.State_Enabled
        else:
            opts.state |= QtWidgets.QStyle.StateFlag.State_ReadOnly
        if checked:
            opts.state |= QtWidgets.QStyle.StateFlag.State_On
        else:
            opts.state |= QtWidgets.QStyle.StateFlag.State_Off
        opts.rect = option.rect
        opts.textVisible = True
        opts.text=text
        QtWidgets.QApplication.style().drawControl(QtWidgets.QStyle.ControlElement.CE_CheckBox, opts, painter)
    
    def editorEvent(self, event, model, option, index):
        """ Change the data in the model and the state of the checkbox if the
        user presses the left mouse button and this cell is editable. Otherwise do nothing.
        """
        if not (index.flags() & QtCore.Qt.ItemFlag.ItemIsEditable):
            return False
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                if option.rect.contains(event.pos()):
                    self.setModelData(None, model, index)
                    return True
            elif event.type() == QtCore.QEvent.Type.MouseButtonDblClick:
                if option.rect.contains(event.pos()):
                    return True
        return False
    
    def setModelData(self, editor, model, index):
        """ Toggle the boolean state in the model.
        """
        checked = not bool(index.model().data(index, self.CHECKBOX_USER_ROLE))
        model.setData(index, checked, self.CHECKBOX_USER_ROLE)
    
class ProgressDelegate(QtWidgets.QStyledItemDelegate):
    PROGRESS_USER_ROLE = QtCore.Qt.ItemDataRole.UserRole+1001
    
    def paint(self, painter, option, index):
        progress = index.data(self.PROGRESS_USER_ROLE)
        #the selection
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight());
        else:
            painter.fillRect(option.rect, option.palette.window());

        opt = QtWidgets.QStyleOptionProgressBar()
        r1 = option.rect
        r1.adjust(3,3,-3,-3)#the "selection" border
        opt.rect = r1
        opt.minimum = 0
        opt.maximum = 100
        if progress is None:
            opt.progress = 0
        else:
            opt.progress = progress
        opt.text = "{}%".format(progress)
        opt.textVisible = True
        QtWidgets.QApplication.style().drawControl(QtWidgets.QStyle.ControlElement.CE_ProgressBar, opt, painter)

# simple delegate to display the filename only         
class PathDelegate(QtWidgets.QStyledItemDelegate):
    def displayText(self, value, locale):
        return os.path.basename(value)  

'''
Support plain icon delegate
'''
class IconDelegate(QtWidgets.QStyledItemDelegate):
    PROGRESS_USER_ROLE = QtCore.Qt.ItemDataRole.UserRole+1001
    def __init__(self, icons, parent=None):
        super(IconDelegate, self).__init__(parent)
        self._icons = icons

    def get_icon(self, index):
        #icon =  self._icons[ index.row()]
        icon =  self._icons[ index]
        return icon

    def paint(self, painter, option, index):
        progress = index.data(self.PROGRESS_USER_ROLE)
        icon = self.get_icon(progress)
        #the selection
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight());
        else:
            painter.fillRect(option.rect, option.palette.window());        
        icon.paint(painter, option.rect, QtCore.Qt.AlignmentFlag.AlignCenter)        

       
'''
Table View that provides drag & drop functions.Mime types can be filtered by setting a function in "setDragFilter"
    
'''            
class DragList(QtWidgets.QTableView):
    onDropURL= pyqtSignal(str)
    onRemove= pyqtSignal(object)
    
    def __init__(self, parent):
        QtWidgets.QTableView.__init__(self, parent)
        self.owner=parent        
        self.verticalHeader().hide()
        #pyqt5 self.setSelectionBehavior(self.SelectRows)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDragDropOverwriteMode(False)    
        self.resizeColumnsToContents()    
        self._createContextMenu()
        model=QtGui.QStandardItemModel()
        self.setModel(model)


    ''' Additional API '''
    def setHeaders(self,textList):
        self.model().setHorizontalHeaderLabels(textList)

    '''
    Resize mode for each column. One of QHeaderView::Interactive,Fixed,Strech,ResizeToContents
    '''        
    def setSectionResizeMode(self,index,resizeMode):
        self.horizontalHeader().setSectionResizeMode(index,resizeMode)   

    def addItems(self,itemList):
        for item in itemList:
            item.setEditable(False)
            item.setDragEnabled(True)
            item.setDropEnabled(False)#if true one could drop one listitem INTO another.  
        
        self.model().appendRow(itemList)
    
    #data of selected row
    def selectedRow(self):
        if self.selectionModel().hasSelection():
            modelIndex= self.selectionModel().currentIndex()
            return self.items(modelIndex.row())
        
        return None
        
            
#         rowList = self.selectionMode().selectedRows() #QItemSelectionModel-> QModelIndex[] list
#         if len(rowList)>0:
#             return rowList[0]

    #returns selected index of the first selected row (single selection)
    def selectedIndex(self):
        if self.selectionModel().hasSelection():
            return self.currentRowIndex()

    #current row index. May not be selected...
    def currentRowIndex(self):
        modelIndex = self.selectionModel().currentIndex()
        if modelIndex.isValid():
            return modelIndex.row()
        return -1
     
    def clear(self):
        self.model().removeRows(0,self.count())#keep the header, else clear()
        self.onRemove.emit(None)
    
    #standardItems of a given row -- TODO: should be a model with data...
    def items(self,index):
        #QStandardItemModel
        res=[]
        cnt=self.model().columnCount()
        for col in range(cnt):
            res.append(self.model().item(index,column=col))
        return res
    
    #returns value list of all items in a row
    def itemModel(self,index):
        res=[]
        cnt=self.model().columnCount()
        for indx in range(cnt):
            stdItem=self.model().item(index,indx)
            modelIndex=self.model().indexFromItem(stdItem)
            qList = self.model().itemData(modelIndex)
            if qList:
                voodoo = next(iter(qList.values()))
                res.append(voodoo)
        return res
        #... and more
    
    #returns a list of standarditems in given column (user must know how to retrieve that data)
    def allColumnItems(self,col):
        #need a QModelIndex...
        cnt=self.model().columnCount()
        res=[]
        if col < cnt:
            for rowIndex in range(self.count()):
                stdItem=self.model().item(rowIndex,col)
                res.append(stdItem)
        return res
        
    def dragEnterEvent(self, event):
        if event.source() == self:
            super(DragList,self).dragEnterEvent(event)
            return
        
        if self._checkMimeData(event.mimeData()):
            event.accept()
        else:
            event.ignore()
        

    '''        
    def dragMoveEvent(self, event):
        if event.source() == self:
            event.accept()
            return

        if event.mimeData().hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()
    '''

    def dropEvent(self, event):
        if event.source() == self:
            super(DragList,self).dropEvent(event)#!important!
            return
  
        if event.mimeData().hasUrls:
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            for url in event.mimeData().urls():
                urlString = str(url.toLocalFile())
                self.onDropURL.emit(urlString)
            event.accept()
        else:
            #TODO: This should be logged
            print("Drop: Invalid mime data")
            event.ignore()
    
    def count(self):
        return self.model().rowCount()
    
    
    def _createContextMenu(self):
        self.contextMenu = QtWidgets.QMenu("Context")
        self.contextMenu.addSeparator()
        #pyqt5 rmAction = QtWidgets.QAction(QtGui.QIcon('icons/del-x.png'), 'Remove', self)
        rmAction = QtGui.QAction(QtGui.QIcon('icons/del-x.png'), 'Remove', self)
        rmAction.triggered.connect(self._rmItem)
        self.contextMenu.addAction(rmAction)
        #pyqt5 rmAllAction = QtWidgets.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction = QtGui.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction.triggered.connect(self._rmAllItems)
        self.contextMenu.addAction(rmAllAction)
        self.contextMenu.addSeparator()
    
    def contextMenuEvent(self, event):
        #QContextMenuEvent
        item = self.rowAt(event.y())
        if item is None:
            return
        self.contextMenu.exec(event.globalPos())
    
    '''interface must be provided by the parent'''
    def _checkMimeData(self,mimeData):
        if self.function is None:
            #post a warning. Invalid implementation
            print("No filter-accept anything")
            return True
        return self.function(mimeData)

    '''
    API to set the "control function or filter" for the items to be dropped
    Function must accept "mimeData" and returns boolean
    ''' 
    def setDragFilter(self,function):
        self.function=function

    '''
    actions
    '''
    def _rmItem(self):
        curr = self.currentRowIndex()
        self.model().takeRow(curr)
        self.onRemove.emit(curr)
        
    def _rmAllItems(self):
        self.clear()
        self._checkMimeData(None) #clear

'''     checkbox 
        cb = QtGui.QStandardItem("Hugo")
        cb.setEditable(True)
        cb.setDragEnabled(True)
        cb.setDropEnabled(False)
        cb.setData(True,CheckBoxDelegate.CHECKBOX_USER_ROLE)
        self.listWidget.addItems([item,pb,cb])
        
        progress bar
        pb = QtGui.QStandardItem()
        pb.setEditable(False)
        pb.setDragEnabled(True)
        pb.setDropEnabled(False)
        pb.setData(cnt*5,ProgressDelegate.PROGRESS_USER_ROLE)
'''
#dont work right. And must implement for all items in the row!
# So this pattern is not really usable for dragndrop
class PathItemXX(QtGui.QStandardItem):
    ROLE = QtCore.Qt.ItemDataRole.UserRole+1
    def __init__(self,another=None):
        QtGui.QStandardItem.__init__(self,another)
        self.path = None
        self.displayName="?"

    #only answer your stuff, else it breaks         
    def data(self,userRole):
        if userRole == QtCore.Qt.ItemDataRole.DisplayRole:
            return self.displayName
        return None

    #only set your stuff, else it breaks
    def setData(self,value,role):
        if role==self.ROLE:
            #print("setData",str(value)," test:", self.displayName)
            self.path=value;
        else:
            return None
 
#     def setFlags(self,flags):
#         super(PathItem,self).setFlags(flags)
 
    #The data stuff, NOT the display. see data for representation
    def text(self):
        #print("text")
        return self.displayName
    
    #This is a sick construct. Clone will be called to the PROTOTYPE instance...
    #So her you generate a new item. But you dont have the data! 
    def clone(self):
        print("clone")
        test = self.model()
        
        copy = PathItemXX()
#        copy.path='%s'% self.path
#        copy.displayName='%s'% self.displayName
#        copy.setData(self.path,self.ROLE)
        return copy #empty useless copy...
     
    def type(self):
        return self.ROLE 

################## more customed widgets ##################
'''
Composite. Reach widgets "statusbar" and "buttonStop" and "progressbar"
'''
class ProgressStatusBar():
    def __init__(self,parent,stopIconPath,minWidth=100):
        self.parent=parent
        self._create(stopIconPath,minWidth)
    
    def _create(self,stopIconPath,minWidth):
        self.statusbar = QtWidgets.QStatusBar(self.parent)
        self.statusbar.setSizeGripEnabled(False)
        self.statusbar.addPermanentWidget(self.__createProgressBar(minWidth))
        self.buttonStop = QtWidgets.QToolButton(self.parent)
        #self.buttonStop.setIcon(QtGui.QIcon('./icons/window-close.png'))
        self.buttonStop.setIcon(QtGui.QIcon(stopIconPath))
        self.buttonStop.setIconSize(QtCore.QSize(20, 20))
        self.buttonStop.setVisible(False)
        self.buttonStop.setToolTip("Stop processing")
        self.statusbar.addPermanentWidget(self.buttonStop, 0)

    def __createProgressBar(self,minWidth):
        self.progressBar = QtWidgets.QProgressBar(self.parent)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximumWidth(minWidth)
        self.progressBar.setVisible(False) 
        self.progressBar.setValue(0)
        return self.progressBar


class StatusBarToggleIcons():
    def __init__(self,parent):    
        pass #TODO