#!/usr/bin/bash

mkdir /etc/actimetre
mkdir /media/actimetre
mkdir /media/actimetre/Data
mkdir /media/actimetre/Repo
mkdir /var/www/cgi-bin

cp actimetre.conf clear2.sh killjava.sh run.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/index.html html/error.html /var/www/html/

cd /etc/actimetre
chown www-data:www-data . actimetre.conf
chmod 777 . clear2.sh
chmod 666 actimetre.conf

cd /media/actimetre
chown www-data:www-data . Data Repo
chmod 777 . Data Repo

cd /var/www/html
chown www-data:www-data index.html error.html
chmod 775 index.html

cd /var/www/cgi-bin
chown www-data:www-data acticentral.py
chmod 775 acticentral.py

echo > /etc/actimetre/server.log
echo > /etc/actimetre/central.log
echo > /etc/actimetre/acticentral.lock
rm -f /media/actimetre/Data/*
rm -f /media/actimetre/Repo/*
echo {} > /etc/actimetre/registry.data
echo {} > /etc/actimetre/actiservers.data
echo {} > /etc/actimetre/actimetres.data
echo {} > /etc/actimetre/self.data
echo {} > /etc/actimetre/meta.data
rm -f /etc/actimetre/acticentral.pid

chmod 666 *.log *.data *.lock *.conf
