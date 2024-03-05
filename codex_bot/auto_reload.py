import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

class ScriptChangeHandler(PatternMatchingEventHandler):
    """A handler for detecting file changes."""
    patterns = ["*.py"]  # Watch for changes in Python files

    def __init__(self, command):
        super().__init__()
        self.command = command
        self.process = None
        self.start_process()

    def start_process(self):
        """Starts or restarts the Python script."""
        if self.process:
            self.process.kill()  # Kill the previous process
            self.process.wait()  # Wait for the process to terminate
        self.process = subprocess.Popen(self.command, shell=True)

    def on_modified(self, event):
        """Called when a file is modified."""
        print(f"{event.src_path} has changed. Reloading...")
        self.start_process()

def main():
    """Main function to set up watchdog and start the observer."""
    path = '.'  # Directory to watch; change if necessary
    command = 'poetry run start-bot'  # Command to run your bot; change if necessary

    event_handler = ScriptChangeHandler(command)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)  # Set recursive=True to watch all subdirectories
    observer.start()

    print(f"Watching for file changes in {path}. Running command '{command}' on change.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
