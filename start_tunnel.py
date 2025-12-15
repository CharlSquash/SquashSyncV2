import os
import sys
import subprocess
import time
from pyngrok import ngrok, conf

def start_tunnel():
    """
    Starts an ngrok tunnel and the Django development server.
    """
    # 1. Get Auth Token
    auth_token = os.environ.get("NGROK_AUTHTOKEN")
    
    if not auth_token:
        print("\n" + "="*60)
        print("NGROK AUTH TOKEN REQUIRED")
        print("="*60)
        print("You can find your auth token at: https://dashboard.ngrok.com/get-started/your-authtoken")
        print("To avoid this step in the future, set the NGROK_AUTHTOKEN environment variable.")
        print("-" * 60)
        auth_token = input("Enter your Ngrok Auth Token: ").strip()
    
    if not auth_token:
        print("Error: Auth token is required to proceed.")
        sys.exit(1)

    # 2. Configure Ngrok
    try:
        ngrok.set_auth_token(auth_token)
    except Exception as e:
        print(f"Error setting auth token: {e}")
        sys.exit(1)

    # 3. Start Tunnel
    print("\nStarting Ngrok tunnel on port 8000...")
    try:
        # Open a HTTP tunnel on the default port 8000
        public_url = ngrok.connect(8000).public_url
        print("\n" + "*"*60)
        print(f"NGROK TUNNEL LIVE AT: {public_url}")
        print("*"*60 + "\n")
    except Exception as e:
        print(f"Failed to start ngrok tunnel: {e}")
        sys.exit(1)

    # 4. Start Django Server
    print("Starting Django Server...")
    try:
        # Run the server in a subprocess so it shares the terminal output
        # We use sys.executable to ensure we use the same python interpreter
        cmd = [sys.executable, "manage.py", "runserver", "8000"]
        subprocess.check_call(cmd)
    except KeyboardInterrupt:
        print("\nShutting down...")
        ngrok.kill()
        sys.exit(0)

if __name__ == "__main__":
    start_tunnel()
