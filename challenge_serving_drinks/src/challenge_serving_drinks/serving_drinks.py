# ROS
import smach

# TU/e Robotics
import robot_smach_states as states
import robot_smach_states.util.designators as ds

from robot_skills.classification_result import ClassificationResult
from robot_skills.robot import Robot
from robocup_knowledge import knowledge_loader

# Challenge serving drinks
from .drive_in import DriveIn
from .serve_one_drink import ServeOneDrink

# Knowledge
challenge_knowledge = knowledge_loader.load_knowledge("challenge_serving_drinks")
common_knowledge = knowledge_loader.load_knowledge("common")


class ServingDrinks(smach.StateMachine):
    """
    State machine for 'Serving Drinks' challenge.
    """

    def __init__(self, robot):
        # type: (Robot) -> str
        """
        Initialization method
        :param robot: robot api object
        """

        super(ServingDrinks, self).__init__(outcomes=["succeeded", "failed", "aborted"])

        # Designators
        bar_designator = ds.EdEntityDesignator(robot=robot, id=challenge_knowledge.bar_id, name='bar_des')
        room_designator = ds.EdEntityDesignator(robot=robot, id=challenge_knowledge.room_id, name='room_des')

        objects_list_des = ds.VariableDesignator(resolve_type=[ClassificationResult], name='objects_list_des')
        unav_drink_des = ds.VariableDesignator(resolve_type=str, name='unav_drink_str_des')

        with self:
            smach.StateMachine.add("DRIVE_IN",
                                   DriveIn(robot=robot,
                                           initial_pose=challenge_knowledge.starting_point,
                                           bar_designator=bar_designator,
                                           room_designator=room_designator,
                                           objects_list_des=objects_list_des,
                                           unav_drink_des=unav_drink_des,
                                           objects=common_knowledge.objects),
                                   transitions={"succeeded": "SAY_HI",
                                                "failed": "SAY_HI",
                                                "aborted": "aborted"})

            smach.StateMachine.add("SAY_HI",
                                   states.Say(robot, "Hi, I am {}. I'll be your waiter today".format(robot.robot_name)),
                                   transitions={"spoken": "SERVE_DRINK_1"})

            # Explicitly add a new state for each drink, i.e., don't use a range iterator to make sure a new state
            # is constructed every time
            for idx in range(1, challenge_knowledge.NR_DRINKS + 1):
                next_state = "SERVE_DRINK_{}".format(idx + 1) if idx < challenge_knowledge.NR_DRINKS else "SAY_DONE"

                smach.StateMachine.add("SERVE_DRINK_{}".format(idx),
                                       ServeOneDrink(robot=robot,
                                                     bar_designator=bar_designator,
                                                     room_id=challenge_knowledge.room_id,
                                                     room_designator=room_designator,
                                                     objects_list_des=objects_list_des,
                                                     unav_drink_des=unav_drink_des,
                                                     name_options=common_knowledge.names,
                                                     objects=common_knowledge.objects),
                                       transitions={"succeeded": next_state,
                                                    "failed": next_state,
                                                    "aborted": "aborted"})

            smach.StateMachine.add("SAY_DONE",
                                   states.Say(robot, "My job here is done. Enjoy your day and see you next time"),
                                   transitions={"spoken": "succeeded"})
