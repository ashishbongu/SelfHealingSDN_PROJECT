from typing import Any


TOPOLOGIES: dict[str, dict[str, Any]] = {
    "diamond": {
        "nodes": ["h1", "s1", "s2", "s3", "s4", "h4"],
        "links": [
            {"source": "h1", "target": "s1", "capacity_mbps": 10},
            {"source": "s1", "target": "s2", "capacity_mbps": 10},
            {"source": "s1", "target": "s3", "capacity_mbps": 10},
            {"source": "s2", "target": "s4", "capacity_mbps": 10},
            {"source": "s3", "target": "s4", "capacity_mbps": 10},
            {"source": "s4", "target": "h4", "capacity_mbps": 10},
        ],
    },
    "multipath_mesh": {
        "nodes": ["h1", *[f"s{i}" for i in range(1, 10)], "h4"],
        "links": [
            {"source": "h1", "target": "s1", "capacity_mbps": 10},
            {"source": "s1", "target": "s2", "capacity_mbps": 10},
            {"source": "s1", "target": "s3", "capacity_mbps": 10},
            {"source": "s2", "target": "s4", "capacity_mbps": 10},
            {"source": "s2", "target": "s5", "capacity_mbps": 10},
            {"source": "s3", "target": "s5", "capacity_mbps": 10},
            {"source": "s3", "target": "s6", "capacity_mbps": 10},
            {"source": "s4", "target": "s7", "capacity_mbps": 10},
            {"source": "s5", "target": "s7", "capacity_mbps": 10},
            {"source": "s5", "target": "s8", "capacity_mbps": 10},
            {"source": "s6", "target": "s8", "capacity_mbps": 10},
            {"source": "s7", "target": "s9", "capacity_mbps": 10},
            {"source": "s8", "target": "s9", "capacity_mbps": 10},
            {"source": "s9", "target": "h4", "capacity_mbps": 10},
        ],
    },
}


def get_topology(name: str) -> dict[str, Any]:
    if name not in TOPOLOGIES:
        raise KeyError(name)
    return TOPOLOGIES[name]

