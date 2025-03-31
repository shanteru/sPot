#!/usr/bin/env python3
"""
Monitor a directory for new image files and upload them to S3.
Works with GStreamer's multifilesink to create a frame extraction and upload pipeline.
"""

import os
import time
import sys
import argparse
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageUploader(FileSystemEventHandler):
    def __init__(self, watch_dir, s3_bucket, s3_prefix, region, delete_after_upload=True):
        """
        Initialize the image uploader
        
        Args:
            watch_dir (str): Directory to watch for new image files
            s3_bucket (str): S3 bucket name
            s3_prefix (str): Prefix (path) within the S3 bucket
            region (str): AWS region
            delete_after_upload (bool): Whether to delete local files after upload
        """
        self.watch_dir = watch_dir
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip('/') + '/'  # Ensure prefix ends with /
        self.delete_after_upload = delete_after_upload
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=region)
        
        # Keep track of processed files
        self.processed_files = set()
        
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and self._is_image_file(event.src_path):
            # Check if we've already processed this file
            if event.src_path in self.processed_files:
                return
                
            # Wait a moment to ensure file is fully written
            time.sleep(0.5)
            
            # Upload file to S3
            self._upload_file(event.src_path)
            
            # Add to processed files
            self.processed_files.add(event.src_path)
            
            # Clean up set periodically to prevent memory growth
            if len(self.processed_files) > 1000:
                self.processed_files = set(list(self.processed_files)[-500:])
    
    def _is_image_file(self, file_path):
        """Check if file is an image based on extension"""
        extensions = ('.jpg', '.jpeg', '.png')
        return file_path.lower().endswith(extensions)
    
    def _upload_file(self, file_path):
        """Upload a file to S3"""
        try:
            # Get filename for the S3 key
            filename = os.path.basename(file_path)
            
            # Create a timestamp string for the S3 path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Create S3 key (path within bucket)
            s3_key = f"{self.s3_prefix}sPotVideoAnalysis/{timestamp}_{filename}"
            
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.s3_bucket,
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )
            
            logger.info(f"Uploaded {filename} to s3://{self.s3_bucket}/{s3_key}")
            
            # Delete local file if configured to do so
            if self.delete_after_upload:
                os.remove(file_path)
                logger.debug(f"Deleted local file {file_path}")
                
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
    
    def process_existing_files(self):
        """Process any existing files in the watch directory"""
        for filename in os.listdir(self.watch_dir):
            file_path = os.path.join(self.watch_dir, filename)
            if os.path.isfile(file_path) and self._is_image_file(file_path):
                self._upload_file(file_path)
                self.processed_files.add(file_path)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Watch a directory and upload new images to S3')
    parser.add_argument('--dir', default='/tmp', help='Directory to watch for images')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', default='uploads/images/temp/', help='S3 prefix (path)')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    parser.add_argument('--keep-files', action='store_true', help='Keep local files after upload')
    
    args = parser.parse_args()
    
    # Ensure the watch directory exists
    if not os.path.isdir(args.dir):
        logger.error(f"Watch directory {args.dir} does not exist")
        sys.exit(1)
    
    # Check AWS credentials
    if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        sys.exit(1)
    
    # Create uploader
    uploader = ImageUploader(
        watch_dir=args.dir,
        s3_bucket=args.bucket,
        s3_prefix=args.prefix,
        region=args.region,
        delete_after_upload=not args.keep_files
    )
    
    # Process any existing files
    uploader.process_existing_files()
    
    # Set up watchdog observer
    observer = Observer()
    observer.schedule(uploader, args.dir, recursive=False)
    observer.start()
    
    logger.info(f"Watching {args.dir} for new images to upload to s3://{args.bucket}/{args.prefix}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping image uploader")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    main()