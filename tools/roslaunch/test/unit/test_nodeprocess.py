#!/usr/bin/env python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import unittest
    
import rospkg
import roslib.packages
import logging
logging.getLogger('roslaunch').setLevel(logging.CRITICAL)

## Test roslaunch.nodeprocess
class TestNodeprocess(unittest.TestCase):

    def test_create_master_process(self):
        from roslaunch.core import Node, Machine, Master, RLException
        from roslaunch.nodeprocess import create_master_process, LocalProcess
        
        ros_root = '/ros/root'
        port = 1234
        type = Master.ROSMASTER
        run_id = 'foo'

        # test invalid params
        try:
            create_master_process(run_id, type, ros_root, -1)
            self.fail("shoud have thrown RLException")
        except RLException: pass
        try:
            create_master_process(run_id, type, ros_root, 10000000)
            self.fail("shoud have thrown RLException")
        except RLException: pass
        try:
            create_master_process(run_id, 'foo', ros_root, port)
            self.fail("shoud have thrown RLException")
        except RLException: pass

        # test valid params
        p = create_master_process(run_id, type, ros_root, port)
        self.assertTrue(isinstance(p, LocalProcess))
        self.assertEqual(p.args[0], 'rosmaster')
        idx = p.args.index('-p')
        self.assertFalse(idx < 1)
        self.assertEqual(p.args[idx+1], str(port))
        self.assertTrue('--core' in p.args)

        self.assertEqual(p.package, 'rosmaster')
        p = create_master_process(run_id, type, ros_root, port)
        
        self.assertEqual(create_master_process(run_id, type, ros_root, port, sigint_timeout=3).sigint_timeout, 3)
        self.assertEqual(create_master_process(run_id, type, ros_root, port, sigint_timeout=1).sigint_timeout, 1)
        self.assertRaises(RLException, create_master_process, run_id, type, ros_root, port, sigint_timeout=0)

        self.assertEqual(create_master_process(run_id, type, ros_root, port, sigterm_timeout=3).sigterm_timeout, 3)
        self.assertEqual(create_master_process(run_id, type, ros_root, port, sigterm_timeout=1).sigterm_timeout, 1)
        self.assertRaises(RLException, create_master_process, run_id, type, ros_root, port, sigterm_timeout=0)
        
        # TODO: have to think more as to the correct environment for the master process
        
        
    def test_create_node_process(self):
        from roslaunch.core import Node, Machine, RLException
        from roslaunch.node_args import NodeParamsException
        from roslaunch.nodeprocess import create_node_process, LocalProcess
        # have to use real ROS configuration for these tests
        ros_root = os.environ['ROS_ROOT']
        rpp = os.environ.get('ROS_PACKAGE_PATH', None)
        master_uri = 'http://masteruri:1234'
        m = Machine('name1', ros_root, rpp, '1.2.3.4')

        run_id = 'id'
        
        # test invalid params
        n = Node('not_a_real_package','not_a_node')
        n.machine = m
        n.name = 'foo'
        try: # should fail b/c node cannot be found
            create_node_process(run_id, n, master_uri)
            self.fail("should have failed")
        except NodeParamsException:
            pass
        
        # have to specify a real node
        n = Node('roslaunch','talker.py')
        n.machine = m
        try: # should fail b/c n.name is not set
            create_node_process(run_id, n, master_uri)
            self.fail("should have failed")
        except ValueError:
            pass
        
        # have to specify a real node
        n = Node('roslaunch','talker.py')

        n.machine = None
        n.name = 'talker'
        try: # should fail b/c n.machine is not set
            create_node_process(run_id, n, master_uri)
            self.fail("should have failed")
        except RLException:
            pass

        # basic integration test
        n.machine = m
        p = create_node_process(run_id, n, master_uri)
        self.assertTrue(isinstance(p, LocalProcess))

        # repeat some setup_local_process_env tests
        d = p.env
        self.assertEqual(d['ROS_MASTER_URI'], master_uri)
        self.assertEqual(d['ROS_ROOT'], ros_root)
        self.assertEqual(d['PYTHONPATH'], os.environ['PYTHONPATH'])
        if rpp:
            self.assertEqual(d['ROS_PACKAGE_PATH'], rpp)
        for k in ['ROS_IP', 'ROS_NAMESPACE']:
            if k in d:
                self.fail('%s should not be set: %s'%(k,d[k]))

        # test package and name
        self.assertEqual(p.package, 'roslaunch')
        # - no 'correct' full answer here 
        self.assertTrue(p.name.startswith('talker'), p.name)

        # test log_output
        n.output = 'log'
        self.assertTrue(create_node_process(run_id, n, master_uri).log_output)
        n.output = 'screen'
        self.assertFalse(create_node_process(run_id, n, master_uri).log_output)

        # test respawn
        n.respawn = True
        self.assertTrue(create_node_process(run_id, n, master_uri).respawn)
        n.respawn = False
        self.assertFalse(create_node_process(run_id, n, master_uri).respawn)        

        # test cwd
        n.cwd = None
        self.assertEqual(create_node_process(run_id, n, master_uri).cwd, None)
        n.cwd = 'ros-root'
        self.assertEqual(create_node_process(run_id, n, master_uri).cwd, 'ros-root')
        n.cwd = 'node'                
        self.assertEqual(create_node_process(run_id, n, master_uri).cwd, 'node')

        # sigint timeout
        self.assertEqual(create_node_process(run_id, n, master_uri).sigint_timeout, 15)
        self.assertEqual(create_node_process(run_id, n, master_uri, sigint_timeout=1).sigint_timeout, 1)
        self.assertRaises(RLException, create_node_process, run_id, n, master_uri, sigint_timeout=0)

        # sigterm timeout
        self.assertEqual(create_node_process(run_id, n, master_uri).sigterm_timeout, 2)
        self.assertEqual(create_node_process(run_id, n, master_uri, sigterm_timeout=1).sigterm_timeout, 1)
        self.assertRaises(RLException, create_node_process, run_id, n, master_uri, sigterm_timeout=0)

        # test args

        # - simplest test (no args)
        n.args = ''
        p = create_node_process(run_id, n, master_uri)
        # - the first arg should be the path to the node executable
        rospack = rospkg.RosPack()
        cmd = roslib.packages.find_node('roslaunch', 'talker.py', rospack)[0]
        self.assertEqual(p.args[0], cmd)

        # - test basic args
        n.args = "arg1 arg2 arg3"
        p = create_node_process(run_id, n, master_uri)
        self.assertEqual(p.args[0], cmd)
        for a in "arg1 arg2 arg3".split():
            self.assertTrue(a in p.args)
            
        # - test remap args
        n.remap_args = [('KEY1', 'VAL1'), ('KEY2', 'VAL2')]
        p = create_node_process(run_id, n, master_uri)
        self.assertTrue('KEY1:=VAL1' in p.args)        
        self.assertTrue('KEY2:=VAL2' in p.args)
        
        # - test __name
        n = Node('roslaunch','talker.py')
        n.name = 'fooname'
        n.machine = m
        self.assertTrue('__name:=fooname' in create_node_process(run_id, n, master_uri).args)
        
        # - test substitution args
        os.environ['SUB_TEST'] = 'subtest'
        os.environ['SUB_TEST2'] = 'subtest2'
        n.args = 'foo $(env SUB_TEST) $(env SUB_TEST2)'
        p = create_node_process(run_id, n, master_uri)        
        self.assertFalse('SUB_TEST' in p.args)
        self.assertTrue('foo' in p.args)
        self.assertTrue('subtest' in p.args)
        self.assertTrue('subtest2' in p.args)

    def test_local_process_stop_timeouts(self):
        from roslaunch.core import Node, Machine

        # have to use real ROS configuration for these tests
        ros_root = os.environ['ROS_ROOT']
        rpp = os.environ.get('ROS_PACKAGE_PATH', None)
        master_uri = 'http://masteruri:1234'
        m = Machine('name1', ros_root, rpp, '1.2.3.4')

        run_id = 'id'

        n = Node('roslaunch', 'signal_logger.py')
        n.name = 'logger'
        n.machine = m
        self.check_stop_timeouts(master_uri, n, run_id, 1.0, 1.0)
        self.check_stop_timeouts(master_uri, n, run_id, 0.00001, 1.0)
        # shorter sigterm times are risky in the test - the signal file might not get written; but in the wild, it's ok
        self.check_stop_timeouts(master_uri, n, run_id, 1.0, 0.001)
        self.check_stop_timeouts(master_uri, n, run_id, 2.0, 3.0)

    def check_stop_timeouts(self, master_uri, n, run_id, sigint_timeout, sigterm_timeout):
        from roslaunch.nodeprocess import create_node_process, LocalProcess

        import time
        import tempfile
        import signal

        signal_log_file = os.path.join(tempfile.gettempdir(), "signal.log")

        try:
            os.remove(signal_log_file)
        except OSError:
            pass

        p = create_node_process(run_id, n, master_uri, sigint_timeout=sigint_timeout, sigterm_timeout=sigterm_timeout)
        self.assertTrue(isinstance(p, LocalProcess))

        p.start()
        time.sleep(3)  # give it time to start

        before_stop_call_time = time.time()
        p.stop()
        after_stop_call_time = time.time()

        signals = dict()
        
        try:
            with open(signal_log_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    sig, timestamp = line.split(" ")
                    sig = int(sig)
                    timestamp = float(timestamp)
                    signals[sig] = timestamp
        except IOError:
            self.fail("Could not open %s" % signal_log_file)

        self.assertSetEqual({signal.SIGINT, signal.SIGTERM}, set(signals.keys()))
        self.assertAlmostEqual(before_stop_call_time, signals[signal.SIGINT], delta=1)
        self.assertAlmostEqual(before_stop_call_time, signals[signal.SIGTERM] - sigint_timeout, delta=1)
        self.assertAlmostEqual(before_stop_call_time, after_stop_call_time - sigint_timeout - sigterm_timeout, delta=1)

    def test__cleanup_args(self):
        # #1595
        from roslaunch.nodeprocess import _cleanup_remappings
        args = [
            'ROS_PACKAGE_PATH=foo',
            '/home/foo/monitor',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            '__name:=bar',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            'topic:=topic2',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log',
            '__log:=/home/pr2/21851/ros-0.7.2/log/8d769688-897d-11de-8e93-00238bdfe0ab/monitor-3.log']
        clean_args = [
            'ROS_PACKAGE_PATH=foo',
            '/home/foo/monitor',
            '__name:=bar',
            'topic:=topic2']

        self.assertEqual([], _cleanup_remappings([], '__log:='))
        self.assertEqual(clean_args, _cleanup_remappings(args, '__log:='))
        self.assertEqual(clean_args, _cleanup_remappings(clean_args, '__log:='))
        self.assertEqual(args, _cleanup_remappings(args, '_foo'))
        
    def test__next_counter(self):
        from roslaunch.nodeprocess import _next_counter
        x = _next_counter()
        y = _next_counter()
        self.assertTrue(x +1 == y)
        self.assertTrue(x > 0)

    def test_create_master_process2(self):
        # accidentally wrote two versions of this, need to merge
        from roslaunch.core import Master, RLException
        import rospkg
        from roslaunch.nodeprocess import create_master_process

        ros_root = rospkg.get_ros_root()
        
        # test failures
        failed = False
        try:
            create_master_process('runid-unittest', Master.ROSMASTER, rospkg.get_ros_root(), 0)
            failed = True
        except RLException: pass
        self.assertFalse(failed, "invalid port should have triggered error")

        # test success with ROSMASTER
        m1 = create_master_process('runid-unittest', Master.ROSMASTER, ros_root, 1234)
        self.assertEqual('runid-unittest', m1.run_id)
        self.assertFalse(m1.started)
        self.assertFalse(m1.stopped)
        self.assertEqual(None, m1.cwd)
        self.assertEqual('master', m1.name)
        master_p = 'rosmaster'
        self.assertTrue(master_p in m1.args)
        # - it should have the default environment
        self.assertEqual(os.environ, m1.env)
        #  - check args
        self.assertTrue('--core' in m1.args)
        # - make sure port arguent is correct
        idx = m1.args.index('-p')
        self.assertEqual('1234', m1.args[idx+1])

        # test port argument
        m2 = create_master_process('runid-unittest', Master.ROSMASTER, ros_root, 1234)
        self.assertEqual('runid-unittest', m2.run_id)

        # test ros_root argument 
        m3 = create_master_process('runid-unittest', Master.ROSMASTER, ros_root, 1234)
        self.assertEqual('runid-unittest', m3.run_id)
        master_p = 'rosmaster'
        self.assertTrue(master_p in m3.args)
