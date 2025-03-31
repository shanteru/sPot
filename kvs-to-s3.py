#!/usr/bin/env python3

import os
import time
import uuid
import cv2
import boto3
import gi
import logging
import subprocess
import threading
from datetime import datetime

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KVSToS3ImageExtractor:
    def __init__(self):
        # Get configuration from environment variables
        self.kvs_stream_name = os.environ.get('KVS_STREAM_NAME')
        self.s3_bucket_name = os.environ.get('S3_BUCKET_NAME')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.image_interval = float(os.environ.get('IMAGE_INTERVAL', '1.0'))
        self.image_format = os.environ.get('IMAGE_FORMAT', 'jpg')
        self.image_quality = int(os.environ.get('IMAGE_QUALITY', '85'))
        
        # Validate required parameters
        if not self.kvs_stream_name:
            raise ValueError("KVS_STREAM_NAME environment variable must be set")
        if not self.s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable must be set")
        
        # Initialize AWS S3 client
        self.s3_client = boto3.client('s3', region_name=self.region)
        
        # Initialize GStreamer
        Gst.init(None)
        
        # Create temporary directory for images
        self.temp_dir = f"/tmp/kvs_images_{uuid.uuid4().hex}"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Initialize pipeline
        self.pipeline = None
        self.loop = None
        
    def build_pipeline(self):
        """Build the GStreamer pipeline"""
        # This pipeline:
        # 1. Uses kvssrc to read from the Kinesis Video Stream
        # 2. Parses the H.264 video
        # 3. Decodes the H.264 video
        # 4. Converts to raw video format
        # 5. Sets framerate to extract images at specified interval
        # 6. Uses a tee to split the pipeline
        # 7. One branch goes to fakesink (to continue processing)
        # 8. Other branch goes to appsink (for image extraction)
        pipeline_str = (
            f"kvssrc stream-name={self.kvs_stream_name} aws-region={self.region} "
            f"! h264parse ! avdec_h264 ! videoconvert ! videorate ! "
            f"video/x-raw,framerate=1/{self.image_interval} ! tee name=t "
            f"t. ! queue ! fakesink "
            f"t. ! queue ! appsink name=image_sink"
        )
        
        logger.info(f"Creating pipeline: {pipeline_str}")
        
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # Get the appsink element and configure it
            self.image_sink = self.pipeline.get_by_name("image_sink")
            self.image_sink.set_property("emit-signals", True)
            self.image_sink.connect("new-sample", self.on_new_sample)
            
            # Set up bus to handle messages
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", self.on_error)
            bus.connect("message::eos", self.on_eos)
            
            return True
        except Exception as e:
            logger.error(f"Failed to build pipeline: {e}")
            return False
            
    def on_new_sample(self, sink):
        """Handle new video frames from the appsink"""
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR
        
        # Extract buffer and caps
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        
        # Map the buffer to get access to data
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            logger.error("Failed to map buffer")
            buffer.unmap(map_info)
            return Gst.FlowReturn.ERROR
        
        try:
            # Create timestamp for image filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{self.temp_dir}/{timestamp}.{self.image_format}"
            
            # Get frame dimensions
            structure = caps.get_structure(0)
            width = structure.get_value('width')
            height = structure.get_value('height')
            
            # Convert buffer to OpenCV image
            import numpy as np
            frame = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            )
            
            # Save the image
            if self.image_format == 'jpg':
                cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, self.image_quality])
            else:
                cv2.imwrite(filename, frame)
                
            # Upload to S3 in a separate thread
            threading.Thread(
                target=self.upload_to_s3,
                args=(filename, timestamp)
            ).start()
            
            logger.info(f"Extracted image: {timestamp}.{self.image_format}")
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
        finally:
            buffer.unmap(map_info)
            
        return Gst.FlowReturn.OK
    
    def upload_to_s3(self, filepath, timestamp):
        """Upload` a file to S3"""
        try:
            # Get the S3 prefix from environment variable or use default
            s3_prefix = os.environ.get('S3_PREFIX', 'frames/')
            
            # Build the complete S3 key (path)
            s3_key = f"{s3_prefix}{self.kvs_stream_name}/{timestamp}.{self.image_format}"
            
            # Upload the file to S3
            self.s3_client.upload_file(
                filepath, 
                self.s3_bucket_name, 
                s3_key,
                ExtraArgs={'ContentType': f'image/{self.image_format}'}
            )
            
            logger.info(f"Uploaded to S3: s3://{self.s3_bucket_name}/{s3_key}")
            
            # Delete the local file
            os.remove(filepath)
        except Exception as e:
            logger.error(f"F`ailed to upload to S3: {e}")
    
    def on_error(self, bus, msg):
        """Handle pipeline errors"""
        err, debug = msg.parse_error()
        logger.error(f"Pipeline error: {err.message}, {debug}")
        if self.loop and self.loop.is_running():
            self.loop.quit()
            
    def on_eos(self, bus, msg):
        """Handle end of stream"""
        logger.info("End of stream reached")
        if self.loop and self.loop.is_running():
            self.loop.quit()
            
    def start(self):
        """Start the pipeline and begin processing"""
        if not self.build_pipeline():
            logger.error("Failed to build pipeline")
            return
            
        # Start the pipeline
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start pipeline")
            return
            
        logger.info(f"Started processing KVS stream: {self.kvs_stream_name}")
        
        # Create and run GLib Main Loop
        self.loop = GLib.MainLoop()
        
        try:
            self.loop.run()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources")
        
        # Stop the pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            
        # Remove temporary files
        try:
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory: {e}")
            
if __name__ == "__main__":
    extractor = KVSToS3ImageExtractor()
    extractor.start()