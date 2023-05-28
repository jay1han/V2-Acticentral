#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /var/www/cgi-bin

cp clearcentral.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html /var/www/html/

cd /var/www
chown www-data:www-data html/actimetre.html html/error.html cgi-bin/acticentral.py
chmod 775 html/actimetre.html cgi-bin/acticentral.py

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
