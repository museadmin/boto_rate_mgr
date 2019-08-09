import statistics
import time
import unittest
from multiprocessing import Lock
from threading import Thread
from time import sleep
from boto_rate_manager import ApiQueueManager


class MyTestCase(unittest.TestCase):

    test_metrics = []
    thread_end_times = []
    mutex = Lock()

    def setUp(self):
        self.start = now_millis()
        self.run_times = []
        self.step = 0
        self.thread_end_times = []
        self.brm = None

    def join_queue(self, thread_id):
        waiter = self.brm.enqueue()
        while waiter.waiting is True:
            now = waiter.now()
            if now >= waiter.timeout:
                print(f'ThreadID {thread_id} timed-out now = {now} tm = {waiter.timeout}')
            pass

        with self.mutex:
            self.thread_end_times.append(waiter.now())

    def test_10_waiters_takes_5_seconds(self):
        self.step = 500
        self.brm = ApiQueueManager(self.step)
        self.brm.start()
        threads = []

        for i in range(10):
            threads.append(Thread(target=self.join_queue, args=[i]))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.brm.stop(True)

        self.record_test_metrics()
        self.assertLess((now_millis() - self.start), 6000)

    def test_100_waiters_with_no_contention(self):
        self.step = 100
        self.brm = ApiQueueManager(self.step)
        self.brm.start()
        threads = []

        for i in range(100):
            threads.append(Thread(target=self.join_queue, args=[i]))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        self.brm.stop(True)
        self.record_test_metrics()

        self.assertTrue(self.brm.queue.empty())

    def test_reset_of_rate_reduces_run_time(self):
        self.step = 500
        self.brm = ApiQueueManager(self.step)
        self.brm.start()
        threads = []

        # 50 threads at .5 secs each is 25 secs ish run time
        for i in range(50):
            threads.append(Thread(target=self.join_queue, args=[i]))

        for t in threads:
            t.start()

        sleep(1)

        # Reset rate to 20 from 500 drops runtime form 30ish to 17ish secs
        self.brm.reset_rate(20)

        for t in threads:
            t.join()

        self.brm.stop(True)

        self.record_test_metrics()
        self.assertLess((now_millis() - self.start), 18000)
        self.assertTrue(self.brm.queue.empty())

    def test_print_metric(self):
        self.print_test_metrics()

    def record_test_metrics(self):
        total = 0
        for t in self.thread_end_times:
            total += t

        avg = get_step_average(self.thread_end_times) / 1000
        avg_step_str = '{0: <25}'.format('Average step interval') + "= {:.2f}".format(avg)
        act_step = '{0: <25}'.format('Set step interval') + "= {:.2f}".format(self.step / 1000)

        dev = "{:.2f}".format(statistics.stdev(get_intervals(self.brm.steps, 1000)))
        std_dev = '{0: <25}'.format('Step Standard Deviation') + f'= {dev}'

        self.test_metrics.append(
            self.TestMetric(
                test_name=self._testMethodName,
                std_dev=std_dev,
                act_step=act_step,
                avg_steps=avg_step_str
            )
                                 )

    def print_test_metrics(self):
        for metrics in self.test_metrics:
            print('\n' + metrics.test_name)
            print('\t' + metrics.std_dev)
            print('\t' + metrics.act_step)
            print('\t' + metrics.avg_steps)

    class TestMetric:
        """
        Record the metrics for a run
        """
        def __init__(self, **kwargs):
            self.test_name = kwargs['test_name']
            self.std_dev = kwargs['std_dev']
            self.act_step = kwargs['act_step']
            self.avg_steps = kwargs['avg_steps']


def get_step_average(steps):
    total = 0
    intervals = get_intervals(steps, 1)
    for interval in intervals:
        total = total + interval

    return total / intervals.__len__()


def get_intervals(collection, divisor):
    high = 0
    intervals = []
    for t in reversed(collection):
        if high == 0:
            high = t
            continue

        intervals.append((high - t) / divisor)
        high = t
    return intervals


def now_millis():
    return int(round(time.time() * 1000))


if __name__ == '__main__':
    unittest.main()
