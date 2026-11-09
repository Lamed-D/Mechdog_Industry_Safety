"""Pure connectivity policy. Physical thresholds must come from field configuration."""
from dataclasses import dataclass
import math
from typing import Protocol


def finite(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)


@dataclass(frozen=True)
class WeakLimits:
    max_telemetry_age_s: float
    max_loss_ratio: float

    def __post_init__(self):
        if (not finite(self.max_telemetry_age_s) or self.max_telemetry_age_s<=0
                or not finite(self.max_loss_ratio) or not 0<self.max_loss_ratio<=1):
            raise ValueError('field-measured weak-link limits required')


@dataclass(frozen=True)
class Link:
    connected: bool
    telemetry_age_s: float
    loss_ratio: float
    latched: bool
    position_trusted: bool
    path_safe: bool

    def valid(self):
        return (all(type(v) is bool for v in (self.connected,self.latched,self.position_trusted,self.path_safe))
                and finite(self.telemetry_age_s) and self.telemetry_age_s>=0
                and finite(self.loss_ratio) and 0<=self.loss_ratio<=1)


@dataclass(frozen=True)
class Intent:
    kind: str
    robot: str | None
    reason: str


class Connectivity:
    def __init__(self, limits, *, internet_timeout=10):
        if not isinstance(limits,WeakLimits) or not finite(internet_timeout) or internet_timeout<=0:
            raise ValueError('limits and internet timeout required')
        self.limits, self.internet_timeout = limits, internet_timeout
        self.states = {'A':'stopped','B':'stopped'}
        self.paused = True
        self._last = None
        self._started = None

    def _weak(self, link):
        return (link.telemetry_age_s>=self.limits.max_telemetry_age_s
                or link.loss_ratio>=self.limits.max_loss_ratio)

    def tick(self, now, last_success, links, *, human_resume=False, estop=False,
             arrived=(), failed=()):
        if not finite(now) or (self._last is not None and now<self._last):
            raise ValueError('monotonic clock required')
        if type(human_resume) is not bool or type(estop) is not bool:
            raise ValueError('explicit boolean required')
        self._last = now
        if self._started is None:
            self._started = now
        internet_ok = finite(last_success) and 0<=now-last_success<self.internet_timeout
        internet_lost = (not internet_ok and
                         (last_success is not None or now-self._started>=self.internet_timeout))
        good = lambda link:isinstance(link,Link) and link.valid()
        ready = lambda link:(good(link) and link.connected and not link.latched
                            and link.position_trusted and link.path_safe and not self._weak(link))
        # Human command is necessary but cannot override missing telemetry, latch or geometry.
        if human_resume and not estop and internet_ok and all(ready(links.get(r)) for r in self.states):
            if self.paused and all(state=='stopped' for state in self.states.values()):
                self.paused = False
                self.states = dict.fromkeys(self.states,'active')
                return [Intent('resume_patrol',None,'human_confirmed')]
        output = []
        for robot,state in list(self.states.items()):
            link = links.get(robot)
            unsafe = (not good(link) or not link.connected or link.latched
                      or not link.position_trusted or not link.path_safe)
            trigger = internet_lost or (good(link) and self._weak(link))
            if estop or unsafe or robot in failed:
                if not self.paused:
                    output.append(Intent('pause_patrol',None,'unsafe_connection'))
                self.paused = True
                self.states[robot] = 'stopped'
                # Repeated stop intents are deliberately safe and avoid stale movement.
                output.append(Intent('stop',robot,'estop' if estop else 'unsafe_connection'))
            elif state=='returning':
                if robot in arrived:
                    self.states[robot] = 'stopped'
                    output.append(Intent('stop',robot,'at_server'))
                # Even if internet recovers, complete return then wait for a human.
            elif trigger and state=='active':
                if not self.paused:
                    output.append(Intent('pause_patrol',None,'connection_degraded'))
                self.paused = True
                self.states[robot] = 'returning'
                output.append(Intent('return_server',robot,'connection_degraded'))
            elif state=='stopped':
                output.append(Intent('stop',robot,'awaiting_human'))
        if self.paused:
            for robot,state in list(self.states.items()):
                if state=='active':
                    self.states[robot] = 'stopped'
                    output.append(Intent('stop',robot,'patrol_paused'))
        return output

    def return_failed(self, robot):
        if robot not in self.states:
            raise ValueError('unknown robot')
        self.paused = True
        self.states[robot] = 'stopped'
        return Intent('stop',robot,'navigator_unavailable')


class Navigator(Protocol):
    def return_to_server(self, robot):
        """Return True only when a checked return request was accepted, not when arrived."""
        ...


def dispatch_returns(policy, intents, navigator=None):
    """Translate only return requests; the service must execute pause/stop before movement."""
    output = []
    for intent in intents:
        if intent.kind != 'return_server':
            output.append(intent)
            continue
        try:
            accepted = navigator is not None and navigator.return_to_server(intent.robot) is True
        except Exception:
            accepted = False
        output.append(intent if accepted else policy.return_failed(intent.robot))
    return output
