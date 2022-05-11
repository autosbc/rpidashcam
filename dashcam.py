#!/usr/bin/env python3
# Stdlibs
from configparser import ConfigParser
from datetime import datetime
from math import isnan
from threading import Thread, Lock
from time import sleep
import subprocess

# Picamera
from picamera import mmal, mmalobj as mo, PiCameraPortDisabled
from PIL import Image, ImageDraw, ImageFont

# GPS
from gps import gps, WATCH_ENABLE, WATCH_NEWSTYLE


class DashCamData(mo.MMALPythonComponent):
    """
    This is to make pylint happy
    """
    def __init__(self, resolution=(1280, 720), title="Test dashcam"):
        """
        This is where we go bob ross on the frames
        Happy little mistakes
        """
        # We also need to initialize the class we inherited for some reason.
        super().__init__(name='py.prutt', outputs=2)
        self._lock = Lock()
        self.inputs[0].supported_formats = {mmal.MMAL_ENCODING_I420}

        self.width, self.height = (resolution)
        self.resolution = resolution
        self.dashcam_title = title

        # We use this to hold the text backgrounds
        self.dashcam_overlay_bg_image = None

        self.dashcam_title_img = None

        # And this for the actual text data
        self.dashcam_overlay_text_image = None

        # Threads and stuff
        self.dashcam_overlay_text_thread = None

        # Set bar height pixels
        self.bar_height = 25
        self.bottom_bar_bg = None

        # Calculate the position of the bottom bar where we keep important text
        # such as the date and time, and the ridiculous speeds in which we are
        # traveling with. These are very advanced arithmetics - data is (x, y)
        self.bottom_bar_position = (0, self.height - self.bar_height)

        # We set the font upfront.
        self.__font = ImageFont.truetype("/usr/share/fonts/game_over.ttf", 50)

        # In order to determine how big our background box for the
        # dashcam title will be we need to cheat to get it.
        dashcam_title_bg_size = self.__font.getsize(self.dashcam_title)

        # Now we add a bit on both axis to have margins so that
        # the title doesn't look cramped.
        dashcam_title_bg_width = dashcam_title_bg_size[0] + 10
        dashcam_title_bg_height = dashcam_title_bg_size[1] + 5

        self.dashcam_title_image = Image.new(
                'RGBA',
                (dashcam_title_bg_width, dashcam_title_bg_height),
                (255, 255, 255, 0)
                )
        title_box_draw = ImageDraw.Draw(self.dashcam_title_image)
        title_box_draw.rectangle(
                (
                    (0, 0),
                    (dashcam_title_bg_width, dashcam_title_bg_height)
                    ),
                (0, 0, 0, 128)
                )

        # Draw our cool dashcam title here.
        title_box_draw.text((5, -5), self.dashcam_title, font=self.__font)
        self.bottom_bar_bg = Image.new(
                    'RGBA',
                    (self.width, self.bar_height),
                    (255, 255, 255, 0)
                    )

        # Start painting the bottom bar
        draw = ImageDraw.Draw(self.bottom_bar_bg)

        # Draw a rectangle as wide as the resolution permits
        # And 25 pixels high and make it black and an opacity of 128
        draw.rectangle(((0, 0), (self.width, self.bar_height)), (0, 0, 0, 128))

        # Initialize GPS
        self.__gps = gps(mode=WATCH_ENABLE | WATCH_NEWSTYLE)
        self.__gps.next()
        self.__gps_thread = None


        # Set first speed so we don't print
        # nan as first value
        self.__current_speed = 0

    def enable(self):
        super().enable()

        # Start gps thread
        self.__gps_thread = Thread(
                target=self._gps_loop
                )
        self.__gps_thread.daemon = True
        self.__gps_thread.start()

        # Initialize our dashcam data renderer
        # in a thread
        self.dashcam_overlay_text_thread = Thread(
                target=self._dashcam_data_run
                )
        self.dashcam_overlay_text_thread.daemon = True
        self.dashcam_overlay_text_thread.start()

    def disable(self):
        super().disable()
        if self.dashcam_overlay_text_thread:
            self.dashcam_overlay_text_thread.join()
            self.dashcam_overlay_text_thread = None
            with self._lock:
                self.dashcam_overlay_bg_image = None
                self.dashcam_overlay_text_image = None
        if self.__gps_thread:
            self.__gps_thread.join()
            self.__gps_thread = None

    def _gps_loop(self):
        """
        This is a loop for the gps part.
        """
        while self.enabled:
            if self.__gps.waiting():
                self.__gps.next()

            # set speed to 0 if we don't have a fix to gps sattelites
            speed = 0 if isnan(self.__gps.fix.speed) else self.__gps.fix.speed
            #speed = int(float(gps_data["speed"])*3.6)

            # Only update the speed if we have a speed of
            # > 0. We do this because, perhaps we lost the gps fix by
            # traveling through a tunnel, or in a garage.
            # If we lost it due to the mentioned reasons we can _probably_
            # assume we're going at the same speed and should display that.
            with self._lock:
                # We get the speed in meters per second.
                # Hence we calculate it to kilometers per hour
                self.__current_speed = int(speed * 3.6)

            # Sleep so that we make the thread release the GIL
            sleep(1)

    def _dashcam_data_run(self):
        """
        Since we pre-created a lot of the stuff
        we will only draw text onto the bottom bar.
        """
        while self.enabled:
            # Because we already created the background for the bottom
            # bar in __init__ we save mucho time here.
            img = self.bottom_bar_bg.copy()
            now = datetime.now()
            date = f"{now.year}-{now.month}-{now.day} {now.hour}:{now.minute}:{now.second}"
            speed = "---" if self.__current_speed == 0 else self.__current_speed


            # We start drawing the text over the black opaque
            # rectangle we just created.
            draw = ImageDraw.Draw(img)
            draw.text(
                    (5, -5),
                    f" {date} {speed} km/h",
                    font=self.__font
                    )

            with self._lock:
                self.dashcam_overlay_text_image = img

            # Sleep to release the GIL.
            sleep(1)

    def _handle_frame(self, port, buf):
        # We check if we have data for the frame
        # If not we bail out by returning True
        try:
            out1 = self.outputs[0].get_buffer(False)
            out2 = self.outputs[1].get_buffer(False)
        except PiCameraPortDisabled:
            return True

        if out1:
            # We have data. Now we do stuff to the frame
            out1.copy_from(buf)
            with out1 as data:
                # Following comments are copied from MMAL documentation
                # construct an image using the Y plane of the output
                # buffers data and tell PIL we can write to the buffer
                img = Image.frombuffer(
                        'L',
                        port.framesize,
                        data,
                        'raw',
                        'L',
                        0,
                        1
                        )
                # We make sure we can manipulate the image by setting
                # readonly to false
                img.readonly = False

                # use locking to be able to quickly do what we want to do
                # And then gtfo
                with self._lock:
                    if self.dashcam_overlay_text_image:
                        # Paste our overlay over the text
                        img.paste(
                                self.dashcam_overlay_text_image,
                                self.bottom_bar_position,
                                self.dashcam_overlay_text_image
                                )
                    if self.dashcam_title_image:
                        img.paste(
                                self.dashcam_title_image,
                                (0, 0),
                                self.dashcam_title_image
                                )

            # If we have a second output that is probably the preview.
            # We therefor copy the same data to it.
            # It will be useful to for example adjust the focus by
            # hooking up a HDMI capable monitor to the Pi.
            if out2:
                out2.replicate(out1)
            try:
                self.outputs[0].send_buffer(out1)
            except PiCameraPortDisabled:
                return True
        if out2:
            try:
                self.outputs[1].send_buffer(out2)
            except PiCameraPortDisabled:
                return True

        return False


class DashCam:
    """
    This is also to make pylint happy
    """
    def __init__(self):

        self.__enabled = False

        self.__resolutions = {
                # 'short': [fps, (width, height)]
                '720p': [30, (1280, 720)],
                '1080p': [24, (1920, 1080)],
                }
        self.__config = ConfigParser()

        self.__config.read("/etc/raspberrydashcam/config.ini")

        # Set up the basic stuff
        self._title = self.__config["dashcam"]["title"]
        self._fps, self._resolution = self.__resolutions[
                self.__config["camera"]["resolution"]
                ]

        self._bitrate = int(self.__config["camera"]["bitrate"])

        # Create the filename that we're going to record to.
        self._filename = datetime.now().strftime(
                "/mnt/storage/%Y-%m-%d-%H-%M-%S.mp4"
                )


        # This is the ffmpeg command we will run
        self.__ffmpeg_command = [
                "/usr/bin/ffmpeg",
                #"-loglevel quiet -stats",
                "-async",
                "1",
                "-vsync",
                "1",
                "-ar",
                "44100",
                "-ac",
                "1",
                "-f",
                "s16le",
                "-f",
                "alsa",
                "-thread_queue_size",
                "10240",
                "-use_wallclock_as_timestamps",
                "1",
                "-i",
                "hw:2,0",
                "-f",
                "h264",
                "-probesize",
                "10M",
                "-r",
                str(self._fps),
                "-thread_queue_size",
                "10240",
                "-use_wallclock_as_timestamps",
                "1",
                "-i",
                "-",  # Read from stdin
                "-crf",
                "22",
                "-vcodec",
                "copy",
                "-acodec",
                "aac",
                "-ab",
                "128k",
                "-g",
                str(self._fps * 2),  # GOP should be double the fps.
                "-r",
                str(self._fps),
                "-f",
                "mp4",
                self._filename
                ]

        self.__camera = mo.MMALCamera()
        self.__preview = mo.MMALRenderer()
        self.__encoder = mo.MMALVideoEncoder()
        self.__dashcam_data = DashCamData(
                title=self._title,
                resolution=self._resolution
                )

        # Here we start the ffmpeg process and at the same time
        # open up a stdin pipe to it.
        self.__ffmpeg_instance = subprocess.Popen(
                " ".join(
                    self.__ffmpeg_command
                    ),
                shell=True,
                stdin=subprocess.PIPE
                )

        # Here we specify that the script should write to stdin of the
        # ffmpeg process.
        self.__target = mo.MMALPythonTarget(self.__ffmpeg_instance.stdin)

        # Setup resolution and fps
        self.__camera.outputs[0].framesize = self._resolution
        self.__camera.outputs[0].framerate = self._fps

        # Commit the two previous changes
        self.__camera.outputs[0].commit()

        # Do base configuration of encoder.
        self.__encoder.outputs[0].format = mmal.MMAL_ENCODING_H264
        self.__encoder.outputs[0].bitrate = self._bitrate

        # Commit the encoder changes.
        self.__encoder.outputs[0].commit()

        # Get current MMAL_PARAMETER_PROFILE from encoder
        profile = self.__encoder.outputs[0].params[
                mmal.MMAL_PARAMETER_PROFILE]

        # Modify the proflle
        # Set the profile to MMAL_VIDEO_PROFILE_H264_HIGH
        profile.profile[0].profile = mmal.MMAL_VIDEO_PROFILE_H264_HIGH
        profile.profile[0].level = mmal.MMAL_VIDEO_LEVEL_H264_41

        # Now make sure encoder get's the modified profile
        self.__encoder.outputs[0].params[mmal.MMAL_PARAMETER_PROFILE] = profile

        # Now to stuff that is completely stolen
        # which I do not yet know what they do.
        self.__encoder.outputs[0].params[
                mmal.MMAL_PARAMETER_VIDEO_ENCODE_INLINE_HEADER] = True
        self.__encoder.outputs[0].params[mmal.MMAL_PARAMETER_INTRAPERIOD] = 48
        self.__encoder.outputs[0].params[
                mmal.MMAL_PARAMETER_VIDEO_ENCODE_INITIAL_QUANT] = 17
        self.__encoder.outputs[0].params[
                mmal.MMAL_PARAMETER_VIDEO_ENCODE_MAX_QUANT] = 17
        self.__encoder.outputs[0].params[
                mmal.MMAL_PARAMETER_VIDEO_ENCODE_MIN_QUANT] = 17

        # Stolen from picamera module, very clever stuff
        self.__mirror_parameter = {
                (False, False): mmal.MMAL_PARAM_MIRROR_NONE,
                (True,  False): mmal.MMAL_PARAM_MIRROR_VERTICAL,
                (False, True):  mmal.MMAL_PARAM_MIRROR_HORIZONTAL,
                (True,  True):  mmal.MMAL_PARAM_MIRROR_BOTH,
                }

        # Set initial values
        self.vflip = self.hflip = False

        # Get actual config values from config
        if self.__config["camera"].getboolean("vflip"):
            self.set_vflip(True)
        if self.__config["camera"].getboolean("hflip"):
            self.set_hflip(True)
        self.__camera.control.params[mmal.MMAL_PARAMETER_VIDEO_STABILISATION] = True
        m_p = self.__camera.control.params[mmal.MMAL_PARAMETER_EXPOSURE_MODE]
        m_p.value = mmal.MMAL_PARAM_EXPOSUREMODE_AUTO
        self.__camera.control.params[mmal.MMAL_PARAMETER_EXPOSURE_MODE] = m_p
        m_p = self.__camera.control.params[mmal.MMAL_PARAMETER_AWB_MODE]
        m_p.value = mmal.MMAL_PARAM_AWBMODE_HORIZON
        self.__camera.control.params[mmal.MMAL_PARAMETER_AWB_MODE] = m_p


    def set_hflip(self, value):
        """
        Sets hflip, matches the pair with what's in
        self.__mirror_parameter.
        """
        value = self.__mirror_parameter[(self.vflip, bool(value))]
        for port in self.__camera.outputs:
            port.params[mmal.MMAL_PARAMETER_MIRROR] = value
        self.hflip = True

    def set_vflip(self, value):
        """
        Sets vflip, matches the pair with what's in
        self.__mirror_parameter.
        """
        value = self.__mirror_parameter[(bool(value), self.hflip)]
        for port in self.__camera.outputs:
            port.params[mmal.MMAL_PARAMETER_MIRROR] = value
        self.vflip = True

    def connect(self):
        """
        Connect and enable everything
        """
        # Give our DashCamData renderer the camera video output
        self.__dashcam_data.inputs[0].connect(self.__camera.outputs[0])

        # DashCamData has two outputs, we give one to preview window and one
        # to encoder
        self.__preview.inputs[0].connect(self.__dashcam_data.outputs[1])
        self.__encoder.inputs[0].connect(self.__dashcam_data.outputs[0])

        # Now connect target with the encoder output so we write video
        self.__target.inputs[0].connect(self.__encoder.outputs[0])

        # Now we enable the connections between the different components
        self.__target.connection.enable()
        self.__encoder.connection.enable()
        self.__preview.connection.enable()
        self.__dashcam_data.connection.enable()

        # And now we enable the components themselves
        self.__target.enable()
        self.__encoder.enable()
        self.__preview.enable()
        self.__dashcam_data.enable()
        self.__enabled = True

    def disconnect(self):
        """
        Tear everything down, it probably means we're shutting down.
        """

        # First disable the components
        self.__target.disable()
        self.__encoder.disable()
        self.__preview.disable()
        self.__dashcam_data.disable()

        # Now disconnect the outputs and inputs
        self.__target.inputs[0].disconnect()
        self.__encoder.inputs[0].disconnect()
        self.__preview.inputs[0].disconnect()
        self.__dashcam_data.inputs[0].disconnect()

        # Shut down ffmpeg recording
        self.__ffmpeg_instance.terminate()
        self.__enabled = False

    def run(self):
        """
        We empty loop, we do this continue to run the class, or else
        the program returns to shell.

        This is black magic looping.
        """
        while self.__enabled:
            sleep(5)


if __name__ == '__main__':
    d = DashCam()
    try:
        d.connect()
        print("Starting video recording")
        d.run()
    except KeyboardInterrupt:
        d.disconnect()
