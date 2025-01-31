import utime

def time():
    return utime.time()

def localtime(secs=None):
    if secs is None:
        secs = time()
    return utime.localtime(secs)

def gmtime(secs=None):
    if secs is None:
        secs = time()
    return utime.gmtime(secs)

def strftime(format, t=None):
    if t is None:
        t = localtime()
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )

def sleep(seconds):
    utime.sleep(seconds)