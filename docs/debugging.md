# Tracing API

The tracing API lets you assign a callback function that will be invoked each
time an input event causes the state machine to move from one state to
another. This can help you figure out problems caused by events occurring in
the wrong order, or not happening at all. Your callback function can print a
message to stdout, write something to a logfile, or deliver the information
in any application-specific way you like. The only restriction is that the
function must not touch the state machine at all.

To prepare the state machine for tracing, you must assign a name to the
"setTrace" method in your class. In this example, we use
`setTheTracingFunction`, but the name can be anything you like:

```python
class Sample(object):
    mm = MethodicalMachine()
    
    @mm.state(initial=True)
    def begin(self):
        "initial state"
    @mm.state()
    def end(self):
        "end state"
    @mm.input()
    def go(self):
        "event that moves us from begin to end"
    @mm.output()
    def doThing1(self):
        "first thing to do"
    @mm.output()
    def doThing2(self):
        "second thing to do"
    
    setTheTracingFunction = mm.setTrace
    
    begin.upon(go, enter=end, outputs=[doThing1, doThing2])
```

Later, after you instantiate the `Sample` object, you can set the tracing
callback for that particular instance by calling the
`setTheTracingFunction()` method on it:

```python
s = Sample()
def tracer(oldState, input, newState):
    pass
s.setTheTracingFunction(tracer)
```

Note that you cannot shortcut the name-assignment step:
`s.mm.setTrace(tracer)` will not work, because Automat goes to great lengths
to hide that `mm` object from external access. And you cannot set the tracing
function at class-definition time (e.g. a class-level `mm.setTrace(tracer)`)
because the state machine has merely been *defined* at that point, not
instantiated (you might eventually have multiple instances of the Sample
class, each with their own independent state machine), and each one can be
traced separately.

## The Tracer Callback Function

When the input event is received, before any transitions are made, the tracer
function is called with three positional arguments:

* `oldState`: a string with the name of the current state
* `input`: a string with the name of the input event
* `newState`: a string with the name of the new state

If your tracer function returns None, then you will only be notified about
the input events. But, if your tracer function returns a callable, then just
before each output function is executed (if any), that callable will be
executed with a single `output` argument (as a string).

So if you only care about the transitions, your tracing function can just do:

```python
 s = Sample()
 def tracer(oldState, input, newState):
     print("%s.%s -> %s" % (oldState, input, newState))
 s.setTheTracingFunction(tracer)
 s.go()
 # prints:
 # begin.go -> end
```

But if you want to know when each output is invoked (perhaps to compare
against other log messages emitted from inside those output functions), you
can do:

```python
 s = Sample()
 def tracer(oldState, input, newState):
     def traceOutputs(output):
         print("%s.%s -> %s: %s()" % (oldState, input, newState, output))
     print("%s.%s -> %s" % (oldState, input, newState))
     return traceOutputs
 s.setTheTracingFunction(tracer)
 s.go()
 # prints:
 # begin.go -> end
 # begin.go -> end: doThing1()
 # begin.go -> end: doThing2()
```


## Tracing Multiple State Machines

If you have multiple state machines in your application, you will probably
want to pass a different tracing function to each, so your logs can
distinguish between the transitions of MachineFoo vs those of MachineBar.
This is particularly important if your application involves network
communication, where an instance of MachineFoo (e.g. in a client) is
communication with a sibling instance of MachineFoo (in a server). When
exercising both sides of this connection in a single process, perhaps in an
automated test, you will need to clearly mark the first as "foo1" and the
second as "foo2" to avoid confusion.

```python
 s1 = Sample()
 s2 = Sample()
 def tracer1(oldState, input, newState):
     print("S1: %s.%s -> %s" % (oldState, input, newState))
 s1.setTheTracingFunction(tracer1)
 def tracer2(oldState, input, newState):
     print("S2: %s.%s -> %s" % (oldState, input, newState))
 s2.setTheTracingFunction(tracer2)
```
