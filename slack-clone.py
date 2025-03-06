import sys
import json
import winreg
from datetime import datetime
import traceback

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QTextEdit, QLineEdit, QPushButton,
    QLabel, QVBoxLayout, QHBoxLayout, QSplitter, QSystemTrayIcon, QMenu, 
    QListWidgetItem, QDialog, QFormLayout, QDialogButtonBox, QInputDialog, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QFrame, QTabWidget, QDateEdit, QCheckBox, QComboBox, QGroupBox, QCompleter
)
from PySide6.QtGui import QIcon, QTextCursor, QMouseEvent, QAction, QFont, QColor, QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QUrl, QObject, Signal, Slot, QThread, QMetaObject, Q_ARG, QTimer, QSize, QDate
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QAbstractSocket
from PySide6.QtWebSockets import QWebSocket

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

# 날짜 변환 유틸리티 함수
def format_date_korean(date_str):
    """날짜 문자열을 한국어 형식으로 변환 (예: '2023-12-25' -> '2023년 12월 25일 월요일')"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        weekday = weekdays[date_obj.weekday()]
        return f"{date_obj.year}년 {date_obj.month}월 {date_obj.day}일 {weekday}"
    except:
        return date_str

class SearchDialog(QDialog):
    def __init__(self, parent=None, workspaces=None, channels=None, current_workspace=None, current_channel=None):
        super().__init__(parent)
        self.setWindowTitle("메시지 검색")
        self.setMinimumSize(600, 400)
        self.workspaces = workspaces or []
        self.channels = channels or []
        self.current_workspace = current_workspace
        self.current_channel = current_channel
        
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # 검색 입력 영역
        formLayout = QFormLayout()
        
        # 검색어 입력
        self.queryInput = QLineEdit()
        self.queryInput.setPlaceholderText("검색어를 입력하세요")
        formLayout.addRow("검색어:", self.queryInput)
        
        # 워크스페이스 선택
        self.workspaceCombo = QComboBox()
        self.workspaceCombo.addItem("모든 워크스페이스")
        if self.workspaces:
            for workspace in self.workspaces:
                self.workspaceCombo.addItem(workspace)
        if self.current_workspace:
            index = self.workspaceCombo.findText(self.current_workspace)
            if index >= 0:
                self.workspaceCombo.setCurrentIndex(index)
        formLayout.addRow("워크스페이스:", self.workspaceCombo)
        
        # 채널 선택
        self.channelCombo = QComboBox()
        self.channelCombo.addItem("모든 채널")
        if self.channels:
            for channel in self.channels:
                self.channelCombo.addItem(channel)
        if self.current_channel:
            index = self.channelCombo.findText(self.current_channel)
            if index >= 0:
                self.channelCombo.setCurrentIndex(index)
        formLayout.addRow("채널:", self.channelCombo)
        
        # 보낸 사람 입력
        self.senderInput = QLineEdit()
        self.senderInput.setPlaceholderText("보낸 사람 이름 (선택 사항)")
        formLayout.addRow("보낸 사람:", self.senderInput)
        
        # 날짜 범위
        dateLayout = QHBoxLayout()
        self.fromDate = QDateEdit()
        self.fromDate.setDate(QDate.currentDate().addDays(-30))  # 기본 30일 전
        self.fromDate.setCalendarPopup(True)
        self.toDate = QDateEdit()
        self.toDate.setDate(QDate.currentDate())  # 오늘
        self.toDate.setCalendarPopup(True)
        
        dateLayout.addWidget(self.fromDate)
        dateLayout.addWidget(QLabel("부터"))
        dateLayout.addWidget(self.toDate)
        dateLayout.addWidget(QLabel("까지"))
        
        self.useDateRange = QCheckBox("날짜 범위 사용")
        self.useDateRange.setChecked(False)
        self.fromDate.setEnabled(False)
        self.toDate.setEnabled(False)
        self.useDateRange.toggled.connect(self.toggleDateRange)
        
        dateGroupBox = QGroupBox("날짜 범위")
        dateGroupBox.setLayout(dateLayout)
        formLayout.addRow(self.useDateRange, dateGroupBox)
        
        # 검색 버튼
        buttonLayout = QHBoxLayout()
        self.searchButton = QPushButton("검색")
        self.searchButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("취소")
        self.cancelButton.clicked.connect(self.reject)
        
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.searchButton)
        buttonLayout.addWidget(self.cancelButton)
        
        layout.addLayout(formLayout)
        layout.addLayout(buttonLayout)
        
    def toggleDateRange(self, checked):
        self.fromDate.setEnabled(checked)
        self.toDate.setEnabled(checked)
        
    def getSearchParams(self):
        params = {
            "query": self.queryInput.text().strip()
        }
        
        # 워크스페이스 설정
        if self.workspaceCombo.currentText() != "모든 워크스페이스":
            params["workspace"] = self.workspaceCombo.currentText()
            
        # 채널 설정
        if self.channelCombo.currentText() != "모든 채널":
            params["channel"] = self.channelCombo.currentText()
            
        # 보낸 사람 설정
        if self.senderInput.text().strip():
            params["sender"] = self.senderInput.text().strip()
            
        # 날짜 범위 설정
        if self.useDateRange.isChecked():
            params["date_from"] = self.fromDate.date().toString("yyyy-MM-dd")
            params["date_to"] = self.toDate.date().toString("yyyy-MM-dd")
            
        return params

class SearchResultsDialog(QDialog):
    messageSelected = Signal(dict)
    
    def __init__(self, parent=None, results=None):
        super().__init__(parent)
        self.setWindowTitle("검색 결과")
        self.setMinimumSize(800, 600)
        self.results = results or []
        
        self.initUI()
        self.populateResults()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # 결과 수 표시
        self.resultCountLabel = QLabel(f"검색 결과: {len(self.results)}개")
        layout.addWidget(self.resultCountLabel)
        
        # 결과 목록
        self.resultsList = QTreeWidget()
        self.resultsList.setHeaderLabels(["날짜", "시간", "워크스페이스", "채널", "보낸 사람", "메시지"])
        self.resultsList.setAlternatingRowColors(True)
        self.resultsList.itemDoubleClicked.connect(self.onItemDoubleClicked)
        
        # 열 너비 설정
        self.resultsList.setColumnWidth(0, 100)  # 날짜
        self.resultsList.setColumnWidth(1, 80)   # 시간
        self.resultsList.setColumnWidth(2, 120)  # 워크스페이스
        self.resultsList.setColumnWidth(3, 100)  # 채널
        self.resultsList.setColumnWidth(4, 120)  # 보낸 사람
        
        layout.addWidget(self.resultsList)
        
        # 닫기 버튼
        buttonLayout = QHBoxLayout()
        self.closeButton = QPushButton("닫기")
        self.closeButton.clicked.connect(self.close)
        
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.closeButton)
        
        layout.addLayout(buttonLayout)
        
    def populateResults(self):
        self.resultsList.clear()
        
        for result in self.results:
            item = QTreeWidgetItem()
            item.setText(0, result.get("date", ""))
            item.setText(1, result.get("time", ""))
            item.setText(2, result.get("workspace", ""))
            item.setText(3, result.get("channel", ""))
            item.setText(4, result.get("sender", ""))
            
            # 메시지가 너무 길면 truncate
            message = result.get("message", "")
            if len(message) > 100:
                message = message[:97] + "..."
            item.setText(5, message)
            
            # 원본 데이터 저장
            item.setData(0, Qt.UserRole, result)
            
            self.resultsList.addTopLevelItem(item)
            
    def onItemDoubleClicked(self, item, column):
        result_data = item.data(0, Qt.UserRole)
        if result_data:
            self.messageSelected.emit(result_data)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(400, 300)
        
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # 탭 위젯
        self.tabWidget = QTabWidget()
        
        # 사용자 탭
        userTab = QWidget()
        userLayout = QFormLayout(userTab)
        
        self.usernameEdit = QLineEdit()
        self.usernameEdit.setText(load_from_registry("username") or "")
        userLayout.addRow("사용자 이름:", self.usernameEdit)
        
        self.emailEdit = QLineEdit()
        self.emailEdit.setText(load_from_registry("email") or "")
        userLayout.addRow("이메일:", self.emailEdit)
        
        # 서버 탭
        serverTab = QWidget()
        serverLayout = QFormLayout(serverTab)
        
        self.serverUrlEdit = QLineEdit()
        self.serverUrlEdit.setText(load_from_registry("server_url") or SERVER_URL)
        serverLayout.addRow("서버 URL:", self.serverUrlEdit)
        
        # 알림 탭
        notificationTab = QWidget()
        notificationLayout = QVBoxLayout(notificationTab)
        
        self.desktopNotifications = QCheckBox("데스크톱 알림 사용")
        self.desktopNotifications.setChecked(load_from_registry("desktop_notifications") == "true")
        
        self.soundNotifications = QCheckBox("소리 알림 사용")
        self.soundNotifications.setChecked(load_from_registry("sound_notifications") == "true")
        
        notificationLayout.addWidget(self.desktopNotifications)
        notificationLayout.addWidget(self.soundNotifications)
        notificationLayout.addStretch()
        
        # 탭 추가
        self.tabWidget.addTab(userTab, "사용자 정보")
        self.tabWidget.addTab(serverTab, "서버 설정")
        self.tabWidget.addTab(notificationTab, "알림 설정")
        
        layout.addWidget(self.tabWidget)
        
        # 버튼
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.saveSettings)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)
        
    def saveSettings(self):
        # 사용자 설정 저장
        username = self.usernameEdit.text().strip()
        if username:
            save_to_registry("username", username)
            
        email = self.emailEdit.text().strip()
        save_to_registry("email", email)
        
        # 서버 설정 저장
        server_url = self.serverUrlEdit.text().strip()
        if server_url:
            save_to_registry("server_url", server_url)
            
        # 알림 설정 저장
        save_to_registry("desktop_notifications", "true" if self.desktopNotifications.isChecked() else "false")
        save_to_registry("sound_notifications", "true" if self.soundNotifications.isChecked() else "false")
        
        self.accept()

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
        print("[WebSocketWorker] Message received:", message[:200], "..." if len(message) > 200 else "")
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
            # 중복 확인
            found = False
            for i in range(self.workspaceList.count()):
                if self.workspaceList.item(i).text() == name:
                    found = True
                    break
            
            if not found:
                self.workspaceList.addItem(name)
                self.wsNameEdit.clear()
    
    def getWorkspaces(self):
        workspaces = []
        for i in range(self.workspaceList.count()):
            workspaces.append(self.workspaceList.item(i).text())
        return workspaces
    
class CreateChannelDialog(QDialog):
    def __init__(self, parent=None, workspace=None):
        super().__init__(parent)
        self.setWindowTitle("새 채널 생성")
        self.setFixedSize(400, 200)
        self.workspace = workspace
        
        layout = QVBoxLayout(self)
        
        formLayout = QFormLayout()
        
        self.channelNameEdit = QLineEdit()
        self.channelNameEdit.setPlaceholderText("채널 이름")
        formLayout.addRow("채널 이름:", self.channelNameEdit)
        
        self.descriptionEdit = QTextEdit()
        self.descriptionEdit.setPlaceholderText("채널 설명 (선택 사항)")
        self.descriptionEdit.setMaximumHeight(80)
        formLayout.addRow("설명:", self.descriptionEdit)
        
        # 버튼
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        layout.addLayout(formLayout)
        layout.addWidget(buttonBox)
        
    def getChannelData(self):
        return {
            "channel_name": self.channelNameEdit.text().strip(),
            "description": self.descriptionEdit.toPlainText().strip(),
            "workspace": self.workspace
        }
        
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
        self.searchBox.setPlaceholderText("전체 검색")
        self.searchBox.returnPressed.connect(self.onGlobalSearch)
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
        self.headerSearch.setPlaceholderText("채널 검색")
        self.headerSearch.setFixedWidth(250)
        self.headerSearch.returnPressed.connect(self.onChannelSearch)
        chHeaderLayout.addWidget(self.headerSearch)
        
        # 헤더 아이콘들
        headerIcons = QWidget()
        headerIconsLayout = QHBoxLayout(headerIcons)
        headerIconsLayout.setContentsMargins(0, 0, 0, 0)
        
        # 채널별 검색 버튼 추가
        self.channelSearchBtn = QPushButton("🔍")
        self.channelSearchBtn.setToolTip("채널 내 검색")
        self.channelSearchBtn.setStyleSheet("background: transparent;")
        self.channelSearchBtn.setFixedSize(40, 40)
        self.channelSearchBtn.clicked.connect(self.showChannelSearchDialog)
        headerIconsLayout.addWidget(self.channelSearchBtn)
        
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
        self.initWebSocketWorker()

        # 시스템 트레이 설정
        self.createTrayIcon()

        # 현재 채널 및 워크스페이스 설정
        self.current_channel = "전체"
        self.current_workspace = "실험실"
        self.workspaces = ["실험실"]

        # 워크스페이스 초기화
        self.initWorkspaces()

        # 사용자 등록
        self.registerUser()
        
    def initWebSocketWorker(self):
        """WebSocket 워커 초기화"""
        self.wsThread = QThread()
        server_url = load_from_registry("server_url") or SERVER_URL
        self.wsWorker = WebSocketWorker(QUrl(server_url))
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
        self.reconnectTimer.timeout.connect(self.reconnectWebSocket)

    def reconnectWebSocket(self):
        """WebSocket 재연결"""
        server_url = load_from_registry("server_url") or SERVER_URL
        self.wsWorker.url = QUrl(server_url)
        QMetaObject.invokeMethod(self.wsWorker, "start", Qt.QueuedConnection)

    def registerUser(self):
        """사용자 등록"""
        username = load_from_registry("username") or "사용자"
        current_time = datetime.now()
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "register_user",
            "username": username
        })
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

    def createTrayIcon(self):
        """시스템 트레이 아이콘 생성"""
        self.trayIcon = QSystemTrayIcon(QIcon(":/images/logo.png"), self)
        self.trayIcon.activated.connect(self.onTrayIconActivated)

        trayMenu = QMenu()
        quitAction = QAction("종료", self)
        quitAction.triggered.connect(QApplication.instance().quit)
        trayMenu.addAction(quitAction)
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.show()

    def showTrayMessage(self, title: str, message: str):
        """트레이 알림 표시"""
        if self.trayIcon.isVisible():
            self.trayIcon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def onTrayIconActivated(self, reason):
        """트레이 아이콘 활성화 시 동작"""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        """창 닫기 이벤트 처리"""
        self.trayIcon.hide()
        self.wsThread.quit()
        self.wsThread.wait()
        event.accept()

    def openSettingsDialog(self):
        """설정 대화상자 열기"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # 서버 URL이 변경되었는지 확인
            old_url = load_from_registry("server_url") or SERVER_URL
            new_url = load_from_registry("server_url")
            if new_url and old_url != new_url:
                # WebSocket 재연결
                self.wsWorker.stop()
                self.reconnectWebSocket()
                
            # 사용자 이름이 변경되었는지 확인
            username = load_from_registry("username")
            if username:
                self.registerUser()

    def onChannelSelected(self, channel_name):
        """채널 선택 시 동작"""
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
        """워크스페이스 목록 요청"""
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
        """채널 목록 요청"""
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
        """채널 데이터 요청"""
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
        """메시지 전송 버튼 클릭 시 동작"""
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
            "workspace": self.current_workspace,
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

    def formatMessage(self, sender, time, message):
        """메시지 포맷팅"""
        return f"""
        <div style="margin-bottom: 12px;">
            <div style="font-weight: bold;">{sender} <span style="font-weight: normal; color: #616061; font-size: 12px;">{time}</span></div>
            <div>{message}</div>
        </div>
        """

    def formatDateSeparator(self, date_str):
        """날짜 구분선 포맷팅"""
        formatted_date = format_date_korean(date_str)
        return f"""
        <div style="display: flex; align-items: center; margin: 20px 0; color: #616061;">
            <hr style="flex-grow: 1; border: none; border-top: 1px solid #E8E8E8; margin-right: 10px;">
            <div style="font-size: 14px; font-weight: bold;">{formatted_date}</div>
            <hr style="flex-grow: 1; border: none; border-top: 1px solid #E8E8E8; margin-left: 10px;">
        </div>
        """

    def getLastDateInMessageArea(self):
        """메시지 영역에 표시된 마지막 날짜 구분선의 날짜를 반환"""
        # 실제로는 HTML 파싱이 필요하지만, 간단한 구현으로 현재 날짜 반환
        return datetime.now().strftime("%Y-%m-%d")

    @Slot(QNetworkReply)
    def onRestReplyFinished(self, reply: QNetworkReply):
        """REST API 응답 처리"""
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
        """WebSocket 메시지 수신 처리"""
        try:
            data = json.loads(msg)
            action = data.get("action")
            
            if action == "channel_data":
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
                        # 24시간 형식을 12시간 형식으로 변환
                        try:
                            time_obj = datetime.strptime(time, "%H:%M:%S")
                            time = time_obj.strftime("%p %I:%M")
                        except:
                            pass
                            
                        text = message.get("message", "")
                        self.messageArea.append(self.formatMessage(sender, time, text))
                        
            elif action == "workspace_list":
                self.workspaces = []
                self.channels = []
                
                workspace_list = data.get("message", {})
                for workspace in workspace_list.keys():
                    self.workspaces.append(workspace)
                
                # 첫 번째 워크스페이스 선택
                if self.workspaces:
                    self.updateWorkspaces(self.workspaces[0])
                    
                    # 채널 목록 업데이트
                    if workspace_list.get(self.current_workspace):
                        self.channels = workspace_list[self.current_workspace]
                        self.updateChannelList(self.channels)
                        
                print("Received workspace list:", self.workspaces)
                
            elif action == "channel_list":
                self.channels = data.get("message", [])
                self.updateChannelList(self.channels)
                print("Received channel list:", self.channels)
                
            elif action == "workspace_update":
                workspace_list = data.get("message", {})
                self.workspaces = list(workspace_list.keys())
                
                # 현재 워크스페이스가 목록에 없으면 첫 번째 워크스페이스로 전환
                if self.current_workspace not in self.workspaces and self.workspaces:
                    self.updateWorkspaces(self.workspaces[0])
                else:
                    # 워크스페이스 메뉴 업데이트
                    self.setupWorkspaceMenu()
                    
                print("Workspace update:", self.workspaces)
                
            elif action == "channel_update":
                workspace = data.get("workspace")
                if workspace == self.current_workspace:
                    self.channels = data.get("message", [])
                    self.updateChannelList(self.channels)
                    print("Channel update:", self.channels)
                    
            elif action == "search_response":
                self.handleSearchResponse(data)
                
            elif action == "register_user_response":
                status = data.get("status")
                message = data.get("message", "")
                if status == "success":
                    print("User registration successful:", message)
                else:
                    print("User registration failed:", message)
                    self.showTrayMessage("사용자 등록", message)
                    
            elif action == "create_workspace_response" or action == "delete_workspace_response" or action == "update_workspace_response":
                status = data.get("status")
                message = data.get("message", "")
                if status == "success":
                    print(f"Workspace operation successful: {message}")
                    self.showTrayMessage("워크스페이스 작업", message)
                else:
                    print(f"Workspace operation failed: {message}")
                    self.showTrayMessage("워크스페이스 작업", message)
                    
            elif action == "create_channel_response" or action == "delete_channel_response" or action == "update_channel_response":
                status = data.get("status")
                message = data.get("message", "")
                if status == "success":
                    print(f"Channel operation successful: {message}")
                    self.showTrayMessage("채널 작업", message)
                else:
                    print(f"Channel operation failed: {message}")
                    self.showTrayMessage("채널 작업", message)
                
            else:
                # 일반 메시지
                sender = data.get("sender", "Unknown")
                text = data.get("message", "")
                time = data.get("time", "")
                date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
                
                # 현재 채널에 해당하는 메시지인지 확인
                if data.get("channel") == self.current_channel:
                    # 메시지 영역에 마지막 날짜 구분선이 없는 경우 추가
                    last_date_in_view = self.getLastDateInMessageArea()
                    if date != last_date_in_view:
                        self.messageArea.append(self.formatDateSeparator(date))
                        
                    # 메시지 추가
                    self.messageArea.append(self.formatMessage(sender, time, text))
                
                # 트레이 알림
                if sender != load_from_registry("username"):
                    self.showTrayMessage(f"새 메시지 ({data.get('channel', '알 수 없음')})", f"{sender}: {text}")
                
        except json.JSONDecodeError:
            print("[WebSocketWorker] Failed to decode message:", msg)
        except Exception as e:
            print("[WebSocketWorker] Error processing message:", str(e))
            traceback.print_exc()

    def handleSearchResponse(self, data):
        """검색 응답 처리"""
        status = data.get("status")
        results = data.get("results", [])
        
        if status == "success":
            dialog = SearchResultsDialog(self, results)
            dialog.messageSelected.connect(self.navigateToSearchResult)
            dialog.exec()
        else:
            error_message = data.get("message", "알 수 없는 오류")
            self.showTrayMessage("검색 오류", error_message)

    def navigateToSearchResult(self, result):
        """검색 결과 선택 시 해당 메시지로 이동"""
        workspace = result.get("workspace")
        channel = result.get("channel")
        
        # 다른 워크스페이스로 이동 필요한 경우
        if workspace != self.current_workspace:
            self.switchWorkspace(workspace)
            
        # 다른 채널로 이동 필요한 경우
        if channel != self.current_channel:
            # 채널 목록에 추가가 필요할 수 있음
            if channel not in self.channel_items:
                channel_item = ChannelItem(channel)
                channel_item.clicked.connect(self.onChannelSelected)
                self.channel_items[channel] = channel_item
                self.channelListLayout.addWidget(channel_item)
                
            self.onChannelSelected(channel)

    @Slot(str)
    def onWebSocketError(self, err: str):
        """WebSocket 오류 처리"""
        print("[WebSocket Error]:", err)
        self.showTrayMessage("WebSocket Error", err)
        self.reconnectTimer.start()

    @Slot()
    def onWebSocketConnected(self):
        """WebSocket 연결 완료 시 동작"""
        self.reconnectTimer.stop()
        self.requestWorkspaceList()
        self.registerUser()

    @Slot()
    def onWebSocketDisconnected(self):
        """WebSocket 연결 해제 시 동작"""
        self.reconnectTimer.start()

    def addChannel(self):
        """새 채널 추가"""
        dialog = CreateChannelDialog(self, self.current_workspace)
        if dialog.exec() == QDialog.Accepted:
            channel_data = dialog.getChannelData()
            
            if not channel_data["channel_name"]:
                self.showTrayMessage("오류", "채널 이름이 필요합니다.")
                return
                
            # 서버에 채널 생성 요청
            current_time = datetime.now()
            username = load_from_registry("username") or "사용자"
            
            request_message = json.dumps({
                "date": current_time.strftime("%Y-%m-%d"),
                "time": current_time.strftime("%I:%M:%S"),
                "sender": username,
                "action": "create_channel",
                "workspace": self.current_workspace,
                "channel_name": channel_data["channel_name"],
                "description": channel_data["description"]
            })
            
            QMetaObject.invokeMethod(
                self.wsWorker,
                "sendMessage",
                Qt.QueuedConnection,
                Q_ARG(str, request_message)
            )

    def updateChannelList(self, channels):
        """채널 목록 업데이트"""
        # 기존 채널 항목 제거
        for item in self.channel_items.values():
            self.channelListLayout.removeWidget(item)
            item.deleteLater()
        self.channel_items.clear()
        
        # 새 채널 항목 추가
        for i, channel in enumerate(channels):
            is_selected = (channel == self.current_channel)
            channel_item = ChannelItem(channel, is_selected)
            channel_item.clicked.connect(self.onChannelSelected)
            self.channel_items[channel] = channel_item
            # 채널 추가 버튼 앞에 추가
            self.channelListLayout.insertWidget(i, channel_item)
            
        # 현재 채널이 목록에 없으면 첫 번째 채널 선택
        if self.current_channel not in channels and channels:
            self.onChannelSelected(channels[0])

    # 워크스페이스 관련 메소드
    def initWorkspaces(self):
        """워크스페이스 초기화"""
        # 서버에서 워크스페이스 목록 요청
        self.requestWorkspaceList()
        
        # 워크스페이스 버튼 업데이트
        self.updateWorkspaceButton()
        
        # 워크스페이스 메뉴 설정
        self.setupWorkspaceMenu()
        
        # 워크스페이스 버튼 클릭 시 메뉴 표시
        self.workspaceBtn.clicked.connect(self.showWorkspaceMenu)
        
    def updateWorkspaces(self, workspace_name):
        """현재 워크스페이스 업데이트"""
        self.current_workspace = workspace_name
        
        # 워크스페이스 버튼 업데이트
        self.updateWorkspaceButton()
        
        # 워크스페이스 메뉴 설정
        self.setupWorkspaceMenu()
        
        # 채널 목록 업데이트 요청
        self.requestChannelList()

    def updateWorkspaceButton(self):
        """워크스페이스 버튼 업데이트"""
        # 현재 워크스페이스의 첫 글자를 버튼에 표시
        if self.current_workspace:
            self.workspaceBtn.setText(self.current_workspace[0])
            # 워크스페이스 헤더 업데이트
            wsTitle = self.wsHeader.findChild(QLabel)
            if wsTitle:
                wsTitle.setText(self.current_workspace)

    def setupWorkspaceMenu(self):
        """워크스페이스 메뉴 설정"""
        self.wsMenu = QMenu(self)
        
        # 워크스페이스 항목 추가
        for ws in self.workspaces:
            action = QAction(ws, self)
            action.triggered.connect(lambda checked, w=ws: self.switchWorkspace(w))
            self.wsMenu.addAction(action)
        
        self.wsMenu.addSeparator()
        
        # 워크스페이스 생성
        createAction = QAction("새 워크스페이스 생성", self)
        createAction.triggered.connect(self.createWorkspace)
        self.wsMenu.addAction(createAction)
        
        # 워크스페이스 관리
        manageAction = QAction("워크스페이스 관리", self)
        manageAction.triggered.connect(self.manageWorkspaces)
        self.wsMenu.addAction(manageAction)

    def showWorkspaceMenu(self):
        """워크스페이스 메뉴 표시"""
        self.wsMenu.exec(self.workspaceBtn.mapToGlobal(self.workspaceBtn.rect().bottomLeft()))

    def switchWorkspace(self, workspace_name):
        """워크스페이스 전환"""
        if workspace_name != self.current_workspace:
            self.current_workspace = workspace_name
            self.updateWorkspaceButton()
            # 채널 목록 업데이트 요청
            self.requestChannelList()

    def createWorkspace(self):
        """새 워크스페이스 생성"""
        workspace_name, ok = QInputDialog.getText(self, "새 워크스페이스 생성", "워크스페이스 이름:")
        if ok and workspace_name:
            # 서버에 워크스페이스 생성 요청
            current_time = datetime.now()
            username = load_from_registry("username") or "사용자"
            
            request_message = json.dumps({
                "date": current_time.strftime("%Y-%m-%d"),
                "time": current_time.strftime("%I:%M:%S"),
                "sender": username,
                "action": "create_workspace",
                "workspace_name": workspace_name
            })
            
            QMetaObject.invokeMethod(
                self.wsWorker,
                "sendMessage",
                Qt.QueuedConnection,
                Q_ARG(str, request_message)
            )

    def manageWorkspaces(self):
        """워크스페이스 관리"""
        dialog = WorkspaceDialog(self, self.workspaces)
        if dialog.exec() == QDialog.Accepted:
            new_workspaces = dialog.getWorkspaces()
            
            # 제거된 워크스페이스 찾기
            for ws in self.workspaces:
                if ws not in new_workspaces:
                    # 워크스페이스 삭제 요청
                    self.deleteWorkspace(ws)
                    
            # 추가된 워크스페이스 찾기
            for ws in new_workspaces:
                if ws not in self.workspaces:
                    # 워크스페이스 생성 요청
                    self.createWorkspaceFromDialog(ws)
                    
            # 현재 워크스페이스가 목록에 없으면 첫 번째 워크스페이스로 전환
            if self.current_workspace not in new_workspaces and new_workspaces:
                self.switchWorkspace(new_workspaces[0])

    def createWorkspaceFromDialog(self, workspace_name):
        """대화상자에서 워크스페이스 생성"""
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "create_workspace",
            "workspace_name": workspace_name
        })
        
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

    def deleteWorkspace(self, workspace_name):
        """워크스페이스 삭제"""
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        
        request_message = json.dumps({
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "delete_workspace",
            "workspace": workspace_name
        })
        
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, request_message)
        )

    # 검색 관련 메소드
    def onGlobalSearch(self):
        """전역 검색"""
        query = self.searchBox.text().strip()
        if query:
            self.showSearchDialog(query)
        else:
            self.showTrayMessage("검색", "검색어를 입력하세요.")

    def onChannelSearch(self):
        """채널 내 검색"""
        query = self.headerSearch.text().strip()
        if query:
            self.showSearchDialog(query, self.current_workspace, self.current_channel)
        else:
            self.showTrayMessage("검색", "검색어를 입력하세요.")

    def showSearchDialog(self, query=None, workspace=None, channel=None):
        """검색 대화상자 표시"""
        dialog = SearchDialog(self, 
                            self.workspaces, 
                            self.channels, 
                            self.current_workspace, 
                            self.current_channel)
        
        # 기본 검색어 설정
        if query:
            dialog.queryInput.setText(query)
        
        # 워크스페이스 선택
        if workspace:
            index = dialog.workspaceCombo.findText(workspace)
            if index >= 0:
                dialog.workspaceCombo.setCurrentIndex(index)
        
        # 채널 선택
        if channel:
            index = dialog.channelCombo.findText(channel)
            if index >= 0:
                dialog.channelCombo.setCurrentIndex(index)
        
        if dialog.exec() == QDialog.Accepted:
            self.executeSearch(dialog.getSearchParams())

    def showChannelSearchDialog(self):
        """현재 채널 내 검색 대화상자 표시"""
        self.showSearchDialog(None, self.current_workspace, self.current_channel)

    def executeSearch(self, params):
        """검색 실행"""
        if not params.get("query"):
            self.showTrayMessage("검색", "검색어가 필요합니다.")
            return
        
        current_time = datetime.now()
        username = load_from_registry("username") or "사용자"
        
        # 검색 요청 메시지 구성
        request_message = {
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%I:%M:%S"),
            "sender": username,
            "action": "search",
            "query": params.get("query")
        }
        
        # 옵션 파라미터 추가
        for key in ["workspace", "channel", "sender", "date_from", "date_to"]:
            if key in params and params[key]:
                request_message[key] = params[key]
        
        # 검색 요청 전송
        QMetaObject.invokeMethod(
            self.wsWorker,
            "sendMessage",
            Qt.QueuedConnection,
            Q_ARG(str, json.dumps(request_message))
        )

    def navigateToHome(self):
        """홈 화면으로 이동하는 로직"""
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
        """DM 화면으로 이동하는 로직"""
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
        """내 활동 화면으로 이동하는 로직"""
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
        """더 보기 메뉴 표시"""
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
        """스레드 화면으로 이동하는 로직"""
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>스레드</h2>
            <p>스레드된 메시지를 모아서 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("🧵 스레드")

    def showFiles(self):
        """파일 화면으로 이동하는 로직"""
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>파일</h2>
            <p>공유된 파일을 모아서 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("📁 파일")

    def showApps(self):
        """앱 화면으로 이동하는 로직"""
        self.messageArea.clear()
        self.messageArea.append("""
        <div style="text-align:center; margin-top:50px;">
            <h2>앱</h2>
            <p>설치된 앱 목록을 보는 화면입니다.</p>
        </div>
        """)
        self.channelTitle.setText("🧩 앱")
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 앱 아이콘 설정 (선택 사항)
    # app.setWindowIcon(QIcon(":/images/app_icon.png"))
    
    # 스타일 설정 (선택 사항)
    # app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())