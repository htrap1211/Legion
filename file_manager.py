import os
import json
import socket
import hashlib
import struct
import shutil
from networking import TCPClient

class FileManager:
    def __init__(self, shared_dir):
        self.shared_dir = shared_dir
        if not os.path.exists(shared_dir):
            os.makedirs(shared_dir)
            
        # Create a welcome file if directory is empty so user has something to share
        if not os.listdir(shared_dir):
            with open(os.path.join(shared_dir, 'welcome.txt'), 'w') as f:
                f.write("Welcome to the P2P File Sharing System!\nThis file is shared from your node.")

    def list_files(self):
        """Return a list of files in the shared directory with metadata."""
        files = {}
        if os.path.exists(self.shared_dir):
            for f in os.listdir(self.shared_dir):
                if not f.startswith('.'):
                    path = os.path.join(self.shared_dir, f)
                    if os.path.isfile(path):
                        size = os.path.getsize(path)
                        files[f] = {
                            'size': size,
                            'hash': self._calculate_hash(path)
                        }
        return files

    def _calculate_hash(self, filepath):
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def share_file(self, filepath):
        """Copy a file to the shared directory to share it."""
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found.")
            return False
            
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self.shared_dir, filename)
        
        try:
            # Don't overwrite if it's the same file
            if os.path.abspath(filepath) != os.path.abspath(dest_path):
                shutil.copy2(filepath, dest_path)
                print(f"Copied '{filename}' to shared directory.")
            else:
                print(f"File '{filename}' is already in shared directory.")
            return True
        except Exception as e:
            print(f"Error sharing file: {e}")
            return False

    def handle_transfer(self, client_sock):
        """Handle an incoming file request."""
        try:
            # Receive filename
            filename = client_sock.recv(1024).decode('utf-8').strip()
            filepath = os.path.join(self.shared_dir, filename)
            
            if os.path.exists(filepath):
                print(f"Sending file: {filename}")
                
                # Send file size header
                filesize = os.path.getsize(filepath)
                client_sock.sendall(struct.pack('>Q', filesize))
                
                # Send file content
                with open(filepath, 'rb') as f:
                    while chunk := f.read(4096):
                        client_sock.sendall(chunk)
            else:
                print(f"File not found: {filename}")
        except Exception as e:
            print(f"Error handling transfer: {e}")
        finally:
            client_sock.close()

    def download_file(self, host, port, filename, save_dir=None, expected_hash=None):
        """Download a file from a peer."""
        print(f"Downloading {filename} from {host}:{port}...")
        try:
            # Connect to peer
            with socket.create_connection((host, port)) as sock:
                # Send filename
                sock.sendall(filename.encode('utf-8'))
                
                # Determine save path
                target_dir = save_dir if save_dir else self.shared_dir
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                    
                save_path = os.path.join(target_dir, filename)
                
                # Progress callback
                def show_progress(received, total):
                    percent = int(100 * received / total) if total > 0 else 0
                    bar_len = 20
                    filled = int(bar_len * received / total) if total > 0 else 0
                    bar = '=' * filled + '-' * (bar_len - filled)
                    # Use \r to overwrite line? TUI might not support it well. 
                    # Let's just print every 20% to avoid flooding
                    if percent % 20 == 0 and received > 0:
                        print(f"Progress: [{bar}] {percent}%")

                # Receive file using TCPClient
                TCPClient.receive_file(sock, save_path, show_progress)
                
            print(f"File {filename} downloaded to {save_path}")
            
            # Verify Hash
            if expected_hash:
                print("Verifying file integrity...")
                calculated_hash = self._calculate_hash(save_path)
                if calculated_hash == expected_hash:
                    print("SUCCESS: File integrity verified (Checksum match).")
                else:
                    print(f"WARNING: File integrity check FAILED!")
                    print(f"Expected: {expected_hash}")
                    print(f"Got:      {calculated_hash}")
            
        except Exception as e:
            print(f"Error downloading file: {e}")
