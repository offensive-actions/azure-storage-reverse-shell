#!/bin/bash

# Define variables, here set via action.yml
#AZ_STORAGE_ACCOUNT_NAME=""       # Replace with your storage account name
#AZ_STORAGE_CONTAINER_NAME=""     # Replace with your container name
#AZ_STORAGE_SAS_TOKEN=""          # Replace with your sas token
#RETRY_INTERVAL=2                 # Time in seconds between retries
#MAX_RETRIES=60                   # Maximal retries without finding a new command to execute

# Save the current time in Unix format
UNIX_TIMESTAMP=$(date +%s)

# Function to download a blob
download_blob() {
  local blob_url="https://${AZ_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/${AZ_STORAGE_CONTAINER_NAME}/${COMMAND_BLOB_NAME}?${AZ_STORAGE_SAS_TOKEN}"
  curl -s -o "command.txt" "$blob_url"
}

# Function to upload a blob
upload_blob() {
  local blob_url="https://${AZ_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/${AZ_STORAGE_CONTAINER_NAME}/${RESULT_BLOB_NAME}?${AZ_STORAGE_SAS_TOKEN}"
  curl -s -X PUT \
    -H "x-ms-blob-type: BlockBlob" \
    -d "$(cat result.txt)" \
    "$blob_url"
}

# Function to get the latest counter for a given timestamp
get_latest_counter() {
  local timestamp=$1
  local latest_counter=0
  local blob_prefix="${timestamp}-"
  local blob_suffix="-command"

  # List all blobs with the prefix and suffix
  blob_list=$(curl -s "https://${AZ_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/${AZ_STORAGE_CONTAINER_NAME}?restype=container&comp=list&${AZ_STORAGE_SAS_TOKEN}" | grep -oP "(?<=<Name>).*?(?=</Name>)")

  for blob in $blob_list; do
    if [[ $blob == ${blob_prefix}* && $blob == *${blob_suffix} ]]; then
      counter=$(echo "$blob" | cut -d'-' -f2)
      if [[ $counter =~ ^[0-9]+$ ]] && (( $counter > $latest_counter )); then
        latest_counter=$counter
      fi
    fi
  done

  echo $latest_counter
}

# Step 1: Save the initial result to a blob with counter 0
RESULT_BLOB_NAME="${UNIX_TIMESTAMP}-0-result"
echo "$(whoami)@$(hostname):~$(pwd)$ " > result.txt
upload_blob

# Initialize the last processed counter
LAST_PROCESSED_COUNTER=0

# Monitor for and process new commands
while : ; do
  # Get the latest counter for the current timestamp
  LATEST_COUNTER=$(get_latest_counter "$UNIX_TIMESTAMP")

  # Check if there is a new blob to process
  if [ "$LATEST_COUNTER" -gt "$LAST_PROCESSED_COUNTER" ]; then
    
    ATTEMPT=0
    COMMAND_BLOB_NAME="${UNIX_TIMESTAMP}-${LATEST_COUNTER}-command"
    RESULT_BLOB_NAME="${UNIX_TIMESTAMP}-${LATEST_COUNTER}-result"

    # Get the blob, read the command and execute it. stop shell if "exit" is received.
    download_blob
    COMMAND=$(cat command.txt)
    if [ "$COMMAND" = "exit" ]; then
      exit 0
    else
      RESULT=$(eval "$COMMAND")
    fi

    # Write the result back to the storage account
    echo "$RESULT" > result.txt
    upload_blob

    # Clean up
    rm command.txt result.txt

    # Update the last processed counter
    LAST_PROCESSED_COUNTER=$LATEST_COUNTER
  else
    # Count tries without new commands and stop trying after given retries
    ATTEMPT=$((ATTEMPT + 1))
    if [ "$ATTEMPT" -eq "$MAX_RETRIES" ]; then
      exit 0
    fi
  fi

  # Wait before checking again
  sleep "$RETRY_INTERVAL"
done
