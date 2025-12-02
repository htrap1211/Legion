import threading
import time
import os
import shutil
import sys
from peer import Peer

def run_peer(peer, name):
    print(f"[{name}] Starting...")
    peer.start()
    try:
        while peer.running:
            time.sleep(1)
    except Exception as e:
        print(f"[{name}] Error: {e}")

def test_system():
    # Setup directories
    if os.path.exists('test_peer1'): shutil.rmtree('test_peer1')
    if os.path.exists('test_peer2'): shutil.rmtree('test_peer2')
    os.makedirs('test_peer1')
    os.makedirs('test_peer2')
    
    # Create a dummy file for Peer 1
    with open('test_peer1/test_file.txt', 'w') as f:
        f.write("Hello from Peer 1")

    # Initialize Peers
    # Use port 0 to let OS assign free ports
    peer1 = Peer(udp_port=0, tcp_port=0, shared_dir='test_peer1')
    peer2 = Peer(udp_port=0, tcp_port=0, shared_dir='test_peer2')
    
    print(f"Peer 1 ID: {peer1.id}")
    print(f"Peer 2 ID: {peer2.id}")
    
    # Start Peer 1 (Should become Leader)
    t1 = threading.Thread(target=run_peer, args=(peer1, "Peer1"), daemon=True)
    t1.start()
    
    print("Waiting for Peer 1 to initialize and become leader...")
    time.sleep(7)
    
    # Start Peer 2 (Should discover Peer 1)
    t2 = threading.Thread(target=run_peer, args=(peer2, "Peer2"), daemon=True)
    t2.start()
    
    print("Waiting for discovery...")
    time.sleep(5)
    
    # Check Discovery
    print(f"Peer 1 State: {peer1.state}, Leader: {peer1.leader_id}")
    print(f"Peer 2 State: {peer2.state}, Leader: {peer2.leader_id}")
    
    if peer2.leader_id == peer1.id:
        print("SUCCESS: Peer 2 discovered Peer 1 as leader.")
    else:
        print("FAILURE: Peer 2 did not discover Peer 1.")
        
    # Test File Transfer via Global Directory
    print("Testing Global Directory & Transfer...")
    
    # Peer 1 publishes files
    print("[Peer1] Publishing files...")
    peer1.publish_files()
    time.sleep(1)
    
    # Peer 2 queries files
    print("[Peer2] Querying files...")
    peer2.query_files()
    time.sleep(2)
    
    # Check if Peer 2 has the catalog
    if 'test_file.txt' in peer2.global_catalog:
        print("SUCCESS: Peer 2 received global catalog.")
        print("Catalog:", peer2.global_catalog)
        
        # Peer 2 downloads using smart download (lookup from catalog) to a custom folder
        # Pick the last one as it's likely the most recent (avoiding stale entries from previous runs)
        target = peer2.global_catalog['test_file.txt'][-1]
        print(f"Downloading from {target['host']}:{target['port']} to 'custom_downloads'...")
        
        # We need to call download_file with the new signature
        peer2.file_manager.download_file(target['host'], target['port'], 'test_file.txt', save_dir='custom_downloads')
    else:
        print("FAILURE: Peer 2 did not receive catalog.")
    
    time.sleep(1)
    if os.path.exists('custom_downloads/test_file.txt'):
        with open('custom_downloads/test_file.txt', 'r') as f:
            content = f.read()
        if content == "Hello from Peer 1":
            print("SUCCESS: File transfer verified (Custom Path).")
        else:
            print("FAILURE: File content mismatch.")
    else:
        print("FAILURE: File not downloaded to custom path.")
        # Check default path just in case
        if os.path.exists('test_peer2/test_file.txt'):
             print("FAILURE: File downloaded to default path instead.")

    # Test Dynamic Sharing
    print("\nTesting Dynamic Sharing...")
    # Create a dummy file outside shared dir
    external_file = "external_doc.txt"
    with open(external_file, 'w') as f:
        f.write("This is an external document.")
        
    print(f"Sharing external file '{external_file}' on Peer 1...")
    if peer1.file_manager.share_file(external_file):
        peer1.publish_files()
        time.sleep(1)
        
        # Peer 2 should see it
        print("[Peer2] Searching for new file...")
        peer2.query_files()
        time.sleep(1)
        
        if 'external_doc.txt' in peer2.global_catalog:
            print("SUCCESS: Dynamic sharing verified.")
        else:
            print("FAILURE: Shared file not found in catalog.")
    else:
        print("FAILURE: Could not share file.")
        
    # Cleanup external file
    if os.path.exists(external_file):
        os.remove(external_file)

    # Test Follower -> Leader Transfer
    # Test Follower -> Leader Transfer
    print("\nTesting Follower -> Leader Transfer...")
    
    # Identify who is Leader and who is Follower
    if peer1.state == 'LEADER':
        leader_peer = peer1
        follower_peer = peer2
        leader_name = "Peer1"
        follower_name = "Peer2"
    else:
        leader_peer = peer2
        follower_peer = peer1
        leader_name = "Peer2"
        follower_name = "Peer1"
        
    print(f"{leader_name} is Leader, {follower_name} is Follower.")
    
    follower_file = "follower_doc.txt"
    with open(follower_file, 'w') as f:
        f.write("Hello from the Follower!")
        
    print(f"Sharing file '{follower_file}' on {follower_name} (Follower)...")
    if follower_peer.file_manager.share_file(follower_file):
        follower_peer.publish_files()
        time.sleep(1)
        
        # Leader should see it in its own catalog
        print(f"[{leader_name}] Checking catalog for follower file...")
        if 'follower_doc.txt' in leader_peer.global_catalog:
            print("Leader sees the file. Downloading...")
            # Leader downloads from Follower
            target = leader_peer.global_catalog['follower_doc.txt'][0]
            leader_peer.file_manager.download_file(target['host'], target['port'], 'follower_doc.txt', 'leader_downloads', target['hash'])
            
            # Verify download
            time.sleep(1)
            if os.path.exists('leader_downloads/follower_doc.txt'):
                print("SUCCESS: Leader downloaded file from Follower.")
            else:
                print("FAILURE: Leader failed to download file.")
        else:
            print("FAILURE: Leader did not receive publication from Follower.")
            
    # Cleanup files
    if os.path.exists(follower_file):
        os.remove(follower_file)
    if os.path.exists('leader_downloads'):
        shutil.rmtree('leader_downloads')

    # Cleanup
    peer1.running = False
    peer2.running = False
    sys.exit(0)

if __name__ == "__main__":
    test_system()
