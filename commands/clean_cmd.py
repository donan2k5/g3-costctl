"""clean — (stretch) bulk terminate resources matching a tag.

WARNING — DESIGN-FOR-SAFETY
---------------------------
This is the most dangerous command in the CLI. Get the contract right:

  1. DEFAULT IS DRY-RUN. Without --apply the command MUST NOT touch resources.
     It only lists what WOULD be deleted.
  2. Even with --apply, you should consider printing a summary count first
     ("about to terminate N EC2 + M volumes — proceed?"), though for this
     starter a hard `--apply` flag is enough.
  3. Never use this with a tag you don't fully own. Reflection prompt in
     README covers the blast-radius scenario.

WHAT YOU MUST BUILD
-------------------
1. `_find_targets(tag_key, tag_val)` — return a dict like:
     {"ec2": [<instance ids in non-terminal state>],
      "volume": [<volume ids in 'available' state only>]}
   Skip terminated/shutting-down instances (already gone).
   Skip in-use volumes (can't delete while attached — would error anyway).

2. `run(args)` — call _find_targets, print the plan, then either:
     - bail with "(dry-run — pass --apply to ...)"  (default)
     - or actually terminate (when --apply)

HELPERS YOU CAN USE
-------------------
From commands._common:
  parse_kv(s) -> (k, v)

AWS APIS YOU'LL NEED
--------------------
- ec2.describe_instances() + describe_volumes() — same as list_cmd
- ec2.terminate_instances(InstanceIds=[...])
- ec2.delete_volume(VolumeId=...)  (per volume, no bulk API)

VERIFY
------
    pytest tests/test_clean.py -v
"""
import boto3

from commands._common import parse_kv


def _find_targets(tag_key, tag_val):
    """Return {"ec2": [...], "volume": [...]} matching tag in non-terminal state."""
    ec2 = boto3.client("ec2")
    result = {"ec2": [], "volume": []}

    # EC2 — skip terminated/shutting-down
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_val]}]
    ):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                state = inst["State"]["Name"]
                if state not in ("terminated", "shutting-down"):
                    result["ec2"].append(inst["InstanceId"])

    # Volumes — only 'available' (not in-use)
    vol_paginator = ec2.get_paginator("describe_volumes")
    for page in vol_paginator.paginate(
        Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_val]}]
    ):
        for vol in page["Volumes"]:
            if vol["State"] == "available":
                result["volume"].append(vol["VolumeId"])

    return result


def run(args):
    """Entry point.

    Args set by argparse:
        args.tag    — "key=value" string (REQUIRED)
        args.apply  — bool, must be True to actually delete (default False = dry-run)
    """
    tag_key, tag_val = parse_kv(args.tag)
    targets = _find_targets(tag_key, tag_val)

    ec2_ids = targets["ec2"]
    vol_ids = targets["volume"]

    if not ec2_ids and not vol_ids:
        print("Nothing to clean.")
        return

    # Print plan
    for iid in ec2_ids:
        print(f"  EC2 {iid}")
    for vid in vol_ids:
        print(f"  Volume {vid}")

    if not args.apply:
        print(f"(dry-run — pass --apply to delete {len(ec2_ids)} EC2 + {len(vol_ids)} volume(s))")
        return

    # Apply
    ec2 = boto3.client("ec2")
    if ec2_ids:
        ec2.terminate_instances(InstanceIds=ec2_ids)
        print(f"Terminated {len(ec2_ids)} EC2 instance(s).")
    for vid in vol_ids:
        ec2.delete_volume(VolumeId=vid)
        print(f"Deleted volume {vid}.")
