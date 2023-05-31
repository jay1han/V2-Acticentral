#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /etc/actimetre/history
mkdir /var/www/cgi-bin
mkdir /var/www/html/images
mkdir /etc/matplotlib
chmod 777 /etc/matplotlib

cp clear*.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html html/*.svg /var/www/html/

cd /var/www
chown www-data:www-data html html/images html/*.html cgi-bin/acticentral.py
chmod 775 html/index.html cgi-bin/acticentral.py
chmod 777 html html/images

cd /etc/actimetre
chown www-data:www-data . *
chmod 777 . *.sh history

echo > central.log
echo > acticentral.lock
echo {} > actiservers.data
echo {} > actimetres.data
rm -f acticentral.pid
chmod 666 *.log *.data *.lock

echo Please run /etc/actimetre/clearregistry.sh if you want to erase the rest (Registry, History, and Projects)

