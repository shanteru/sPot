#!/usr/bin/env python3
"""
Capture frames from webcam and upload directly to S3 at regular intervals
"""

import os
import time
import cv2
import boto3
import logging
from datetime import datetime
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebcamToS3:
    def __init__(self, bucket_name, prefix, region="ap-southeast-1", 
                 interval=1.0, camera_index=0, resolution=(640, 480),
                 format="jpg", quality=85):
        """
        Initialize the webcam to S3 uploader
        
        Args:
            bucket_name (str): S3 bucket name
            prefix (str): Prefix (path) in the S3 bucket
            region (str): AWS region
            interval (float): Seconds between frame captures
            camera_index (int): Camera device index (usually 0 for built-in webcam)
            resolution (tuple): Width and height for captured frames
            format (str): Image format (jpg, png)
            quality (int): JPEG quality (1-100)
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') + '/'
        self.region = region
        self.interval = interval
        self.camera_index = camera_index
        self.width, self.height = resolution
        self.format = format
        self.quality = quality
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', region_name=self.region)
        
        # Initialize webcam
        self.cap = None
        
    def initialize_webcam(self):
        """Initialize the webcam"""
        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # Check if camera opened successfully
        if not self.cap.isOpened():
            logger.error("Error: Could not open webcam")
            return False
        
        # Wait for camera to initialize
        time.sleep(1)
        return True
    
    def capture_and_upload(self):
        """Capture a frame and upload it to S3"""
        # Capture frame
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to capture frame")
            return False
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}.{self.format}"
        
        # Create temporary file
        temp_path = f"/tmp/{filename}"
        
        # Save frame to temporary file
        if self.format.lower() == 'jpg':
            cv2.imwrite(temp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        else:
            cv2.imwrite(temp_path, frame)
        
        # Upload to S3
        try:
            # Create S3 key (path in bucket)
            s3_key = f"{self.prefix}sPotVideoAnalysis/{filename}"
            
            # Upload file
            self.s3_client.upload_file(
                temp_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': f'image/{self.format}'}
            )
            
            logger.info(f"Uploaded {filename} to s3://{self.bucket_name}/{s3_key}")
            
            # Remove temporary file
            os.remove(temp_path)
            return True
            
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False
    
    def start_capture(self):
        """Start capturing and uploading frames"""
        if not self.initialize_webcam():
            return
        
        logger.info(f"Starting webcam capture every {self.interval} seconds")
        logger.info(f"Uploading to s3://{self.bucket_name}/{self.prefix}")
        
        try:
            count = 0
            start_time = time.time()
            
            while True:
                # Capture and upload frame
                if self.capture_and_upload():
                    count += 1
                
                # Display stats every 10 frames
                if count % 10 == 0:
                    elapsed = time.time() - start_time
                    fps = count / elapsed
                    logger.info(f"Captured {count} frames, average rate: {fps:.2f} fps")
                
                # Wait for next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            logger.info("Capture interrupted by user")
        finally:
            self.stop_capture()
    
    def stop_capture(self):
        """Stop capture and release resources"""
        if self.cap is not None:
            self.cap.release()
        
        logger.info("Capture stopped")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Capture webcam frames and upload to S3')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', default='uploads/images/temp/', help='S3 prefix (path)')
    parser.add_argument('--region', default='ap-southeast-1', help='AWS region')
    parser.add_argument('--interval', type=float, default=1.0, help='Capture interval in seconds')
    parser.add_argument('--camera', type=int, default=0, help='Camera index')
    parser.add_argument('--width', type=int, default=640, help='Image width')
    parser.add_argument('--height', type=int, default=480, help='Image height')
    parser.add_argument('--format', choices=['jpg', 'png'], default='jpg', help='Image format')
    parser.add_argument('--quality', type=int, default=85, help='JPEG quality (1-100)')
    
    args = parser.parse_args()
    
    # Check AWS credentials
    if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        return
    
    # Start capture
    uploader = WebcamToS3(
        bucket_name=args.bucket,
        prefix=args.prefix,
        region=args.region,
        interval=args.interval,
        camera_index=args.camera,
        resolution=(args.width, args.height),
        format=args.format,
        quality=args.quality
    )
    
    uploader.start_capture()

if __name__ == "__main__":
    main()