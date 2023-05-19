#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /media/actimetre
mkdir /var/www/cgi-bin

cp clearcentral.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/index.html html/error.html /var/www/html/

cd /media/actimetre
chown www-data:www-data .
chmod 777 .
rm -f /media/actimetre/*

cd /var/www
chown www-data:www-data html/index.html html/error.html cgi-bin/acticentral.py
chmod 775 html/index.html cgi-bin/acticentral.py

cd /etc/actimetre
chown www-data:www-data .
chmod 777 . *.sh
echo > central.log
echo > acticentral.lock
echo {} > registry.data
echo {} > actiservers.data
echo {} > actimetres.data
echo {} > meta.data
rm -f acticentral.pid
chmod 666 *.log *.data *.lock
