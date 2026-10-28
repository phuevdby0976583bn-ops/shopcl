# -*- coding: utf-8 -*-
import os
import sys
import json
import platform
from typing import List

# Repository and folder name on mobile sdcard
REPO_FOLDER_NAME = "facebook-account-registration"


def is_termux_or_mobile() -> bool:
    """Check if the current execution environment is Android / Termux."""
    if "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux"):
        return True
    if os.path.exists("/sdcard"):
        return True
    if "ANDROID_ROOT" in os.environ:
        return True
    return False


def get_base_storage_dir() -> str:
    """Get the base working directory for input and output files."""
    if is_termux_or_mobile():
        sdcard_path = "/sdcard"
        if os.path.exists(sdcard_path):
            target_dir = os.path.join(sdcard_path, REPO_FOLDER_NAME)
            try:
                os.makedirs(target_dir, exist_ok=True)
                return target_dir
            except Exception:
                pass
    return os.path.abspath(".")


def get_output_dir() -> str:
    """Get the primary directory path for output files."""
    base_dir = get_base_storage_dir()
    out_dir = os.path.join(base_dir, "output")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        out_dir = os.path.join(".", "output")
        os.makedirs(out_dir, exist_ok=True)
    return out_dir


def get_output_filepaths() -> List[str]:
    """Get list of paths where output should be written."""
    paths = []
    
    # Check config.json for custom override
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
                out = cfg.get("output_file", "accounts.txt")
                if isinstance(out, str) and out:
                    if out not in paths:
                        paths.append(out)
                elif isinstance(out, list) and out:
                    for p in out:
                        if p not in paths:
                            paths.append(p)
        except Exception:
            pass

    # Primary storage path (sdcard on Termux, local on PC)
    primary_out = os.path.join(get_output_dir(), "success.txt")
    if primary_out not in paths:
        paths.append(primary_out)

    # Legacy output file accounts.txt
    legacy_out = os.path.abspath("accounts.txt")
    if legacy_out not in paths:
        paths.append(legacy_out)

    # If running on mobile, also write to local project output as backup
    if is_termux_or_mobile():
        local_out = os.path.abspath(os.path.join(".", "output", "success.txt"))
        if local_out not in paths:
            try:
                os.makedirs(os.path.dirname(local_out), exist_ok=True)
                paths.append(local_out)
            except Exception:
                pass

    return paths
