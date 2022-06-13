from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, List, Protocol

from automat import TypicalBuilder


# scaffolding; no state machines yet


@dataclass
class Request(object):
    id: int = field(default_factory=count(1).__next__)


@dataclass
class RequestGetter(object):
    cb: Callable[[Request], None] | None = None

    def startGettingRequests(self, cb: Callable[[Request], None]) -> None:
        self.cb = cb


@dataclass(repr=False)
class Task(object):
    performer: TaskPerformer
    request: Request
    done: Callable[[Task, bool], None]
    active: bool = True
    number: int = field(default_factory=count(1000).__next__)

    def __repr__(self) -> str:
        return f"<task={self.number} request={self.request.id}>"

    def complete(self, success: bool) -> None:
        # Also a state machine, maybe?
        print("complete", success)
        self.performer.activeTasks.remove(self)
        self.active = False
        self.done(self, success)

    def stop(self) -> None:
        self.complete(False)


@dataclass
class TaskPerformer(object):
    activeTasks: List[Task] = field(default_factory=list)

    def performTask(self, r: Request, done: Callable[[Task, bool], None]) -> Task:
        self.activeTasks.append(it := Task(self, r, done))
        return it


#
class ConnectionCoordinator(Protocol):
    def start(self):
        "kick off the whole process"

    def requestReceived(self, r: Request) -> None:
        "a task was received"

    def taskComplete(self, task: Task, success: bool) -> None:
        "task complete"

    def atCapacity(self) -> None:
        "we're at capacity stop handling requests"

    def headroom(self) -> None:
        "one of the tasks completed"

    def cleanup(self) -> None:
        "clean everything up"


@dataclass
class ConnectionState(object):
    getter: RequestGetter
    performer: TaskPerformer
    allDone: Callable[[Task], None]
    queue: List[Request] = field(default_factory=list)


machine = TypicalBuilder(ConnectionCoordinator, ConnectionState)


@machine.implement(ConnectionCoordinator.taskComplete)
def taskComplete(
    c: ConnectionCoordinator, s: ConnectionState, task: Task, success: bool
) -> None:
    if success:
        c.cleanup()
        s.allDone(task)
    else:
        c.headroom()


@machine.handle(ConnectionCoordinator.cleanup, enter=lambda: CleaningUp)
# TODO: it would be neat to be able to read the explicit `self` annotation here
# and automatically associate this with Requested and AtCapacity without
# needing cleanup=cleanup in both classes.
def cleanup(self: Requested | AtCapacity):

    # We *don't* want to recurse in here; stopping tasks will cause
    # taskComplete!
    while self.state.performer.activeTasks:
        self.state.performer.activeTasks[-1].stop()


@machine.state()
@dataclass
class Initial(object):
    coord: ConnectionCoordinator
    state: ConnectionState

    @machine.handle(ConnectionCoordinator.start, enter=lambda: Requested)
    def start(self) -> None:
        "let's get this party started"
        self.state.getter.startGettingRequests(self.coord.requestReceived)


TASK_LIMIT = 3


@machine.state()
@dataclass
class Requested(object):
    state: ConnectionState
    coord: ConnectionCoordinator

    @machine.handle(ConnectionCoordinator.requestReceived, enter=lambda: Requested)
    def requestReceived(self, r: Request) -> None:
        print("immediately handling request", r)
        self.state.performer.performTask(r, self.coord.taskComplete)
        if len(self.state.performer.activeTasks) >= TASK_LIMIT:
            self.coord.atCapacity()

    @machine.handle(ConnectionCoordinator.atCapacity, enter=lambda: AtCapacity)
    def atCapacity(self) -> None:
        "at capacity; don't do anything, but enter a state"
        print("at capacity")

    @machine.handle(ConnectionCoordinator.headroom)
    def headroom(self) -> None:
        "no-op in this state"
        print("headroom in requested state")

    cleanup = cleanup


@machine.state()
@dataclass
class AtCapacity(object):
    state: ConnectionState
    coord: ConnectionCoordinator

    @machine.handle(ConnectionCoordinator.requestReceived, enter=lambda: AtCapacity)
    def requestReceived(self, r: Request) -> None:
        print("buffering request", r)
        self.state.queue.append(r)

    @machine.handle(ConnectionCoordinator.headroom, enter=lambda: Requested)
    def headroom(self) -> None:
        "nothing to do, just transition to Requested state"
        unhandledRequest = self.state.queue.pop()
        print("dequeueing", unhandledRequest)
        self.coord.requestReceived(unhandledRequest)

    cleanup = cleanup


@machine.state()
class CleaningUp(object):
    @machine.handle(ConnectionCoordinator.cleanup, enter=lambda: CleaningUp)
    def noop(self) -> None:
        "we're already cleaning up don't clean up"
        print("cleanup in cleanup")

    @machine.handle(ConnectionCoordinator.headroom)
    def headroom(self) -> None:
        "no-op in this state"
        print("headroom in requested state")


ConnectionMachine = machine.buildClass()


def begin(r: RequestGetter, t: TaskPerformer, done: Callable[[Task], None]) -> ConnectionCoordinator:
    machine = ConnectionMachine(r, t, done)
    machine.start()
    return machine


#

rget = RequestGetter()
tper = TaskPerformer()


def yay(t: Task) -> None:
    print("yay")


m = begin(rget, tper, yay)
cb = rget.cb
assert cb is not None
cb(Request())
cb(Request())
cb(Request())
cb(Request())
cb(Request())
cb(Request())
cb(Request())
print([each for each in tper.activeTasks])
sc: ConnectionState = m._stateCore  # type:ignore
print(sc.queue)
tper.activeTasks[0].complete(False)
tper.activeTasks[0].complete(False)
print([each for each in tper.activeTasks])
print(sc.queue)
tper.activeTasks[0].complete(True)
print([each for each in tper.activeTasks])
