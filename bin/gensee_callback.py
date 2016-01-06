#!/usr/bin/python
# -*- coding: utf8 -*-


import MySQLdb
import urllib
import urllib2
import json
import time
import threading
from data_interface import *
import sys
reload(sys)
sys.setdefaultencoding('utf8')

gensee_callback_path = 'http://withustudy.gensee.com/integration/site/training'
login_user_name = 'admin@withustudy.com'
login_password = 'withustudy'


#处理展示互动平台触发的回调请求, 包括创建直播课堂/开始直播/结束直播等等
def process_gensee_callback(ClassNo, Operator, Action, Affected, totalusernum):
    #检查参数
    if not ClassNo or not Operator or not Action:
        return
    #根据Action参数区分不同的回调触发行为
    #101:用户进入, 102:课堂创建, 103:直播开始, 104直播暂停
    #105:直播结束, 106:结束录制, 107:用户离开, 110:用户异常离开
    Action_callbacks = {'101': gensee_callback_user_entry, \
                        '102': gensee_callback_create_room, \
                        '103': gensee_callback_start_room, \
                        '105': gensee_callback_end_room}
    if Action not in Action_callbacks:
        return
    Action_callbacks[Action](ClassNo, Operator)
    return


#课堂创建
def gensee_callback_create_room(ClassNo, Operator):
    global gensee_callback_path, login_user_name, login_password
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, me:
        print 'gensee_callback_create_room连接mysql异常: %s' %(me.args[1])
        return
    #业务处理
    try:
        #调用展视的api获取新建课堂的信息字段
        request = urllib2.Request('%s/room/info?roomId=%s&loginName=%s&password=%s' %(gensee_callback_path, ClassNo, login_user_name, login_password))
        response = urllib2.urlopen(request).read()
        ret_json = json.loads(response)
        #课堂信息字段
        live_id = ClassNo
        gensee_number = ret_json[u'number'].encode('utf8')
        watch_passwd = ret_json[u'studentClientToken'].encode('utf8') if u'studentClientToken' in ret_json else ''
        video_name = ret_json[u'subject'].encode('utf8') if u'subject' in ret_json else ''
        disp_start_time = ret_json[u'startDate']/1000 if u'startDate' in ret_json else 0
        disp_end_time = ret_json[u'invalidDate']/1000 if u'invalidDate' in ret_json else 0
        #插入数据库
        if course_db_cursor.execute('select * from live_video where live_id="%s"' %(live_id)) == 0:
            course_db_cursor.execute('insert into live_video values("%s","%s","%s","%s",%d,%d,"","",0,0)' \
                %(live_id, gensee_number, watch_passwd, video_name, disp_start_time, disp_end_time))
    except MySQLdb.Error, me:
        print 'gensee_callback_create_room插入mysql记录失败: %s' %(me.args[1])
    except urllib2.HTTPError, he:
        print 'gensee_callback_create_room请求api的http异常: %d %s' %(he.code, he.reason)
    except urllib2.URLError, ue:
        print 'gensee_callback_create_room请求api的url异常: %d %s' %(ue.reason)
    except ValueError, ve:
        print 'gensee_callback_create_room解析api返回的json失败: %s' %(ve)
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    return


#直播开始
def gensee_callback_start_room(ClassNo, Operator):
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, me:
        print 'gensee_callback_start_room连接mysql异常: %s' %(me.args[1])
        return
    #业务处理
    try:
        #如果直播还未开始则修正直播真实开始时间, 使得课程状态更新为直播中
        course_db_cursor.execute('update live_video set real_start_time=unix_timestamp() where live_id="%s" and real_start_time=0' %(ClassNo))
    except MySQLdb.Error, me:
        print 'gensee_callback_start_room更新直播真实开始时间异常: %s' %(me.args[1])
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    return


#直播结束
def gensee_callback_end_room(ClassNo, Operator):
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, me:
        print 'gensee_callback_end_room连接mysql异常: %s' %(me.args[1])
        return
    #业务处理
    try:
        #如果直播还未结束则修正直播真实结束时间, 使得课程状态更新为已结课
        course_db_cursor.execute('update live_video set real_end_time=unix_timestamp() where live_id="%s" and real_start_time>0 and real_end_time=0' %(ClassNo))
    except MySQLdb.Error, me:
        print 'gensee_callback_end_room更新直播真实结束时间异常: %s' %(me.args[1])
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    return


#用户进入
def gensee_callback_user_entry(ClassNo, Operator):
    return


#直播课堂结束之后, 定期探测录制件的产生
class DetectLiveRecordThread(threading.Thread):
    def __init__(self, interval=60):
        threading.Thread.__init__(self)
        self._interval_ = interval #探测周期, 单位s
        #上次探测前的时间点, 格式 yyyy-MM-dd HH:mm:ss, 每次探测创建时间大于该时间点的录制件
        self._detect_timestamp_ = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    #线程运行
    def run(self):
        global gensee_callback_path, login_user_name, login_password
        while True:
            time.sleep(self._interval_)
            before_detect_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self._detect_live_record_()
            self._detect_timestamp_ = before_detect_timestamp

    #探测录制件的完成并更新到live_video和record_video数据表中
    def _detect_live_record_(self):
        #连接数据库
        try:
            course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
                user=course_db[3], passwd=course_db[4], charset=course_db[5])
            course_db_cursor = course_db_conn.cursor()
        except MySQLdb.Error, me:
            print 'detect_live_record连接mysql异常: %s' %(me.args[1])
            return
        #业务处理
        try:
            #获取新创建的所有录制件的信息
            request = urllib2.Request('%s/record/syn?startTime=%s&loginName=%s&password=%s' % \
                (gensee_callback_path, urllib.quote(self._detect_timestamp_), login_user_name, login_password))
            response = urllib2.urlopen(request).read()
            ret_json = json.loads(response)
            record_list = ret_json[u'list'] if u'list' in ret_json else []
            for record_info in record_list:
                live_id = record_info[u'roomId'].encode('utf8')
                video_name = record_info[u'name'].encode('utf8') if u'name' in record_info else ''
                duration = (record_info[u'recordEndTime']-record_info[u'recordStartTime'])/1000
                file_size = record_info[u'size']
                is_trail = 0
                handout = ''
                record_time = record_info[u'createdTime']/1000
                #根据live_id获取课件信息
                request = urllib2.Request('%s/courseware/list?roomId=%s&loginName=%s&password=%s' %(gensee_callback_path, live_id, login_user_name, login_password))
                response = urllib2.urlopen(request).read()
                ret_json = json.loads(response)
                if u'coursewares' not in ret_json or not ret_json[u'coursewares']:
                    continue #没有录制完成
                courseware = ret_json[u'coursewares'][0]
                record_id = courseware[u'id'].encode('utf8')
                gensee_number = courseware[u'number'].encode('utf8')
                watch_passwd = courseware[u'token'].encode('utf8') if u'token' in courseware else ''
                #在数据表record_video中插入录制件记录
                course_db_cursor.execute('insert into record_video values("%s","%s","%s","%s",%d,%d,%d,"%s",%d)' % \
                    (record_id, gensee_number, watch_passwd, video_name, duration, file_size, is_trail, handout, record_time))
                #修改live_video中的录制件字段
                course_db_cursor.execute('update live_video set record_id="%s" where live_id="%s"' %(record_id, live_id))
        except MySQLdb.Error, me:
            print 'detect_live_record更新直播真实结束时间异常: %s' %(me.args[1])
        except urllib2.HTTPError, he:
            print 'detect_live_record请求api的http异常: %d %s' %(he.code, he.reason)
        except urllib2.URLError, ue:
            print 'detect_live_record请求api的url异常: %d %s' %(ue.reason)
        except ValueError, ve:
            print 'detect_live_record解析api返回的json失败: %s' %(ve)
        #任务提交, 关闭数据库连接
        course_db_conn.commit()
        course_db_cursor.close()
        course_db_conn.close()
        return
