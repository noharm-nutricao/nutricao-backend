#!/bin/bash

set -e

rm -rf package
rm -f lambda.zip

mkdir package

python3 -m pip install -r requirements.txt -t package

cp -r app package/
cp app/lambda_handler.py package/

cd package
zip -r ../lambda.zip .
cd ..