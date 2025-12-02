import time
import threading
from networking import get_local_ip

class ElectionManager:
    def __init__(self, peer):
        self.peer = peer
        self.election_in_progress = False
        self.last_election_time = 0

    def start_election(self):
        """Initiate the Bully Election algorithm."""
        if self.election_in_progress:
            return
        
        print(f"Peer {self.peer.id} starting election...")
        self.election_in_progress = True
        self.last_election_time = time.time()
        
        # Multicast ELECTION message
        msg = {
            'type': 'ELECTION',
            'sender_id': self.peer.id
        }
        self.peer.unicast_socket.send_broadcast(msg)
        
        # Wait for responses (Bully algorithm: if no higher ID responds, I win)
        # In a real Bully algo, we'd unicast to higher IDs. 
        # Here, we multicast and wait for anyone with a higher ID to take over.
        threading.Timer(3.0, self.check_election_result).start()

    def handle_election_message(self, message):
        """Handle incoming ELECTION message."""
        sender_id = message['sender_id']
        
        if sender_id > self.peer.id:
            # Someone with higher ID is holding an election or responding.
            # We yield and wait for Coordinator announcement.
            self.election_in_progress = False
            print(f"Yielding election to higher ID: {sender_id}")
        elif sender_id < self.peer.id:
            # Someone with lower ID started election. We must take over.
            if not self.election_in_progress:
                self.start_election()
            # Send ALIVE/OK message to the lower ID (optional in this simplified multicast version)
            # For now, just starting our own election is enough to suppress them.

    def check_election_result(self):
        """Called after timeout. If no higher ID took over, declare self as Leader."""
        if self.election_in_progress:
            print(f"No higher peer responded. Peer {self.peer.id} declaring victory!")
            self.declare_victory()

    def declare_victory(self):
        """Announce self as the new Coordinator."""
        self.peer.state = 'LEADER'
        self.peer.leader_id = self.peer.id
        self.election_in_progress = False
        
        msg = {
            'type': 'COORDINATOR',
            'sender_id': self.peer.id,
            'addr': (get_local_ip(), self.peer.unicast_socket.port)
        }
        self.peer.unicast_socket.send_broadcast(msg)
        print("I am the new Coordinator!")
