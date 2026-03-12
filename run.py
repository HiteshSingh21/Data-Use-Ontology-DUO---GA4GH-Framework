import subprocess
import os
import time

def main():
    print("Starting FastAPI Backend...")
    # Start FastAPI in the background
    backend_process = subprocess.Popen(
        [os.path.join("venv", "Scripts", "python"), "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    time.sleep(3) # Wait for backend to initialize
    
    print("Starting Streamlit Frontend...")
    frontend_process = subprocess.Popen(
        [os.path.join("venv", "Scripts", "streamlit"), "run", "frontend/app.py"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    try:
        frontend_process.wait()
    except KeyboardInterrupt:
        print("Shutting down...")
        backend_process.terminate()
        frontend_process.terminate()

if __name__ == "__main__":
    main()
