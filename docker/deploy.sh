#!/bin/bash

set -euo pipefail
tag_name=$1

echo "Docker login"
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin;

echo "Pushing to Docker-hub, generated from branch $TRAVIS_BRANCH";
docker build -f docker/Dockerfile -t gnosispm/dex-open-solver:$tag_name .;
docker push gnosispm/dex-open-solver:$tag_name;
echo "The image has been pushed";