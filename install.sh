#!/usr/bin/bash

systemctl stop acticentral.timer
systemctl stop acticentral-daily.timer
systemctl stop acticentral-weekly.timer

mkdir /etc/actimetre
mkdir /etc/actimetre/history
mkdir /etc/actimetre/daily
mkdir /etc/actimetre/weekly
mkdir /etc/actimetre/registry
mkdir /etc/matplotlib
chmod 777 /etc/matplotlib
mkdir /var/www/cgi-bin
mkdir /var/www/html/images
mkdir /var/www/html/actimetre
mkdir /var/www/html/actiserver
mkdir /var/www/html/project

cp .secret *.sh administrators /etc/actimetre
cp cgi-bin/*.py /var/www/cgi-bin/
cp html/*.html html/*.svg html/*.pdf /var/www/html/
cp *.service /etc/systemd/system/
cp *.timer /etc/systemd/system/

cd /var/www
chown -R www-data:www-data *
chmod 666 html/* html/images/* html/actimetre/* html/actiserver/* html/project/*
chmod 664 html/index.html
chmod 775 cgi-bin/acticentral.py
chmod 777 html html/images html/actimetre html/actiserver

cd /etc/actimetre
echo > central.log
echo > acticentral.lock
echo > registry.data
echo > projects.data
chown -R www-data:www-data . *
chmod 666 * history/*
chmod 777 . *.sh history daily weekly registry

systemctl daemon-reload
systemctl enable acticentral.timer
systemctl start acticentral.timer
systemctl enable acticentral-daily.timer
systemctl start acticentral-daily.timer
systemctl enable acticentral-weekly.timer
systemctl start acticentral-weekly.timer

echo "Entry point is /var/www/html/acticentral.html: make links as needed"
echo "Edit /etc/actimetre/.secret for the secret key"
