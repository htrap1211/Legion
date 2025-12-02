import time
import threading
import uuid
import json
import os
from networking import UDPSocket, BroadcastSocket, TCPServer, get_local_ip
from election import ElectionManager
from file_manager import FileManager

# Peer States
FOLLOWER = 'FOLLOWER'
CANDIDATE = 'CANDIDATE'
LEADER = 'LEADER'

# Message Types
# Message Types
MSG_DISCOVERY = 'DISCOVERY'
MSG_DISCOVERY_RESPONSE = 'DISCOVERY_RESPONSE'
MSG_HEARTBEAT = 'HEARTBEAT'
MSG_ELECTION = 'ELECTION'
MSG_COORDINATOR = 'COORDINATOR'
MSG_PUBLISH = 'PUBLISH'
MSG_QUERY_FILES = 'QUERY_FILES'
MSG_FILE_LIST = 'FILE_LIST'

class Peer:
    def __init__(self, host='0.0.0.0', udp_port=0, tcp_port=0, shared_dir='shared_files'):
        self.id = str(uuid.uuid4())
        self.state = FOLLOWER
        self.leader_id = None
        self.peers = {}  # {peer_id: {'addr': (ip, port), 'last_seen': timestamp}}
        self.global_catalog = {} # {filename: [{'peer_id': id, 'addr': (ip, port)}]}
        self.last_heartbeats = {} # {peer_id: timestamp}
        self.last_leader_heartbeat = time.time() # Track last heartbeat from leader
        
        # Components
        self.unicast_socket = UDPSocket(port=udp_port)
        self.multicast_socket = BroadcastSocket() # Listens on 5007 (Broadcast)
        self.tcp_server = TCPServer(port=tcp_port)
        self.election_manager = ElectionManager(self)
        self.file_manager = FileManager(shared_dir)
        
        self.running = True
        print(f"Peer {self.id} started on UDP:{self.unicast_socket.port} TCP:{self.tcp_server.port}")

    def start(self):
        """Start the peer's main loops."""
        # Start listening for UDP messages (Unicast)
        self.unicast_socket.listen(self.handle_udp_message)
        
        # Start listening for Broadcast messages
        self.multicast_socket.listen(self.handle_udp_message)
        
        # Start TCP server for file transfers
        self.tcp_server.listen(self.handle_tcp_connection)
        
        # Start discovery
        self.discover_leader()
        
        # Start heartbeat loop
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        
        # Start Peer Heartbeat (Send to Leader)
        threading.Thread(target=self._send_heartbeats, daemon=True).start()
        
        # Start Peer Monitor (Leader only)
        threading.Thread(target=self._monitor_peers, daemon=True).start()

    def discover_leader(self):
        """Broadcast a discovery message to find the leader."""
        print("Broadcasting discovery message...")
        msg = {
            'type': MSG_DISCOVERY,
            'sender_id': self.id,
            'addr': (get_local_ip(), self.unicast_socket.port)
        }
        # Send using unicast socket (as sender) to broadcast address
        self.unicast_socket.send_broadcast(msg)
        
        # If no response after a timeout, start election
        threading.Timer(5.0, self.check_discovery_timeout).start()

    def check_discovery_timeout(self):
        """If no leader found, start election."""
        if self.leader_id is None:
            print("No leader found. Starting election...")
            self.election_manager.start_election()

    def publish_files(self):
        """Send local file list to the Leader."""
        if not self.leader_id:
            print("Cannot publish: No leader found.")
            return
            
        files = self.file_manager.list_files()
        if not files:
            print(f"Warning: No files found in '{self.file_manager.shared_dir}' to publish.")
            print(f"Tip: Copy files into '{self.file_manager.shared_dir}' or run with --shared-dir .")
            return

        msg = {
            'type': MSG_PUBLISH,
            'sender_id': self.id,
            'files': files, # Now a dict {filename: {size, hash}}
            'tcp_port': self.tcp_server.port # Send TCP port so others can download
        }
        
        # Send to Leader (Unicast)
        leader_info = self.peers.get(self.leader_id)
        if leader_info:
            self.unicast_socket.send_packet(msg, leader_info['addr'])
            print(f"Published {len(files)} files to Leader.")
        elif self.state == LEADER:
            # If I am leader, update my own catalog
            self.handle_publish(msg, None)
        else:
            print("Leader address unknown.")

    def query_files(self):
        """Request global file list from Leader."""
        if not self.leader_id:
            print("Cannot query: No leader found.")
            return

        msg = {
            'type': MSG_QUERY_FILES,
            'sender_id': self.id
        }
        
        leader_info = self.peers.get(self.leader_id)
        if leader_info:
            self.unicast_socket.send_packet(msg, leader_info['addr'])
            print("Requested file list from Leader.")
        elif self.state == LEADER:
            print("I am the Leader. Global File List:")
            if not self.global_catalog:
                print("  (Catalog is empty)")
            else:
                for filename, peers in self.global_catalog.items():
                    print(f" - {filename} (Available on {len(peers)} peers)")

    def handle_udp_message(self, message, addr):
        """Dispatch incoming UDP messages."""
        msg_type = message.get('type')
        sender_id = message.get('sender_id')
        
        # print(f"[{self.id}] Received {msg_type} from {sender_id}")

        if sender_id == self.id:
            # print(f"[{self.id}] Ignoring own message")
            return  # Ignore own messages

        if msg_type == MSG_DISCOVERY:
            self.handle_discovery(message, addr)
        elif msg_type == MSG_DISCOVERY_RESPONSE:
            self.handle_discovery_response(message, addr)
        elif msg_type == MSG_HEARTBEAT:
            self.handle_heartbeat(message)
        elif msg_type == MSG_ELECTION:
            self.handle_election(message)
        elif msg_type == MSG_COORDINATOR:
            self.handle_coordinator(message)
        elif msg_type == MSG_PUBLISH:
            self.handle_publish(message, addr)
        elif msg_type == MSG_QUERY_FILES:
            self.handle_query_files(message, addr)
        elif msg_type == MSG_FILE_LIST:
            self.handle_file_list(message)

    def handle_discovery(self, message, addr):
        """Handle a discovery request (only if Leader)."""
        if self.state == LEADER:
            print(f"Received discovery from {message['sender_id']}")
            response = {
                'type': MSG_DISCOVERY_RESPONSE,
                'sender_id': self.id,
                'leader_id': self.id
            }
            # Respond to the peer's unicast address
            self.unicast_socket.send_packet(response, addr)
            
            # Add new peer to directory
            self.peers[message['sender_id']] = {'addr': addr, 'last_seen': time.time()}

    def handle_discovery_response(self, message, addr):
        """Handle a response to our discovery broadcast."""
        print(f"Found leader: {message['leader_id']}")
        self.leader_id = message['leader_id']
        self.state = FOLLOWER
        
        # Save leader's address so we can send unicast messages (like PUBLISH)
        if addr:
            self.peers[self.leader_id] = {'addr': addr, 'last_seen': time.time()}

    def _send_heartbeats(self):
        """Send heartbeat to Leader every 5 seconds."""
        while self.running:
            if self.leader_id and self.leader_id != self.id:
                msg = {
                    'type': MSG_HEARTBEAT,
                    'peer_id': self.id
                }
                # Send to leader
                leader_info = self.peers.get(self.leader_id)
                if leader_info:
                    self.unicast_socket.send_packet(msg, leader_info['addr'])
            time.sleep(5)

    def _monitor_peers(self):
        """Monitor peers for timeouts (Leader only)."""
        while self.running:
            if self.state == LEADER:
                now = time.time()
                dead_peers = []
                for peer_id, last_seen in self.last_heartbeats.items():
                    if now - last_seen > 15: # 15 seconds timeout
                        dead_peers.append(peer_id)
                
                for peer_id in dead_peers:
                    print(f"Peer {peer_id} timed out. Removing.")
                    if peer_id in self.last_heartbeats:
                        del self.last_heartbeats[peer_id]
                    # Remove from peers list
                    if peer_id in self.peers:
                        del self.peers[peer_id]
                    # Remove from global catalog
                    for filename in list(self.global_catalog.keys()):
                        self.global_catalog[filename] = [entry for entry in self.global_catalog[filename] if entry['peer_id'] != peer_id]
                        if not self.global_catalog[filename]:
                            del self.global_catalog[filename]
            time.sleep(5)

    def handle_heartbeat(self, message):
        """Handle heartbeat messages."""
        # If I am Follower, this might be Leader heartbeat (keep alive)
        if self.state == FOLLOWER and message.get('sender_id') == self.leader_id:
            self.last_leader_heartbeat = time.time()
            
        # If I am Leader, this is a Peer heartbeat
        if self.state == LEADER:
            # Check if this is a conflicting Leader
            if message.get('role') == LEADER:
                sender_id = message.get('sender_id')
                if sender_id > self.id:
                    print(f"Detected higher leader {sender_id}. Stepping down.")
                    self.state = FOLLOWER
                    self.leader_id = sender_id
                    self.last_leader_heartbeat = time.time()
                    return
            
            peer_id = message.get('peer_id') or message.get('sender_id')
            if peer_id:
                self.last_heartbeats[peer_id] = time.time()
                # Also update peers list if not present (re-discovery)
                if peer_id in self.peers:
                    self.peers[peer_id]['last_seen'] = time.time()

    def handle_election(self, message):
        """Handle election messages."""
        self.election_manager.handle_election_message(message)

    def handle_coordinator(self, message):
        """Handle coordinator announcement."""
        new_leader = message['sender_id']
        addr = message.get('addr')
        
        print(f"New Coordinator announced: {new_leader}")
        self.leader_id = new_leader
        self.state = FOLLOWER
        self.election_manager.election_in_progress = False
        
        # Update peer list with leader's address
        if addr:
            self.peers[new_leader] = {'addr': tuple(addr), 'last_seen': time.time()}
            
        # Clear catalog on new leader election (or request rebuild)
        self.global_catalog = {}

    def handle_publish(self, message, addr):
        """Handle PUBLISH message (Leader only)."""
        if self.state == LEADER:
            sender_id = message['sender_id']
            files = message['files']
            tcp_port = message['tcp_port']
            
            # If addr is None (self-publish), use localhost
            # Note: The provided snippet had an indentation issue here.
            # The 'host' variable is not used in the new logic, as 'addr[0]' is used directly.
            # Keeping the original 'if addr is None' block for consistency, though it's effectively unused
            # by the new catalog update logic.
            if addr is None:
                host = get_local_ip()
            else:
                host = addr[0]

            files = message.get('files', {})
            peer_id = message.get('sender_id') # Use sender_id from message
            port = message.get('tcp_port') # Use tcp_port from message
            
            print(f"Received PUBLISH from {peer_id}: {len(files)} files")

            # Store in global catalog
            # Catalog structure: {filename: [{peer_id, host, port, size, hash}, ...]}
            
            # If files is a list (old protocol), convert to dict
            if isinstance(files, list):
                new_files = {f: {'size': 0, 'hash': None} for f in files}
                files = new_files

            for filename, metadata in files.items():
                if filename not in self.global_catalog:
                    self.global_catalog[filename] = []
                
                # Remove existing entry for this peer if any
                self.global_catalog[filename] = [entry for entry in self.global_catalog[filename] if entry['peer_id'] != peer_id]
                
                # Add new entry
                entry = {
                    'peer_id': peer_id,
                    'host': addr[0] if addr else get_local_ip(), # Use actual addr or localhost for self-publish
                    'port': port,
                    'size': metadata.get('size', 0),
                    'hash': metadata.get('hash')
                }
                self.global_catalog[filename].append(entry)

    def handle_query_files(self, message, addr):
        """Handle QUERY_FILES message (Leader only)."""
        if self.state == LEADER:
            print(f"Received QUERY_FILES from {message['sender_id']}")
            response = {
                'type': MSG_FILE_LIST,
                'sender_id': self.id,
                'catalog': self.global_catalog
            }
            self.unicast_socket.send_packet(response, addr)

    def handle_file_list(self, message):
        """Handle FILE_LIST response from Leader."""
        print("Received Global File List:")
        self.global_catalog = message['catalog']
        if not self.global_catalog:
            print("  (Catalog is empty)")
        else:
            for filename, peers in self.global_catalog.items():
                print(f" - {filename} (Available on {len(peers)} peers)")

    def handle_tcp_connection(self, client_sock, addr):
        """Handle incoming file transfer connections."""
        print(f"Incoming TCP connection from {addr}")
        self.file_manager.handle_transfer(client_sock)

    def heartbeat_loop(self):
        """Periodic tasks like sending heartbeats or checking leader health."""
        while self.running:
            time.sleep(2)
            if self.state == LEADER:
                # Send heartbeat to all peers (broadcast)
                # Send heartbeat to all peers (broadcast)
                msg = {'type': MSG_HEARTBEAT, 'sender_id': self.id, 'role': LEADER}
                self.unicast_socket.send_broadcast(msg)
            elif self.state == FOLLOWER:
                # Check if leader is alive
                if self.leader_id and (time.time() - self.last_leader_heartbeat > 10):
                    print(f"Leader {self.leader_id} timed out! Starting election...")
                    self.leader_id = None
                    self.election_manager.start_election()
