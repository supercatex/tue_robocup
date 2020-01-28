from sensor_msgs.msg import Image
import smach
import rospy


class ShowOpenPose(smach.State):
    def __init__(self, robot):
        smach.State.__init__(self, outcomes=['done', 'failed'])
        self._robot = robot
        self._image_openpose = None
        self._openpose_subscriber = rospy.Subscriber('openpose/result_image', Image, self._callback)

    def execute(self, userdata=None):
        rgb, depth, info = self._robot.perception.get_rgb_depth_caminfo()
        self._robot.perception.detect_person_3d(rgb, depth, info)
        if self._image_openpose:
            self._robot.hmi.show_image_from_msg(self._image_openpose)  # also parse seconds for duration?
            return 'done'
        else:
            return 'failed'

    def _callback(self, data):
        rospy.logdebug('Received openpose result image')
        self._image_openpose = data


class ShowOpenPoseLoop(smach.State):
    def __init__(self, robot, iterations=10):
        smach.State.__init__(self, outcomes=['done', 'failed'])
        self._robot = robot
        self._iterations = iterations

    def execute(self, userdata=None):
        state = ShowOpenPose(self._robot)
        for i in range(self._iterations):
            outcome = state.execute()
            if outcome == 'failed':
                return 'failed'
        return 'done'
