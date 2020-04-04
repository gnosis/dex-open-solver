FROM ubuntu:bionic

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.7 python3-pip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/open_solver
COPY ./src ./src
COPY ./requirements.txt ./requirements.txt

RUN pip3 install --no-cache-dir -r requirements.txt
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /app



