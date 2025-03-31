FROM public.ecr.aws/amazonlinux/amazonlinux:2

# Install dependencies
RUN yum update -y && \
    yum install -y \
    gcc-c++ \
    pkgconfig \
    cmake3 \
    make \
    openssl-devel \
    curl-devel \
    log4cplus-devel \
    git \
    python3 \
    python3-devel \
    python3-pip \
    wget

# Install GStreamer and plugins
RUN amazon-linux-extras install -y epel && \
    yum install -y \
    gstreamer1 \
    gstreamer1-devel \
    gstreamer1-plugins-base \
    gstreamer1-plugins-good \
    gstreamer1-plugins-bad-free \
    gstreamer1-plugins-ugly-free \
    opencv \
    opencv-devel

# Install AWS KVS SDK
WORKDIR /opt
RUN git clone https://github.com/awslabs/amazon-kinesis-video-streams-producer-sdk-cpp.git
WORKDIR /opt/amazon-kinesis-video-streams-producer-sdk-cpp/build
RUN cmake3 .. -DBUILD_GSTREAMER_PLUGIN=ON && \
    make && \
    make install

# Set up environment variables for GStreamer
ENV GST_PLUGIN_PATH=/usr/lib64/gstreamer-1.0:/opt/amazon-kinesis-video-streams-producer-sdk-cpp/build
ENV LD_LIBRARY_PATH=/opt/amazon-kinesis-video-streams-producer-sdk-cpp/open-source/local/lib

# Install Python dependencies
RUN pip3 install boto3 numpy opencv-python pillow

# Set up working directory
WORKDIR /app

# Copy the image extraction script
COPY kvs-to-s3.py /app/
RUN chmod +x /app/kvs-to-s3.py

# Set up environment variables (these can be overridden at runtime)
ENV KVS_STREAM_NAME=""
ENV S3_BUCKET_NAME=""
ENV AWS_REGION="ap-southeast-1"
ENV IMAGE_INTERVAL="1.0"
ENV IMAGE_FORMAT="jpg"
ENV IMAGE_QUALITY="85"
ENV S3_PREFIX="uploads/images/temp/"

# Command to run when container starts
ENTRYPOINT ["python3", "/app/kvs-to-s3.py"]