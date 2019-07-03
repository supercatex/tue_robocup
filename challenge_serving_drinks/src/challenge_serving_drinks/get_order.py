# ROS
import smach

# TU/e Robotics
import robot_smach_states as states
import robot_smach_states.util.designators as ds

# Serving drinks
from .sd_states import AskDrink


class ToggleBool(smach.State):
    def __init__(self, check_designator):
        super(ToggleBool, self).__init__(outcomes=["done"])
        ds.is_writeable(check_designator)
        ds.check_type(check_designator, bool)
        self._check_designator = check_designator

    def execute(self, userdata=None):
        val = self._check_designator.resolve()
        if val:
            self._check_designator.write(False)
        else:
            self._check_designator.write(True)

        return "done"


class GetOrder(smach.StateMachine):
    """
    Gets an order. If succeeded, the person_designator and drink_designator are filled and can be used in subsequent
    states.
    """
    def __init__(self, robot, operator_name, drink_designator,
                 available_drinks_designator, unavailable_drink_designator,
                 name_options, objects, learn_check_designator):
        # type: (Robot, str, VariableDesignator) -> None
        """
        Initialization method
        :param robot: robot api object
        :param operator_name: name with which the operator will be stored in image recognition module
        :param drink_designator: (VariableDesignator) in which the drink to fetch is stored
        :param available_drinks_designator: (VariableDesignator) in which the available drinks are stored
        :param unavailable_drink_designator: (VariableDesignator) in which the unavailable drink is stored
        :param name_options: Names from common knowledge
        :param objects: Objects from common knowledge
        """
        smach.StateMachine.__init__(self, outcomes=["succeeded", "failed", "aborted"])

        with self:

            # Operator id
            caller_id = "operator"
            caller_designator = ds.EdEntityDesignator(robot=robot, id=caller_id, name="caller_des", none_resolve=True)

            # Detect - people holding drinks and people without drinks  #ToDo: implement!
            smach.StateMachine.add("SAY_PEOPLE_WITHOUT_DRINKS",
                                   states.Say(robot=robot, sentence="Trying to find people without a drink",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "FIND_PERSON_WITHOUT_DRINK"})

            # TODO: Change DummyState to actual state
            smach.StateMachine.add("FIND_PERSON_WITHOUT_DRINK",
                                   states.DummyState(robot=robot,
                                                     result_designator="failed",
                                                     caller_id=caller_id),
                                   transitions={"succeeded": "SAY_I_HAVE_SEEN",
                                                "failed": "ASK_FOR_WAVING",
                                                "aborted": "ASK_FOR_WAVING"})

            # Detect fallback - detect waving people
            smach.StateMachine.add("ASK_FOR_WAVING",
                                   states.Say(robot=robot,
                                              sentence="Could not find people without a drink. Please wave if you want me to bring you something",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "SAY_COULD_NOT_FIND_WAVING"}) # Change to WAIT_FOR_WAVING

            smach.StateMachine.add("WAIT_FOR_WAVING",
                                   states.SetPoseFirstFoundPersonToEntity(robot=robot,
                                                                          properties={'tags': ['LWave', 'RWave']},
                                                                          strict=False,
                                                                          dst_entity_designator=caller_id),
                                   transitions={"done": "SAY_I_HAVE_SEEN",
                                                "failed": "SAY_COULD_NOT_FIND_WAVING"})

            # Navigate to person who wants to place an order
            smach.StateMachine.add("SAY_COULD_NOT_FIND_WAVING",
                                   states.Say(robot=robot,
                                              sentence="I did not find any waving person.",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "ASK_STEP_IN_FRONT"})

            smach.StateMachine.add("SAY_I_HAVE_SEEN",
                                   states.Say(robot=robot,
                                              sentence="Found person who might want to place an order. I will be there shortly!",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "NAVIGATE_TO_PERSON"})

            # Navigate to waving people
            smach.StateMachine.add("NAVIGATE_TO_PERSON",
                                   states.NavigateToObserve(robot=robot, entity_designator=caller_designator,
                                                            radius=1.1),
                                   transitions={"arrived": "LEARN_NAME",
                                                "unreachable": "SAY_COULD_NOT_NAVIGATE",
                                                "goal_not_defined": "SAY_PEOPLE_WITHOUT_DRINKS"})

            # Detect waving people fallback - ask operator in front
            smach.StateMachine.add("SAY_COULD_NOT_NAVIGATE",
                                   states.Say(robot=robot,
                                              sentence="Sorry! I could not navigate to you.",
                                              look_at_standing_person=True),
                                   transitions={"spoken": "ASK_STEP_IN_FRONT"})

            smach.StateMachine.add("ASK_STEP_IN_FRONT",
                                   states.Say(robot=robot,
                                              sentence="Please step in front of me to give your order",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "LEARN_NAME"})

            # Ask operator for his name
            smach.StateMachine.add("LEARN_NAME",
                                   states.AskPersonName(robot=robot,
                                                        person_name_des=operator_name.writeable,
                                                        name_options=name_options,
                                                        default_name="john",
                                                        nr_tries=2),
                                   transitions={"succeeded": "LEARN_OPERATOR",
                                                "failed": "LEARN_NAME_FALLBACK",
                                                "timeout": "LEARN_NAME_FALLBACK"})

            # Ask operator for his name fallback
            smach.StateMachine.add("LEARN_NAME_FALLBACK",
                                   states.Say(robot=robot,
                                              sentence="Sorry, I did not get your name, I'll just call you john",
                                              look_at_standing_person=True),
                                   transitions={"spoken": "LEARN_OPERATOR"})

            # Learn operator
            smach.StateMachine.add("LEARN_OPERATOR",
                                   states.LearnPerson(robot=robot,
                                                      name_designator=operator_name,
                                                      nr_tries=5),
                                   transitions={"succeeded": "ASK_DRINK",
                                                "failed": "LEARN_OPERATOR_FALLBACK"})

            # Learn operator fallback
            smach.StateMachine.add("LEARN_OPERATOR_FALLBACK",
                                   states.Say(robot=robot,
                                              sentence="I will call you by your name when I'm back",
                                              look_at_standing_person=True,
                                              block=True),
                                   transitions={"spoken": "LEARN_OPERATOR_FLAG_TOGGLE"})

            smach.StateMachine.add("LEARN_OPERATOR_FLAG_TOGGLE",
                                   ToggleBool(learn_check_designator),
                                   transitions={"done": "ASK_DRINK"})

            # Ask for preferred beverage
            smach.StateMachine.add("ASK_DRINK",
                                   AskDrink(robot=robot,
                                            operator_name=operator_name,
                                            drink_designator=drink_designator.writeable,
                                            available_drinks_designator=available_drinks_designator,
                                            unavailable_drink_designator=unavailable_drink_designator,
                                            objects=objects),
                                   transitions={"succeeded": "succeeded",
                                                "failed": "failed"})
