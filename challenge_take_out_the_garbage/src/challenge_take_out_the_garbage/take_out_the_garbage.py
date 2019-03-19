# ROS
import smach

# Robot smach states
import robot_smach_states as states
from robocup_knowledge import load_knowledge
import robot_smach_states.util.designators as ds
from challenge_take_out_the_garbage.take_out import DefaultGrabDesignator, GrabSingleItem, TakeOut
challenge_knowledge = load_knowledge('challenge_take_out_the_garbage')

STARTING_POINT = challenge_knowledge.starting_point


class TakeOutGarbage(smach.StateMachine):
    """ This is my example state machine

    """
    def __init__(self, robot):
        """ Initialization method

        :param robot: robot api object
        """
        smach.StateMachine.__init__(self, outcomes=["succeeded", "failed", "aborted"])

        # Create designators
        trashbin_id = "trashbin"
        trashbin_designator = ds.EdEntityDesignator(robot=robot,
                                                    id=trashbin_id)
        trash_designator = DefaultGrabDesignator(robot=robot,
                                                 surface_designator=trashbin_designator,
                                                 area_description="on_top_of",
                                                 debug=True)
        trashbin_id2 = "trashbin2"
        trashbin_designator2 = ds.EdEntityDesignator(robot=robot,
                                                     id=trashbin_id2)
        trash_designator2 = DefaultGrabDesignator(robot=robot,
                                                  surface_designator=trashbin_designator2,
                                                  area_description="on_top_of",
                                                  debug=True)
        drop_zone_id = "cabinet"
        drop_zone_designator = ds.EdEntityDesignator(robot=robot, id=drop_zone_id)

        with self:

            # Start challenge via StartChallengeRobust
            smach.StateMachine.add("START_CHALLENGE_ROBUST",
                                   states.StartChallengeRobust(robot, STARTING_POINT),
                                   transitions={"Done": "TAKE_OUT",
                                                "Aborted": "aborted",
                                                "Failed": "failed"})

            smach.StateMachine.add("TAKE_OUT",
                                   TakeOut(robot=robot, trashbin_designator=trashbin_designator,
                                           trash_designator=trash_designator, drop_designator=drop_zone_designator),
                                   transitions={"succeeded": "ANNOUNCE_TASK",
                                                "aborted": "aborted",
                                                "failed": "failed"})

            smach.StateMachine.add("ANNOUNCE_TASK",
                                   states.Say(robot, "First bag has been dropped at the collection zone",
                                              block=False),
                                   transitions={'spoken': 'TAKE_OUT2'})
            # # wip
            smach.StateMachine.add("TAKE_OUT2",
                                   TakeOut(robot=robot, trashbin_designator=trashbin_designator2,
                                           trash_designator=trash_designator2, drop_designator=drop_zone_designator),
                                   transitions={"succeeded": "ANNOUNCE_TASK2",
                                                "aborted": "aborted",
                                                "failed": "failed"})

            smach.StateMachine.add("ANNOUNCE_TASK2",
                                   states.Say(robot, "Second bag has been dropped at the collection zone."
                                                     "All the thrash has been taken care of",
                                              block=False),
                                   transitions={'spoken': 'succeeded'})
