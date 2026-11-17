"""Container entry point: put the baked-in model where it can be written to."""

import os
import shutil

if not os.path.exists("/tmp/models"):
    shutil.copytree("/opt/models", "/tmp/models")

from aiwash.aws import scorer  # noqa: E402


def handler(event, context):
    return scorer(event, context)
