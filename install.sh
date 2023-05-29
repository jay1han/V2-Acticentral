#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /etc/actimetre/history
mkdir /var/www/cgi-bin
mkdir /var/www/html/images

cp clearcentral.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html /var/www/html/

cd /var/www
chown www-data:www-data html/*.html cgi-bin/acticentral.py
chmod 775 html/index.html cgi-bin/acticentral.py
chmod 777 html/images

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
