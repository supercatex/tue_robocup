#! /usr/bin/env python
import roslib; 
import rospy
import smach
import geometry_msgs.msg
import time
import ed

from math import cos, sin
from geometry_msgs.msg import *
from cb_planner_msgs_srvs.srv import *
from cb_planner_msgs_srvs.msg import *

import math
from psi import Term, Compound, Conjunction
import actionlib
from random import choice

from robot_smach_states.navigation import NavigateToObserve

# ----------------------------------------------------------------------------------------------------

class PickUp(smach.State):
    def __init__(self, robot, arm, grab_entity_designator):
        smach.State.__init__(self, outcomes=['succeeded','failed'])
        self._robot = robot
        self.arm = arm
        self.grab_entity_designator = grab_entity_designator

    def execute(self, userdata=None):
        print "PickUp!"

        try:
            entity_id = self.grab_entity_designator.resolve().id
        except Exception:
            rospy.logerr("No entity found")
            return 'failed'

        # goal in map frame
        goal_map = msgs.Point(0, 0, 0)

        # Transform to base link frame
        goal_bl = transformations.tf_transform(goal_map, entity_id, "/amigo/base_link", tf_listener=self._robot.tf_listener)
        if goal_bl == None:
            return 'failed'

        print goal_bl

        # Arm to position in a safe way
        self.arm.send_joint_trajectory('prepare_grasp')

        # Open gripper
        self.arm.send_gripper_goal('open')

        # Pre-grasp
        if not self.arm.send_goal(goal_bl.x, goal_bl.y, goal_bl.z, 0, 0, 0,
                             frame_id="/amigo/base_link", timeout=20, pre_grasp=True, first_joint_pos_only=True):
            print "Pre-grasp failed"
            
            self.arm.reset()
            self.arm.send_gripper_goal('close', timeout=None)
            return

        # Grasp
        if not self.arm.send_goal(goal_bl.x, goal_bl.y, goal_bl.z, 0, 0, 0, frame_id="/amigo/base_link", timeout=120, pre_grasp = True):
            self._robot.speech.speak("I am sorry but I cannot move my arm to the object position", block=False)
            print "Grasp failed"
            self.arm.reset()
            self.arm.send_gripper_goal('close', timeout=None)
            return

        # Close gripper
        self.arm.send_gripper_goal('close')

        # Lift
        if not self.arm.send_goal( goal_bl.x, goal_bl.y, goal_bl.z + 0.1, 0.0, 0.0, 0.0, timeout=20, pre_grasp=False, frame_id="/amigo/base_link"):
            print "Failed lift"

        # Retract
        if not self.arm.send_goal( goal_bl.x - 0.1, goal_bl.y, goal_bl.z + 0.1, 0.0, 0.0, 0.0, timeout=20, pre_grasp=False, frame_id="/amigo/base_link"):
            print "Failed retract"

        # Carrying pose
        if side == "left":
            y_home = 0.2
        else:
            y_home = -0.2

        print "y_home = " + str(y_home)
        
        rospy.loginfo("start moving to carrying pose")        
        if not self.arm.send_goal(0.18, y_home, goal_bl.z + 0.1, 0, 0, 0, 60):            
            print 'Failed carrying pose'                 


        #machine = robot_smach_states.manipulation.GrabMachineWithoutBase(side=side, robot=self._robot, grabpoint_query=query)
        #machine.execute()             
        
# ----------------------------------------------------------------------------------------------------

class Grab(smach.StateMachine):
    def __init__(self, robot, designator, side="left"):
        smach.StateMachine.__init__(self, outcomes=['done', 'failed'])
        self.robot = robot

        with self:

            smach.StateMachine.add('NAVIGATE_TO_GRAB', NavigateToObserve(self.robot, designator),
                transitions={'done'   :   'GRAB',
                             'failed' :   'failed'})

            smach.StateMachine.add('GRAB', PickUp(self.robot, designator, side),
                transitions={'done'   :   'done',
                             'failed' :   'failed'})