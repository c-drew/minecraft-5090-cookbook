"""Tiny client for the LACT daemon socket (same JSON protocol as the LACT GUI).

Usage: lactctl.py show | set CORE_MHZ MEM_MHZ | undervolt MHZ MV MEM_MHZ | reset
The GPU is LACT_GPU if set, else the first device LACT lists. LACT memory offsets are twice the
value MSI Afterburner shows (+2000 here = +1000 in Afterburner). Needs access to /run/lactd.sock
(LACT's admin group). Undervolting and memory offsets can crash or corrupt; test and back off.
"""
import json, os, socket, sys

def req(obj):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect('/run/lactd.sock')
    s.sendall((json.dumps(obj) + '\n').encode())
    buf = b''
    while not buf.endswith(b'\n'):
        chunk = s.recv(1 << 20)
        if not chunk: break
        buf += chunk
    s.close(); return json.loads(buf)

GPU = os.environ.get("LACT_GPU") or next(d["id"] for d in req({"command": "list_devices"})["data"]
                                          if d["id"].upper().startswith("10DE"))  # first NVIDIA GPU

def offsets():
    t = req({"command": "device_clocks_info", "args": {"id": GPU}})["data"]["table"]["value"]
    return {"core_p0": t["gpu_offsets"]["0"]["current"], "mem_p0": t["mem_offsets"]["0"]["current"]}

if __name__ == '__main__':
    if sys.argv[1] == 'show':
        print(offsets())
    elif sys.argv[1] == 'set':   # set CORE MEM (MHz offsets, P0)
        core, mem = int(sys.argv[2]), int(sys.argv[3])
        r = req({"command": "batch_set_clocks_value", "args": {"id": GPU, "commands": [
            {"type": {"gpu_clock_offset": 0}, "value": core},
            {"type": {"mem_clock_offset": 0}, "value": mem}]}})
        print("set:", r.get("status"), r.get("data") if r.get("status") != "ok" else "")
        c = req({"command": "confirm_pending_config", "args": {"command": "confirm"}})
        print("confirm:", c.get("status"), c.get("data") if c.get("status") != "ok" else "")
        print(offsets())
    elif sys.argv[1] == 'undervolt':   # undervolt MHZ MV MEM: cap the core at MHZ, reached at MV
        target_mhz, target_mv, mem = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        curve = req({"command": "device_clocks_info", "args": {"id": GPU}})["data"]["table"]["value"]["gpu_vf_curve"]
        anchor = max((p for p in curve if p["base_voltage"] <= target_mv), key=lambda p: p["base_voltage"])
        lift = target_mhz - anchor["base_freq"]   # shift of the curve up to the target voltage
        points = {}
        for p in curve:
            if p["base_voltage"] < 800:
                continue   # idle region (fixed 300 MHz points)
            if p["base_voltage"] <= target_mv:
                off = lift
            else:
                off = target_mhz - p["base_freq"]   # flatten everything above the target voltage
            points[str(p["index"])] = {"clockspeed_offset": off}
        cfg = req({"command": "get_gpu_config", "args": {"id": GPU}})["data"] or {}
        cfg["gpu_clock_offsets"] = {"0": 0}
        cfg["mem_clock_offsets"] = {"0": mem}
        cfg["nvidia_gpu_vf_curve"] = points
        r = req({"command": "set_gpu_config", "args": {"id": GPU, "config": cfg}})
        print("set:", r.get("status"), r.get("data") if r.get("status") != "ok" else "")
        c = req({"command": "confirm_pending_config", "args": {"command": "confirm"}})
        print("confirm:", c.get("status"), c.get("data") if c.get("status") != "ok" else "")
        # The GPU rounds each point to its own frequency steps; flatten everything above the
        # target voltage to the anchor's rounded frequency so no higher-voltage point is faster.
        curve = req({"command": "device_clocks_info", "args": {"id": GPU}})["data"]["table"]["value"]["gpu_vf_curve"]
        cap = next(p["freq"] for p in curve if p["index"] == anchor["index"])
        for p in curve:
            if p["base_voltage"] > target_mv:
                points[str(p["index"])] = {"clockspeed_offset": cap - p["base_freq"]}
        cfg["nvidia_gpu_vf_curve"] = points
        r = req({"command": "set_gpu_config", "args": {"id": GPU, "config": cfg}})
        c = req({"command": "confirm_pending_config", "args": {"command": "confirm"}})
        print("reflatten:", r.get("status"), c.get("status"))
        print("anchor %d mV base %d MHz, lift %+d MHz, cap %d MHz, %d points" % (anchor["base_voltage"], anchor["base_freq"], lift, cap, len(points)))
    elif sys.argv[1] == 'reset':
        r = req({"command": "set_clocks_value", "args": {"id": GPU, "command": {"type": "reset", "value": None}}})
        print("reset:", r.get("status"))
        c = req({"command": "confirm_pending_config", "args": {"command": "confirm"}})
        print("confirm:", c.get("status")); print(offsets())
