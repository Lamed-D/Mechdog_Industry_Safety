from dataclasses import replace
import unittest
from host.hub.connectivity import Connectivity, Link, WeakLimits, dispatch_returns


class ConnectivityTests(unittest.TestCase):
    def setUp(self):
        # Synthetic test thresholds, not installation defaults or measured specifications.
        self.policy = Connectivity(WeakLimits(.2,.25))
        self.good = Link(True,.01,0,False,True,True)
        self.links = dict.fromkeys(('A','B'),self.good)

    def start(self):
        self.assertEqual(self.policy.tick(0,0,self.links,human_resume=True)[0].kind,'resume_patrol')

    def test_boot_does_not_start_and_ten_second_boundary(self):
        self.assertTrue(all(i.kind=='stop' for i in self.policy.tick(0,None,self.links)))
        self.start()
        self.assertEqual(self.policy.tick(9.999,0,self.links),[])
        intents = self.policy.tick(10,0,self.links)
        self.assertEqual([i.robot for i in intents if i.kind=='return_server'],['A','B'])
        self.assertTrue(self.policy.paused)

    def test_recovery_does_not_resume_return_or_stopped(self):
        self.start()
        self.policy.tick(10,0,self.links)
        self.assertEqual(self.policy.tick(11,11,self.links),[])
        self.assertEqual(self.policy.tick(12,12,self.links,human_resume=True),[])
        stopped = self.policy.tick(13,13,self.links,arrived=('A','B'))
        self.assertTrue(all(i.kind=='stop' for i in stopped))
        self.assertTrue(all(i.kind=='stop' for i in self.policy.tick(14,14,self.links)))
        self.assertEqual(self.policy.tick(15,15,self.links,human_resume=True)[0].kind,'resume_patrol')

    def test_weak_robot_returns_other_stops_and_complete_loss_stops_in_place(self):
        self.start()
        self.links['A'] = replace(self.good,loss_ratio=.25)
        intents = self.policy.tick(1,1,self.links)
        self.assertIn(('return_server','A'),[(i.kind,i.robot) for i in intents])
        self.assertIn(('stop','B'),[(i.kind,i.robot) for i in intents])
        self.links['A'] = replace(self.good,connected=False)
        intents = self.policy.tick(2,2,self.links)
        self.assertNotIn('return_server',[i.kind for i in intents])
        self.assertEqual(self.policy.states['A'],'stopped')

    def test_missing_failed_navigator_stops_in_place(self):
        for navigator in (None,FalseNavigator(),BrokenNavigator()):
            self.setUp()
            self.start()
            intents = self.policy.tick(10,0,self.links)
            output = dispatch_returns(self.policy,intents,navigator)
            self.assertNotIn('return_server',[i.kind for i in output])
            self.assertEqual(self.policy.states,{'A':'stopped','B':'stopped'})

    def test_navigator_acceptance_is_not_arrival(self):
        self.start()
        intents = self.policy.tick(10,0,self.links)
        nav = AcceptNavigator()
        output = dispatch_returns(self.policy,intents,nav)
        self.assertEqual(nav.robots,['A','B'])
        self.assertEqual(self.policy.states['A'],'returning')
        self.assertIn('return_server',[i.kind for i in output])

    def test_latch_geometry_estop_and_invalid_metrics_never_return(self):
        for link in (replace(self.good,latched=True),replace(self.good,path_safe=False),
                     replace(self.good,position_trusted=False),replace(self.good,loss_ratio=float('nan'))):
            self.setUp()
            self.start()
            self.links['A'] = link
            result = self.policy.tick(10,0,self.links)
            self.assertNotIn(('return_server','A'),[(i.kind,i.robot) for i in result])
            self.assertTrue(self.policy.paused)
        result = self.policy.tick(11,11,self.links,estop=True,human_resume=True)
        self.assertTrue(all(i.kind!='resume_patrol' for i in result))

    def test_configuration_and_clock_reject_bad_values(self):
        for age,loss in ((0,.2),(float('nan'),.2),(.2,0),(.2,1.1)):
            with self.assertRaises(ValueError):
                WeakLimits(age,loss)
        self.policy.tick(5,5,self.links)
        with self.assertRaises(ValueError):
            self.policy.tick(4,4,self.links)


class FalseNavigator:
    def return_to_server(self, robot):
        return False


class BrokenNavigator:
    def return_to_server(self, robot):
        raise RuntimeError('synthetic planning failure')


class AcceptNavigator:
    def __init__(self):
        self.robots = []

    def return_to_server(self, robot):
        self.robots.append(robot)
        return True
