'''
Created on Jul 3, 2013

@author: farago
'''
import numpy as np
import quantities as q
from unittest import TestCase
from syris.opticalelements import geometry as geom
from syris.opticalelements.geometry import Trajectory
from scipy import interpolate as interp


class TestTrajectory(TestCase):
    def setUp(self):
        self.n = 100
        x = np.linspace(0, 2 * np.pi, self.n)
        # + 1 not to go below zero.
        y = 1 + np.sin(x)
        z = np.zeros(self.n)
        self.time_dist = zip(x * q.s, y * q.m)
        self.control_points = zip(x, y, z) * q.m
        
        self.traj = Trajectory(self.control_points, self.time_dist)
        
    def test_init(self):
        def test_stationary(traj):
            self.assertEqual(traj.length, 0 * q.m)
            self.assertEqual(traj.time, 0 * q.s)
            
        # Stationary trajectory.
        traj = Trajectory([(0, 0, 0)] * q.m)
        test_stationary(traj)
        
        times = np.linspace(0, 2 * np.pi, self.n)
        dist = np.sin(times)
        
        # Length is zero but velocities given.
        traj = Trajectory([(0, 0, 0)] * q.m, zip(times, dist))
        test_stationary(traj)
        
        # Length is non-zero but no velocities given.
        traj = Trajectory(self.control_points)
        test_stationary(traj)
        
        # Constant velocity.
        velocity = 10 * q.m / q.s
        traj = Trajectory(self.control_points, velocity=velocity)
        self.assertAlmostEqual(traj.length / velocity, traj.time)
        
        # Constant velocity and times and distances
        self.assertRaises(ValueError, Trajectory, self.control_points,
                          time_dist=zip(times, dist),
                          velocity=10 * q.mm / q.s)
        
        # Invalid velocity profile (negative distance).
        self.assertRaises(ValueError, Trajectory, self.control_points,
                                                 zip(times * q.s, dist * q.m))
        # Time not monotonic.
        time_dist = [(1 * q.s, 1 * q.m), (1 * q.s, 1 * q.m)]
        self.assertRaises(ValueError, Trajectory, self.control_points,
                                                 time_dist)
        time_dist = [(1 * q.s, 1 * q.m), (0 * q.s, 1 * q.m)]
        self.assertRaises(ValueError, Trajectory, self.control_points,
                                                 time_dist)
        
        # Negative time.
        time_dist = [(-1 * q.s, 1 * q.m), (1 * q.s, 1 * q.m)]
        self.assertRaises(ValueError, Trajectory, self.control_points,
                                                 time_dist)


    def test_get_next_time(self):
        d_s = 0.5 * q.m
        # Negative time is inadmissible.
        self.assertRaises(ValueError, self.traj.get_next_time,
                          -0.2 * q.s, 0.5 * q.m)
        # No movement, we are at the end of the trajectory.
        t_1 = self.traj.get_next_time(self.traj.time, 0.5 * q.m)
        self.assertEqual(t_1, None)
        # No movement, d_s too big.
        t_1 = self.traj.get_next_time(0.2 * q.s, 50.5 * q.m)
        self.assertEqual(t_1, None)
            
        # No extrema in the way, d_s positive.
        t_0 = 0.2 * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = np.arcsin(np.sin(t_0.magnitude) + d_s.magnitude)
        self.assertAlmostEqual(t_1.magnitude, truth)
             
        # Maximum between t_0 and t_1.
        t_0 = 3 * np.pi / 8 * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = np.pi - np.arcsin(np.sin(t_0.magnitude) - d_s.magnitude)
        self.assertAlmostEqual(t_1.magnitude, truth)
           
        # Minimum between t_0 and t_1.
        t_0 = 11 * np.pi / 8 * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = 2 * np.pi + np.arcsin(np.sin(t_0.magnitude) + d_s.magnitude)
        self.assertAlmostEqual(t_1.magnitude, truth)
            
        # No extrema in the way, d_s negative.
        t_0 = np.pi * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = np.pi + np.arcsin(d_s.magnitude)
        self.assertAlmostEqual(t_1.magnitude, truth)
            
        # t_0 in maximum.
        t_0 = np.pi / 2 * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = np.pi - np.arcsin(0.5)
        self.assertAlmostEqual(t_1.magnitude, truth)
           
        # t_0 in minimum.
        t_0 = 3 * np.pi / 2 * q.s
        t_1 = self.traj.get_next_time(t_0, d_s)
        truth = 2 * np.pi + np.arcsin(-0.5)
        self.assertAlmostEqual(t_1.magnitude, truth)
         
    def test_get_point(self):
        # Stationary trajectory
        traj = Trajectory(self.control_points)
        np.testing.assert_equal(traj.get_point(1 * q.s), traj.control_points[0])
         
        tck = interp.splprep(zip(*self.control_points))[0]
           
        def evaluate_point(t):
            if t > 1:
                t = 1
            return interp.splev(t, tck) * q.m
           
        # Create velocity profile which goes until the trajectory end.
        # We need to scale the sine amplitude in order to
        # max(sin(x)) = trajectory.length
        times = np.linspace(0, 2 * np.pi, self.n) * q.s
        # Normalize for not going below zero.
        dist = (self.traj.length + self.traj.length * \
                np.sin(times.magnitude)) * q.m
         
        traj = Trajectory(self.control_points, zip(times, dist))
         
        for i in range(len(times)):
            np.testing.assert_almost_equal(traj.get_point(times[i]),
                                  evaluate_point(dist[i] / traj.length))
