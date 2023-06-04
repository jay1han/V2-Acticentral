#!/usr/bin/bash

cd /etc/actimetre

echo > central.log
echo > acticentral.lock
echo {} > actiservers.data
echo {} > actimetres.data

chmod 666 *.data *.log
rm -f history/Actim*.hist

rm -f /var/www/html/images/*
echo > /var/www/html/images/index.txt
chmod 666 /var/www/html/images/index.txt

ls -lRA

