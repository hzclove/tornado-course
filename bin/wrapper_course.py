#!/usr/bin/python
# -*- coding: utf8 -*-


import MySQLdb
import json
from data_interface import *


#计算课程的视频相关信息, 包括直播课程的状态等, 缓存会极大优化性能TODO
def compute_course_info(course_list, course_db_cursor):
    for node in course_list:
        if node.category == 0:
            live_ids = [v['video_id'].encode('utf8') for v in json.loads(node.video_list)]
            if live_ids:
                course_db_cursor.execute('select disp_start_time,disp_end_time,real_start_time,real_end_time \
                    from live_video where live_id in (%s)' %(','.join(['"%s"' %(v) for v in live_ids])))
                live_infos = course_db_cursor.fetchall()
                node.update_live_info(live_infos)
        else:
            record_ids = set()
            chapter_list = json.loads(node.video_list)
            for cnode in chapter_list:
                section_list = cnode['section_list']
                for snode in section_list:
                    record_ids |= set([v['video_id'].encode('utf8') for v in snode['video_list']])
            if record_ids:
                course_db_cursor.execute('select is_trail from record_video where \
                    record_id in (%s)' %(','.join(['"%s"' %(v) for v in record_ids])))
                record_infos = course_db_cursor.fetchall()
                node.update_record_info(record_infos)
    return


#对课程进行排序: 1. 直播中 > 即将直播 > 已开课 > 其他直播课和录播课; 2. 按创建时间排序
def sort_course_list(course_list):
    living_plays, soon_plays, lived_plays, other_courses = [], [], [], []
    for node in course_list:
        if node.category == 0 and node.play_status == '直播中':
            living_plays.append(node)
        elif node.category == 0 and node.play_status == '即将直播':
            soon_plays.append(node)
        elif node.category == 0 and node.play_status == '已开课':
        	lived_plays.append(node)
        else:
            other_courses.append(node)
    #按创建时间排序
    living_plays.sort(key=lambda d:d.create_time, reverse=True)
    soon_plays.sort(key=lambda d:d.create_time, reverse=True)
    lived_plays.sort(key=lambda d:d.create_time, reverse=True)
    other_courses.sort(key=lambda d:d.create_time, reverse=True)
    return (living_plays + soon_plays + lived_plays + other_courses)


#获取全部课程列表
def get_all_course(user_id, major_id, page_no, page_size, include_hide):
    #检查参数
    user_id = user_id.strip()
    major_id = major_id.strip()
    page_no = page_no if page_no else '1'
    page_size = page_size if page_size else '10'
    if not page_no.isdigit() or not page_size.isdigit():
        return {'result': 'false', 'msg': 'page_no|page_size is not integer'}
    page_no = int(page_no)
    page_size = int(page_size)
    #是否获取隐藏课程一起返回, app正式客户端不传递该参数
    include_hide = 1 if include_hide.strip() else 0
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #映射用户到展视平台
        if user_id and not course_db_cursor.execute('select * from gensee_user where user_id="%s"' %(user_id)):
            course_db_cursor.execute('insert into gensee_user values(null, "%s", unix_timestamp())' % (user_id))
        #查询课程表
        if not major_id:
            course_db_cursor.execute('select * from course_info where major_id="public" and is_hide<=%d' %(include_hide))
            course_list = course_db_cursor.fetchall()
        else:
            course_db_cursor.execute('select * from course_info where major_id like "%%%s%%" or major_id="public" and is_hide<=%d' %(major_id, include_hide))
            course_list = course_db_cursor.fetchall()
        course_ids = set([v[0].encode('utf8') for v in course_list])
        if course_ids:
            #查询已售数目
            course_db_cursor.execute('select course_id,count(*) as sold_num from purchase where \
                course_id in (%s) group by course_id' %(','.join(['"%s"' %(v) for v in course_ids])))
            sold_nums = course_db_cursor.fetchall()
            sold_nums = dict(zip([v[0].encode('utf8') for v in sold_nums], [v[1] for v in sold_nums]))
            #查询当前用户的购买记录
            my_buys = set()
            if user_id:
                course_db_cursor.execute('select course_id from purchase where user_id="%s"' % (user_id))
                my_buys = set([v[0].encode('utf8') for v in course_db_cursor.fetchall()])
            #数据格式转换
            course_list = [ CourseNode(v, sold_nums, my_buys) for v in course_list ]
            #计算课程的视频相关信息
            compute_course_info(course_list, course_db_cursor)
            #排序: 1. 直播中 > 即将直播 > 已开课 > 其他直播课和录播课; 2. 按创建时间排序
            course_list = sort_course_list(course_list)
            #分页
            course_list = course_list[(page_no-1)*page_size:page_no*page_size]
        result_info = {'result': 'true', 'course_list': [v.pack_res() for v in course_list]}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取我的课程列表
def get_my_course(user_id, major_id, page_no, page_size, include_hide):
    #检查参数
    user_id = user_id.strip()
    if not user_id:
        return {'result': 'false', 'msg': 'user_id is empty'}
    major_id = major_id.strip()
    page_no = page_no if page_no else '1'
    page_size = page_size if page_size else '10'
    if not page_no.isdigit() or not page_size.isdigit():
        return {'result': 'false', 'msg': 'page_no|page_size is not integer'}
    page_no = int(page_no)
    page_size = int(page_size)
    #是否获取隐藏课程一起返回, app正式客户端不传递该参数
    include_hide = 1 if include_hide.strip() else 0
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #查询课程表
        course_db_cursor.execute('select course_info.* from course_info,purchase where \
                purchase.user_id="%s" and course_info.course_id=purchase.course_id and course_info.is_hide<=%d' %(user_id, include_hide))
        course_list = course_db_cursor.fetchall()
        course_ids = set([v[0].encode('utf8') for v in course_list])
        if course_ids:
            #查询已售数目
            course_db_cursor.execute('select course_id,count(*) as sold_num from purchase where \
                course_id in (%s) group by course_id' %(','.join(['"%s"' %(v) for v in course_ids])))
            sold_nums = course_db_cursor.fetchall()
            sold_nums = dict(zip([v[0].encode('utf8') for v in sold_nums], [v[1] for v in sold_nums]))
            #查询当前用户的购买记录
            my_buys = course_ids
            #数据格式转换
            course_list = [ CourseNode(v, sold_nums, my_buys) for v in course_list ]
            #计算课程的视频相关信息
            compute_course_info(course_list, course_db_cursor)
            #排序: 1. 直播中 > 即将直播 > 已开课 > 其他直播课和录播课; 2. 按创建时间排序
            course_list = sort_course_list(course_list)
            #分页
            course_list = course_list[(page_no-1)*page_size:page_no*page_size]
        result_info = {'result': 'true', 'course_list': [v.pack_res() for v in course_list]}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取课程详情
def get_course_detail(user_id, course_id):
    #检查参数
    user_id = user_id.strip()
    course_id = course_id.strip()
    if not course_id:
        return {'result': 'false', 'msg': 'course_id is empty'}
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #映射用户到展视平台
        if user_id and not course_db_cursor.execute('select * from gensee_user where user_id="%s"' %(user_id)):
            course_db_cursor.execute('insert into gensee_user values(null, "%s", unix_timestamp())' % (user_id))
        #查询课程表
        if not course_db_cursor.execute('select * from course_info where course_id="%s"' %(course_id)):
            raise MySQLdb.Error(-1, 'course_id is not exist in db')
        course_info = course_db_cursor.fetchall()[0]
        #查询已售数目
        count = course_db_cursor.execute('select count(*) from purchase where course_id="%s"' %(course_id))
        sold_nums = {course_id : count}
        #查询当前用户的购买记录
        my_buys = set()
        if user_id:
            if course_db_cursor.execute('select course_id from purchase where \
                user_id="%s" and course_id="%s"' %(user_id, course_id)):
                my_buys = set([course_id])
        #数据格式转换
        course_list = [CourseNode(course_info, sold_nums, my_buys)]
        #计算课程的视频相关信息
        compute_course_info(course_list, course_db_cursor)
        result_info = {'result': 'true', 'course': course_list[0].pack_res()}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取录播课程的视频列表
def get_record_list(user_id, course_id):
    #检查参数
    user_id = user_id.strip()
    course_id = course_id.strip()
    if not course_id:
        return {'result': 'false', 'msg': 'course_id is empty'}
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #查询课程表
        if not course_db_cursor.execute('select video_list,aspect_ratio from course_info where category=1 and course_id="%s"' %(course_id)):
            raise MySQLdb.Error(-1, 'course_id is not exist in db')
        #解析出视频id集合,从录播视频表中获取详细信息
        video_list, aspect_ratio = course_db_cursor.fetchall()[0]
        aspect_ratio = aspect_ratio.encode('utf8')
        record_ids = set()
        chapter_list = json.loads(video_list.encode('utf8'))
        for cnode in chapter_list: #第一层是章节
            section_list = cnode['section_list']
            for snode in section_list:
                record_ids |= set([v['video_id'].encode('utf8') for v in snode['video_list']])
        if not record_ids:
            raise IOError('no video in course_dir')
        #录播视频信息
        course_db_cursor.execute('select * from record_video where \
            record_id in (%s)' %(','.join(['"%s"' %(v) for v in record_ids])))
        record_infos = course_db_cursor.fetchall()
        dict_record = dict(zip([v[0].encode('utf8') for v in record_infos], record_infos))
        #我的观看记录
        my_watchs = dict()
        if user_id:
            course_db_cursor.execute('select video_id,watch_progress from watch_record where user_id="%s" and course_id="%s"' % (user_id, course_id))
            my_watchs = course_db_cursor.fetchall()
            my_watchs = dict(zip([v[0].encode('utf8') for v in my_watchs],[v[1] for v in my_watchs]))
        #该课程最近一次观看的视频的id
        if course_db_cursor.execute('select video_id from watch_record where course_id="%s" and user_id="%s" order by watch_time desc limit 1' % (course_id, user_id)):
            last_watch_vid = course_db_cursor.fetchall()[0][0].encode('utf8')
        else:
            last_watch_vid = ''
        #拼装录播课程的目录信息: 用详细video信息替换video_id
        for cnode in chapter_list: #第一层是章节
            section_list = cnode['section_list']
            for snode in section_list:
                snode['video_list'] = [VideoNode(None, dict_record[v['video_id']], my_watchs).pack_res() for v in snode['video_list'] if v['video_id'] in dict_record]
        result_info = {'result': 'true', 'course_dir': chapter_list, 'aspect_ratio': aspect_ratio, 'last_watch_vid': last_watch_vid}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    except IOError, e:
        result_info = {'result': 'false', 'msg': e.args[0]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取直播课程的直播列表
def get_live_list(user_id, course_id):
    #检查参数
    user_id = user_id.strip()
    course_id = course_id.strip()
    if not course_id:
        return {'result': 'false', 'msg': 'course_id is empty'}
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #查询课程表
        if not course_db_cursor.execute('select video_list,aspect_ratio from course_info where category=0 and course_id="%s"' %(course_id)):
            raise MySQLdb.Error(-1, 'course_id is not exist in db')
        #解析出视频id集合,从录播视频表中获取详细信息
        video_list, aspect_ratio = course_db_cursor.fetchall()[0]
        aspect_ratio = aspect_ratio.encode('utf8')
        live_ids = [v['video_id'].encode('utf8') for v in json.loads(video_list.encode('utf8'))]
        #直播视频信息
        course_db_cursor.execute('select * from live_video where live_id in (%s)' %(','.join(['"%s"' %(v) for v in live_ids])))
        live_infos = course_db_cursor.fetchall()
        dict_live = dict(zip([v[0].encode('utf8') for v in live_infos], live_infos))
        #直播对应的回放视频信息,回放视频存在录播视频表中
        playback_ids = [v[7].encode('utf8') for v in live_infos if v[7]]
        dict_playback = {}
        if playback_ids:
            course_db_cursor.execute('select * from record_video where record_id in (%s)' %(','.join(['"%s"' %(v) for v in playback_ids])))
            playback_infos = course_db_cursor.fetchall()
            dict_playback = dict(zip([v[0].encode('utf8') for v in playback_infos], playback_infos))
        #我的观看记录
        my_watchs = dict()
        if user_id:
            course_db_cursor.execute('select video_id,watch_progress from watch_record where user_id="%s" and course_id="%s" ' % (user_id, course_id))
            my_watchs = course_db_cursor.fetchall()
            my_watchs = dict(zip([v[0].encode('utf8') for v in my_watchs],[v[1] for v in my_watchs]))
        #直播视频目录拆分为直播列表和回放列表,并将直播和回放按开始时间排序
        living_list, playback_list = [], []
        for lvid in live_ids:
            if lvid not in dict_live:
                continue 
            live_info = dict_live[lvid]
            real_end_time, record_id = live_info[9], live_info[7].encode('utf8')
            if real_end_time > 0: #直播结束
                playback_list.append(VideoNode(live_info, dict_playback[record_id] if record_id in dict_playback else None, my_watchs))
            else:
                living_list.append(VideoNode(live_info, None, my_watchs))
        playback_list.sort(key=lambda d:d.disp_start_time)
        living_list.sort(key=lambda d:d.disp_start_time)
        #获得映射展示平台的gensee_uid返回
        gensee_uid = ''
        if user_id and course_db_cursor.execute('select gensee_uid from gensee_user where user_id="%s"' % (user_id)):
            gensee_uid = course_db_cursor.fetchall()[0][0]
        result_info = {'result': 'true', \
            'gensee_uid': gensee_uid, \
            'aspect_ratio': aspect_ratio, \
            'living_list': [v.pack_res() for v in living_list], \
            'playback_list': [v.pack_res() for v in playback_list]}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#推送用户观看视频的进度
def push_watch_progress(user_id, course_id, video_id, watch_progress):
    #检查参数
    user_id = user_id.strip()
    course_id = course_id.strip()
    video_id = video_id.strip()
    watch_progress = watch_progress.strip()
    if not user_id or not course_id or not video_id:
        return {'result': 'false', 'mag': 'user_id|course_id|video_id is empty'}
    if not watch_progress.isdigit():
         return {'result': 'false', 'msg': 'watch_progress is not integer'}
    watch_progress = int(watch_progress)
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #检查该用户该课程下的该视频是否观看
        course_db_cursor.execute('insert into watch_record values("%s","%s","%s",unix_timestamp(),%d) \
            on duplicate key update watch_time=unix_timestamp(), watch_progress=%d' \
            % (user_id, course_id, video_id, watch_progress, watch_progress))
        result_info = {'result': 'true'}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#推送用户购买课程的记录支付server推送过来
def push_buy_course(user_id,course_id):
    #检验参数
    user_id = user_id.strip()
    course_id = course_id.strip()
    if not user_id or not course_id:
        return {'result': 'false', 'msg': 'user_id|course_id is empty'}
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        course_db_cursor.execute('insert into purchase values("%s","%s",unix_timestamp()) \
            on duplicate key update buy_time=unix_timestamp()' %(user_id, course_id))
        result_info = {'result': 'true'}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取直播开始和结束与当前时间的时间差
def remind_live_course(user_id, major_id, startup):
    #检验参数
    user_id = user_id.strip()
    major_id = major_id.strip()
    startup = startup.strip() if startup else '0'
    #连接数据库
    try:
        course_db_conn = MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], \
            user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_db_cursor = course_db_conn.cursor()
    except MySQLdb.Error, e:
        return {'result': 'false', 'msg': e.args[1]}
    #业务处理
    try:
        #返回直播课程分为 1.公共课直播 2.majorid对应的直播 3.用户购买的直播课
        course_db_cursor.execute('select video_list from course_info where category=0 and major_id="public" and is_hide=0')
        video_lists = course_db_cursor.fetchall()
        if major_id:
            course_db_cursor.execute('select video_list from course_info where category=0 and major_id like "%%%s%%" and is_hide=0' % (major_id))
            video_lists += course_db_cursor.fetchall()
        if user_id:
            course_db_cursor.execute('select video_list from course_info,purchase where \
                course_info.category=0 and purchase.user_id="%s" and course_info.course_id=purchase.course_id  and course_info.is_hide=0' % (user_id))
            video_lists += course_db_cursor.fetchall()
        #解析出直播视频live_ids列表
        live_ids = []
        for record in video_lists:
            video_list = '' if not record[0] else record[0].encode('utf8')
            if not video_list:
                continue
            live_ids += json.loads(video_list)
        if not live_ids:
            return {'result': 'true', 'start_time': -1, 'end_time': -1}
        #获取所有直播课程的开始时间大于点击时间,结束时间大于当前时间的
        now_time = int(time.time())
        click_time = 0
        if startup != '0' and user_id:
            #当用户点击课程tab时触发请求并记录点击时间
            click_time = now_time
            course_db_cursor.execute('insert into tab_click values("%s",%d) on duplicate key update click_time=%d' % (user_id, click_time, click_time))            
        if startup == '0' and user_id and course_db_cursor.execute('select click_time from tab_click where user_id="%s"' %(user_id)):
            click_time = course_db_cursor.fetchall()[0][0]
        course_db_cursor.execute('select disp_start_time,disp_end_time from live_video \
            where disp_start_time>%d and disp_end_time>%d and live_id in (%s) order by disp_start_time' \
            % (click_time, now_time, ','.join(set(['"%s"' %(v['video_id'].encode('utf8')) for v in live_ids]))))
        live_times = course_db_cursor.fetchall()
        if not live_times:
            result_info = {'result': 'true', 'start_time': -1, 'end_time': -1}
        else:
            #直播提醒的时间区段
            remind_start_time = live_times[0][0]
            remind_end_time = live_times[0][1]
            for record in live_times:
                if record[0] <= remind_end_time:
                    remind_end_time = max(remind_end_time, record[1])
                else:
                    break
            remind_start_time = max(remind_start_time-now_time, 0)
            remind_end_time -= now_time
            result_info = {'result': 'true', 'start_time': remind_start_time, 'end_time': remind_end_time}
    except MySQLdb.Error, e:
        result_info = {'result': 'false', 'msg': e.args[1]}
    except ValueError, ve:
        result_info = {'result': 'false', 'msg': ve}
    #任务提交, 关闭数据库连接
    course_db_conn.commit()
    course_db_cursor.close()
    course_db_conn.close()
    #返回可以直接转为json的格式数据
    return result_info


#获取课程名和课程介绍图片链接用于渲染介绍页
def get_course_intro(course_id):
    course_info = ['', []] #title,images
    #链接数据库
    try:
        course_conn=MySQLdb.connect(host=course_db[0], port=course_db[1], db=course_db[2], user=course_db[3], passwd=course_db[4], charset=course_db[5])
        course_conn.unicode_literal.charset = 'utf8'
        course_conn.string_decoder.charset = 'utf8'
        course_cursor=course_conn.cursor()
    except MySQLdb.Error, e:
        print 'mysql exception %d: %s' %(e.args[0], e.args[1])
        return course_info
    #查询课程名，以及课程介绍图片链接
    try:
        course_cursor.execute('select course_name, intro from course_info where course_id="%s"' % (course_id))
        record = course_cursor.fetchall()[0]
        title = '' if not record[0] else record[0]
        images ='' if not record[1] else record[1]
        course_info[0] = title
    #对图片链接进行分割，列表形式存储
        image_list = list(images.split(';'))
        course_info[1] = image_list
    except MySQLdb.Error, e:
        print 'mysql exception %d: %s' %(e.args[0], e.args[1])
    course_conn.commit()
    course_cursor.close()
    course_conn.close()           
    return course_info

