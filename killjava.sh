#!/usr/bin/bash

kill `ps x | grep ActiserverKt | grep java | grep -o -E ^[[:space:]]*[0-9]+[[:space:]]`
