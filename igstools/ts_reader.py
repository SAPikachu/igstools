import logging
import io
import struct

from .utils import eof_aware_read, log_dict, unpack_from_stream

TS_PACKET_SIZE = 188
TS_MAX_PACKET_SIZE = 204
PROBE_PACKETS = 2048
SYNC_BYTE = b"\x47"
STREAM_TYPE_IGS = 0x91

log = logging.getLogger("ts_reader")


def raw_packets(stream):
    while True:
        stream.read(4)  # Bluray header
        skipped_bytes = 0
        try:
            for i in range(TS_MAX_PACKET_SIZE):
                byte = stream.read(1)
                if not byte:
                    return

                if byte == SYNC_BYTE:
                    break

                skipped_bytes += 1
            else:
                raise ValueError("Can't find sync byte in the stream")
        finally:
            if skipped_bytes:
                log.debug("Skipped %d bytes", skipped_bytes)

        yield SYNC_BYTE + eof_aware_read(stream, TS_PACKET_SIZE - 1, True)


def packets(raw_packets):
    for packet in raw_packets:
        packet_stream = io.BytesIO(packet)
        packet_stream.read(1)
        flags1, flags2 = unpack_from_stream(">HB", packet_stream)
        parsed_packet = {
            "transport_error": bool(flags1 & 0x8000),
            "payload_unit_start": bool(flags1 & 0x4000),
            "transport_priority": bool(flags1 & 0x2000),
            "pid": flags1 & 0x1fff,
            "scrambling_control": (flags2 & 0xc0) >> 6,
            "has_adaptation_field": bool(flags2 & 0x20),
            "has_payload": bool(flags2 & 0x10),
            "continuity_counter": flags2 & 0xf,
        }
        if parsed_packet["has_adaptation_field"]:
            field_length = ord(eof_aware_read(packet_stream, 1, True))
            field_data = eof_aware_read(
                packet_stream, field_length, True,
            )
            if field_length > 0:
                parsed_packet["adaptation_field_data"] = field_data
                field_flag = field_data[0]
                parsed_packet["adaptation_field"] = {
                    "discontinuity": bool(field_flag & 0x80),
                    "random_access": bool(field_flag & 0x40),
                    "priority": bool(field_flag & 0x20),
                    "has_pcr": bool(field_flag & 0x10),
                    "has_opcr": bool(field_flag & 0x8),
                    "has_splicing_point": bool(field_flag & 0x4),
                    "has_private_data": bool(field_flag & 0x2),
                    "has_extension": bool(field_flag & 0x1),
                }

        parsed_packet["payload"] = packet_stream.read()
        yield parsed_packet


def parse_psi_table(packet):
    assert packet["has_payload"]
    data = packet["payload"]
    if packet["payload_unit_start"]:
        data = data[data[0]+1:]

    table_id = data[0]

    section_length = struct.unpack_from(">H", data, 1)[0] & 0x0fff
    return table_id, data[3:3+section_length]


def programs_from_pat(packet):
    assert packet["pid"] == 0
    table_id, table_data = parse_psi_table(packet)
    assert table_id == 0

    program_data = table_data[5:-4]
    assert len(program_data) % 4 == 0

    for i in range(len(program_data) // 4):
        num, pid = struct.unpack_from(">HH", program_data, i * 4)
        yield {
            "num": num,
            "pid": pid & 0x1fff,
        }


def streams_from_pmt(packet):
    table_id, table_data = parse_psi_table(packet)
    program_info_length = struct.unpack_from(">H", table_data, 7)[0] & 0xfff
    stream_info_data = table_data[9+program_info_length:-4]
    si_stream = io.BufferedReader(io.BytesIO(stream_info_data))
    while True:
        if not si_stream.peek(1):
            return

        type, pid, es_info_length = unpack_from_stream(">BHH", si_stream)
        pid = pid & 0x1fff
        es_info_length = es_info_length & 0xfff
        yield {
            "stream_type": type,
            "pid": pid,
            "es_descriptor": eof_aware_read(si_stream, es_info_length, True),
        }


def igs_demuxer_iter(stream):
    pid_info = {
        0: {"type": "pat"}
    }
    packet_count = 0
    have_igs = False
    for p in packets(raw_packets(stream)):
        pid = p["pid"]
        if pid not in pid_info:
            log.debug("Unknown PID: %d", pid)
            pid_info[pid] = {"type": "unknown"}
            continue

        packet_type = pid_info[pid]["type"]
        if packet_type == "pat":
            for program in programs_from_pat(p):
                pid_info[program["pid"]] = program
                program["type"] = "pmt"
                log_dict(log, program)
        elif packet_type == "pmt":
            for stream_info in streams_from_pmt(p):
                pid_info[stream_info["pid"]] = stream_info
                stream_info["type"] = "stream"
                log_dict(log, stream_info)
        elif (packet_type == "stream" and
              pid_info[pid]["stream_type"] == STREAM_TYPE_IGS):
            payload = p["payload"]
            if p["payload_unit_start"]:
                yield b"IG" + b"\x00" * 8
                assert payload[:3] == b"\x00\x00\x01"
                pes_header_length = payload[8] + 9
                payload = payload[pes_header_length:]

            yield payload
            have_igs = True

        packet_count += 1
        if not have_igs and packet_count > PROBE_PACKETS:
            raise ValueError("Can't find IGS stream")
