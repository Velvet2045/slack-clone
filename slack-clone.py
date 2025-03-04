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
                color: #3F0E40;
                font-weight: bold;
                font-size: 18px;
                width: 36px;
                height: 36px;
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
        
        # 워크스페이스 버튼 (다락방)
        self.workspaceBtn = QPushButton("다")
        self.workspaceBtn.setObjectName("workspaceButton")
        self.workspaceBtn.setFixedSize(36, 36)
        wsLayout.addWidget(self.workspaceBtn, 0, Qt.AlignHCenter)
        
        # 메뉴 아이콘들 (홈, DM, ...)
        menuIcons = [
            {"text": "홈", "icon": "🏠"},
            {"text": "DM", "icon": "✉️"},
            {"text": "내 활동", "icon": "🔍"}
        ]
        
        for item in menuIcons:
            btn = QPushButton(item["icon"])
            btn.setToolTip(item["text"])
            btn.setObjectName("sidebarItem")
            btn.setFixedSize(36, 36)
            wsLayout.addWidget(btn, 0, Qt.AlignHCenter)
        
        wsLayout.addStretch()
        
        # 사용자 프로필 아이콘
        self.profileBtn = QPushButton("👤")
        self.profileBtn.setObjectName("sidebarItem")
        self.profileBtn.setFixedSize(36, 36)
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
        
        wsTitle = QLabel("다락방")
        wsTitle.setStyleSheet("color: white; font-weight: bold;")
        wsHeaderLayout.addWidget(wsTitle)
        
        newButton = QPushButton("▼")
        newButton.setStyleSheet("background: transparent; color: white; font-weight: bold;")
        newButton.setFixedSize(24, 24)
        wsHeaderLayout.addWidget(newButton)
        
        leftLayout.addWidget(self.wsHeader)
        
        # 검색창
        self.searchBox = QLineEdit()
        self.searchBox.setObjectName("searchBox")
        self.searchBox.setPlaceholderText("다락방 검색")
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
        self.channels = ["슬랙-클론", "개발", "일반"]
        self.channel_items = {}
        
        for channel in self.channels:
            channel_item = ChannelItem(channel, channel == "슬랙-클론")
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
        
        self.channelTitle = QLabel("# 슬랙-클론")
        self.channelTitle.setObjectName("channelTitle")
        chHeaderLayout.addWidget(self.channelTitle)
        
        # 헤더 검색창
        self.headerSearch = QLineEdit()
        self.headerSearch.setPlaceholderText("다락방 검색")
        self.headerSearch.setFixedWidth(250)
        chHeaderLayout.addWidget(self.headerSearch)
        
        # 헤더 아이콘들
        headerIcons = QWidget()
        headerIconsLayout = QHBoxLayout(headerIcons)
        headerIconsLayout.setContentsMargins(0, 0, 0, 0)
        
        for icon in ["🔔", "👥", "ⓘ"]:
            btn = QPushButton(icon)
            btn.setStyleSheet("background: transparent;")
            btn.setFixedSize(32, 32)
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
        self.messageInput.setPlaceholderText("#슬랙-클론에 메시지 보내기")
        self.messageInput.setFixedHeight(80)
        
        # 메시지 도구 모음
        messageToolbar = QWidget()
        toolbarLayout = QHBoxLayout(messageToolbar)
        toolbarLayout.setContentsMargins(0, 5, 0, 0)
        
        # 포맷팅 버튼들
        for icon in ["B", "I", "S", "🔗", "•", "1."]:
            btn = QPushButton(icon)
            btn.setStyleSheet("background: transparent; color: #616061;")
            btn.setFixedSize(28, 28)
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
        self.wsWorker = WebSocketWorker(QUrl("ws://localhost:8081/ws"))
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
        self.current_channel = "슬랙-클론"

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
        dialog.exec_()

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

    def requestChannelData(self, channel_name):
        self.messageArea.clear()
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "get_channel_data", 
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
            if data.get("action") == "channel_data":
                self.messageArea.clear()
                messages = data.get("message", [])
                for message in messages:
                    sender = message.get("sender", "Unknown")
                    time = message.get("time", "")
                    text = message.get("message", "")
                    self.messageArea.append(self.formatMessage(sender, time, text))
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
        self.requestChannelData(self.current_channel)
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())