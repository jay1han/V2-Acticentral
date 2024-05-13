#!/usr/bin/bash

cd /etc/actimetre

echo > central.log
echo > acticentral.lock
echo > ./secrets
echo {} > actiservers.data
echo {} > actimetres.data

chmod 666 *.data *.log
rm -f history/Actim*.hist

cd /var/www/html

rm -f images/*
rm -f actimetre/*
rm -f actiserver/*
rm -f actim*.html server*.html project*.html

ls -lRA

