import socket
import struct
import threading
import json
import time

# Constants
BROADCAST_PORT = 5007
BUFFER_SIZE = 4096

def get_local_ip():
    """Detect the local IP address connected to the network."""
    try:
        # Connect to an external server (doesn't actually send data) to get the interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class UDPSocket:
    def __init__(self, port=0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            self.sock.bind(('', port))
        except Exception as e:
            print(f"Error binding UDP socket: {e}")
            raise
        self.port = self.sock.getsockname()[1]

    def send_packet(self, message, addr):
        """Send a unicast message to a specific address."""
        try:
            data = json.dumps(message).encode('utf-8')
            self.sock.sendto(data, addr)
        except Exception as e:
            print(f"Error sending UDP packet: {e}")

    def send_broadcast(self, message, port=BROADCAST_PORT):
        """Send a broadcast message to the network."""
        try:
            data = json.dumps(message).encode('utf-8')
            self.sock.sendto(data, ('<broadcast>', port))
        except Exception as e:
            print(f"Error sending broadcast: {e}")

    def listen(self, callback):
        """Listen for incoming UDP packets in a separate thread."""
        def _listen():
            while True:
                try:
                    data, addr = self.sock.recvfrom(BUFFER_SIZE)
                    message = json.loads(data.decode('utf-8'))
                    callback(message, addr)
                except Exception as e:
                    print(f"Error receiving UDP packet: {e}")
                    break
        
        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()

class BroadcastSocket(UDPSocket):
    def __init__(self, port=BROADCAST_PORT):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # SO_REUSEPORT is needed on Mac/Linux for multiple listeners on same port
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass # Not available on Windows
            
        try:
            self.sock.bind(('', port))
        except Exception as e:
            print(f"Error binding Broadcast socket: {e}")
            raise
            
        self.port = port

class TCPServer:
    def __init__(self, port=0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('', port))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]

    def listen(self, handler_callback):
        """Listen for incoming TCP connections."""
        def _accept():
            while True:
                try:
                    client_sock, addr = self.sock.accept()
                    threading.Thread(target=handler_callback, args=(client_sock, addr), daemon=True).start()
                except Exception as e:
                    print(f"Error accepting TCP connection: {e}")
                    break
        
        thread = threading.Thread(target=_accept, daemon=True)
        thread.start()

class TCPClient:
    @staticmethod
    def send_file(host, port, file_path):
        """Send a file to a peer."""
        try:
            filesize = os.path.getsize(file_path)
            with socket.create_connection((host, port)) as sock:
                # Send file size (8 bytes)
                sock.sendall(struct.pack('>Q', filesize))
                
                with open(file_path, 'rb') as f:
                    while chunk := f.read(BUFFER_SIZE):
                        sock.sendall(chunk)
        except Exception as e:
            print(f"Error sending file: {e}")

    @staticmethod
    def receive_file(sock, save_path, progress_callback=None):
        """Receive a file from a peer."""
        try:
            # Read file size
            raw_size = sock.recv(8)
            if not raw_size:
                return
            filesize = struct.unpack('>Q', raw_size)[0]
            
            received = 0
            with open(save_path, 'wb') as f:
                while received < filesize:
                    chunk = sock.recv(min(BUFFER_SIZE, filesize - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, filesize)
        except Exception as e:
            print(f"Error receiving file: {e}")
