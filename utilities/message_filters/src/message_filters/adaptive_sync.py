import threading
from functools import reduce
from sortedcontainers import SortedDict
from message_filters import SimpleFilter
import rospy


class AdaptiveTimeSynchronizer(SimpleFilter):
    """
    Synchronizes messages by their timestamps.
    """

    def __init__(self, fs, queue_size=2, reset=True):
        super().__init__()
        self.connectInput(fs)
        self.queue_size = queue_size
        self.lock = threading.Lock()
        self.enable_reset = reset
        self.latest_time = rospy.Time()

    def connectInput(self, fs):
        self.queues = [SortedDict() for f in fs]
        self.input_connections = [f.registerCallback(self.add, q) for f, q in zip(fs, self.queues)]

    def add(self, msg, my_queue):
        with self.lock:
            # check for jump backs of ROS time
            now = rospy.Time.now()
            is_simtime = not rospy.rostime.is_wallclock()
            if is_simtime and self.enable_reset and now < self.latest_time:
                rospy.logwarn(f"Detected jump back in time: {self.latest_time} -> {now}. "
                              "Clearing message filter queues")
                for q in self.queues:
                    q.clear()
            self.latest_time = now

            # store new message, but limit to queue_size
            t = msg.header.stamp
            my_queue[t] = msg
            while len(my_queue) > self.queue_size:
                my_queue.popitem(0)  # delete oldest message (with smallest stamp)

            if any([not q for q in self.queues]):
                return  # we don't yet have a message in each queue

            # time ranges yield from heads of all queues: <0: past, >0: future stamps
            time_range = [q.peekitem(-1)[0] - t for q in self.queues]
            tmin, tmax = min(time_range), max(time_range)

            # only consider message that are within the time range of the heads
            candidate_lists = [[item for item in q.items() if item[0] if item[0] - t >=
                                tmin and item[0] - t <= tmax] for q in self.queues]
            # sort candidates by their time distance to the current message
            candidate_lists = [sorted(l, key=lambda item: abs(item[0]-t)) for l in candidate_lists]
            # fetch first item from each candidate list
            times, msgs = zip(*[l[0] for l in candidate_lists])
            for t, q in zip(times, self.queues):  # remove messages older than the used one
                while len(q) and q.peekitem(0)[0] <= t:
                    q.popitem(0)

            self.signalMessage(*msgs)
