cmake_minimum_required(VERSION 2.8.3)
project(challenge_help_me_carry)

find_package(catkin REQUIRED COMPONENTS
    rospy
    robot_skills
    robot_smach_states
)

catkin_python_setup()

catkin_package()

# ------------------------------------------------------------------------------------------------
#                                              BUILD
# ------------------------------------------------------------------------------------------------

include_directories(
    include
    ${catkin_INCLUDE_DIRS}
)

