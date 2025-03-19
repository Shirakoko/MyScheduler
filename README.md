# my_schedule任务调度模块说明文档

## 前言

为什么要造这个轮子？因为被sched库坑了。

> 简而言之，就是：
>
> 1. sched本身不具备线程管理功能，需要把sched.run()放到子线程中执行。
> 2. sched.run()是**阻塞式**的，在run的过程中如果重置了任务队列（sched.queue），不能重新run
> 3. 原因是原来已经在run了就会阻塞子线程（底层是time.sleep，阻塞式且不可中断）。

```python
lock = self._lock
q = self._queue
delayfunc = self.delayfunc
timefunc = self.timefunc
pop = heapq.heappop
while True:
    with lock:
        if not q:
            break
        (time, priority, sequence, action,
         argument, kwargs) = q[0]
        now = timefunc()
        if time > now:
            delay = True
        else:
            delay = False
            pop(q)
    if delay:
        if not blocking:
            return time - now
        delayfunc(time - now)
    else:
        action(*argument, **kwargs)
        delayfunc(0)   # Let other threads run
```

所以在想是不是能自己造轮子，实现一个**自带子线程**、**支持任务中断**的线程管理模块？

------

## 特性

`MyScheduler` 是一个轻量级的调度器模块，用于管理和执行定时任务。它基于**优先队列**和**线程管理**，支持动态添加任务、中断任务执行以及重置调度器。

1. **优先级任务**：
   - 使用 `queue.PriorityQueue` 存储任务，确保任务按执行时间排序。
   - 支持动态添加任务，任务按延迟时间独立计时。
2. **线程管理**：
   - 使用单独的线程 (`task_thread`) 监控任务队列并执行任务。
   - 提供 `start()` 和 `stop()` 方法，用于控制调度器线程的生命周期。
3. **事件中断**：
   - 使用 `threading.Event()` 实现任务执行的中断和重置。
   - 支持动态重置调度器，清空任务队列并中断当前任务的延迟执行。
4. **线程通信**：
   - 使用 `queue.PriorityQueue` 作为任务载体， 主线程放入或清空、子线程取出并执行；`threading.Event()` 实现线程间的通信。

## 方法

1. **`add_task(task, delay)`**
   - **功能**：向任务队列中添加任务。
   - 参数：
     - `task` (callable)：要执行的任务函数。
     - `delay` (float)：任务的延迟时间（秒）。
2. **`clear_tasks()`**
   - **功能**：清空任务队列。
3. **`reset()`**
   - **功能**：重置调度器，清空任务队列并中断当前任务的延迟执行。
4. **`start()`**
   - **功能**：启动调度器线程。
5. **`stop()`**
   - **功能**：停止调度器线程。

## 实现细节

### 优先队列排序任务

在 Python 的 `queue.PriorityQueue` 中，任务的排序是通过比较**元组的第一个元素**（即 `execute_time`）来实现的。当将 `(execute_time, task)` 放入 `PriorityQueue` 时，`execute_time` 越小的任务会排在越前面。

```python
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
    logging.info(f"任务已添加到队列，执行时间: {datetime.fromtimestamp(execute_time)}")
```

### 线程执行支持中断

`threading.Event()` 是一个简单的**线程同步**工具，它允许**一个线程通知另一个线程某个事件已经发生**，用来处理阻塞和中断：

- `.wait()`：阻塞线程，直到指定的延迟时间或事件被触发。
- `.set()`：中断阻塞，允许线程重置或重新安排任务。

与time.sleep对比：

|      特性      |  `time.sleep`  |      `threading.Event().wait`      |
| :------------: | :------------: | :--------------------------------: |
| **是否可中断** |    不可中断    |               可中断               |
|  **中断方式**  |       无       |           通过 `.set()`            |
|   **返回值**   |       无       | `True`（被中断）或 `False`（超时） |
|  **适用场景**  | 简单的定时等待 |       需要响应外部事件的等待       |

子线程的线程方法监听主线程中是否.set()

```python
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
                    logging.info("调度器被重置，重新安排任务")
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
                    logging.info("调度器被重置，重新安排任务")
                    continue
        except Exception as e:
            logging.error(f"任务执行出错: {e}")
```

主线程提供重置和停止线程的接口，都需要.set()

```python
def reset(self):
    """
    重置调度器，清空任务队列并中断当前 sleep。
    """
    self.clear_tasks()
    self.reset_event.set()  # 中断 sleep
```

```python
def stop(self):
    """
    停止调度器线程。
    """
    if not self.running:
        return
    self.running = False # 标志位设成False
    self.reset_event.set()  # 中断线程
    logging.info("调度器线程任务已停止")
```

## 使用案例

与业务模块紧耦合的schedule.py使用了该模块，使用案例在my_schedule.py中。