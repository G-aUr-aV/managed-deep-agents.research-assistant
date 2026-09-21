#!/bin/bash
set -u

mkdir -p /logs/verifier

ANSWER=""
for candidate in /app/answer.txt /answer.txt; do
  if [ -f "$candidate" ]; then
    ANSWER="$candidate"
    break
  fi
done

if [ -z "$ANSWER" ]; then
  echo "missing answer.txt" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

content=$(cat "$ANSWER")
length=${#content}

has_http=0
has_paper=0
echo "$content" | grep -qiE 'https?://' && has_http=1
echo "$content" | grep -qiE 'openalex\.org|doi\.org' && has_paper=1

if [ "$length" -gt 200 ] && [ "$has_http" -eq 1 ] && [ "$has_paper" -eq 1 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo "length=$length has_http=$has_http has_paper=$has_paper" >&2
  echo 0 > /logs/verifier/reward.txt
fi
