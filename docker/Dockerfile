FROM ubuntu:bionic

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.7 python3-pip python3-setuptools \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/open_solver
COPY ./dex_open_solver ./dex_open_solver

#COPY ./requirements.txt ./requirements.txt
#RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./setup.py ./setup.py
COPY ./README.md ./README.md
RUN pip3 install --no-cache-dir .

RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /app



