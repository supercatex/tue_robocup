import sys
import cv2
from threading import Event
from collections import OrderedDict

# ROS
import rospy
import smach
import cv_bridge
from std_msgs.msg import String
from sensor_msgs.msg import Image

# Robot skills
from robot_smach_states import WaitTime
from robot_smach_states.util.designators import EdEntityDesignator
import robot_smach_states as states


class SelectOptionByImage(smach.State):
    def __init__(self, robot, options,
                 question='Which do you want?',
                 instruction='Please let me know your selection',
                 timeout=60, strict=True):
        """

        :param robot: Robot object, because all our Smach states have this and we need consistency
        :param options: What options are available?
        :type options: List[str]
        :param question: What is the question to select something for?
        :type question: str
        :param instruction: Instructions for the user on what to do
        :type instruction: str
        :param timeout: How long to wait until the state returns failed
        :type timeout: int
        :param strict: Only allow selection from the options list
        :type strict: bool
        """
        smach.State.__init__(self,
                             outcomes=['succeeded', 'failed'],
                             input_keys=['person_dict'],
                             output_keys=['selection'])

        self._timeout = timeout
        self._received = Event()

        self._options = options
        self._option_str = ', '.join(self._options[:-1])
        if len(self._options) > 1:
            self._option_str += ' or ' + self._options[-1]

        self._strict = strict

        self._cv_bridge = cv_bridge.CvBridge()

        self._selection = ''

        self._question = question
        self._instruction = instruction

        self._image_pub = rospy.Publisher('image_from_ros', Image, queue_size=10)
        self._text_pub = rospy.Publisher('message_from_ros', String, queue_size=10)
        self._text_sub = rospy.Subscriber('message_to_ros', String, self._handle_reply)

    def execute(self, user_data):
        # Get a dict {'rgb':..., 'person_detection':..., 'map_ps':...}
        # Publish this image to telegram
        # Then ask what their selection is from a list of options

        self._received = Event()
        self._selection = None

        self._text_pub.publish(self._question)
        self._text_pub.publish(self._option_str)

        try:
            ros_image = user_data['person_dict']['rgb']
            self._image_pub.publish(ros_image)

            self._text_pub.publish(self._instruction)

            start = rospy.Time.now()
            while not rospy.is_shutdown() and rospy.Time.now() < start + rospy.Duration(self._timeout):
                if self._received.wait(1):
                    user_data['selection'] = self._selection
                    return 'succeeded'
                else:
                    rospy.logwarn_throttle(10, "No reply received yet")
        except Exception as ex:
            rospy.logerr('Exception while getting selection: {}'.format(ex))

        self._text_pub.publish("I didn't get a reply in time, sorry")
        user_data['selection'] = None
        return 'failed'

    def _handle_reply(self, msg):
        # type: (String) -> None
        rospy.loginfo('Got answer from user: {}'.format(msg.data))

        if self._strict:
            if msg.data.lower().strip() not in self._options:
                self._text_pub.publish("{} is not on my list, please select something else, like {}"
                                       .format(msg.data, self._options))
            else:
                self._selection = msg.data
                self._received.set()
        else:
            self._selection = msg.data
            self._received.set()


class SelectOptionForEachImage(smach.StateMachine):

    # For each people_dicts in people_dicts:
    #   1. Send picture to telegram
    #   2. Get reply
    #   3. Store current ppl dict with its reply

    def __init__(self, robot, question='Which do you want?', timeout=60):
        smach.StateMachine.__init__(self,
                             outcomes=['succeeded', 'failed'],
                             input_keys=['people_dicts'],
                             output_keys=['selections'])

        pass


if __name__ == '__main__':
    from robot_skills import get_robot

    if len(sys.argv) > 1:
        robot_name = sys.argv[1]
        image_path = sys.argv[2]

        rospy.init_node('test_find_person_in_room')
        _robot = None # get_robot(robot_name)

        bridge = cv_bridge.CvBridge()

        sm = SelectOptionByImage(_robot, options=['banana', 'widget', 'gadget'])

        ud = {}

        cv_image = cv2.imread(image_path)

        ros_image = bridge.cv2_to_imgmsg(cv_image, encoding="bgr8")  # cv2.imread returns in bgr order
        ud['person_dict'] = {'rgb': ros_image}  # Other keys are not required for this state

        print(sm.execute(ud))

        rospy.loginfo(ud['selection'])
    else:
        print "Please provide robot name as argument."
        exit(1)

