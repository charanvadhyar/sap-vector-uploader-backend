import requests
import json
import os
from dotenv import load_dotenv
import argparse

# Load environment variables from .env
load_dotenv()

def create_admin_user(email, password, full_name):
    """
    Create an admin user in the SAP FICO Uploader backend
    """
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/auth/register"

    # Prepare user data
    user_data = {
        "email": email,
        "password": password,
        "full_name": full_name,
        "is_admin": True
    }

    try:
        # Make the request to create the user
        response = requests.post(endpoint, json=user_data)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        result = response.json()
        print(f"Admin user created successfully!")
        print(f"Email: {result['email']}")
        print(f"Name: {result['full_name']}")
        print(f"Admin: {result['is_admin']}")
        print("\nYou can now use these credentials to log in to the application.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error creating admin user: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json().get('detail', 'Unknown error')
                print(f"Server response: {error_detail}")
            except:
                print(f"Status code: {e.response.status_code}")
                print(f"Response: {e.response.text}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an admin user for SAP FICO Uploader")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", required=True, help="Admin full name")
    
    args = parser.parse_args()
    
    create_admin_user(args.email, args.password, args.name)
