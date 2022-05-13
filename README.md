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
Works with Raspberry Pi 4. 1080p at 30 FPS.



## Notes

You'll need ffmpeg installed.

Copy example config to `/etc/raspberrydashcam/config.ini`.

The following tuning was made in `/boot/config.txt` (not sure they're needed).

```
over_voltage=6
arm_freq=2000
gpu_freq=750
```

`mmalobj.py` from picamera needs to be changed. See this [MR](https://github.com/waveform80/picamera/pull/645/files) to see how to do it.

In gps module `gpsjson` object class we need to change to remove decode.

`unpack` method should look like this:

```
    def unpack(self, buf):
        "Unpack a JSON string"
        try:
            self.data = dictwrapper(json.loads(buf.strip()))
        except ValueError as e:
            raise json_error(buf, e.args[0])
        # Should be done for any other array-valued subobjects, too.
        # This particular logic can fire on SKY or RTCM2 objects.
        if hasattr(self.data, "satellites"):
            self.data.satellites = [dictwrapper(x)
                                    for x in self.data.satellites]
```

No other tweaks are necessary.

# Example video
[![TEST VIDEO](https://img.youtube.com/vi/N6YJ4wGo5z8/0.jpg)](https://www.youtube.com/watch?v=N6YJ4wGo5z8)
