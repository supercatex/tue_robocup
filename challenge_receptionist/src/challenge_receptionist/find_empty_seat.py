#! /usr/bin/env python
import rospy
import robot_smach_states as states
import robot_smach_states.util.designators as ds
import smach
from robot_skills.util.entity import Entity
from robot_skills.util.volume import Volume
from robot_skills.classification_result import ClassificationResult


class SeatsInRoomDesignator(ds.Designator):
    def __init__(self, robot, seat_ids, room, name=None, debug=False):
        super(SeatsInRoomDesignator, self).__init__(resolve_type=[Entity], name=name)

        self.robot = robot

        ds.check_type(seat_ids, [str])
        ds.check_type(room, Entity)

        self.room = room
        self.seat_ids = seat_ids
        self.debug = debug

    def _resolve(self):
        if self.debug:
            import ipdb;ipdb.set_trace()
        room = self.room.resolve() if hasattr(self.room, 'resolve') else self.room  # type: Entity
        if not room:
            rospy.logwarn("Room is None, so cannot find seats there")
            return None
        seats = [self.robot.ed.get_entity(seat_id) for seat_id in self.seat_ids]  # type: List[Entity]

        true_seats = [seat for seat in seats if seat is not None]  # get_entity returns None if entity does not exist

        seats_in_room = room.entities_in_volume(true_seats,"in")

        return seats_in_room

    def __repr__(self):
        return "SeatsInRoomDesignator({}, {}, {}, {})".format(self.robot, self.seat_ids, self.room, self.name)



class SeatVolumeNamesDesignator(ds.Designator):
    def __init__(self, robot, seat_entity_designator, name=None, debug=False):
        super(SeatVolumeNamesDesignator, self).__init__(resolve_type=[str], name=name)

        self.robot = robot

        ds.check_type(seat_entity_designator, Entity)
        self.seat_entity_designator = seat_entity_designator

        self.debug = debug

    def _resolve(self):
        if self.debug:
            import ipdb;ipdb.set_trace()

        try:
            seat_entity = self.seat_entity_designator.resolve()  # type: Entity
            seat_volume_names = [k for k in seat_entity.volumes.keys() if k.endswith('seat')]

            return seat_volume_names
        except AttributeError:
            return None

    def __repr__(self):
        return "SeatsInRoomDesignator({}, {}, {}, {})".format(self.robot, self.seat_ids, self.room, self.name)


class FindEmptySeat(smach.StateMachine):
    """
    Iterate over all seat-type objects and check that their 'on-top-of' volume is empty
    That can be done with an Inspect and then query for any Entities inside that volume.
    If there are none, then the seat is empty
    """
    def __init__(self, robot, seats_to_inspect, room, seat_is_for=None):
        smach.StateMachine.__init__(self, outcomes=['succeeded', 'failed'])

        seats = SeatsInRoomDesignator(robot, seats_to_inspect, room, "seats_in_room")
        seat_ent_des = ds.VariableDesignator(resolve_type=Entity)
        if seat_is_for:
            ds.check_type(seat_is_for, str)
        else:
            seat_is_for = ds.Designator(' ')

        seat_volumes = SeatVolumeNamesDesignator(robot, seat_ent_des)
        seat_volume_des = ds.VariableDesignator(resolve_type=str)

        with self:
            smach.StateMachine.add('SAY_LETS_FIND_SEAT',
                                   states.Say(robot,
                                              ["Let me find a place for {name} to sit. Please be patient while I check out where there's place to sit"],
                                              name=seat_is_for,
                                              block=False),
                                   transitions={'spoken': 'ITERATE_NEXT_SEAT'})

            smach.StateMachine.add('ITERATE_NEXT_SEAT',
                                   states.IterateDesignator(seats, seat_ent_des.writeable),
                                   transitions={'next': 'ITERATE_NEXT_VOLUME',
                                                'stop_iteration': 'SAY_NO_EMPTY_SEATS'})

            smach.StateMachine.add('ITERATE_NEXT_VOLUME',
                                   states.IterateDesignator(seat_volumes, seat_volume_des.writeable),
                                   transitions={'next': 'CHECK_SEAT_EMPTY',
                                                'stop_iteration': 'ITERATE_NEXT_SEAT'})

            smach.StateMachine.add('CHECK_SEAT_EMPTY',
                                   states.CheckVolumeEmpty(robot, seat_ent_des, seat_volume_des, 0.2),
                                   transitions={'occupied': 'ITERATE_NEXT_SEAT',
                                                'empty': 'POINT_AT_EMPTY_SEAT',
                                                'partially_occupied': 'POINT_AT_PARTIALLY_OCCUPIED_SEAT',
                                                'failed': 'ITERATE_NEXT_SEAT'})

            smach.StateMachine.add('POINT_AT_EMPTY_SEAT',
                                   states.PointAt(robot=robot,
                                                  arm_designator=ds.UnoccupiedArmDesignator(robot, {'required_goals':['point_at']}),
                                                  point_at_designator=seat_ent_des,
                                                  look_at_designator=seat_ent_des),
                                   transitions={"succeeded": "SAY_SEAT_EMPTY",
                                                "failed": "SAY_SEAT_EMPTY"})

            smach.StateMachine.add('SAY_SEAT_EMPTY',
                                   states.Say(robot,
                                              ["Please sit on the {seat}, {name}"],
                                              name=seat_is_for,
                                              seat=ds.AttrDesignator(seat_ent_des, 'id', resolve_type=str),
                                              block=True),
                                   transitions={'spoken': 'RESET_SUCCESS'})

            smach.StateMachine.add('POINT_AT_PARTIALLY_OCCUPIED_SEAT',
                                   states.PointAt(robot=robot,
                                                  arm_designator=ds.UnoccupiedArmDesignator(robot, {'required_goals':['point_at']}),
                                                  point_at_designator=seat_ent_des,
                                                  look_at_designator=seat_ent_des),
                                   transitions={"succeeded": "SAY_SEAT_PARTIALLY_OCCUPIED",
                                                "failed": "SAY_SEAT_PARTIALLY_OCCUPIED"})

            smach.StateMachine.add('SAY_SEAT_PARTIALLY_OCCUPIED',
                                   states.Say(robot,
                                              ["I think there's some space left here where you can sit {name}"],
                                              name=seat_is_for,
                                              block=True),
                                   transitions={'spoken': 'RESET_SUCCESS'})

            smach.StateMachine.add('SAY_NO_EMPTY_SEATS',
                                   states.Say(robot,
                                              ["Sorry, there are no empty seats. I guess you just have to stand {name}"],
                                              name=seat_is_for,
                                              block=True),
                                   transitions={'spoken': 'RESET_FAIL'})

            smach.StateMachine.add('RESET_FAIL',
                                   states.ResetArms(robot),
                                   transitions={'done': 'failed'})

            smach.StateMachine.add('RESET_SUCCESS',
                                   states.ResetArms(robot),
                                   transitions={'done': 'succeeded'})


if __name__ == "__main__":
    import sys
    from robot_skills import get_robot

    if len(sys.argv) < 4:
        print "Please provide robot_name, room and seats_to_inspect as arguments. Eg. 'hero livingroom dinner_table bar dinnertable",
        sys.exit(1)

    robot_name = sys.argv[1]
    room = sys.argv[2]
    seats_to_inspect = sys.argv[3:]

    rospy.init_node('test_find_emtpy_seat')
    robot = get_robot(robot_name)

    sm = FindEmptySeat(robot,
                       seats_to_inspect=seats_to_inspect,
                       room=ds.EntityByIdDesignator(robot, room))
    sm.execute()
