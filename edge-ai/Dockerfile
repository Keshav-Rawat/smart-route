FROM python:3.10-slim

WORKDIR /app

# Prevent PyTorch/NumPy Segmentation Faults (Exit Code 139) on ARM64 / Mac Silicon
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_CORETYPE=ARMV8
ENV YOLO_CONFIG_DIR=/tmp/ultralytics

# Install minimal system deps
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Install torch from default PyPI (newer versions are stable on ARM64)
# Using 1000s timeout because the ARM64 wheel is ~400MB
RUN pip install --no-cache-dir --timeout=1000 \
    torch==2.2.2 torchvision==0.17.2

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Uninstall the non-headless OpenCV pulled by ultralytics to prevent conflicts
RUN pip uninstall -y opencv-python opencv-python-headless && \
    pip install --no-cache-dir opencv-python-headless==4.10.0.84 numpy==1.26.4

# Copy source
COPY . .

# Run detector
CMD ["python", "detector.py"]