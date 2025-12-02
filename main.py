import argparse
import time
import sys
import threading
from peer import Peer
from tui import TUI
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description='P2P File Sharing System')
    parser.add_argument('--udp-port', type=int, default=0, help='UDP port to bind to')
    parser.add_argument('--tcp-port', type=int, default=0, help='TCP port to bind to')
    parser.add_argument('--shared-dir', type=str, default='shared_files', help='Directory to share files from')
    
    args = parser.parse_args()
    
    peer = Peer(udp_port=args.udp_port, tcp_port=args.tcp_port, shared_dir=args.shared_dir)
    tui = TUI(peer)
    
    # Start Peer in a separate thread so TUI can run on main thread
    peer_thread = threading.Thread(target=peer.start, daemon=True)
    peer_thread.start()
    
    # Start TUI in a separate thread to keep main thread free? 
    # Actually curses usually wants to be on the main thread.
    # Let's run TUI on main thread.
    
    tui_thread = threading.Thread(target=tui.start, daemon=True)
    tui_thread.start()
    
    try:
        while tui.running:
            if not tui.input_queue.empty():
                cmd_str = tui.input_queue.get()
                cmd = cmd_str.strip().split()
                if not cmd:
                    continue
                    
                if cmd[0] == 'quit':
                    tui.running = False
                    break
                elif cmd[0] == 'help':
                    print("\n=== Available Commands ===")
                    print("  list                  : List your shared files")
                    print("  publish               : Announce files to the network")
                    print("  share <path>          : Share a specific file")
                    print("  search                : List all available files in network")
                    print("  download <file> [dir] : Download a file (auto-find peer)")
                    print("  cd <path>             : Change current directory")
                    print("  quit                  : Exit the application")
                    print("  <shell command>       : Run any system command (ls, pwd, etc.)")
                    print("==========================\n")
                elif cmd[0] == 'list':
                    print(f"Local files: {peer.file_manager.list_files()}")
                elif cmd[0] == 'publish':
                    if len(cmd) > 1:
                        # User provided a file, treat it like 'share'
                        filepath = cmd[1]
                        if peer.file_manager.share_file(filepath):
                            peer.publish_files()
                    else:
                        # Just announce existing files
                        peer.publish_files()
                elif cmd[0] == 'share':
                    if len(cmd) < 2:
                        print("Usage: share <filepath>")
                        continue
                    filepath = cmd[1]
                    if peer.file_manager.share_file(filepath):
                        peer.publish_files()
                elif cmd[0] == 'search':
                    peer.query_files()

                elif cmd[0] == 'download':
                    if len(cmd) < 2:
                        print("Usage: download <filename> [destination_dir] OR download <filename> <host> <port> [destination_dir]")
                        continue
                    filename = cmd[1]
                    
                    # Check for Direct Download (host port provided)
                    # Heuristic: if cmd[2] looks like an IP or cmd[3] is int? 
                    # Simpler: if len >= 4 and cmd[3] is digits, assume direct.
                    
                    is_direct = False
                    if len(cmd) >= 4 and cmd[3].isdigit():
                        is_direct = True
                        
                    if is_direct:
                        host = cmd[2]
                        port = int(cmd[3])
                        save_dir = cmd[4] if len(cmd) > 4 else None
                        threading.Thread(target=peer.file_manager.download_file, args=(host, port, filename, save_dir), daemon=True).start()
                    else:
                        # Smart Download (Global Catalog)
                        save_dir = cmd[2] if len(cmd) > 2 else None
                        
                        # Look up in global catalog
                        peers_with_file = peer.global_catalog.get(filename)
                        if peers_with_file:
                            # Pick the first one (could be random)
                            target = peers_with_file[0]
                            expected_hash = target.get('hash')
                            print(f"Found {filename} on {target['host']}:{target['port']}")
                            threading.Thread(target=peer.file_manager.download_file, args=(target['host'], target['port'], filename, save_dir, expected_hash), daemon=True).start()
                        else:
                            print(f"File {filename} not found in global catalog. Try 'search' first.")
                elif cmd[0] == 'cd':
                    try:
                        path = cmd[1] if len(cmd) > 1 else os.path.expanduser('~')
                        os.chdir(path)
                        print(f"Changed directory to {os.getcwd()}")
                    except Exception as e:
                        print(f"Error changing directory: {e}")
                else:
                    # Try executing as system command
                    try:
                        # Windows compatibility: alias 'ls' to 'dir'
                        if os.name == 'nt' and cmd[0] == 'ls':
                            cmd_str = 'dir ' + ' '.join(cmd[1:])
                            
                        # Run command and capture output
                        result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
                        if result.stdout:
                            print(result.stdout.strip())
                        if result.stderr:
                            print(f"Error: {result.stderr.strip()}")
                    except Exception as e:
                        print(f"Command failed: {e}")
            
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        tui.running = False
        peer.running = False
        # Restore stdout just in case
        sys.stdout = sys.__stdout__
        sys.exit(0)

if __name__ == '__main__':
    main()
