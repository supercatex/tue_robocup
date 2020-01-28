# ROS
import rospy
import sys

# TU/e Robotics
from robot_skills.get_robot import get_robot_from_argv

# Robot Smach States
import robot_smach_states


if __name__ == "__main__":
    assert len(sys.argv) == 2, "Please provide the robot name" \
                               "e.g., 'python show_openpose.py hero'"

    rospy.init_node("test_openpose_stuff")

    robot = get_robot_from_argv(index=1)

    openpose_state = robot_smach_states.ShowOpenPose(robot=robot)
    result = openpose_state.execute()
    rospy.loginfo("Openpose state finished with result {}".format(result))
