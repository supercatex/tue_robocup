import robot_smach_states as states
import robot_smach_states.util.designators as ds
import smach
from hmi_msgs.msg import QueryResult
from robocup_knowledge import load_knowledge
from robot_skills.util.entity import Entity

challenge_knowledge = load_knowledge('challenge_receptionist')


class LearnGuest(smach.StateMachine):
    def __init__(self, robot, door_waypoint, guest_ent_des, guest_name_des, guest_drink_des):
        """

        :param robot: Robot that should execute this state
        :param door_waypoint: Entity-designator resolving to a waypoint Where are guests expected to come in
        :param guest_ent_des: Entity of the guest
        :param guest_name_des: designator that the name (str) of the guest is written to
        :param guest_drink_des: designator that the drink type (str) of the drink the guest wants
        """
        smach.StateMachine.__init__(self, outcomes=['succeeded', 'abort'])

        self.drink_spec_des = ds.Designator(challenge_knowledge.common.drink_spec, name='drink_spec')

        with self:
            smach.StateMachine.add('GOTO_DOOR',
                                   states.NavigateToWaypoint(robot,
                                                             door_waypoint,
                                                             challenge_knowledge.waypoint_door['radius']),
                                   transitions={'arrived': 'SAY_PLEASE_COME_IN',
                                                'unreachable': 'SAY_PLEASE_COME_IN',
                                                'goal_not_defined': 'abort'})

            smach.StateMachine.add('SAY_PLEASE_COME_IN',
                                   states.Say(robot, ["Please come in, I'm waiting"],
                                              block=True,
                                              look_at_standing_person=True),
                                   transitions={'spoken': 'WAIT_FOR_GUEST'})

            smach.StateMachine.add("WAIT_FOR_GUEST",
                                   states.WaitForPersonInFront(robot, attempts=30, sleep_interval=1),
                                   transitions={'success': 'SAY_HELLO',
                                                'failed': 'SAY_PLEASE_COME_IN'})

            smach.StateMachine.add('SAY_HELLO',
                                   states.Say(robot, ["Hi there, I'll learn your face now"],
                                              block=True,
                                              look_at_standing_person=True),
                                   transitions={'spoken': 'ASK_GUEST_NAME'})

            smach.StateMachine.add('ASK_GUEST_NAME',
                                   states.AskPersonName(robot, guest_name_des.writeable, challenge_knowledge.common.names),
                                   transitions={'succeeded': 'LEARN_PERSON',
                                                'failed': 'SAY_HELLO'})

            smach.StateMachine.add('LEARN_PERSON',
                                   states.LearnPerson(robot, name_designator=guest_name_des),
                                   transitions={'succeeded': 'SAY_GUEST_LEARNED',
                                                'failed': 'SAY_FAILED_LEARNING'})

            smach.StateMachine.add('SAY_FAILED_LEARNING',
                                   states.Say(robot, ["Oops, I'm confused, let's try again"],
                                              block=False),
                                   transitions={'spoken': 'LEARN_PERSON'})

            smach.StateMachine.add('SAY_GUEST_LEARNED',
                                   states.Say(robot, ["Okidoki, now I know what you look like"], block=True),
                                   transitions={'spoken': 'SAY_DRINK_QUESTION'})

            smach.StateMachine.add('SAY_DRINK_QUESTION',
                                   states.Say(robot, ["What's your favorite drink?"], block=True),
                                   transitions={'spoken': 'HEAR_DRINK_ANSWER'})

            smach.StateMachine.add('HEAR_DRINK_ANSWER',
                                   states.HearOptionsExtra(robot,
                                                      self.drink_spec_des,
                                                      guest_drink_des.writeable),
                                   transitions={'heard': 'succeeded',
                                                'no_result': 'SAY_DRINK_QUESTION'})


class IntroduceGuestToOperator(smach.StateMachine):
    def __init__(self, robot, operator_des, guest_ent_des):
        smach.StateMachine.__init__(self, outcomes=['succeeded', 'abort'])

        with self:
            smach.StateMachine.add('FIND_OPERATOR',
                                   states.FindPersonInRoom(robot,
                                                           challenge_knowledge.waypoint_livingroom['id'],
                                                           challenge_knowledge.operator_name,
                                                           operator_des),
                                   transitions={'found': 'GOTO_OPERATOR',
                                                'not_found': 'GOTO_OPERATOR'})

            smach.StateMachine.add('GOTO_OPERATOR',
                                   states.NavigateToObserve(robot,
                                                            operator_des),
                                   transitions={'arrived': 'SAY_LOOKING_FOR_GUEST',
                                                'unreachable': 'SAY_LOOKING_FOR_GUEST',
                                                'goal_not_defined': 'abort'})

            smach.StateMachine.add('SAY_LOOKING_FOR_GUEST',
                                   states.Say(robot, ["Now I should be looking at the guest and pointing at him or her"], block=True),
                                   transitions={'spoken': 'INTRODUCE_GUEST'})

            smach.StateMachine.add('FIND_GUEST',
                                   states.FindPerson(robot=robot,
                                                     person_label='guest1',  # TODO: Should be able to be a designator
                                                     found_entity_designator=guest_ent_des),
                                   transitions={"found": "INTRODUCE_GUEST",
                                                "failed": "abort"})

            smach.StateMachine.add('INTRODUCE_GUEST',
                                   states.Say(robot, ["This is person X and he likes drink Y"], block=True),
                                   transitions={'spoken': 'succeeded'})  # TODO: Iterate to guest 2


class ChallengeReceptionist(smach.StateMachine):
    def __init__(self, robot):
        smach.StateMachine.__init__(self, outcomes=['succeeded', 'abort'])

        self.door_waypoint = ds.EntityByIdDesignator(robot, id=challenge_knowledge.waypoint_door['id'])
        self.livingroom_waypoint = ds.EntityByIdDesignator(robot, id=challenge_knowledge.waypoint_livingroom['id'])

        self.operator_designator = ds.VariableDesignator(resolve_type=Entity)

        self.guest1_entity_des = ds.VariableDesignator(resolve_type=Entity, name='guest1_entity')
        self.guest1_name_des = ds.VariableDesignator('guest 1', name='guest1_name')
        self.guest1_drink_des = ds.VariableDesignator(resolve_type=QueryResult, name='guest1_drink')

        with self:
            smach.StateMachine.add('INITIALIZE',
                                   states.Initialize(robot),
                                   transitions={'initialized': 'SET_INITIAL_POSE',
                                                'abort': 'abort'})

            smach.StateMachine.add('SET_INITIAL_POSE',
                                   states.SetInitialPose(robot, challenge_knowledge.starting_point),
                                   transitions={'done': 'LEARN_GUEST_1',
                                                "preempted": 'abort',
                                                'error': 'LEARN_GUEST_1'})

            smach.StateMachine.add('LEARN_GUEST_1',
                                   LearnGuest(robot, self.door_waypoint, self.guest1_entity_des, self.guest1_name_des, self.guest1_drink_des),
                                   transitions={'succeeded': 'GOTO_LIVINGROOM_1',
                                                'abort': 'abort'})


            smach.StateMachine.add('GOTO_LIVINGROOM_1',
                                   states.NavigateToWaypoint(robot,
                                                             self.livingroom_waypoint,
                                                             challenge_knowledge.waypoint_livingroom['radius']),
                                   transitions={'arrived': 'INTRODUCE_GUEST',
                                                'unreachable': 'INTRODUCE_GUEST',
                                                'goal_not_defined': 'abort'})

            smach.StateMachine.add('INTRODUCE_GUEST',
                                   IntroduceGuestToOperator(robot, self.operator_designator, self.guest1_entity_des),
                                   transitions={'succeeded': 'succeeded',
                                                'abort': 'abort'})


            # - [x] Wait at the door, say you're waiting
            # - [x] Wait until person can come in
            # - [x] Ask their name
            # - [x] Ask their favourite drink
            # - [x] Ask for favourite drink <drink1>
            # - [x] GOTO living room
            # - [x] Locate John (not sure how that should work, maybe just FindPersonInRoom)
            # - [x] GOTO John
            # - [.] Locate guest1:
            # - [ ]   rotate head until <guest1> is detected
            # - [.] Point at guest1
            # - [.] Say: This is <guest1> and (s)he likes to drink <drink1>

