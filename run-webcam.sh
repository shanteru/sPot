#!/bin/bash

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Creating .env file. Please edit it with your AWS credentials and settings."
  cat > .env << EOF
# AWS Credentials
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=
export AWS_SESSION_TOKEN=

# KVS Settings
export KVS_STREAM_NAME=
export AWS_REGION=us-east-1
EOF

  echo ".env file created. Please edit it with your credentials and settings."
  exit 1
fi

# Source the .env file to set environment variables
source .env

# Check if virtual environment exists, create if it doesn't
if [ ! -d "kvs_env" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv kvs_env
  
  # Activate virtual environment
  source kvs_env/bin/activate
  
  # Install requirements
  echo "Installing required packages..."
  pip install -r requirements.txt
else
  # Activate virtual environment
  source kvs_env/bin/activate
fi

# Run the webcam-to-kvs script
echo "Starting webcam streaming to KVS..."
python webcam-to-kvs.py --stream-name $KVS_STREAM_NAME --region $AWS_REGION