#!/bin/bash
# Setup and run the S3 image uploader with a Python virtual environment

# Default values for my use case 
WATCH_DIR="/tmp"
S3_BUCKET="spot-service-bucket"
S3_PREFIX="uploads/images/temp/"
AWS_REGION="ap-southeast-1"
VENV_DIR="s3_uploader_env"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
  echo "Creating .env file. Please edit it with your AWS credentials and settings."
  cat > .env << EOF
# AWS Credentials
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=

# S3 Settings
export S3_BUCKET=spot-service-bucket
export S3_PREFIX=uploads/images/temp/
export AWS_REGION=ap-southeast-1

# Image settings
export WATCH_DIR=/tmp
EOF
  
  echo ".env file created. Please edit it with your credentials and settings."
  echo "Then run this script again."
  exit 1
fi

# Source environment variables
source .env

# Check required variables
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$S3_BUCKET" ]; then
  echo "Error: Required environment variables are not set in .env file."
  echo "Please make sure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and S3_BUCKET are set."
  exit 1
fi

# Override defaults with environment variables if set
[ ! -z "$WATCH_DIR" ] && WATCH_DIR="$WATCH_DIR"
[ ! -z "$S3_BUCKET" ] && S3_BUCKET="$S3_BUCKET"
[ ! -z "$S3_PREFIX" ] && S3_PREFIX="$S3_PREFIX"
[ ! -z "$AWS_REGION" ] && AWS_REGION="$AWS_REGION"

# Check if s3-uploader.py exists
if [ ! -f "s3-uploader.py" ]; then
  echo "Error: s3-uploader.py script not found in current directory."
  exit 1
fi

# Set up Python virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
  
  # Activate virtual environment and install dependencies
  source "$VENV_DIR/bin/activate"
  pip install boto3 watchdog
  
  echo "Virtual environment setup complete."
else
  # Just activate the existing environment
  source "$VENV_DIR/bin/activate"
fi

echo "Starting S3 uploader to watch $WATCH_DIR and upload to s3://$S3_BUCKET/$S3_PREFIX"
echo "Press Ctrl+C to stop."

# Run the uploader script
python s3-uploader.py --dir "$WATCH_DIR" --bucket "$S3_BUCKET" --prefix "$S3_PREFIX" --region "$AWS_REGION"

# Deactivate virtual environment when done
deactivate