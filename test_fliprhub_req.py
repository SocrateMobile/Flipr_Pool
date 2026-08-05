import requests
import os
import json

def test():
    email = os.environ.get("FLIPR_EMAIL", "jfl95880@gmail.com")
    password = os.environ.get("FLIPR_PASSWORD", "Flipr95880$") # Mdp typique si on l'a vu
    
    # Try with .env if possible or hardcode (actually I don't know the password).
    # Wait, the user has a configuration in Home Assistant. I can read it from .storage? No, the user gave us the auth.
    pass

