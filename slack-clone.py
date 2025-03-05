import sys
import json
import winreg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QTextEdit, QLineEdit, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QSplitter, QSystemTrayIcon, QMenu, 
    QListWidgetItem, QDialog, QFormLayout, QDialogButtonBox, QInputDialog, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QFrame
)
from PySide6.QtGui import QIcon, QTextCursor, QMouseEvent, QAction, QFont, QColor
from PySide6.QtCore import Qt, QUrl, QObject, Signal, Slot, QThread, QMetaObject, Q_ARG, QTimer, QSize
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QAbstractSocket
from datetime import datetime

# Registry key for storing settings
REG_PATH = r"Software\SlackClone"
SERVER_URL = "ws://localhost:8081/ws"

def save_to_registry(key, value):
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(registry_key, key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(registry_key)
    except WindowsError:
        pass

def load_from_registry(key):
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        value, regtype = winreg.QueryValueEx(registry_key, key)
        winreg.CloseKey(registry_key)
        return value
    except WindowsError:
        return None

# 날짜 변환 유틸리티 함수 (클래스 외부에 추가)
def format_date_korean(date_str):
    """날짜 문자열을 한국어 형식으로 변환 (예: '2023-12-25' -> '2023년 12월 25일 월요일')"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        weekday = weekdays[date_obj.weekday()]
        return f"{date_obj.year}년 {date_obj.month}월 {date_obj.day}일 {weekday}"
    except:
        return date_str
    
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(300, 150)
        
        self.layout = QFormLayout(self)
        
        self.usernameEdit = QLineEdit(self)
        self.usernameEdit.setText(load_from_registry("username") or "")
        self.layout.addRow("사용자 이름:", self.usernameEdit)
        
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)
        
    def accept(self):
        username = self.usernameEdit.text().strip()
        if username:
            save_to_registry("username", username)
        super().accept()

class WebSocketWorker(QObject):
    newMessage = Signal(str)
    errorOccurred = Signal(str)
    connected = Signal()
    disconnected = Signal()

    def __init__(self, url: QUrl, parent=None):
        super().__init__(parent)
        self.url = url
        self.websocket = None

    @Slot()
    def start(self):
        from PySide6.QtWebSockets import QWebSocket
        self.websocket = QWebSocket()
        self.websocket.error.connect(self.onError)
        self.websocket.textMessageReceived.connect(self.onTextMessageReceived)
        self.websocket.connected.connect(self.onConnected)
        self.websocket.disconnected.connect(self.onDisconnected)
        self.websocket.open(self.url)

    @Slot()
    def stop(self):
        if self.websocket and self.websocket.state() == QAbstractSocket.ConnectedState:
            self.websocket.close()

    @Slot(str)
    def sendMessage(self, msg: str):
        if self.websocket and self.websocket.state() == QAbstractSocket.ConnectedState:
            self.websocket.sendTextMessage(msg)
        else:
            self.errorOccurred.emit("WebSocket이 연결되지 않았습니다.")

    @Slot()
    def onConnected(self):
        print("[WebSocketWorker] Connected to", self.url.toString())
        self.connected.emit()

    @Slot()
    def onDisconnected(self):
        print("[WebSocketWorker] Disconnected from", self.url.toString())
        self.disconnected.emit()

    @Slot(str)
    def onTextMessageReceived(self, message: str):
        print("[WebSocketWorker] Message received:", message)
        self.newMessage.emit(message)

    @Slot()
    def onError(self):
        err_msg = self.websocket.errorString() if self.websocket else "알 수 없는 오류"
        print("[WebSocketWorker] WebSocket Error:", err_msg)
        self.errorOccurred.emit(err_msg)

class ChannelItem(QWidget):
    clicked = Signal(str)
    
    def __init__(self, channel_name, is_selected=False, parent=None):
        super().__init__(parent)
        self.channel_name = channel_name
        self.is_selected = is_selected
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        icon_label = QLabel("#")
        icon_label.setStyleSheet("color: #616061; font-weight: bold;")
        
        self.name_label = QLabel(channel_name)
        self.name_label.setStyleSheet("color: #1D1C1D;")
        
        layout.addWidget(icon_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        
        self.setStyleSheet("""
            ChannelItem {
                border-radius: 4px;
                padding: 2px;
            }
            ChannelItem:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        self.update_selection(is_selected)
        
    def update_selection(self, is_selected):
        self.is_selected = is_selected
        if is_selected:
            self.setStyleSheet("""
                background-color: #1164A3;
                border-radius: 4px;
                padding: 2px;
            """)
            self.name_label.setStyleSheet("color: white; font-weight: bold;")
        else:
            self.setStyleSheet("""
                border-radius: 4px;
                padding: 2px;
            """)
            self.name_label.setStyleSheet("color: #1D1C1D;")
            
    def mousePressEvent(self, event):
        self.clicked.emit(self.channel_name)
        super().mousePressEvent(event)

# 워크스페이스 관리 클래스 추가
class WorkspaceDialog(QDialog):
    def __init__(self, parent=None, workspaces=None):
        super().__init__(parent)
        self.setWindowTitle("워크스페이스 관리")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # 현재 워크스페이스 목록
        self.workspaceList = QListWidget(self)
        if workspaces:
            for ws in workspaces:
                self.workspaceList.addItem(ws)
        
        # 새 워크스페이스 추가 영역
        inputLayout = QHBoxLayout()
        self.wsNameEdit = QLineEdit()
        self.wsNameEdit.setPlaceholderText("새 워크스페이스 이름")
        addButton = QPushButton("추가")
        addButton.clicked.connect(self.addWorkspace)
        
        inputLayout.addWidget(self.wsNameEdit)
        inputLayout.addWidget(addButton)
        
        # 버튼
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        layout.addWidget(QLabel("워크스페이스 목록:"))
        layout.addWidget(self.workspaceList)
        layout.addLayout(inputLayout)
        layout.addWidget(buttonBox)
    
    def addWorkspace(self):
        name = self.wsNameEdit.text().strip()
        if name:
            self.workspaceList.addItem(name)
            self.wsNameEdit.clear()
    
    def getWorkspaces(self):
        workspaces = []
        for i in range(self.workspaceList.count()):
            workspaces.append(self.workspaceList.item(i).text())
        return workspaces
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slack 클론")
        self.resize(1280, 800)
        
        # 스타일 시트 설정
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
                color: #1D1C1D;
            }
            QSplitter::handle {
                background-color: #E8E8E8;
                width: 1px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QLabel {
                color: #1D1C1D;
                font-size: 14px;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #1D1C1D;
                border: 1px solid #BBBABB;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #1264A3;
            }
            QPushButton {
                background-color: #007a5a;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #148567;
            }
            QTextEdit {
                background-color: #FFFFFF;
                color: #1D1C1D;
                border: none;
                font-size: 14px;
            }
            #leftSidebar {
                background-color: #3F0E40;
                min-width: 220px;
                max-width: 260px;
            }
            #workspaceHeader {
                background-color: #3F0E40;
                color: white;
                font-weight: bold;
                font-size: 18px;
                padding: 10px;
                border-bottom: 1px solid #522653;
            }
            #channelList {
                background-color: #3F0E40;
            }
            #searchBox {
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: white;
                padding: 5px 8px;
                margin: 8px;
            }
            #sectionLabel {
                color: #BCABBC;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 10px;
            }
            #channelHeader {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E8E8E8;
                padding: 10px;
            }
            #channelTitle {
                font-weight: bold;
                font-size: 16px;
            }
            #messageInput {
                border: 1px solid #BBBABB;
                border-radius: 4px;
                margin: 10px;
                padding: 8px;
            }
            #messageArea {
                border: none;
                padding: 10px;
            }
            #workspaceButton {
                background-color: white;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 18px;
                width: 60px;
                height: 60px;
                border-radius: 4px;
                text-align: center;
                margin: 5px;
            }
            #sidebarItem {
                padding: 5px 10px;
                border-radius: 4px;
                margin: 2px 8px;
                color: #CFC3CF;
                font-size: 15px;
            }
            #sidebarItem:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            #bodyContainer {
                background-color: white;
            }
        """)

        # 메인 위젯 설정
        self.mainWidget = QWidget()
        self.mainLayout = QHBoxLayout(self.mainWidget)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.setCentralWidget(self.mainWidget)

        # 워크스페이스 선택기 (좌측 세로 사이드바)
        self.workspaceSidebar = QWidget()
        self.workspaceSidebar.setObjectName("workspaceSidebar")
        self.workspaceSidebar.setFixedWidth(65)
        self.workspaceSidebar.setStyleSheet("background-color: #3F0E40;")
        
        wsLayout = QVBoxLayout(self.workspaceSidebar)
        wsLayout.setContentsMargins(5, 5, 5, 5)
        wsLayout.setAlignment(Qt.AlignTop)
        
        # 워크스페이스 버튼 (실험실)
        self.workspaceBtn = QPushButton("실")
        self.workspaceBtn.setObjectName("workspaceButton")
        self.workspaceBtn.setFixedSize(60, 60)
        wsLayout.addWidget(self.workspaceBtn, 0, Qt.AlignHCenter)
        
        # 메뉴 아이콘들 (홈, DM, 내 활동, 더 보기)
        menuIcons = [
            {"text": "홈", "icon": "🏠", "action": self.navigateToHome},
            {"text": "DM", "icon": "✉️", "action": self.navigateToDM},
            {"text": "내 활동", "icon": "🔍", "action": self.navigateToActivity},
            {"text": "더 보기", "icon": "...", "action": self.showMoreMenu}
        ]

        for item in menuIcons:
            btn = QPushButton(item["icon"])
            btn.setToolTip(item["text"])
            btn.setObjectName("sidebarItem")
            btn.setFixedSize(60, 60)
            if "action" in item and item["action"]:
                btn.clicked.connect(item["action"])
            wsLayout.addWidget(btn, 0, Qt.AlignHCenter)
        
        wsLayout.addStretch()
        
        # 사용자 프로필 아이콘
        self.profileBtn = QPushButton("👤")
        self.profileBtn.setObjectName("sidebarItem")
        self.profileBtn.setFixedSize(60, 60)
        self.profileBtn.clicked.connect(self.openSettingsDialog)
        wsLayout.addWidget(self.profileBtn, 0, Qt.AlignHCenter)
        
        # 좌측 채널 사이드바
        self.leftSidebar = QWidget()
        self.leftSidebar.setObjectName("leftSidebar")
        
        leftLayout = QVBoxLayout(self.leftSidebar)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        leftLayout.setSpacing(0)
        
        # 워크스페이스 헤더
        self.wsHeader = QWidget()
        self.wsHeader.setObjectName("workspaceHeader")
        wsHeaderLayout = QHBoxLayout(self.wsHeader)
        wsHeaderLayout.setContentsMargins(10, 10, 10, 10)
        
        wsTitle = QLabel("실험실")
        wsTitle.setStyleSheet("color: white; font-weight: bold;")
        wsHeaderLayout.addWidget(wsTitle)
        
        newButton = QPushButton("▼")
        newButton.setStyleSheet("background: transparent; color: white; font-weight: bold;")
        newButton.setFixedSize(40, 40)
        wsHeaderLayout.addWidget(newButton)
        
        leftLayout.addWidget(self.wsHeader)
        
        # 검색창
        self.searchBox = QLineEdit()
        self.searchBox.setObjectName("searchBox")
        self.searchBox.setPlaceholderText("실험실 검색")
        leftLayout.addWidget(self.searchBox)
        
        # 섹션 & 채널 목록
        channelContainer = QWidget()
        channelContainerLayout = QVBoxLayout(channelContainer)
        channelContainerLayout.setContentsMargins(0, 10, 0, 0)
        channelContainerLayout.setSpacing(0)
        
        # 홈 섹션
        homeLabel = QLabel("홈")
        homeLabel.setObjectName("sidebarItem")
        channelContainerLayout.addWidget(homeLabel)
        
        # 채널 섹션
        channelLabel = QLabel("채널")
        channelLabel.setObjectName("sectionLabel")
        channelContainerLayout.addWidget(channelLabel)
        
        # 채널 목록
        self.channelListWidget = QWidget()
        self.channelListWidget.setObjectName("channelList")
        self.channelListLayout = QVBoxLayout(self.channelListWidget)
        self.channelListLayout.setContentsMargins(0, 0, 0, 0)
        self.channelListLayout.setAlignment(Qt.AlignTop)
        self.channelListLayout.setSpacing(0)
        
        # 채널 항목 추가
        self.channels = ["전체", "소셜"]
        self.channel_items = {}
        
        for channel in self.channels:
            channel_item = ChannelItem(channel, channel == "전체")
            channel_item.clicked.connect(self.onChannelSelected)
            self.channel_items[channel] = channel_item
            self.channelListLayout.addWidget(channel_item)
        
        # 채널 추가 버튼
        addChannelBtn = QPushButton("+ 채널 추가")
        addChannelBtn.setObjectName("sidebarItem")
        addChannelBtn.setStyleSheet("background: transparent; color: #CFC3CF; text-align: left; padding-left: 25px;")
        addChannelBtn.clicked.connect(self.addChannel)
        self.channelListLayout.addWidget(addChannelBtn)
        
        # 스크롤 영역에 채널 목록 추가
        channelScroll = QScrollArea()
        channelScroll.setWidgetResizable(True)
        channelScroll.setWidget(self.channelListWidget)
        channelScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        channelScroll.setStyleSheet("background-color: #3F0E40; border: none;")
        
        channelContainerLayout.addWidget(channelScroll)
        leftLayout.addWidget(channelContainer)
        
        # 메인 컨텐츠 영역
        self.bodyContainer = QWidget()
        self.bodyContainer.setObjectName("bodyContainer")
        bodyLayout = QVBoxLayout(self.bodyContainer)
        bodyLayout.setContentsMargins(0, 0, 0, 0)
        bodyLayout.setSpacing(0)
        
        # 채널 헤더
        self.channelHeader = QWidget()
        self.channelHeader.setObjectName("channelHeader")
        chHeaderLayout = QHBoxLayout(self.channelHeader)
        
        self.channelTitle = QLabel("# 전체")
        self.channelTitle.setObjectName("channelTitle")
        chHeaderLayout.addWidget(self.channelTitle)
        
        # 헤더 검색창
        self.headerSearch = QLineEdit()
        self.headerSearch.setPlaceholderText("실험실 검색")
        self.headerSearch.setFixedWidth(250)
        chHeaderLayout.addWidget(self.headerSearch)
        
        # 헤더 아이콘들
        headerIcons = QWidget()
        headerIconsLayout = QHBoxLayout(headerIcons)
        headerIconsLayout.setContentsMargins(0, 0, 0, 0)
        
        for icon in ["🔔", "👥", "ⓘ"]:
            btn = QPushButton(icon)
            btn.setStyleSheet("background: transparent;")
            btn.setFixedSize(40, 40)
            headerIconsLayout.addWidget(btn)
        
        chHeaderLayout.addWidget(headerIcons)
        bodyLayout.addWidget(self.channelHeader)
        
        # 메시지 영역
        self.messageArea = QTextEdit()
        self.messageArea.setObjectName("messageArea")
        self.messageArea.setReadOnly(True)
        bodyLayout.addWidget(self.messageArea)
        
        # 메시지 입력 영역
        self.messageInputContainer = QWidget()
        inputLayout = QVBoxLayout(self.messageInputContainer)
        inputLayout.setContentsMargins(10, 10, 10, 10)
        
        self.messageInput = QTextEdit()
        self.messageInput.setObjectName("messageInput")
        self.messageInput.setPlaceholderText("#전체에 메시지 보내기")
        self.messageInput.setFixedHeight(80)
        
        # 메시지 도구 모음
        messageToolbar = QWidget()
        toolbarLayout = QHBoxLayout(messageToolbar)
        toolbarLayout.setContentsMargins(0, 5, 0, 0)
        
        # 포맷팅 버튼들
        for icon in ["B", "I", "S", "🔗", "•", "1."]:
            btn = QPushButton(icon)
            btn.setStyleSheet("background: transparent; color: #616061;")
            btn.setFixedSize(40, 40)
            toolbarLayout.addWidget(btn)
        
        toolbarLayout.addStretch()
        
        # 전송 버튼
        sendBtn = QPushButton("전송")
        sendBtn.clicked.connect(self.onSendClicked)
        toolbarLayout.addWidget(sendBtn)
        
        inputLayout.addWidget(self.messageInput)
        inputLayout.addWidget(messageToolbar)
        bodyLayout.addWidget(self.messageInputContainer)
        
        # 레이아웃 배치
        self.mainLayout.addWidget(self.workspaceSidebar)
        self.mainLayout.addWidget(self.leftSidebar)
        self.mainLayout.addWidget(self.bodyContainer, 1)  # 1은 stretch 비율
        
        # 네트워크 관리자
        self.networkManager = QNetworkAccessManager(self)
        self.networkManager.finished.connect(self.onRestReplyFinished)
        
        # WebSocket Worker (별도 스레드)
        self.wsThread = QThread()
        self.wsWorker = WebSocketWorker(QUrl(SERVER_URL))
        self.wsWorker.moveToThread(self.wsThread)
        self.wsThread.started.connect(self.wsWorker.start)
        self.wsThread.finished.connect(self.wsWorker.stop)
        self.wsWorker.newMessage.connect(self.onWebSocketMessage)
        self.wsWorker.errorOccurred.connect(self.onWebSocketError)
        self.wsWorker.connected.connect(self.onWebSocketConnected)
        self.wsWorker.disconnected.connect(self.onWebSocketDisconnected)
        self.wsThread.start()
        
        self.reconnectTimer = QTimer(self)
        self.reconnectTimer.setInterval(5000)  # 5초 간격으로 재연결 시도
        self.reconnectTimer.timeout.connect(self.wsWorker.start)
        
        # 시스템 트레이 설정
        self.createTrayIcon()
        
        # 현재 채널 설정
        self.current_channel = "전체체"
        
        # Add at the end of __init__
        self.initWorkspaces()

    def createTrayIcon(self):
        self.trayIcon = QSystemTrayIcon(QIcon(":/images/logo.png"), self)
        self.trayIcon.activated.connect(self.onTrayIconActivated)

        trayMenu = QMenu()
        quitAction = QAction("종료", self)
        quitAction.triggered.connect(QApplication.instance().quit)
        trayMenu.addAction(quitAction)
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.show()

    def showTrayMessage(self, title: str, message: str):
        if self.trayIcon.isVisible():
            self.trayIcon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def onTrayIconActivated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        self.trayIcon.hide()
        self.wsThread.quit()
        self.wsThread.wait()
        event.accept()

    def openSettingsDialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def onChannelSelected(self, channel_name):
        # 이전 선택 해제
        if self.current_channel in self.channel_items:
            self.channel_items[self.current_channel].update_selection(False)
        
        # 새 채널 선택
        if channel_name in self.channel_items:
            self.channel_items[channel_name].update_selection(True)
            self.current_channel = channel_name
            self.channelTitle.setText(f"# {channel_name}")
            self.messageInput.setPlaceholderText(f"#{channel_name}에 메시지 보내기")
            
            # 채널 데이터 요청
            self.requestChannelData(channel_name)

    def requestWorkspaceList(self):
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "get_workspace_list",
            "message": ""
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )
        
    def requestChannelList(self):
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "get_channel_list",
            "workspace": self.current_workspace,
            "message": ""
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )
        
    def requestChannelData(self, channel_name):
        self.messageArea.clear()
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "get_channel_data", 
            "workspace": self.current_workspace,
            "channel": channel_name, 
            "message": ""
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

    @Slot()
    def onSendClicked(self):
        text = self.messageInput.toPlainText().strip()
        if not text:
            return

        channel = self.current_channel
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"), 
            "time": current_time.strftime("%I:%M:%S"), 
            "sender": username,
            "action": "send_message", 
            "channel": channel, 
            "message": text
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

        self.messageArea.append(self.formatMessage(username, current_time.strftime('%p %I:%M'), text))
        self.messageInput.clear()

    def formatMessage(self, sender, time, message):
        return f"""
        <div style="margin-bottom: 12px;">
            <div style="font-weight: bold;">{sender} <span style="font-weight: normal; color: #616061; font-size: 12px;">{time}</span></div>
            <div>{message}</div>
        </div>
        """

    @Slot(QNetworkReply)
    def onRestReplyFinished(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NoError:
            response = reply.readAll().data().decode('utf-8')
            print("[REST] Response:", response)
        else:
            err = reply.errorString()
            print("[REST] Error:", err)
            self.showTrayMessage("REST Error", err)
        reply.deleteLater()

    @Slot(str)
    def onWebSocketMessage(self, msg: str):
        try:
            data = json.loads(msg)
            action = data.get("action")
            if data.get("action") == "channel_data":
                self.messageArea.clear()
                messages = data.get("message", [])
                
                # 메시지를 날짜별로 그룹화
                message_groups = {}
                for message in messages:
                    date = message.get("date", "Unknown")
                    if date not in message_groups:
                        message_groups[date] = []
                    message_groups[date].append(message)
                
                # 정렬된 날짜 목록
                sorted_dates = sorted(message_groups.keys())
                
                # 날짜별로 메시지 표시
                for date in sorted_dates:
                    # 날짜 구분선 추가
                    self.messageArea.append(self.formatDateSeparator(date))
                    
                    # 해당 날짜의 메시지들 추가
                    for message in message_groups[date]:
                        sender = message.get("sender", "Unknown")
                        time = message.get("time", "")
                        text = message.get("message", "")
                        self.messageArea.append(self.formatMessage(sender, time, text))
            elif action == "workspace_list":
                self.workspaces = []
                self.channels = []
                self.messageArea.clear()
                for action in self.wsMenu.actions():
                    self.wsMenu.removeAction(action)
                
                workspace_list = data.get("message", {})
                for workspace in workspace_list.keys():
                    self.workspaces.append(workspace)
                for channel in workspace_list[self.workspaces[0]]:
                    self.channels.append(channel)
                    
                self.updateWorkspaces(self.workspaces[0])
                print("Received workspace list:", self.workspaces)
                # Handle workspace list update logic here
            elif action == "channel_list":
                self.messageArea.clear()
                self.channels = data.get("message", [])
                print("Received channel list:", self.channels)
                # Handle channel list update logic here
            else:
                current_time = datetime.now().strftime("%p %I:%M")
                self.messageArea.append(self.formatMessage("Server", current_time, msg))
                self.showTrayMessage("새 메시지 도착", msg)
        except json.JSONDecodeError:
            print("[WebSocketWorker] Failed to decode message:", msg)

    @Slot(str)
    def onWebSocketError(self, err: str):
        print("[WebSocket Error]:", err)
        self.showTrayMessage("WebSocket Error", err)

    @Slot()
    def onWebSocketConnected(self):
        self.requestWorkspaceList()
        self.reconnectTimer.stop()

    @Slot()
    def onWebSocketDisconnected(self):
        self.reconnectTimer.start()
        QMetaObject.invokeMethod(self.wsWorker, "start", Qt.QueuedConnection)

    def addChannel(self):
        channel_name, ok = QInputDialog.getText(self, "채널 추가", "채널 이름을 입력하세요:")
        if ok and channel_name:
            if channel_name not in self.channel_items:
                self.channels.append(channel_name)
                channel_item = ChannelItem(channel_name)
                channel_item.clicked.connect(self.onChannelSelected)
                self.channel_items[channel_name] = channel_item
                
                # 새 채널 항목을 추가 버튼 앞에 추가
                self.channelListLayout.insertWidget(len(self.channels) - 1, channel_item)
                
                # 새 채널로 바로 전환
                self.onChannelSelected(channel_name)

    # MainWindow 클래스에 워크스페이스 관련 메소드 추가 (아래 코드는 MainWindow 클래스 내에 추가)
    def initWorkspaces(self):
        # 레지스트리에서 워크스페이스 목록 로드
        saved_workspaces = load_from_registry("workspaces")
        if saved_workspaces:
            try:
                self.workspaces = json.loads(saved_workspaces)
            except:
                self.workspaces = ["실험실"]  # 기본값
        else:
            self.workspaces = ["실험실"]  # 기본값
        
        self.current_workspace = self.workspaces[0]
        
        # 워크스페이스 버튼 업데이트
        self.updateWorkspaceButton()
        
        # 워크스페이스 메뉴 설정
        self.setupWorkspaceMenu()
        
        # 채널 목록 업데이트 요청
        self.workspaceBtn.clicked.connect(self.showWorkspaceMenu)
        
    def updateWorkspaces(self, workspace_name):
        self.current_workspace = workspace_name
        
        # 워크스페이스 버튼 업데이트
        self.updateWorkspaceButton()
        
        # 워크스페이스 메뉴 설정
        self.setupWorkspaceMenu()

    def updateWorkspaceButton(self):
        # 현재 워크스페이스의 첫 글자를 버튼에 표시
        if self.current_workspace:
            self.workspaceBtn.setText(self.current_workspace[0])
            self.wsHeader.findChild(QLabel).setText(self.current_workspace)

    def setupWorkspaceMenu(self):            
        self.wsMenu = QMenu(self)
        
        for ws in self.workspaces:
            action = QAction(ws, self)
            action.triggered.connect(lambda checked, w=ws: self.switchWorkspace(w))
            self.wsMenu.addAction(action)
        
        self.wsMenu.addSeparator()
        
        manageAction = QAction("워크스페이스 관리", self)
        manageAction.triggered.connect(self.manageWorkspaces)
        self.wsMenu.addAction(manageAction)

    def showWorkspaceMenu(self):
        self.wsMenu.exec(self.workspaceBtn.mapToGlobal(self.workspaceBtn.rect().bottomLeft()))

    def switchWorkspace(self, workspace_name):
        if workspace_name != self.current_workspace:
            self.current_workspace = workspace_name
            self.updateWorkspaceButton()
            # 채널 목록 업데이트 요청
            self.requestWorkspaceData(workspace_name)

    def requestWorkspaceData(self, workspace_name):
        # 워크스페이스에 해당하는 채널 목록 요청 (실제 서버와 통신할 경우 구현)
        # 이 예제에서는 임시로 몇 개의 채널을 생성
        self.clearChannelList()
        
        # 워크스페이스별 기본 채널 설정
        if workspace_name == "실험실":
            self.channels = ["전체", "소셜"]
        else:
            self.channels = [f"{workspace_name}-전체", f"{workspace_name}-소셜"]
        
        # 채널 항목 추가
        for channel in self.channels:
            channel_item = ChannelItem(channel, channel == self.channels[0])
            channel_item.clicked.connect(self.onChannelSelected)
            self.channel_items[channel] = channel_item
            self.channelListLayout.addWidget(channel_item)
        
        # 첫 번째 채널 선택
        if self.channels:
            self.current_channel = self.channels[0]
            self.channelTitle.setText(f"# {self.current_channel}")
            self.messageInput.setPlaceholderText(f"#{self.current_channel}에 메시지 보내기")
            self.requestChannelData(self.current_channel)

    def clearChannelList(self):
        # 기존 채널 항목 모두 제거
        self.current_channel = ""
        for item in self.channel_items.values():
            self.channelListLayout.removeWidget(item)
            item.deleteLater()
        self.channel_items.clear()
        self.channels.clear()

    def manageWorkspaces(self):
        dialog = WorkspaceDialog(self, self.workspaces)
        if dialog.exec() == QDialog.Accepted:
            self.workspaces = dialog.getWorkspaces()
            # 워크스페이스 목록 저장
            save_to_registry("workspaces", json.dumps(self.workspaces))
            # 워크스페이스 메뉴 업데이트
            self.setupWorkspaceMenu()
            
            # 현재 워크스페이스가 목록에 없으면 첫 번째 워크스페이스로 전환
            if self.current_workspace not in self.workspaces and self.workspaces:
                self.switchWorkspace(self.workspaces[0])
          
    # MainWindow 클래스에 새로운 네비게이션 메소드 추가
    def navigateToHome(self):
        # 홈 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>홈</h2>
            <p>최근 활동 및 알림을 표시하는 화면입니다.</p>
        </div>
        """)
        self.messageInput.setPlaceholderText("메시지를 입력하세요")
        self.channelTitle.setText("🏠 홈")

    def navigateToDM(self):
        # DM 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>다이렉트 메시지</h2>
            <p>사용자와의 개인 메시지를 주고받는 화면입니다.</p>
        </div>
        """)
        self.messageInput.setPlaceholderText("DM을 입력하세요")
        self.channelTitle.setText("✉️ 다이렉트 메시지")

    def navigateToActivity(self):
        # 내 활동 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>내 활동</h2>
            <p>나의 최근 활동 내역을 확인하는 화면입니다.</p>
        </div>
        """)
        self.messageInput.setPlaceholderText("검색어를 입력하세요")
        self.channelTitle.setText("🔍 내 활동")

    def showMoreMenu(self):
        # 더 보기 메뉴 표시
        moreMenu = QMenu(self)
        
        # 메뉴 항목 추가
        actions = [
            {"text": "스레드", "icon": "🧵", "action": self.showThreads},
            {"text": "파일", "icon": "📁", "action": self.showFiles},
            {"text": "앱", "icon": "🧩", "action": self.showApps},
            {"text": "설정", "icon": "⚙️", "action": self.openSettingsDialog}
        ]
        
        for action in actions:
            act = QAction(f"{action['icon']} {action['text']}", self)
            if "action" in action and action["action"]:
                act.triggered.connect(action["action"])
            moreMenu.addAction(act)
        
        # 버튼 위치에 메뉴 표시
        senderBtn = self.sender()
        if senderBtn:
            moreMenu.exec(senderBtn.mapToGlobal(senderBtn.rect().bottomLeft()))

    def showThreads(self):
        # 스레드 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>스레드</h2>
            <p>스레드된 메시지를 모아서 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("🧵 스레드")

    def showFiles(self):
        # 파일 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>파일</h2>
            <p>공유된 파일을 모아서 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("📁 파일")

    def showApps(self):
        # 앱 화면으로 이동하는 로직
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>앱</h2>
            <p>설치된 앱 목록을 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("🧩 앱")

    # 날짜 구분선 포맷 메소드 추가 (MainWindow 클래스 내)
    def formatDateSeparator(self, date_str):
        formatted_date = format_date_korean(date_str)
        return f"""
        <div style="display: flex; align-items: center; margin: 20px 0; color: #616061;">
            <hr style="flex-grow: 1; border: none; border-top: 1px solid #E8E8E8; margin-right: 10px;">
            <div style="font-size: 14px; font-weight: bold;">{formatted_date}</div>
            <hr style="flex-grow: 1; border: none; border-top: 1px solid #E8E8E8; margin-left: 10px;">
        </div>
        """

    # onSendClicked 메소드 수정 (MainWindow 클래스 내)
    @Slot()
    def onSendClicked(self):
        text = self.messageInput.toPlainText().strip()
        if not text:
            return

        channel = self.current_channel
        current_time = datetime.now()
        current_date = current_time.strftime("%Y-%m-%d")
        username = load_from_registry("username") or "사용자"
        
        # WebSocket 메시지 전송
        request_message = json.dumps({
            "date": current_date, 
            "time": current_time.strftime("%I:%M:%S"), 
            "sender": username,
            "action": "send_message", 
            "channel": channel, 
            "message": text
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

        # 현재 메시지 영역에 마지막 날짜 구분선이 없는 경우 추가
        last_date_in_view = self.getLastDateInMessageArea()
        if last_date_in_view != current_date:
            self.messageArea.append(self.formatDateSeparator(current_date))
        
        # 메시지 추가
        formatted_time = current_time.strftime('%p %I:%M')
        self.messageArea.append(self.formatMessage(username, formatted_time, text))
        self.messageInput.clear()

    # 메시지 영역에서 마지막 날짜 구분선 확인 메소드 추가 (MainWindow 클래스 내)
    def getLastDateInMessageArea(self):
        """메시지 영역에 표시된 마지막 날짜 구분선의 날짜를 반환"""
        html = self.messageArea.toHtml()
        
        # 간단한 구현: 현재 날짜 반환 (실제로는 HTML 파싱 필요)
        # 실제 구현에서는 정규식이나 HTML 파서를 사용하여 
        # 마지막으로 표시된 날짜 구분선을 찾아야 함
        return datetime.now().strftime("%Y-%m-%d")  
      
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())