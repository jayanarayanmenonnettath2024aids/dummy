#!/usr/bin/env python3
"""
iTantra: Tactical Neural Walkie-Talkie Web UI Launcher
Smart India Hackathon 2026 — Problem Statement SIH26173
"""

import sys
import os
import socket
import argparse
import webbrowser
import uvicorn

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = DummyColor()
    Style = DummyColor()

from app.ui.server import create_app

def get_local_ip() -> str:
    """Retrieve local LAN IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_banner(web_port: int, tcp_port: int, peer_host: str, peer_port: int, local_ip: str):
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}========================================================================
   _ _____             _             
  (_)  ___|           | |            
   _| |_ __ _ _ __  __| |__  _ __ __ _ 
  | |  _/ _` | '_ \\/ _` | '_ \\| '__/ _` |
  | | || (_| | | | | (_| | |_) | | | (_| |
  |_|\\_|\\__,_|_| |_|\\__,_|_.__/|_|  \\__,_|
  
  TACTICAL NEURAL WALKIE-TALKIE // MISSION CONTROL WEB UI
  Smart India Hackathon 2026 -- SIH26173
========================================================================{Style.RESET_ALL}
{Fore.GREEN}[OK] 100% Local Inference  |  [OK] Zero Cloud API  |  [OK] Internet-Independent
[OK] Audio NOT Transmitted  |  [OK] Half-Duplex Push-To-Talk Node{Fore.RESET}
========================================================================

  {Fore.YELLOW}Local Web Dashboard :{Fore.RESET} {Fore.CYAN}{Style.BRIGHT}http://localhost:{web_port}{Style.RESET_ALL}
  {Fore.YELLOW}Network Dashboard   :{Fore.RESET} {Fore.CYAN}{Style.BRIGHT}http://{local_ip}:{web_port}{Style.RESET_ALL}
  {Fore.YELLOW}TCP Listen Port     :{Fore.RESET} {tcp_port}
  {Fore.YELLOW}Target Peer Node    :{Fore.RESET} {peer_host}:{peer_port}

========================================================================
"""
    print(banner)

def main():
    parser = argparse.ArgumentParser(description="iTantra Tactical Web UI")
    parser.add_argument("--web-port", type=int, default=8000, help="Web dashboard port (default: 8000)")
    parser.add_argument("--tcp-port", type=int, default=65432, help="TCP listen port for speech packets (default: 65432)")
    parser.add_argument("--peer-host", type=str, default="127.0.0.1", help="Default target peer IP (default: 127.0.0.1)")
    parser.add_argument("--peer-port", type=int, default=65432, help="Default target peer TCP port (default: 65432)")
    parser.add_argument("--lang", type=str, default="en", help="Language code (default: 'en')")
    parser.add_argument("--node-name", type=str, default=None, help="Custom identifier for this device node")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")

    args = parser.parse_args()

    local_ip = get_local_ip()
    print_banner(args.web_port, args.tcp_port, args.peer_host, args.peer_port, local_ip)

    app = create_app(
        tcp_listen_port=args.tcp_port,
        peer_host=args.peer_host,
        peer_port=args.peer_port,
        language=args.lang,
        node_name=args.node_name
    )

    if not args.no_browser:
        # Open web dashboard in default browser after short delay
        import threading
        def open_tab():
            import time
            time.sleep(1.0)
            webbrowser.open(f"http://localhost:{args.web_port}")
        threading.Thread(target=open_tab, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=args.web_port, log_level="warning")

if __name__ == "__main__":
    main()
