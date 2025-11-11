
from dotenv import load_dotenv
import os

load_dotenv()

# Debug: Print what's loaded
print("=== DEBUG: Environment Variables ===")
print(f"DB_HOST: {os.getenv('DB_HOST')}")
print(f"DB_PORT: {os.getenv('DB_PORT')}")
print(f"DB_USER: {os.getenv('DB_USER')}")
print(f"DB_PASSWORD: {'*' * len(os.getenv('DB_PASSWORD', ''))}")
print("====================================\n")

# Test DNS resolution first
import socket
try:
    host = os.getenv('DB_HOST')
    print(f"Attempting DNS lookup for: {host}")
    ip = socket.gethostbyname(host)
    print(f"✓ DNS resolved to: {ip}\n")
except socket.gaierror as e:
    print(f"✗ DNS lookup failed: {e}")
    print("This means the hostname doesn't exist or can't be reached.\n")
    exit(1)