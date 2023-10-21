#!/usr/bin/bash

sudo systemctl stop acticentral.timer
sudo systemctl stop acticentral-daily.timer
sudo systemctl stop acticentral-weekly.timer

cp clear*.sh /etc/actimetre
cp cgi-bin/acticentral.py /var/www/cgi-bin/acticentral.py
cp html/*.html html/*.svg /var/www/html/
cp *.service /etc/systemd/system/
cp *.timer /etc/systemd/system/

cd /var/www
echo > html/images/index.txt
chown www-data:www-data html html/images html/*.html cgi-bin/acticentral.py
chmod 666 html/* html/images/*
chmod 775 html/index.html cgi-bin/acticentral.py
chmod 777 html html/images

cd /etc/actimetre
echo > central.log
echo > acticentral.lock
rm -f acticentral.pid
chown -R www-data:www-data . *
chmod 666 * history/*
chmod 777 . *.sh history

systemctl daemon-reload
sudo systemctl enable acticentral.timer
sudo systemctl start acticentral.timer
systemctl enable acticentral-daily.timer
systemctl start acticentral-daily.timer
systemctl enable acticentral-weekly.timer
systemctl start acticentral-weekly.timer
