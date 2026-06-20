#!/bin/bash

SLEEP_TIME=10
SERVICE="${SERVICE_NAME:-{project-name}_api}"

for i in {1..12}; do
    echo "Attempt $i : Waiting Backend to be Ready"
    docker inspect "$SERVICE" > /dev/null 2>&1 || { echo -e "$SERVICE container does not exist. \nExiting with status 1"; exit 1; }
    STATUS=$(docker inspect "$SERVICE" | grep 'Status' | awk -F ':' {'print $2'} | tr -d '\", ')
    if [ "$STATUS" == "exited" ]; then
        echo "Backend Status: $STATUS, terminating..."
        echo "Exiting with status code 1."
        exit 1
    fi
    if curl --silent --fail http://"$URL":"$PORT"/health/ready; then
        echo " Backend Status: $STATUS"
        echo " Backend is Ready!"
        exit 0
    fi
    echo "Backend Status: $STATUS, Not Ready Yet, sleeping $SLEEP_TIME seconds..."
    sleep $SLEEP_TIME
done

echo "Backend failed to become ready until the 10 minutes mark."
exit 1
