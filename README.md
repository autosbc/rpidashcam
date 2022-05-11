# rpidashcam
Dashcam software designed to run on Raspberry Pi.


## Requirements
* USB microphone or similar
* USB GPS module
* External storage
* Camera module (HQ camera prefered but should work with any other camera that is supported by raspios) I use [Arducam B0241](https://www.arducam.com/product/b0241-arducam-imx477-hq-camera-6/) (IMX477).
* 32 bit version of raspbian (until libcamera has a saner less bloated alternative to [picamera2](https://github.com/raspberrypi/picamera2))
* For best performance use python 3.10 (`3.10.4` is currently the newest). 

### 720p
Tested with Raspberry Pi 3B+ and working fine. Audio is synced properly and running full FPS.

### 1080p
Kind of works with Raspberry Pi 4. It sometimes lags though. 24 FPS works.


# Example video
[![TEST VIDEO](https://img.youtube.com/vi/N6YJ4wGo5z8/0.jpg)](https://www.youtube.com/watch?v=N6YJ4wGo5z8)
