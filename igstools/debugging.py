import pdb, sys, traceback
import signal

activated = False

def setup():
    def info(type, value, tb):
        traceback.print_exception(type, value, tb)
        pdb.pm()

    sys.excepthook = info
    activated = True

def dumpstacks(signal, frame):
    id2name = dict([(th.ident, th.name) for th in threading.enumerate()])
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# Thread: %s(%d)" % (id2name.get(threadId,""), threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))
    print("\n".join(code))

def dump_on_ctrl_break():
    signal.signal(signal.SIGBREAK, dumpstacks)

