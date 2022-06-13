# Task example (simplified happy eyeballs)
# workflow is:
# 1. start up, subscribe to incoming requests to perform tasks (i.e.: start resolving names)
# 2. as they arrive, perform tasks up to a concurrency limit (i.e.: start processing results)
# 3. when one succeeds, cancel the pending ones

from dataclasses import dataclass, field
from typing import Callable, List

# scaffolding; no state machines yet

class Request(object):
    pass


@dataclass
class RequestGetter(object):
    cb: Callable[[Request], None] | None = None

    def startGettingRequests(self, cb: Callable[[Request], None]) -> None:
        self.cb = cb


@dataclass
class Task(object):
    performer: TaskPerformer
    request: Request
    done: Callable[[Task, bool], None]
    active: bool = True

    def complete(self, success: bool):
        # also a state machine, maybe?
        self.performer.activeTasks.remove(self)
        self.active = False
        self.done(self, success)


@dataclass
class TaskPerformer(object):
    activeTasks: List[Task] = field(default_factory=list)

    def performTask(self, r: Request, done: Callable[[Task, bool], None]) -> Task:
        self.activeTasks.append(it := Task(self, r, done))
        return it


rq = RequestGetter()
tg = TaskPerformer()
