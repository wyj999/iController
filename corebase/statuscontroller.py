#!/usr/bin/env python
# coding=utf-8

import time
from setting import *
from utils.log import LOG
from database import Database
from datetime import datetime
from corebase.coreorder import CoreOrder

log = LOG()

class CoreStatusController():
    def __init__(self):
        self.db = Database(STATUS_REDIS)

    def checkAdvertiserMoney(self, advid):
        remoney = self.db.getAdvertiserMoney(advid)
        if  remoney <= 0:
            return False
        else:
            return True

    def checkOrderMoney(self, orid, budget, hourlist = False):
        havespend, hourspend = self.db.getOrderTodayMoney(orid)
        if havespend == None and hourspend == None:
            # Error
            return False, STATUS_ERROR
        if havespend == 0 and hourspend == 0:
            # No Impression
            return True, STATUS_OK
        
        if havespend >= budget:
            return False, STATUS_DAY_BUDGET

        if hourlist == False:
            # No Hour Share
            return True, STATUS_OK
        else:
            if not self.dealOrderHourList(hourlist):
                # No this hour
                return False, STATUS_NO_THIS_HOUR
            elif self.checkOrderHourMoney(havespend, hourspend, budget, hourlist):
                return True, STATUS_OK
            else:
                # hour share control
                return True, STATUS_HOUR_BUDGET

    def checkOrderHourMoney(self,havespend, hourspend, budget, hourlist):
        if hourspend == 0:
            return True

        now_hour = int(datetime.now().hour)
        hour_count = 0
        for h in hourlist:
            if int(h) >= now_hour:
                hour_count = hour_count + 1

        if hour_count == 0:
            return False
        if hour_count == 1:
            return True
        if (budget - (havespend - hourspend))/hour_count > hourspend:
            return True
        else:
            return False
        
    def dealOrderHourList(self, hourlist):
        now_hour = int(datetime.now().hour)
        for h in hourlist:
            if int(h) == now_hour:
                return True
        return False

    def coreProcess(self, orderID, real_info, status_db = None):
        try:
            if status_db is None:
                db = self.db
            else:
                db = status_db
            if real_info.has_key('adverID'):
                advid = real_info['adverID']
            if real_info.has_key('hourlist'):
                hourlist = real_info['hourlist']
            if real_info.has_key('budget'):
                budget = real_info['budget']
            if real_info.has_key('hourshare'):
                hourshare = real_info['hourshare']

            if advid:
                # adver money
                if not self.checkAdvertiserMoney(advid):
                    db.setOrderStatus(orderID, STATUS_ADV_NO_MONEY)
                    log.info('OrderStatus Set %s -> %s' % (orderID, STATUS_ADV_NO_MONEY))
                    return
                # date control
                if not hourlist:
                    db.setOrderStatus(orderID, STATUS_NO_TODAY_RANGE)
                    log.info('OrderStatus Set %s -> %s' % (orderID, STATUS_NO_TODAY_RANGE))
                    return

                # hour control
                if not self.dealOrderHourList(hourlist):
                    db.setOrderStatus(orderID, STATUS_NO_THIS_HOUR)
                    log.info('OrderStatus Set %s -> %s' % (orderID, STATUS_NO_THIS_HOUR))
                    return
                # no control budget
                if budget == 0:
                    db.setOrderStatus(orderID, STATUS_OK)
                    log.info('OrderStatus Set %s -> %s This Order Has No Budget Control!' % (orderID, STATUS_OK))
                    return
                # control budget
                if hourshare :
                    result , status = self.checkOrderMoney(orderID, budget, hourlist)
                else:
                    result , status = self.checkOrderMoney(orderID, budget)
                #log.info('OrderStatus Set %s -> %s' % (orderID, status))
                db.setOrderStatus(orderID, status)
                return
        except Exception, e:
            print "statuscontroller coreProcess: %s" % e


def ordercheckcontroller():
    db = Database(STATUS_REDIS)
    ob_order = CoreOrder()
    ob_controller = CoreStatusController()
    st = int( time.time() )
    interval = 10
    reload = True
    while True:
        try:
            time.sleep(0.1)
            if ob_order.newConfigureMonitor():
                ob_order.reload()
                reload = True
            else:
                if int(time.time()) - st > interval :
                    reload = True
                    st = int( time.time() )
            if reload:
                reload = False
                for orderID in ob_order.getOrderRealList():
                    real_info = ob_order.getOrderRealInfo(orderID)
                    if not real_info:
                        continue
                    else:
                        ob_controller.coreProcess(orderID, real_info, status_db = db)

                
        except Exception, e:
            log.error("ordercheckcontroller:%s" % e)
            continue


def statuscontroller(sock):
    db = Database(STATUS_REDIS)
    ob_order = CoreOrder()
    ob_controller = CoreStatusController()
    ob_order.start()
    while True:
        try:
            time.sleep(2)
            #orderID = '15740'
            for orderID in ob_order.getOrderRealList():
                if orderID == '15588':
                    real_info = ob_order.getOrderRealInfo(orderID)
                    if not real_info:
                        # no in config
                        continue
                    else:
                        ob_controller.coreProcess(orderID, real_info, status_db = db)
        except Exception, e:
            print "statuscontroller: %s" % e
