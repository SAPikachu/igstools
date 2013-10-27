import struct


def eof_aware_read(stream, length, fail_on_no_data=False):
    if length == 0:
        return b""

    ret = stream.read(length)
    if not ret:
        if fail_on_no_data:
            raise EOFError()

        return None

    if len(ret) < length:
        raise EOFError()

    return ret


def unpack_from_stream(fmt, stream):
    data = eof_aware_read(stream, struct.calcsize(fmt))
    if not data:
        return None

    return struct.unpack(fmt, data)


def dump_dict(d):
    def _dump_value(v):
        if isinstance(v, dict):
            return "{{{}}}".format(dump_dict(v))
        elif isinstance(v, (bytes, list)):
            return "<Len: {}>".format(len(v))

        return str(v)

    return ", ".join(["=".join([str(k), _dump_value(v)])
                      for k, v in d.items()])


def log_dict(log, d, prefix=""):
    log.debug(prefix + dump_dict(d))
