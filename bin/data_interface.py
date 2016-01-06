#!/usr/bin/python
# -*- coding: utf8 -*-


import time

#课程显示"即将开课", 视频显示"还有X天"的倒计时间段, 单位秒
soon_open_interval = 259200
#视频和课程显示"即将直播"的倒计时间段, 单位秒
soon_live_interval = 3600

course_db = ['10.51.111.18', 3306, 'course', 'work', 'work', 'utf8']

#直播时间格式化
def format_live_time(start_time, end_time):
    start_date, start_hmtime = time.strftime('%Y.%m.%d %H:%M', time.localtime(start_time)).split()
    end_date, end_hmtime = time.strftime('%Y.%m.%d %H:%M', time.localtime(end_time)).split()
    if start_date == end_date:
        live_time = '%s  %s~%s' %(start_date, start_hmtime, end_hmtime)
    else:
        live_time = '%s~%s' %(start_date, end_date)
    return live_time


#课程信息
class CourseNode:
    def __init__(self, node_info, sold_nums, my_buys):
        self.course_id = node_info[0].encode('utf8') if node_info[0] else '' #课程内部id
        self.course_name = node_info[1].encode('utf8') if node_info[1] else '' #课程名字
        self.category = 1 if node_info[2] else 0 #课程类别 0=直播 1=录播
        self.pic_url = node_info[3].encode('utf8') if node_info[3] else '' #课程封面图片链接
        self.tag = node_info[4].encode('utf8') if node_info[4] else '' #课程推荐标签
        self.intro = 'http://course.kdzikao.com/course/intro?course_id=%s' % (self.course_id)#课程介绍
        self.price = node_info[6] if node_info[6] else 0.0 #课程当前价格
        self.major_id = node_info[7].encode('utf8') if node_info[7] else '' #课程对应专业集合
        self.video_list = node_info[8].encode('utf8') if node_info[8] else '' #课程视频列表信息
        self.aspect_ratio = node_info[9].encode('utf8') if node_info[9] else '' #课程视频屏幕宽高比
        self.create_time = node_info[10] if node_info[10] else 0 #课程创建时间
        self.sold_num = sold_nums[self.course_id] if self.course_id in sold_nums else 0 #课程已售数
        self.buy_status = int(self.course_id in my_buys) #课程是否已被当前用户购买
        #直播课程的播放状态,课时,直播时间
        self.play_status, self.course_hour, self.live_time = '', 0, ''
        #录播课程的试看标记,视频个数
        self.is_trail, self.video_num = 0, 0

    #更新直播课程信息: 课时,最近一次直播时间,播放状态
    #"未开课", "即将开课", "已开课", "即将直播", "直播中", "已结课"
    def update_live_info(self, live_infos):
        global soon_open_interval, soon_live_interval
        #课时
        if not live_infos:
            return
        #计算真实课时, 四舍五入
        for i in xrange(0, len(live_infos)):
            disp_start_time, disp_end_time, real_start_time, real_end_time = live_infos[i]
            self.course_hour += (disp_end_time - disp_start_time)
        self.course_hour = int(round(self.course_hour/3600.0))
        #最近一次直播时间, 根据展示直播时间选取, 先对视频列表按照预期结束时间从小到大排序
        #依据常识:视频按照预期时间的排序同按真实时间的排序是一致的
        live_infos = list(live_infos)
        live_infos.sort(key=lambda x:x[1])
        now_timestamp = int(time.time())
        #未开课/即将开课: 第一课未开播并且距离预计开始时间还差3天以上则"未开课", 还差3天以内1小时以上则"即将开课"
        disp_start_time, disp_end_time, real_start_time, real_end_time = live_infos[0]
        if real_start_time == 0: #真实开始时间取0表示未赋值, 即未开播
            if now_timestamp + soon_open_interval < disp_start_time:
                self.play_status = '未开课'
                self.live_time = format_live_time(disp_start_time, disp_end_time)
                return
            if now_timestamp + soon_live_interval < disp_start_time:
                self.play_status = '即将开课'
                self.live_time = format_live_time(disp_start_time, disp_end_time)
                return
        #已结课: 最后一课已经结束则"已结课"
        disp_start_time, disp_end_time, real_start_time, real_end_time = live_infos[-1]
        if real_end_time > 0:
            self.play_status = '已结课'
            self.live_time = format_live_time(disp_start_time, disp_end_time)
            return
        #直播中/即将直播/已开课: 根据最早的未结束的课的时间判断
        for i in xrange(0, len(live_infos)):
            disp_start_time, disp_end_time, real_start_time, real_end_time = live_infos[i]
            if real_end_time > 0:
                continue
            #真实开始时间取0表示未赋值, 即未结束
            self.live_time = format_live_time(disp_start_time, disp_end_time)
            if real_start_time > 0:
                self.play_status = '直播中'
            elif now_timestamp + soon_live_interval >= disp_start_time:
                self.play_status = '即将直播'
            else:
                self.play_status = '已开课'
            break
        return
        

    #更新录播课程信息: 试看标记,视频个数,播放状态
    def update_record_info(self, record_infos):
        self.video_num = len(record_infos)
        self.is_trail = int(len([v for v in record_infos if v[0]]) > 0)
        self.play_status = '观看' if self.buy_status else ''
        return

    def pack_res(self):
        keys = ['course_id', 'course_name', 'pic_url', 'tag', 'intro', 'price', \
            'sold_num', 'buy_status', 'category', \
            'play_status', 'course_hour', 'live_time', 'is_trail', 'video_num']
        values = [self.course_id, self.course_name, self.pic_url, self.tag, self.intro, self.price, \
            self.sold_num+50, self.buy_status, self.category, \
            self.play_status, self.course_hour, self.live_time, self.is_trail, self.video_num]
        return dict(zip(keys, values))


#视频信息
class VideoNode:
    def __init__(self, live_info, record_info, my_watchs):
        self.video_id = record_info[0].encode('utf8') if record_info else live_info[0].encode('utf8') #视频id，录播时为cc平台上的videoid
        self.video_number = record_info[1].encode('utf8') if record_info else live_info[1].encode('utf8') #视频编号,在录播视频时为空
        self.watch_passwd = record_info[2].encode('utf8') if record_info else live_info[2].encode('utf8') #视频观看口令，当为录播视频时不需要该返回值        
        self.video_name = record_info[3].encode('utf8') if record_info else live_info[3].encode('utf8') #视频名字
        self.handout = record_info[7].encode('utf8') if record_info else live_info[6].encode('utf8') #视频讲义
        self.disp_start_time = live_info[4] if live_info and live_info[4] else 0 #开始时间用于目录排序
        self.duration = record_info[4] if record_info else 0 #视频时长,对录播和直播回放有意义
        self.watch_progress = my_watchs[self.video_id] if self.video_id in my_watchs else 0 #已看时长,对录播和直播回放有意义
        self.file_size = record_info[5] if record_info else 0 #视频文件大小,对录播和直播回放有意义
        self.is_trail = record_info[6] if record_info else 0 #视频是否允许试看,对录播有意义
        self.live_time = format_live_time(live_info[4], live_info[5]) if live_info else '' #直播时间,对直播和直播回放有意义
        self.play_status = ''
        if live_info:
            self._compute_play_status_(record_info, live_info) #视频的直播状态

    #计算直播视频的状态: "未开课", "还有X天", "还有X小时", "即将直播", "直播中", "转录中", ""
    def _compute_play_status_(self, record_info, live_info):
        global soon_open_interval, soon_live_interval
        disp_start_time, disp_end_time, real_start_time, real_end_time = live_info[4], live_info[5], live_info[8], live_info[9]
        now_timestamp = int(time.time())
        if real_end_time > 0:
            self.play_status = '' if record_info else '转录中'
        elif real_start_time > 0:
            self.play_status = '直播中'
        elif now_timestamp + soon_live_interval > disp_start_time:
            self.play_status = '即将直播'
        elif now_timestamp + 86400 > disp_start_time:
            self.play_status = '还有%d小时' %((disp_start_time-now_timestamp)/3600)
        elif now_timestamp + soon_open_interval > disp_start_time:
            self.play_status = '还有%d天' %((disp_start_time-now_timestamp)/86400)
        else:
            self.play_status = '未开课'
        return

    def pack_res(self):
        keys = ['video_id', 'video_number', 'watch_passwd', 'video_name', 'handout', \
            'duration', 'watch_progress', 'file_size', 'is_trail', 'live_time', 'play_status']
        values = [self.video_id, self.video_number, self.watch_passwd, self.video_name, self.handout, \
            self.duration, self.watch_progress, self.file_size, self.is_trail, self.live_time, self.play_status]
        return dict(zip(keys, values))
