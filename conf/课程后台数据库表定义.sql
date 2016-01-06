--1.课程表
create table if not exists course_info
(
    course_id varchar(128) not null check(course_id!=''), //课程id, 内部生成
    course_name varchar(100) not null check(course_name!=''), //课程名字
    category tinyint not null, // 课程类别 0=直播, 1=录播
    pic_url text, //课程封面图片url
    tag text, //课程标签推荐
    intro text, //课程介绍 H5
    price float(8,1) not null, //课程价格
    major_id text not null, //课程属于的专业
    video_list text, //课程的视频列表
    aspect_ratio varchar(20) not null check(aspect_ratio!=''), //课程下视频的屏幕宽高比
    create_time bigint not null, //课程创建时间
    is_hide tinyint(1) not null, //是否隐藏课程对用户不可见, 1=隐藏, 0=可见
    primary key(course_id)
)engine=innodb default charset=utf8;

--2.录制视频表
create table if not exists record_video
(
    record_id varchar(50) not null check(record_id!=''), //展视播放需要的sdk_id
    gensee_number varchar(20) not null check(gensee_number!=''), //展视播放需要的编号
    watch_passwd varchar(20) not null check(watch_passwd!=''), //展视播放需要的口令
    video_name varchar(100) not null check(video_name!=''), //视频名字
    duration int not null, //视频时长秒数
    file_size int not null, //视频文件大小字节数
    is_trail tinyint not null, // 是否允许试看 0=不允许, 1=允许
    handout text, //讲义
    record_time bigint not null, //视频录制时间
    primary key(record_id)
)engine=innodb default charset=utf8;

--3.直播视频表
create table if not exists live_video
(
    live_id varchar(50) not null check(live_id!=''), //展视播放需要的sdk_id
    gensee_number varchar(20) not null check(gensee_number!=''), //展视播放需要的编号
    watch_passwd varchar(20) not null check(watch_passwd!=''), //展视播放需要的口令
    video_name varchar(100) not null check(video_name!=''), //视频名字
    disp_start_time bigint not null, //直播预计开始时间
    disp_end_time bigint not null, //直播预计结束时间
    handout text, //讲义
    record_id varchar(50), //直播完毕对应的录制视频id
    real_start_time bigint not null, //直播真实开始时间
    real_end_time bigint not null, //直播真实结束时间
    primary key(live_id)
)engine=innodb default charset=utf8;

--4.课程用户表
create table if not exists gensee_user
(
    gensee_uid int not null auto_increment, //映射到展视平台的用户id
    user_id varchar(128) not null check(user_id!=''), //内部用户id
    visit_time bigint not null, //用户映射访问时间
    primary key(gensee_uid),
    unique key (user_id)
)engine=innodb default charset=utf8 auto_increment=1000000001;
alter table gensee_user add unique(user_id);//创建唯一约束

--5.课程购买表
create table if not exists purchase
(
    user_id varchar(128) not null check(user_id!=''), //内部用户id
    course_id varchar(128) not null check(course_id!=''), //课程id, 内部生成
    buy_time bigint not null, //用户映射创建时间
    primary key(user_id, course_id)
)engine=innodb default charset=utf8;

--6.用户观看时间表
create table if not exists watch_record
(
    user_id varchar(128) not null check(user_id!=''), //内部用户id
    course_id varchar(128) not null check(course_id!=''), //课程id, 内部生成
    video_id varchar(50) not null check(video_id!=''), //视频id
    watch_time bigint not null, //观看时间
    watch_progress int not null,//观看进度
    primary key(user_id, course_id, video_id)
)engine=innodb default charset=utf8;

--7.用户点击课程tab时间表, 用于直播提醒区间的计算
create table if not exists tab_click
(
    user_id varchar(128) not null check(user_id!=''), //内部用户id
    click_time bigint not null, //点击时间
    primary key(user_id)
)engine=innodb default charset=utf8;


