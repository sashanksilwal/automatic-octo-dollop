#!/usr/bin/env python3
"""One-command simulated three-device demo; uses only Python's standard library."""
import argparse
from pathlib import Path
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
    parser.add_argument("--port",type=int,default=8000)
    args=parser.parse_args()
    stop=threading.Event()
    trace=Trace(ROOT/"data/raw"/f"simulated-laptop-{time.time_ns()}.csv")
    source,phone,laptop=Hub(),Hub(),Hub(trace)
    servers=[];receivers=[];workers=[]
    try:
        for hub,token in [(source,"source536"),(phone,"relay536")]:
            server=Server(("127.0.0.1",0),hub,token=token)
            servers.append(server)
            worker=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.1},daemon=True)
            workers.append(worker);worker.start()
        for url,token,hub in [(f"http://127.0.0.1:{servers[0].server_port}","source536",phone),
                              (f"http://127.0.0.1:{servers[1].server_port}","relay536",laptop)]:
            receiver=Receiver(url,token,hub);receivers.append(receiver);receiver.start()
        generator=threading.Thread(target=generate,args=(source,stop,8),daemon=True)
        workers.append(generator);generator.start()
        dashboard=Server(("127.0.0.1",args.port),laptop,dashboard=True)
        print(f"SIMULATED glasses → SIMULATED phone → laptop viewer: http://127.0.0.1:{dashboard.server_port}",flush=True)
        print("Press Ctrl+C to stop. This is not a physical-device Part A demo.",flush=True)
        try:
            dashboard.serve_forever(poll_interval=.1)
        finally:
            dashboard.server_close()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for receiver in reversed(receivers):receiver.close()
        for hub in (source,phone,laptop):hub.close()
        for server in servers:server.shutdown();server.server_close()
        for worker in workers:worker.join(2)
        trace.close()


if __name__=="__main__":main()
