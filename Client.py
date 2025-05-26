import sys
import socket
import threading
import base64
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFileDialog

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 12345
BUFFER_SIZE = 1024

class ReceiverThread(QtCore.QThread):
    message_received = QtCore.pyqtSignal(str)

    def __init__(self, sock, parent=None):
        super(ReceiverThread, self).__init__(parent)
        self.sock = sock
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.sock.recv(BUFFER_SIZE).decode()
                if data:
                    self.message_received.emit(data)
                else:
                    break
            except Exception:
                break

    def stop(self):
        self.running = False
        self.wait()

class LoginWindow(QtWidgets.QDialog):
    def __init__(self):
        super(LoginWindow, self).__init__()
        self.setWindowTitle("Login or Register")
        self.setGeometry(100, 100, 400, 300)

        layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("<h2 style='color:#4CAF50;'>Welcome to ChatApp</h2>")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Login", "Register"])
        layout.addWidget(QtWidgets.QLabel("Select Mode:"))
        layout.addWidget(self.mode_combo)

        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("Username")
        layout.addWidget(self.username_edit)

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        layout.addWidget(self.password_edit)

        self.submit_btn = QtWidgets.QPushButton("Submit")
        self.submit_btn.clicked.connect(self.submit)
        layout.addWidget(self.submit_btn)

        self.setLayout(layout)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def submit(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QtWidgets.QMessageBox.warning(self, "Error", "Please enter both username and password.")
            return
        mode = self.mode_combo.currentText().lower()
        try:
            self.sock.connect((SERVER_HOST, SERVER_PORT))
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Connection Error", "Cannot connect to server.")
            return
        credentials = f"{mode}|{username}:{password}"
        self.sock.send(credentials.encode())
        try:
            response = self.sock.recv(BUFFER_SIZE).decode()
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Error", "No response from server.")
            return
        if "failed" in response.lower() or "exists" in response.lower():
            QtWidgets.QMessageBox.warning(self, "Authentication Failed", response)
            self.sock.close()
        else:
            self.accept()
            self.chat_window = ChatWindow(self.sock, username)
            self.chat_window.show()

class ChatWindow(QtWidgets.QMainWindow):
    def __init__(self, sock, username):
        super(ChatWindow, self).__init__()
        self.sock = sock
        self.username = username
        self.setWindowTitle(f"Chat - {username}")
        self.setGeometry(100, 100, 800, 600)

        self.selected_contact = None

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout()
        central_widget.setLayout(main_layout)

        self.contacts_list = QtWidgets.QListWidget()
        self.contacts_list.setMaximumWidth(200)
        self.contacts_list.itemDoubleClicked.connect(self.set_target_contact)
        main_layout.addWidget(self.contacts_list)

        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget)

        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display)

        h_layout = QtWidgets.QHBoxLayout()
        self.message_edit = QtWidgets.QLineEdit()
        h_layout.addWidget(self.message_edit)

        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        h_layout.addWidget(self.send_btn)

        self.send_file_btn = QtWidgets.QPushButton("Send File")
        self.send_file_btn.clicked.connect(self.send_file)
        h_layout.addWidget(self.send_file_btn)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["Broadcast (B)", "Unicast (U)", "Multicast (M)", "Create Group (C)"])
        h_layout.addWidget(self.type_combo)

        self.logout_btn = QtWidgets.QPushButton("Logout")
        self.logout_btn.clicked.connect(self.logout)
        h_layout.addWidget(self.logout_btn)

        right_layout.addLayout(h_layout)

        self.status_label = QtWidgets.QLabel("Connected")
        right_layout.addWidget(self.status_label)

        self.receiver_thread = ReceiverThread(self.sock)
        self.receiver_thread.message_received.connect(self.append_message)
        self.receiver_thread.start()

    def set_target_contact(self, item):
        self.selected_contact = item.text()
        self.type_combo.setCurrentText("Unicast (U)")
        self.chat_display.append(f"<i>[System] Target set to: {self.selected_contact}</i>")

    def append_message(self, message):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.chat_display.append(f"{timestamp} {message}")

    def send_message(self):
        msg_type_item = self.type_combo.currentText()
        msg_type = msg_type_item[0]
        text = self.message_edit.text().strip()
        if not text:
            return
        display_message = ""
        if msg_type == "C":
            group, ok = QtWidgets.QInputDialog.getText(self, "Create Group", "Enter group name:")
            if not ok or not group:
                return
            members, ok = QtWidgets.QInputDialog.getText(self, "Create Group", "Enter usernames (comma separated):")
            if not ok or not members:
                return
            members_list = members.split(",")
            members_list.append(self.username)
            message = f"C:{group}:{','.join(members_list)}"
            display_message = f"<b>[Group Creation]</b> Created group '{group}' with members {','.join(members_list)}"
            self.contacts_list.addItem(group)
        elif msg_type in ["U", "M"]:
            if msg_type == "U" and self.selected_contact:
                target = self.selected_contact
            else:
                target, ok = QtWidgets.QInputDialog.getText(self, "Target", "Enter username or group:")
                if not ok or not target:
                    return
            message = f"{msg_type}:{target}:{text}"
            display_message = f"<b>[To: {target}]</b> {text}"
            if msg_type == "U" and not self.contact_exists(target):
                self.contacts_list.addItem(target)
        else:
            message = f"B::{text}"
            display_message = f"<b>[Broadcast]</b> {text}"
        try:
            self.sock.send(message.encode())
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            self.chat_display.append(f"{timestamp} {display_message}")
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to send message.")
        self.message_edit.clear()

    def send_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if not file_path:
            return
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            encoded_data = base64.b64encode(file_data).decode()
            filename = file_path.split("/")[-1]
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to read file.")
            return
        target = ""
        if self.selected_contact:
            target = self.selected_contact
        else:
            target, ok = QtWidgets.QInputDialog.getText(self, "Target", "Enter target username for file:")
            if not ok or not target:
                return
        message = f"F:{target}:{filename}:{encoded_data}"
        try:
            self.sock.send(message.encode())
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            self.chat_display.append(f"{timestamp} <b>[To: {target}]</b> File sent: {filename}")
            if not self.contact_exists(target):
                self.contacts_list.addItem(target)
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to send file.")

    def contact_exists(self, contact):
        for index in range(self.contacts_list.count()):
            if self.contacts_list.item(index).text() == contact:
                return True
        return False

    def logout(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        self.receiver_thread.stop()
        self.sock.close()
        self.close()
        self.login_window = LoginWindow()
        self.login_window.show()

    def closeEvent(self, event):
        try:
            self.receiver_thread.stop()
        except:
            pass
        try:
            self.sock.close()
        except:
            pass
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QDialog {
            background-color: #f9f9f9;
        }
        QLabel {
            font-size: 14px;
            color: #333;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 5px 10px;
            font-size: 14px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QLineEdit, QTextEdit, QListWidget, QComboBox {
            background-color: white;
            border: 1px solid #ccc;
            padding: 3px;
            border-radius: 3px;
        }
        QComboBox {
            min-width: 120px;
        }
    """)
    login = LoginWindow()
    if login.exec_() == QtWidgets.QDialog.Accepted:
        sys.exit(app.exec_())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
