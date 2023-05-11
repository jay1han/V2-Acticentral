#!/usr/bin/bash

echo {} > Conf/registry.json
echo {} > Conf/actiservers.json
echo {} > Conf/actimetres.json
echo [] > Conf/local.json
echo > Log/server.log
echo > Log/central.log
echo > Log/lib.log
rm Data/*
rm Repo/*
echo {} > Conf/registry.data
echo {} > Conf/actiservers.data
echo {} > Conf/actimetres.data
echo {} > Conf/self.data
