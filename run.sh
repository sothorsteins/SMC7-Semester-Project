#!/bin/bash

python3 threshold.py &
node bridge.js &
yarn watch
