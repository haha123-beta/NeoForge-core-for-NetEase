# -*- coding: utf-8 -*-
"""Reviewed SLF4J info(String) subset, routed to the host script log."""
from __future__ import print_function

class Logger(object):
    def __init__(self,name):
        self.name=name
        self.records=[]
    def info(self,message):
        self.records.append(('INFO',message))
        print('[INFO] '+self.name+' - '+('null' if message is None else message))

class LogUtils(object):
    _loggers={}
    @staticmethod
    def forCaller(name):
        if name not in LogUtils._loggers:LogUtils._loggers[name]=Logger(name)
        return LogUtils._loggers[name]

JAVA_MAP={'com.mojang.logging.LogUtils':LogUtils,'org.slf4j.Logger':Logger}
