#!/bin/bash

SOURCE_BRANCH=${SOURCE_BRANCH//refs\/heads\//}
STATUS=$(curl -sH \
    "Authorization: Bearer $BEARER_TOKEN" \
    "$SONARQUBE_URL/$API?projectKey=$PROJECT_KEY&branch=$SOURCE_BRANCH" \
    | jq | grep -B 1 'coverage' | grep 'status' | awk '{print $2}' | sed 's/"//g' | sed 's/,//g')

echo "##[debug] Source branch: $SOURCE_BRANCH"
echo "##[debug] Sonarqube status: $STATUS"

if [ "$STATUS" != "OK" ]; then
    echo "##vso[task.logissue type=error]SonarQube Quality Gate failed"
    exit 1
else
    echo "##[debug] SonarQube Quality Gate passed"
    exit 0
fi