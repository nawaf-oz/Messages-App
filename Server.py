import socket
import threading
import os
import hashlib
import base64

HOST = '0.0.0.0'
PORT = 12345
BUFFER_SIZE = 1024

user_db_file = "users.txt"
log_file     = "chat_log.txt"
groups_file  = "groups.txt"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    users = {}
    if os.path.exists(user_db_file):
        with open(user_db_file, "r") as f:
            for line in f:
                username, hashed = line.strip().split(":")
                users[username] = hashed
    return users

def save_user(username, password):
    hashed = hash_password(password)
    with open(user_db_file, "a") as f:
        f.write(f"{username}:{hashed}\n")

def log_message(msg):
    with open(log_file, "a") as f:
        f.write(msg + "\n")

def save_group(group_name, members):
    with open(groups_file, "a") as f:
        f.write(f"{group_name}:{','.join(members)}\n")

def load_groups():
    groups = {}
    if os.path.exists(groups_file):
        with open(groups_file, "r") as f:
            for line in f:
                group_name, members = line.strip().split(":")
                groups[group_name] = members.split(",")
    return groups

groups = load_groups()
clients = {}

def recv_line(sock):
    buf = b""
    while True:
        ch = sock.recv(1)
        if not ch or ch == b"\n":
            break
        buf += ch
    return buf.decode()

def recv_all(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(min(n - len(data), 4096))
        if not chunk:
            return None
        data += chunk
    return data

def broadcast(sender, message):
    log_entry = f"[{sender} -> All]: {message}"
    log_message(log_entry)
    for user, sock in clients.items():
        if user != sender:
            try:
                sock.send(log_entry.encode())
            except:
                continue

def multicast(sender, group_name, message):
    groups = load_groups()
    if group_name not in groups:
        clients[sender].send(f"[Server] Group '{group_name}' not found.".encode())
        return
    if sender not in groups[group_name]:
        clients[sender].send(f"[Server] You are not a member of group '{group_name}'.".encode())
        return
    log_entry = f"[{sender} -> {group_name}]: {message}"
    log_message(log_entry)
    for user in groups[group_name]:
        if user != sender and user in clients:
            try:
                clients[user].send(log_entry.encode())
            except:
                continue

def unicast(sender, receiver, message):
    users_db = load_users()
    if receiver not in users_db:
        clients[sender].send(f"[Server] User '{receiver}' does not exist.".encode())
    elif receiver not in clients:
        clients[sender].send(f"[Server] User '{receiver}' exists but is not online.".encode())
    else:
        try:
            full_msg = f"[{sender} -> You]: {message}"
            clients[receiver].send(full_msg.encode())
            log_message(f"[{sender} -> {receiver}]: {message}")
        except:
            clients[sender].send(f"[Server] Failed to send message to '{receiver}'.".encode())

def file_transfer(sender, receiver, filename, filedata):
    users_db = load_users()
    if receiver not in users_db:
        clients[sender].send(f"[Server] User '{receiver}' does not exist.".encode())
    elif receiver not in clients:
        clients[sender].send(f"[Server] User '{receiver}' exists but is not online.".encode())
    else:
        try:
            forward_msg = f"[{sender} -> You]: File received: {filename}"
            clients[receiver].send(forward_msg.encode())
            log_message(f"[{sender} -> {receiver}]: File received: {filename}")
        except:
            clients[sender].send(f"[Server] Failed to send file to '{receiver}'.".encode())

def handle_client(client_socket):
    users_db = load_users()
    username = None
    try:
        credentials = client_socket.recv(BUFFER_SIZE).decode()
        mode, data = credentials.split("|", 1)
        username, password = data.split(":")

        if mode == "register":
            if username in users_db:
                client_socket.send("[Server] Username already exists.".encode())
                client_socket.close()
                return
            save_user(username, password)
            users_db[username] = hash_password(password)
            client_socket.send(f"[Server] Registered successfully. Welcome {username}!".encode())
        elif mode == "login":
            if username not in users_db or users_db[username] != hash_password(password):
                client_socket.send("[Server] Authentication failed.".encode())
                client_socket.close()
                return
            client_socket.send(f"[Server] Welcome {username}!".encode())
        else:
            client_socket.send("[Server] Invalid mode.".encode())
            client_socket.close()
            return

        clients[username] = client_socket
        print(f"{username} connected.")

        while True:
            msg = client_socket.recv(BUFFER_SIZE).decode()
            if not msg:
                break
            if msg.startswith("F:"):
                parts = msg.split(":", 3)
                if len(parts) < 4:
                    client_socket.send("[Server] Invalid file message format.".encode())
                    continue
                _, target, filename, filedata = parts
                file_transfer(username, target, filename, filedata)
            else:
                parts = msg.split(":", 2)
                if len(parts) < 3:
                    client_socket.send("[Server] Invalid message format.".encode())
                    continue
                msg_type, target, content = parts
                if msg_type == "U":
                    unicast(username, target, content)
                elif msg_type == "M":
                    multicast(username, target, content)
                elif msg_type == "B":
                    broadcast(username, content)
                elif msg_type == "C":
                    members = content.split(",")
                    if username not in members:
                        members.append(username)
                    groups[target] = members
                    save_group(target, members)
                    client_socket.send(f"[Server] Group '{target}' created with members: {', '.join(members)}.".encode())
                    log_message(f"[Server] Group '{target}' created by {username} with members: {', '.join(members)}")
                else:
                    client_socket.send("[Server] Unknown message type.".encode())
    except Exception as e:
        print(f"Error with a client: {e}")
    finally:
        if username in clients:
            del clients[username]
            print(f"{username} disconnected.")
        client_socket.close()

def start_server():
    print(f"Starting server on {HOST}:{PORT}...")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    while True:
        client_socket, addr = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()

if __name__ == "__main__":
    start_server()
