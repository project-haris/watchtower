#!/usr/bin/env python3
"""Idempotently merge the sim-tcp NMEA0183 piped provider into Signal K settings.json.

Usage: merge_sim_tcp_provider.py <settings.json> <tcp_port>

Exit codes:
  0  provider was added or updated (changed)
  3  provider already present with the same config (no change)
  >0 error
"""
import json
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: merge_sim_tcp_provider.py <settings.json> <tcp_port>", file=sys.stderr)
        sys.exit(2)
    path, port = sys.argv[1], int(sys.argv[2])

    with open(path) as f:
        d = json.load(f)

    d.setdefault("pipedProviders", [])

    entry = {
        "enabled": True,
        "id": "sim-tcp",
        "pipeElements": [
            {
                "type": "providers/simple",
                "options": {
                    "logging": False,
                    "type": "NMEA0183",
                    "subOptions": {
                        "type": "tcp",
                        "host": "127.0.0.1",
                        "port": port,
                        "suppress0183event": True,
                    },
                },
            }
        ],
    }

    existing = [x for x in d["pipedProviders"] if x.get("id") == "sim-tcp"]
    if existing == [entry]:
        print("sim-tcp provider already correct")
        sys.exit(3)

    d["pipedProviders"] = [x for x in d["pipedProviders"] if x.get("id") != "sim-tcp"]
    d["pipedProviders"].append(entry)

    with open(path, "w") as f:
        json.dump(d, f, indent=4)
    print("sim-tcp provider merged into %s (port %d)" % (path, port))
    sys.exit(0)


if __name__ == "__main__":
    main()
