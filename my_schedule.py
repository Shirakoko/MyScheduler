import queue
import threading
import logging
import time
from datetime import datetime


class MyScheduler:
    """
    自定义调度器，提供任务队列、线程管理以及事件中断功能。
    """

    def __init__(self):
        self.task_queue = queue.PriorityQueue()  # 优先队列
        self.task_thread = None  # 调度器线程
        self.reset_event = threading.Event()  # 用于中断 sleep 的事件
        self.running = False  # 调度器是否正在运行

    def add_task(self, task, delay):
        """
        向任务队列中添加任务。

        参数:
            task (callable): 要执行的任务函数。
            delay (float): 任务的延迟时间（秒），指距离添加时的延迟。
        """
        # 计算任务的执行时间
        execute_time = time.time() + delay
        # 将任务和执行时间放入优先级队列
        self.task_queue.put((execute_time, task))
        formatted_time = datetime.fromtimestamp(execute_time).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"MyScheduler.add_task: 任务已添加到队列，执行时间: {formatted_time}, 当前线程是否启动: {self.running}")

    def clear_tasks(self):
        """
        清空任务队列。
        """
        with self.task_queue.mutex:
            self.task_queue.queue.clear()
        logging.info("MyScheduler.clear_tasks: 任务队列已清空")

    def reset(self):
        """
        重置调度器，清空任务队列并中断当前 sleep。
        """
        self.clear_tasks()
        self.reset_event.set()  # 中断 sleep

    def __run_scheduler(self):
        """
        调度器线程的主循环：不断从队列中取出任务并执行。
        """
        while self.running:
            try:
                if self.task_queue.empty():
                    # 如果队列为空，短暂等待后继续检查
                    if self.reset_event.wait(timeout=1):
                        # 如果 reset_event 被设置，需要重置调度器
                        self.reset_event.clear()
                    continue

                # 取出最早需要执行的任务
                execute_time, task = self.task_queue.queue[0]
                now = time.time()
                if now >= execute_time:
                    # 如果任务已到执行时间，取出并执行
                    self.task_queue.get()
                    task()
                else:
                    # 否则，等待到任务的执行时间
                    delay = execute_time - now
                    if self.reset_event.wait(timeout=delay):
                        # 如果 reset_event 被设置，需要重置调度器
                        self.reset_event.clear()
                        continue
            except Exception as e:
                logging.error(f"任务执行出错: {e}")
    
    def get_next_task_time(self):
        """
        获取下一个任务的执行时间。

        返回:
            str: 下一个任务的执行时间字符串，如果队列为空则返回 "当前没有任务"。
        """
        if self.task_queue.empty():
            return "当前没有任务"
        else:
            # 获取下一个任务的执行时间
            execute_time, _ = self.task_queue.queue[0]
            return datetime.fromtimestamp(execute_time).strftime("%Y-%m-%d %H:%M:%S")

    def start(self):
        """
        启动调度器线程。
        """
        if self.running:
            return
        self.running = True # 标志位设成True
        next_task_time = self.get_next_task_time()  # 获取下个任务的执行时间
        logging.info(f"MyScheduler.start: 调度器线程已启动，下个任务执行时间: {next_task_time}")
        if self.task_thread is None or not self.task_thread.is_alive():
            self.task_thread = threading.Thread(target=self.__run_scheduler, daemon=True)
            self.task_thread.start()


    def stop(self):
        """
        停止调度器线程。
        """
        if not self.running:
            return
        self.running = False # 标志位设成False
        self.reset_event.set()  # 中断线程
        logging.info("MyScheduler.stop: 调度器线程已停止")
