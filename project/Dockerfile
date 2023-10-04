# pull official base image
FROM python:3.10.13-bookworm

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt
# RUN pip install spleeter==2.4.0

# copy project
COPY . .
