# 1. Install Gstreamer locally in my mac
It will take quite a while, just note that this is done locally. 
```bash
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly
```

# 2. Install the KVS Producer SDK 
```bash
git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git
cd amazon-kinesis-video-streams-producer-sdk-cpp
mkdir build
cd build
cmake .. -DBUILD_GSTREAMER_PLUGIN=ON
make
```

# 3. Your Environment Variables Set up 
Make a `.env` file, referencing the `.env-example` 

# 4. Stream webcam to KVS
I have a stream in KVS named `sPotVideoAnalysis`
```bash
gst-launch-1.0 autovideosrc ! videoconvert ! video/x-raw,format=I420,width=640,height=480 ! \
  h264enc ! h264parse ! kvssink stream-name=sPotVideoAnalysis &
```

# In another terminal or script:
# 5. Extract frames and upload to S3
```bash
gst-launch-1.0 kvssrc stream-name=sPotVideoAnalysis ! \
  h264parse ! avdec_h264 ! videoconvert ! videorate ! video/x-raw,framerate=1/1 ! \
  jpegenc ! multifilesink location=/tmp/frame-%05d.jpg post-messages=true
```

