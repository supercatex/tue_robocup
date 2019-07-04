# ROS
import rospy
import smach

# TU/e
import robot_skills
from robot_skills.simulation import is_sim_mode
import robot_smach_states as states
import robot_smach_states.util.designators as ds
from hmi import HMIResult
from robocup_knowledge import load_knowledge
from robot_smach_states.human_interaction.give_directions import GiveDirections
from robot_smach_states.navigation import guidance

# Challenge where is this
from .simulation import mock_detect_operator

if is_sim_mode():
    guidance._detect_operator_behind_robot = mock_detect_operator

knowledge = load_knowledge("challenge_where_is_this")
BACKUP_SCENARIOS = knowledge.backup_scenarios  # Extract knowledge here so that stuff fails on startup if not defined


class EntityFromHmiResults(ds.Designator):
    """ Designator to pick the closest item on top of the table to grab. This is used for testing

    """
    def __init__(self, robot, hmi_result_des, parse=True):
        """ Constructor

        :param robot: robot object
        :param hmi_result_des:
        """
        super(EntityFromHmiResults, self).__init__(resolve_type=robot_skills.util.entity.Entity)

        self._robot = robot
        self._hmi_result_des = hmi_result_des
        self.parse = parse

    def _resolve(self):
        """ Resolves

        :return: entity in the <area_description> of the <surface_designator> that is closest to the robot
        """
        sem = self._hmi_result_des.resolve().semantics
        entity_id = sem["target-location"]["id"]

        entities = self._robot.ed.get_entities(id=entity_id, parse=self.parse)
        if entities:
            return entities[0]
        else:
            return None


class GuideToRoomOrObject(smach.StateMachine):
    def __init__(self, robot, entity_des):
        """ Constructor
        :param robot: robot object
        :param entity_des: designator resolving to a room or a piece of furniture
        """
        smach.StateMachine.__init__(
            self, outcomes=["arrived", "unreachable", "goal_not_defined", "lost_operator", "preempted"])

        with self:
            @smach.cb_interface(outcomes=["room", "object"])
            def determine_type(userdata=None):
                entity = entity_des.resolve()
                entity_type = entity.type
                if entity_type == "room":
                    return "room"
                else:
                    return "object"

            smach.StateMachine.add("DETERMINE_TYPE",
                                   smach.CBState(determine_type),
                                   transitions={"room": "GUIDE_TO_ROOM",
                                                "object": "GUIDE_TO_FURNITURE"})

            smach.StateMachine.add("GUIDE_TO_ROOM",
                                   guidance.GuideToSymbolic(robot, {entity_des: "in"}, entity_des),
                                   transitions={"arrived": "arrived",
                                                "unreachable": "unreachable",
                                                "goal_not_defined": "goal_not_defined",
                                                "lost_operator": "lost_operator",
                                                "preempted": "preempted"})

            smach.StateMachine.add("GUIDE_TO_FURNITURE",
                                   guidance.GuideToSymbolic(robot, {entity_des: "in_front_of"}, entity_des),
                                   transitions={"arrived": "arrived",
                                                "unreachable": "GUIDE_NEAR_FURNITURE",  # Something is blocking in front
                                                "goal_not_defined": "GUIDE_NEAR_FURNITURE",  # in_front_of not defined
                                                "lost_operator": "lost_operator",
                                                "preempted": "preempted"})

            smach.StateMachine.add("GUIDE_NEAR_FURNITURE",
                                   guidance.GuideToSymbolic(robot, {entity_des: "near"}, entity_des),
                                   transitions={"arrived": "arrived",
                                                "unreachable": "unreachable",
                                                "goal_not_defined": "goal_not_defined",
                                                "lost_operator": "lost_operator",
                                                "preempted": "preempted"})


class InformMachine(smach.StateMachine):
    def __init__(self, robot):
        """ Constructor
        :param robot: robot object
        """
        smach.StateMachine.__init__(self, outcomes=["succeeded", "failed"])

        with self:
            self.spec_des = ds.Designator(knowledge.location_grammar)
            self.answer_des = ds.VariableDesignator(resolve_type=HMIResult)
            self.entity_des = EntityFromHmiResults(robot, self.answer_des)
            self._location_hmi_attempt = 0
            self._max_hmi_attempts = 5  # ToDo: parameterize?

            @smach.cb_interface(outcomes=["reset"])
            def _reset_location_hmi_attempt(userdata=None):
                """ Resets the location hmi attempt so that each operator gets three attempts """
                self._location_hmi_attempt = 0
                return "reset"

            smach.StateMachine.add("RESET_HMI_ATTEMPT",
                                   smach.CBState(_reset_location_hmi_attempt),
                                   transitions={"reset": "ANNOUNCE_ITEM"})

            smach.StateMachine.add("ANNOUNCE_ITEM",
                                   states.Say(robot, "Hello, my name is {}. Please call me by my name. "
                                                     "Talk loudly into my microphone and wait for the ping".
                                              format(robot.robot_name), block=True),
                                   transitions={"spoken": "WAIT_TO_BE_CALLED"})

            smach.StateMachine.add("WAIT_TO_BE_CALLED",
                                   states.HearOptions(robot, ["{}".format(robot.robot_name)], rospy.Duration(10)),
                                   transitions={"{}".format(robot.robot_name): "INSTRUCT",
                                                "no_result": "ANNOUNCE_ITEM"})

            smach.StateMachine.add("INSTRUCT",
                                   states.Say(robot,
                                              ["Please tell me where you would like to go. "
                                               "Talk loudly into my microphone and wait for the ping"],
                                              block=True),
                                   transitions={"spoken": "LISTEN_FOR_LOCATION"})

            smach.StateMachine.add("LISTEN_FOR_LOCATION",
                                   states.HearOptionsExtra(robot, self.spec_des, self.answer_des.writeable,
                                                           rospy.Duration(15)),
                                   transitions={"heard": "INSTRUCT_FOR_WAIT",
                                                "no_result": "HANDLE_FAILED_HMI"})

            @smach.cb_interface(outcomes=["retry", "fallback", "failed"])
            def _handle_failed_hmi(userdata=None):
                """ Handle failed HMI queries so we can try up to x times """
                self._location_hmi_attempt += 1  # Increment
                if self._location_hmi_attempt == self._max_hmi_attempts:
                    rospy.logwarn("HMI failed for the {} time, returning 'failed'".format(self._max_hmi_attempts))

                    if not BACKUP_SCENARIOS:
                        rospy.logwarn("No fallback scenario's available anymore")
                        return "failed"

                    backup = BACKUP_SCENARIOS.pop(0)
                    robot.speech.speak("I am sorry but I did not hear you", mood="sad", block=False)
                    robot.speech.speak(backup.sentence, block=False)
                    self.answer_des.writeable.write(HMIResult("", {"target-location": {"id": backup.entity_id}}))
                    return "fallback"

                rospy.loginfo("HMI failed for the {} time out of {}, retrying".format(
                    self._location_hmi_attempt, self._max_hmi_attempts))

                return "retry"

            smach.StateMachine.add("HANDLE_FAILED_HMI",
                                   smach.CBState(_handle_failed_hmi),
                                   transitions={"retry": "INSTRUCT",
                                                "fallback": "INSTRUCT_FOR_WAIT",
                                                "failed": "failed"})

            smach.StateMachine.add("INSTRUCT_FOR_WAIT",
                                   states.human_interaction.SayFormatted(
                                       robot,
                                       ["Let me think how to get to the {entity_id}",
                                        "I will now determine the best route to the {entity_id}"],
                                       entity_id=ds.AttrDesignator(self.entity_des, "id", resolve_type=str)),
                                   transitions={"spoken": "GIVE_DIRECTIONS"})

            smach.StateMachine.add("GIVE_DIRECTIONS",
                                   GiveDirections(robot, self.entity_des),
                                   transitions={"succeeded": "INSTRUCT_FOLLOW",
                                                "failed": "failed"})

            smach.StateMachine.add("INSTRUCT_FOLLOW",
                                   states.Say(robot,
                                              ["Please follow me"],
                                              block=True),
                                   transitions={"spoken": "GUIDE_OPERATOR"})

            smach.StateMachine.add("GUIDE_OPERATOR",
                                   GuideToRoomOrObject(robot, self.entity_des),
                                   transitions={"arrived": "SUCCESS",
                                                "unreachable": "SAY_CANNOT_REACH",
                                                "goal_not_defined": "SAY_CANNOT_REACH",
                                                "lost_operator": "SAY_LOST_OPERATOR",
                                                "preempted": "failed"})

            smach.StateMachine.add("SUCCESS",
                                   states.Say(robot,
                                              ["We have arrived"],
                                              block=True),
                                   transitions={"spoken": "RETURN_TO_INFORMATION_POINT"})

            smach.StateMachine.add("SAY_CANNOT_REACH",
                                   states.Say(robot,
                                              ["I am sorry but I cannot reach the destination."],
                                              block=True),
                                   transitions={"spoken": "RETURN_TO_INFORMATION_POINT"})

            smach.StateMachine.add("SAY_LOST_OPERATOR",
                                   states.Say(robot,
                                              ["Oops I have lost you completely."],
                                              block=True),
                                   transitions={"spoken": "RETURN_TO_INFORMATION_POINT"})

            smach.StateMachine.add("RETURN_TO_INFORMATION_POINT",
                                   states.NavigateToWaypoint(robot, ds.EntityByIdDesignator(robot, "starting_point")),
                                   transitions={"arrived": "succeeded",
                                                "unreachable": "failed",
                                                "goal_not_defined": "failed"})
