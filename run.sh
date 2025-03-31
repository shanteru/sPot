#!/bin/bash

# Ensure the script directory contains all necessary files
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if .env file exists, create it if not
if [ ! -f .env ]; then
  echo "Creating .env file. Please edit it with your AWS credentials and settings."
  cat > .env << EOF
# AWS Credentials
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=

# KVS and S3 Settings
KVS_STREAM_NAME=
S3_BUCKET_NAME=
S3_PREFIX=
AWS_REGION=us-east-1

# Image Settings
IMAGE_INTERVAL=1.0
IMAGE_FORMAT=jpg
IMAGE_QUALITY=85
EOF

  echo ".env file created. Please edit it with your credentials and settings."
  exit 1
fi

# Source the .env file
source .env

# Check required variables
if [ -z "$KVS_STREAM_NAME" ] || [ -z "$S3_BUCKET_NAME" ] || [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
  echo "Error: Required environment variables are not set in .env file."
  echo "Please make sure KVS_STREAM_NAME, S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY are set."
  exit 1
fi

# Build and run the container using docker-compose
echo "Building and starting KVS to S3 image extractor..."
docker-compose up --build -d

echo "Container started. View logs with: docker-compose logs -f"