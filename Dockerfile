FROM python:3.10.4-buster

ENV READTHEDOCS=True

# hadolint ignore=DL3008,DL3013
RUN apt-get update \
    && apt-get -yqq --no-install-recommends install \
		ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
		gps \
		picamera \
		pillow \
    && mkdir /etc/raspberrydashcam \


COPY config/sample_config.ini /etc/raspberrydashcam/config.ini
COPY dashcam.py /usr/local/bin

# Overwrite mmalobj.py because it is poopy
COPY mmalobj.py /usr/local/lib/python3.10/site-packages/picamera

# Overwrite gps.py because it didnt catch up with newer python
COPY client.py /usr/local/lib/python3.10/site-packages/gps/
# Copy font
COPY font/game_over.ttf /usr/share/fonts
ENV LD_LIBRARY_PATH /opt/vc/lib
ENTRYPOINT ["python3", "/usr/local/bin/dashcam.py"]
