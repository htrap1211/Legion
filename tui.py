try:
    import curses
except ImportError:
    import sys
    print("Error: 'curses' module not found.")
    print("On Windows, please install it via: pip install windows-curses")
    sys.exit(1)

import sys
import threading
import time
from queue import Queue

class TUI:
    def __init__(self, peer):
        self.peer = peer
        self.log_queue = Queue()
        self.input_queue = Queue()
        self.running = True
        
        # Redirect stdout to capture print statements
        self.original_stdout = sys.stdout
        sys.stdout = self

    def write(self, text):
        """Capture stdout and put it in the log queue."""
        if text.strip():
            for line in text.split('\n'):
                if line.strip():
                    self.log_queue.put(line.strip())

    def flush(self):
        pass

    def start(self):
        """Start the curses application."""
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        # Setup colors
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Hacker Green
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Info Cyan
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)    # Error Red
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_GREEN)  # Inverted Header

        curses.curs_set(1) # Show cursor
        stdscr.nodelay(True) # Non-blocking input
        stdscr.timeout(100) # Refresh every 100ms

        # Layout dimensions
        height, width = stdscr.getmaxyx()
        header_height = 3
        footer_height = 3
        log_height = height - header_height - footer_height

        # Windows
        header_win = curses.newwin(header_height, width, 0, 0)
        log_win = curses.newwin(log_height, width, header_height, 0)
        footer_win = curses.newwin(footer_height, width, height - footer_height, 0)
        
        # Log buffer
        logs = []
        input_buffer = ""
        
        while self.running and self.peer.running:
            # --- HEADER ---
            header_win.erase()
            header_win.bkgd(' ', curses.color_pair(4))
            header_win.box()
            status = f" ID: {self.peer.id[:8]}... | Role: {self.peer.state} | Leader: {str(self.peer.leader_id)[:8]}... "
            header_win.addstr(1, 2, status[:width-4], curses.A_BOLD)
            header_win.refresh()

            # --- LOGS ---
            while not self.log_queue.empty():
                logs.append(self.log_queue.get())
                if len(logs) > 100: # Keep last 100 logs
                    logs.pop(0)
            
            log_win.erase()
            log_win.bkgd(' ', curses.color_pair(1))
            log_win.box()
            
            # Draw logs
            available_lines = log_height - 2
            start_idx = max(0, len(logs) - available_lines)
            for i, log in enumerate(logs[start_idx:]):
                try:
                    log_win.addstr(i + 1, 2, log[:width-4])
                except:
                    pass # Ignore if line too long
            log_win.refresh()

            # --- FOOTER (INPUT) ---
            footer_win.erase()
            footer_win.bkgd(' ', curses.color_pair(2))
            footer_win.box()
            footer_win.addstr(1, 2, f"> {input_buffer}")
            footer_win.refresh()

            # --- INPUT HANDLING ---
            try:
                key = stdscr.getch()
                if key != -1:
                    if key == 10: # Enter
                        self.input_queue.put(input_buffer)
                        input_buffer = ""
                    elif key == 127 or key == curses.KEY_BACKSPACE: # Backspace
                        input_buffer = input_buffer[:-1]
                    elif 32 <= key <= 126: # Printable chars
                        input_buffer += chr(key)
            except:
                pass

            time.sleep(0.05)

        # Cleanup
        sys.stdout = self.original_stdout
