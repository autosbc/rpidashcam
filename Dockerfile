FROM python:3.10.4-slim-buster

ENV READTHEDOCS=True

# hadolint ignore=DL3008,DL3013
RUN apt-get update \
    && apt-get -yqq --no-install-recommends install gnupg \
    && echo 'deb http://archive.raspberrypi.org/debian/ buster main' > /etc/apt/sources.list.d/raspi.list \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 82B129927FA3303E \ 
    && apt-get update \
    && apt-get -yqq --no-install-recommends install \
		gcc \
		libfreetype6-dev \
		libjpeg-dev \
		zlib1g-dev \
		ffmpeg \
                cmake \
    && pip install --upgrade pip \
    && pip install --no-cache-dir setuptools \
    && pip install -v --no-cache-dir \
		gps \
		picamera \
		pillow \
    && apt-get -yqq --purge remove \
		gcc \
		cmake \
    && apt-get clean \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "done!"

COPY dashcam.py /usr/local/bin

# Overwrite mmalobj.py because it is poopy
COPY mmalobj.py /usr/local/lib/python3.10/site-packages/picamera

# Overwrite gps.py because it didnt catch up with newer python
COPY client.py /usr/local/lib/python3.10/site-packages/gps/
# Copy font
COPY font/game_over.ttf /usr/share/fonts
ENV LD_LIBRARY_PATH /opt/vc/lib
VOLUME ["/mnt/storage"]
ENTRYPOINT ["/usr/local/bin/dashcam.py"]
