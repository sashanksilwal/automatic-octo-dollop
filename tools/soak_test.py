#!/usr/bin/env python3
"""65-second loopback endurance test through the actual Java transport relay."""
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"laptop-viewer"))
from server import Server
from streaming import Hub,Receiver,Trace
from simulate import generate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration",type=float,default=65)
    args=parser.parse_args()
    if args.duration<5:parser.error("Duration must be at least five seconds")
    java=Path(os.environ.get("JAVA_HOME",ROOT/".tools/jdk/Contents/Home"))/"bin/java"
    classes=ROOT/".tools/test-classes"
    if not java.exists() or not (classes/"RelayHarness.class").exists():
        parser.error("Run tools/check.sh first to compile RelayHarness with a JDK")
    output=ROOT/"output/verification";output.mkdir(parents=True,exist_ok=True)
    trace=Trace(output/f"simulated-soak-{time.time_ns()}.csv")
    source,destination=Hub(),Hub(trace)
    server=Server(("127.0.0.1",0),source,token="source536")
    service=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.05},daemon=True);service.start()
    process=subprocess.Popen([str(java),"-cp",str(classes)+os.pathsep+str(ROOT/"stream-core/build/classes/java/main"),
                              "RelayHarness",f"http://127.0.0.1:{server.server_port}"],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stop=threading.Event();receiver=None;generator=None
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            if not selector.select(8):raise RuntimeError("Java relay did not start")
        port=int(process.stdout.readline().strip())
        receiver=Receiver(f"http://127.0.0.1:{port}","relay536",destination);receiver.start()
        generator=threading.Thread(target=generate,args=(source,stop,8),daemon=True);generator.start()
        first=destination.next(-1,timeout=8)
        if first is None:raise RuntimeError("No first frame received")
        started=last=time.monotonic();version=first[0];max_gap=0.0;observed=1
        while time.monotonic()-started<args.duration:
            sample=destination.next(version,timeout=2)
            if sample is None:raise RuntimeError("No fresh frame within two seconds")
            now=time.monotonic();max_gap=max(max_gap,now-last);last=now;version=sample[0];observed+=1
        elapsed=last-started
        result=dict(test="SIMULATED Python camera → actual Java core relay → Python receiver",
                    hardware_test=False,duration_seconds=round(elapsed,3),frames_observed=observed,
                    received_frames=destination.frames,source_frames=source.frames,
                    observed_fps=round((observed-1)/elapsed,3),max_interarrival_gap_ms=round(max_gap*1000,3),
                    source_session=destination.last_session,
                    passed=observed>=args.duration*7 and max_gap<2 and not trace.error)
        (output/"soak-result.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2),flush=True)
        if not result["passed"]:raise RuntimeError("Endurance thresholds failed")
    finally:
        stop.set()
        if generator:generator.join(2)
        if receiver:receiver.close()
        process.terminate();process.communicate(timeout=8)
        source.close();destination.close();server.shutdown();server.server_close();service.join(2);trace.close()


if __name__=="__main__":main()
