import logging
from datetime import datetime, timedelta
from tool.my_schedule import MyScheduler
from savior_editor.savior_editor import SaviorEditor
from savior_editor.sync_widget import SyncWidget

# 全局调度器实例
scheduler = MyScheduler()

# 定时任务时间
SYNC_P4_TIME = "17:14"  # 定时拉取更新的时间
KILL_PROCESS = True  # 是否启用杀进程功能
savior_window = None

# 是否启用定时任务
ENABLE_SCHEDULER = True  # 默认启用


def enable_scheduler_and_update_status(enable=None):
    """
    启用或禁用定时任务
    """
    if enable is not None:
        global ENABLE_SCHEDULER
        ENABLE_SCHEDULER = enable
        
        if ENABLE_SCHEDULER:
            # 如果定时任务被重新启用，检查任务是否过期
            now = datetime.now()
            today = now.date()
            next_run = datetime.strptime(f"{today} {SYNC_P4_TIME}", "%Y-%m-%d %H:%M")

            if now >= next_run:
                # 如果任务已经过期，清空任务队列并重新安排任务
                scheduler.clear_tasks()
                __schedule_next_run()
                scheduler.start()
        else:
            scheduler.stop()

    if savior_window:
        savior_window.update_task_status_label(get_next_task_status())  # 更新界面文字
    logging.info(f"定时任务已 {'启用' if enable else '禁用'}")

def get_next_task_status():
    """
    返回定时任务的状态信息

    返回值:
        str: 如果定时任务开启，返回下次任务的时间；否则返回“没有开启定时任务”。
    """
    global ENABLE_SCHEDULER
    if not ENABLE_SCHEDULER:
        return "当前定时更新未开启"

    # 计算下一次任务的时间
    now = datetime.now()
    today = now.date()
    next_run = datetime.strptime(f"{today} {SYNC_P4_TIME}", "%Y-%m-%d %H:%M")

    # 如果当前时间已经超过任务时间，则将任务安排到明天
    if now >= next_run:
        next_run += timedelta(days=1)

    # 格式化时间字符串
    next_run_str = next_run.strftime("%Y/%m/%d %H:%M")
    return f"下次定时更新任务安排于 {next_run_str}，\n温馨提醒：拉取前请检查工作区是否有未shelve的变更~"

def __sync_p4():
    """
    定时任务：唤起界面并调用同步操作
    """
    if SyncWidget.is_sync_widget_open():
        return
    logging.info("定时任务：唤起界面并调用同步操作")
    global savior_window
    if savior_window is None:
        savior_window = SaviorEditor()
    savior_window.restore_from_tray_public()  # 从托盘恢复窗口
    # 根据 KILL_PROCESS 决定是否启用杀进程功能
    savior_window._show_sync_widget(sync_p4_with_clean_no_prompt=not KILL_PROCESS, sync_p4_with_kill_process=KILL_PROCESS)


def __schedule_next_run():
    """
    计算下一次任务执行的时间，并将任务放入队列
    """
    now = datetime.now()
    today = now.date()
    # 将今天的日期和任务时间组合成下一次执行的时间
    next_run = datetime.strptime(f"{today} {SYNC_P4_TIME}", "%Y-%m-%d %H:%M")
    # 如果当前时间已经超过任务时间，则将任务安排到明天
    if now >= next_run:
        next_run += timedelta(days=1)
    # 计算距离下一次执行的时间差（秒）
    delay = (next_run - now).total_seconds()
    # 将任务放入队列
    scheduler.add_task(__sync_p4, delay)


def start_scheduler(savior_window_instance=None, sync_p4_time=None, kill_process=None, enable_scheduler=None):
    """
    初始化调度器并启动定时任务线程

    参数:
        savior_window_instance: 可选，SaviorEditor 实例
        sync_p4_time: 可选，定时任务时间字符串（格式为 "HH:MM"）
        kill_process: 可选，是否启用杀进程功能
    """
    global savior_window, SYNC_P4_TIME, KILL_PROCESS, ENABLE_SCHEDULER
    if savior_window_instance is not None:
        savior_window = savior_window_instance

    if sync_p4_time is not None:
        SYNC_P4_TIME = sync_p4_time

    if kill_process is not None:
        KILL_PROCESS = kill_process
    
    if enable_scheduler is not None:
        ENABLE_SCHEDULER = enable_scheduler
    
    # 初始化任务队列
    scheduler.clear_tasks()

    # 安排第一次任务
    __schedule_next_run()
    # 启动定时任务线程
    scheduler.start()


def update_sync_time(hour, minute):
    """
    更新定时任务的时间并重置调度器
    """
    global SYNC_P4_TIME
    # 格式化时间为 "HH:MM"
    SYNC_P4_TIME = f"{int(hour):02d}:{int(minute):02d}"
    enable_scheduler_and_update_status() # 设置时间后也要更新状态
    scheduler.reset()
    __schedule_next_run() # 安排下一次任务

def update_kill_process(enable_kill_process):
    """
    更新是否启用杀进程功能并重置调度器
    """
    global KILL_PROCESS
    KILL_PROCESS = enable_kill_process
    scheduler.reset()
    __schedule_next_run() # 安排下一次任务