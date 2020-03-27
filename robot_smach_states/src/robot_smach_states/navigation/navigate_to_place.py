from __future__ import absolute_import

# ROS
import rospy

# TU/e Robotics
from cb_planner_msgs_srvs.srv import *
from cb_planner_msgs_srvs.msg import *
from robot_skills.util.kdl_conversions import FrameStamped
from .navigation import NavigateTo
from .constraint_functions import arms_reach_constraint
from ..util.designators import Designator, check_resolve_type


# ----------------------------------------------------------------------------------------------------
class NavigateToPlace(NavigateTo):
    def __init__(self, robot, place_pose_designator, arm_designator=None):
        """Navigate so that the arm can reach the place point
        @param place_pose_designator designator that resolves to a geometry_msgs.msg.PoseStamped
        @param arm which arm to eventually place with?
        """
        check_resolve_type(place_pose_designator, FrameStamped)

        if not arm_designator:
            rospy.logerr('NavigateToPlace: side should be determined by arm_designator.'
                         'Please specify left or right, will default to left')
            arm_designator = Designator(robot.leftArm)

        super(NavigateToPlace, self).__init__(robot, lambda: arms_reach_constraint(place_pose_designator, arm_designator, look=True))
