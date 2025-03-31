#!/usr/bin/env python3
"""
Capture video from macOS webcam and send to Kinesis Video Streams
"""

import os
import time
import cv2
import boto3
import numpy as np
import threading
import logging
from datetime import datetime
from amazon_kinesis_video_streams.producer import KvsClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebcamToKVS:
    def __init__(self, stream_name, region="us-east-1", camera_index=0, 
                 resolution=(640, 480), fps=15):
        """
        Initialize the Webcam to KVS streamer
        
        Args:
            stream_name (str): Name of the Kinesis Video Stream
            region (str): AWS region
            camera_index (int): Index of the camera to use (usually 0 for built-in webcam)
            resolution (tuple): Width and height of video
            fps (int): Frames per second
        """
        self.stream_name = stream_name
        self.region = region
        self.camera_index = camera_index
        self.width, self.height = resolution
        self.fps = fps
        
        # Initialize flag for stopping
        self.running = False
        
        # Initialize AWS clients
        self.kvs_client = boto3.client('kinesisvideo', region_name=self.region)
        
        # Initialize KVS producer
        self.producer = KvsClient(
            stream_name=self.stream_name,
            region_name=self.region,
            access_key=os.environ.get('AWS_ACCESS_KEY_ID'),
            secret_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            session_token=os.environ.get('AWS_SESSION_TOKEN')
        )
        
    def initialize_webcam(self):
        """Initialize the webcam capture"""
        self.cap = cv2.VideoCapture(self.camera_index)
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # Check if camera opened successfully
        if not self.cap.isOpened():
            logger.error("Error: Could not open webcam")
            return False
        
        # Let the camera warm up
        time.sleep(1)
        return True
    
    def start_streaming(self):
        """Start capturing from webcam and streaming to KVS"""
        if not self.initialize_webcam():
            return
        
        logger.info(f"Starting stream to {self.stream_name}")
        
        # Start the KVS producer
        self.producer.start()
        
        self.running = True
        start_time = time.time()
        frame_count = 0
        
        try:
            while self.running:
                # Capture frame-by-frame
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.error("Failed to capture frame from webcam")
                    break
                
                # Encode frame to JPEG
                _, jpeg_frame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                # Send frame to KVS
                timestamp = int(time.time() * 1000)  # Milliseconds
                self.producer.put_frame(jpeg_frame.tobytes(), timestamp=timestamp)
                
                frame_count += 1
                elapsed_time = time.time() - start_time
                
                # Calculate actual FPS and log every 5 seconds
                if elapsed_time >= 5:
                    actual_fps = frame_count / elapsed_time
                    logger.info(f"Streaming at {actual_fps:.2f} FPS")
                    start_time = time.time()
                    frame_count = 0
                
                # Control frame rate
                time.sleep(max(0, 1.0/self.fps - (time.time() - start_time)))
                
        except KeyboardInterrupt:
            logger.info("Streaming interrupted")
        finally:
            self.stop_streaming()
    
    def stop_streaming(self):
        """Stop streaming and clean up resources"""
        self.running = False
        
        # Stop the producer
        if hasattr(self, 'producer'):
            self.producer.stop()
        
        # Release the capture
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
        
        logger.info("Streaming stopped")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Stream webcam video to Kinesis Video Streams')
    parser.add_argument('--stream-name', required=True, help='Kinesis Video Stream name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--camera', type=int, default=0, help='Camera index')
    parser.add_argument('--width', type=int, default=640, help='Video width')
    parser.add_argument('--height', type=int, default=480, help='Video height')
    parser.add_argument('--fps', type=int, default=15, help='Frames per second')
    
    args = parser.parse_args()
    
    # Check for AWS credentials
    if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
        return
    
    streamer = WebcamToKVS(
        stream_name=args.stream_name,
        region=args.region,
        camera_index=args.camera,
        resolution=(args.width, args.height),
        fps=args.fps
    )
    
    streamer.start_streaming()

if __name__ == "__main__":
    main()