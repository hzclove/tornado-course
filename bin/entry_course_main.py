 #!/usr/bin/python
# -*- coding: utf8 -*-

import os
import json
import time
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor
from tornado.options import define, options
define("port", default=8300, help="run on the given port", type=int)

import wrapper_course, gensee_callback

ExecutorNum = 100

#处理课程列表请求
class CourseListHandler(tornado.web.RequestHandler):
    '''
        1. get_all_course?uid=&major_id=&page_no=&page_size= 获取全部课程列表
        2. get_my_course?uid=&major_id=&page_no=&page_size= 获取我的课程列表
    '''
    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, input):
        user_id = str(self.get_argument('uid', ''))
        major_id = str(self.get_argument('major_id', ''))
        page_no = str(self.get_argument('page_no', ''))
        page_size = str(self.get_argument('page_size', ''))
        include_hide = str(self.get_argument('include_hide', ''))
        operators = {'get_all_course': self._get_all_course_, \
            'get_my_course': self._get_my_course_}
        result_info = yield operators[input](user_id, major_id, page_no, page_size, include_hide)
        self.write(json.dumps(result_info))
        self.finish()

    @run_on_executor
    def _get_all_course_(self, user_id, major_id, page_no, page_size, include_hide):
        return wrapper_course.get_all_course(user_id, major_id, page_no, page_size, include_hide)
        
    @run_on_executor
    def _get_my_course_(self, user_id, major_id, page_no, page_size, include_hide):
        return wrapper_course.get_my_course(user_id, major_id, page_no, page_size, include_hide)

    def write_error(self, status_code, **kwargs):
        result_info = {'result': 'false', 'msg': 'http error %d' %(status_code)}
        self.write(json.dumps(result_info))


#处理课程信息请求
class CourseInfoHandler(tornado.web.RequestHandler):
    '''
        1. get_course_detail?uid=&course_id= 获取课程详情
        2. get_record_list?uid=&course_id= 获取录播课程的视频列表
        3. get_live_list?uid=&course_id= 获取直播课程的直播列表
    '''
    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, input):
        user_id = str(self.get_argument('uid', ''))
        course_id = str(self.get_argument('course_id', ''))
        operators = {'get_course_detail': self._get_course_detail_, \
            'get_record_list': self._get_record_list_, \
            'get_live_list': self._get_live_list_}
        result_info = yield operators[input](user_id, course_id)
        self.write(json.dumps(result_info))
        self.finish()

    @run_on_executor
    def _get_course_detail_(self, user_id, course_id):
        return wrapper_course.get_course_detail(user_id, course_id)

    @run_on_executor
    def _get_record_list_(self, user_id, course_id):
        return wrapper_course.get_record_list(user_id, course_id)

    @run_on_executor
    def _get_live_list_(self, user_id, course_id):
        return wrapper_course.get_live_list(user_id, course_id)

    def write_error(self, status_code, **kwargs):
        result_info = {'result': 'false', 'msg': 'http error %d' %(status_code)}
        self.write(json.dumps(result_info))


#处理用户行为请求
class UserActionHandler(tornado.web.RequestHandler):
    '''
        1. push_watch_progress?uid=&course_id=&video_id=&watch_progress 推送用户观看视频的进度
        2. push_buy_course?uid=&course_id=推送用户购买课程的记录支付server推送过来
    '''
    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self, input):
    	user_id = self.get_argument('uid', '')
    	course_id = self.get_argument('course_id', '')
    	video_id = self.get_argument('video_id', '')
    	watch_progress = self.get_argument('watch_progress', '')
    	if input == 'push_watch_progress':
    		result_info = yield self._push_watch_progress_(user_id, course_id, video_id, watch_progress)
    	elif input == 'push_buy_course':
    		result_info = yield self._push_buy_course_(user_id, course_id)
        self.write(json.dumps(result_info)) 
        self.finish()

    @run_on_executor
    def _push_watch_progress_(self, user_id, course_id, video_id, watch_progress):
    	return wrapper_course.push_watch_progress(user_id, course_id, video_id, watch_progress)

    @run_on_executor
    def _push_buy_course_(self, user_id, course_id):
    	return wrapper_course.push_buy_course(user_id, course_id)

    def write_error(self, status_code, **kwargs):
        result_info = {'result': 'false', 'msg': 'http error %d' %(status_code)}
        self.write(json.dumps(result_info))

#直播课程提醒接口
class RemindCourseHandler(tornado.web.RequestHandler):
    '''remind_live_course?uid=&major=&startup= 请求获取开始和结束时间的时间差'''

    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        user_id = self.get_argument('uid', '')
        major_id = self.get_argument('major', '')
        startup = self.get_argument('startup', '')
        result_info = yield self._remind_live_course_(user_id, major_id, startup)
        self.write(json.dumps(result_info))
        self.finish()

    @run_on_executor
    def _remind_live_course_(self, user_id, major_id, startup):
        return wrapper_course.remind_live_course(user_id, major_id, startup)

#展视互动触发的回调请求
class GenseeCallbackHandler(tornado.web.RequestHandler):
    '''process_gensee_callback?ClassNo=&Operator=&Action=&Affected=&totalusernum= 展视互动上用户动作触发的回调请求'''

    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        ClassNo = self.get_argument('ClassNo', '')
        Operator = self.get_argument('Operator', '')
        Action = self.get_argument('Action', '')
        Affected = self.get_argument('Affected', '')
        totalusernum = self.get_argument('totalusernum', '')
        yield self._process_gensee_callback_(ClassNo, Operator, Action, Affected, totalusernum)
        self.write('')
        self.finish()

    @run_on_executor
    def _process_gensee_callback_(self, ClassNo, Operator, Action, Affected, totalusernum):
        gensee_callback.process_gensee_callback(ClassNo, Operator, Action, Affected, totalusernum)

#课程介绍页，根据course_id渲染指定的课程
class CourseIntroHandler(tornado.web.RequestHandler):
    '''course/intro?course_id=课程对应的课程介绍页渲染'''
    global ExecutorNum
    executor = ThreadPoolExecutor(ExecutorNum)

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        course_id = self.get_argument('course_id', '').strip()
        course_info = yield self.__get_course_info__(course_id)
        #对课程分享页进行渲染
        self.render('courseintro.html', title=course_info[0], images=course_info[1])

    @run_on_executor
    def __get_course_info__(self, course_id):
        return wrapper_course.get_course_intro(course_id)

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        handlers=[
            (r"/course/(get_all_course|get_my_course)", CourseListHandler),
            (r'/course/(get_course_detail|get_record_list|get_live_list)', CourseInfoHandler),
            (r'/course/(push_watch_progress|push_buy_course)', UserActionHandler),
            (r'/course/remind_live_course', RemindCourseHandler),
            (r'/course/process_gensee_callback', GenseeCallbackHandler),
            (r'/course/intro', CourseIntroHandler),
        ],
        template_path = os.path.join(os.path.dirname(__file__), "templates"),
        static_path = os.path.join(os.path.dirname(__file__), "static")
    )

    #探测直播课堂录制件产出
    detect_live_record_thread = gensee_callback.DetectLiveRecordThread()
    detect_live_record_thread.start()

    #启动web服务器
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
