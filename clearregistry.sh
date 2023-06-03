#!/usr/bin/bash

cd /etc/actimetre
rm -f history/Actim*.hist
echo {} > registry.data
echo {} > projects.data
chmod 666 *.data
