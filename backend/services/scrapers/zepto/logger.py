import sys
import threading
import builtins
from .state import add_log_entry

_original_print = builtins.print
_target_thread = None
_lock = threading.Lock()

def _custom_print(*args, **kwargs):
    current_thread = threading.current_thread()
    # Check if the print call originates from our target background thread
    if _target_thread and current_thread.ident == _target_thread.ident:
        message = " ".join(str(arg) for arg in args)
        
        # Categorize log level dynamically from keywords
        level = "INFO"
        upper_msg = message.upper()
        if "[!]" in message or "ERROR" in upper_msg or "FAILED" in upper_msg or "EXCEPTION" in upper_msg:
            level = "ERROR"
        elif "[WARNING]" in message or "WARNING" in upper_msg or "SKIP" in upper_msg:
            level = "WARNING"
            
        add_log_entry(message, level)
        
    # Always call the original stdout print
    _original_print(*args, **kwargs)

def start_intercepting(thread):
    """Binds stdout print calls specifically for the target thread."""
    global _target_thread
    with _lock:
        _target_thread = thread
        builtins.print = _custom_print

def stop_intercepting():
    """Restores global print back to the original builtin print."""
    global _target_thread
    with _lock:
        _target_thread = None
        builtins.print = _original_print
