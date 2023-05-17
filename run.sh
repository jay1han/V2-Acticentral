#!/usr/bin/bash

./killjava.sh

cd /home/pi/IdeaProjects/Actiserver
java -cp classes:lib/'*' ActiserverKt
