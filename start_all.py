import subprocess
import sys
import os
import signal
from concurrent.futures import ThreadPoolExecutor

# Store processes globally for clean termination
processes = []

def run_script(script_name):
    """Run a Python script and handle its output"""
    try:
        print(f"Starting {script_name}...")
        
        # Use python-telegram-bot's cli runner for telegram_bot.py
        if script_name == 'telegram_bot.py':
            cmd = [sys.executable, '-m', 'telegram', script_name]
        else:
            cmd = [sys.executable, script_name]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            env=os.environ.copy()  # Pass current environment variables
        )
        
        # Store process for clean termination
        processes.append(process)
        
        # Print output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"[{script_name}] {output.strip()}")
        
        # Print any errors
        stderr = process.stderr.read()
        if stderr:
            print(f"[{script_name}] Error: {stderr}")
            
        return process.poll()
    
    except Exception as e:
        print(f"Error running {script_name}: {e}")
        return 1

def signal_handler(signum, frame):
    """Handle clean termination of child processes"""
    print("\nStopping all bots...")
    for process in processes:
        try:
            if sys.platform == 'win32':
                process.terminate()
            else:
                process.send_signal(signal.SIGTERM)
        except:
            pass
    sys.exit(0)

def main():
    """Run all three scripts concurrently"""
    scripts = ['telegram_bot.py', 'run_bot.py', 'main.py']
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting all bots...")
    print("Press Ctrl+C to stop all bots\n")
    
    # Run scripts concurrently using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as executor:
        try:
            # Start all scripts
            futures = [executor.submit(run_script, script) for script in scripts]
            
            # Wait for all to complete (they should run indefinitely)
            for future in futures:
                future.result()
        
        except KeyboardInterrupt:
            signal_handler(None, None)

if __name__ == "__main__":
    main() 