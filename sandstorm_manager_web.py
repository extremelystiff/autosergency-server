#!/usr/bin/env python3
"""
Sandstorm Manager Web - Unified Server Management & RTV Platform
Combines sandstorm_manager.sh functionality with RTVcliWEB.py features
"""

import os
import sys
import time
import json
import re
import socket
import struct
import logging
import threading
import math
import random
import subprocess
import requests
from datetime import datetime
from copy import deepcopy
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, Response

# ============================================================
# CONFIGURATION
# ============================================================

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

# Default paths (relative to script location)
DEFAULT_SERVER_DIR = os.path.join(SCRIPT_DIR, "sandstorm_server")
DEFAULT_STEAMCMD_DIR = os.path.join(SCRIPT_DIR, "steamcmd")
DEFAULT_PRESETS_FILE = os.path.join(SCRIPT_DIR, "sandstorm_presets.conf")

# Load paths from config or use defaults
CONFIG_FILE = "sandstorm_manager_config.json"

def load_path_config():
    """Load path configuration from config file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return {
                    'steamcmd_dir': config.get('steamcmd_dir', DEFAULT_STEAMCMD_DIR),
                    'server_dir': config.get('server_dir', DEFAULT_SERVER_DIR),
                    'presets_file': config.get('presets_file', DEFAULT_PRESETS_FILE),
                    'home': config.get('home', HOME)
                }
        except:
            pass
    return {
        'steamcmd_dir': DEFAULT_STEAMCMD_DIR,
        'server_dir': DEFAULT_SERVER_DIR,
        'presets_file': DEFAULT_PRESETS_FILE,
        'home': HOME
    }

PATH_CONFIG = load_path_config()

# Server paths from config
STEAMCMD_DIR = PATH_CONFIG['steamcmd_dir']
SERVER_DIR = PATH_CONFIG['server_dir']
PRESETS_FILE = PATH_CONFIG['presets_file']
HOME = PATH_CONFIG['home']

APP_ID = "581330"
SESSION_NAME = "sandstorm"
MULTIPLEXER = "tmux"

# Installation tracking (global for web access)
INSTALLATION_STATUS = {
    "steamcmd": {"running": False, "complete": False, "output": "", "error": ""},
    "server": {"running": False, "complete": False, "output": "", "error": ""}
}
INSTALLATION_LOCK = threading.Lock()

# Watchdog config
WATCHDOG_PID_FILE = f"{HOME}/.sandstorm_watchdog.pid"
LAST_LAUNCHED_PRESET_FILE = f"{HOME}/.sandstorm_last_launched_preset.txt"
WATCHDOG_LOG_FILE = f"{HOME}/sandstorm_watchdog.log"
WATCHDOG_CHECK_INTERVAL = 30

# MOD.IO config
MODIO_API_KEY = "bbf3af200848aef28418c032a601e7a2"
MODIO_AUTH_URL = "https://g-254.modapi.io/v1/oauth/emailrequest"
MODIO_CACHE_DIR = f"{HOME}/.modio"
SAVED_SECURITY_CODE_FILE = f"{HOME}/.sandstorm_security_code.txt"

# Default config
DEFAULT_CONFIG = {
    "rcon": {
        "ip": "127.0.0.1",
        "port": 27015,
        "password": "password"
    },
    "query_port": 27016,
    "steam_api_key": "",
    "log_file_path": f"{SERVER_DIR}/Insurgency/Saved/Logs/Insurgency.log",
    "mapcycle_file_path": "Config/Server/MapCycle.txt",
    "map_source_mode": 0,
    "rtv_threshold_percent": 0.6,
    "rtv_min_players": 1,
    "web_port": 5000,
    "server_port": 27102,
    "server_query_port": 27131,
    "steamcmd_dir": STEAMCMD_DIR,
    "server_dir": SERVER_DIR,
    "presets_file": PRESETS_FILE,
    "home": HOME,
    "timerslack_system_user": "",
    "timerslack_enabled": True,
    "global_gslt_token": "",
    "global_gamestats_token": "",
    "mapcycle_presets": {},
    "custom_scenarios": []
}

# Ensure config exists
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)

# ============================================================
# MODIOBACKGROUND TIMERSLACK HACK
# ============================================================

def apply_timerslack_hack(system_user, enabled=True):
    """
    Apply timerslack hack to reduce high CPU usage from ModioBackground thread.
    
    This is a workaround for a bug in the Sandstorm server where the ModioBackground
    thread enters an infinite loop of clock_nanosleep calls, causing high CPU usage.
    
    Setting timerslack to 200ms (200000000 ns) instead of default 1ms reduces CPU usage.
    
    Args:
        system_user: The system user the server runs as
        enabled: Whether to apply the hack (can be disabled in config)
    
    Returns:
        bool: True if hack was applied successfully, False otherwise
    """
    if not enabled or not system_user:
        return False
    
    try:
        # Find all ModioBackground thread IDs for the specified user
        result = subprocess.run(
            f"ps Hh -u '{system_user}' -o tid,comm | grep ModioBackground | grep --only-matching '[0-9]*'",
            shell=True, capture_output=True, text=True
        )
        
        pids = result.stdout.strip().split('\n')
        applied_count = 0
        
        for pid in pids:
            pid = pid.strip()
            if pid and pid.isdigit():
                try:
                    # Set timerslack to 200ms (200000000 ns)
                    with open(f"/proc/{pid}/timerslack_ns", 'w') as f:
                        f.write("200000000")
                    applied_count += 1
                    logging.info(f"Applied timerslack hack to ModioBackground thread {pid}")
                except Exception as e:
                    logging.warning(f"Failed to set timerslack for PID {pid}: {e}")
        
        return applied_count > 0
    except Exception as e:
        logging.warning(f"Timerslack hack failed: {e}")
        return False

# ============================================================
# HARDCODED MAP DATABASE (from RTVcliWEB.py)
# ============================================================

HARDCODED_MAPS = [
    ("Bab?Scenario=Scenario_Bab_Checkpoint_Insurgents", "Bab Checkpoint Insurgents"),
    ("Bab?Scenario=Scenario_Bab_Checkpoint_Security", "Bab Checkpoint Security"),
    ("Bab?Scenario=Scenario_Bab_Domination", "Bab Domination"),
    ("Bab?Scenario=Scenario_Bab_Firefight_East", "Bab Firefight East"),
    ("Bab?Scenario=Scenario_Bab_Outpost", "Bab Outpost"),
    ("Bab?Scenario=Scenario_Bab_Push_Insurgents", "Bab Push Insurgents"),
    ("Bab?Scenario=Scenario_Bab_Push_Security", "Bab Push Security"),
    ("Citadel?Scenario=Scenario_Citadel_Ambush", "Citadel Ambush"),
    ("Citadel?Scenario=Scenario_Citadel_Checkpoint_Insurgents", "Citadel Checkpoint Insurgents"),
    ("Citadel?Scenario=Scenario_Citadel_Checkpoint_Security", "Citadel Checkpoint Security"),
    ("Citadel?Scenario=Scenario_Citadel_Domination", "Citadel Domination"),
    ("Citadel?Scenario=Scenario_Citadel_Firefight_East", "Citadel Firefight East"),
    ("Citadel?Scenario=Scenario_Citadel_Outpost", "Citadel Outpost"),
    ("Citadel?Scenario=Scenario_Citadel_Push_Insurgents", "Citadel Push Insurgents"),
    ("Citadel?Scenario=Scenario_Citadel_Push_Security", "Citadel Push Security"),
    ("Citadel?Scenario=Scenario_Citadel_Survival", "Citadel Survival"),
    ("Citadel?Scenario=Scenario_Citadel_Defusal", "Citadel Defusal"),
    ("Canyon?Scenario=Scenario_Crossing_Ambush", "Crossing Ambush"),
    ("Canyon?Scenario=Scenario_Crossing_Checkpoint_Insurgents", "Crossing Checkpoint Insurgents"),
    ("Canyon?Scenario=Scenario_Crossing_Checkpoint_Security", "Crossing Checkpoint Security"),
    ("Canyon?Scenario=Scenario_Crossing_Domination", "Crossing Domination"),
    ("Canyon?Scenario=Scenario_Crossing_Firefight_West", "Crossing Firefight West"),
    ("Canyon?Scenario=Scenario_Crossing_Frontline", "Crossing Frontline"),
    ("Canyon?Scenario=Scenario_Crossing_Outpost", "Crossing Outpost"),
    ("Canyon?Scenario=Scenario_Crossing_Push_Insurgents", "Crossing Push Insurgents"),
    ("Canyon?Scenario=Scenario_Crossing_Push_Security", "Crossing Push Security"),
    ("Canyon?Scenario=Scenario_Crossing_Skirmish", "Crossing Skirmish"),
    ("Canyon?Scenario=Scenario_Crossing_Team_Deathmatch", "Crossing Team Deathmatch"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Ambush", "Farmhouse Ambush"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Insurgents", "Farmhouse Checkpoint Insurgents"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security", "Farmhouse Checkpoint Security"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Domination", "Farmhouse Domination"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Firefight_East", "Farmhouse Firefight East"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Firefight_West", "Farmhouse Firefight West"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Frontline", "Farmhouse Frontline"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Push_Insurgents", "Farmhouse Push Insurgents"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Push_Security", "Farmhouse Push Security"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Skirmish", "Farmhouse Skirmish"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Survival", "Farmhouse Survival"),
    ("Farmhouse?Scenario=Scenario_Farmhouse_Team_Deathmatch", "Farmhouse Team Deathmatch"),
    ("Forest?Scenario=Scenario_Forest_Push_Insurgents", "Forest Push Insurgents"),
    ("Forest?Scenario=Scenario_Forest_Push_Security", "Forest Push Security"),
    ("Forest?Scenario=Scenario_Forest_Firefight_East", "Forest Firefight East"),
    ("Forest?Scenario=Scenario_Forest_Firefight_West", "Forest Firefight West"),
    ("Forest?Scenario=Scenario_Forest_Survival", "Forest Survival"),
    ("Forest?Scenario=Scenario_Forest_Ambush", "Forest Ambush"),
    ("Forest?Scenario=Scenario_Forest_FFA", "Forest FFA"),
    ("Forest?Scenario=Scenario_Forest_Defusal", "Forest Defusal"),
    ("Forest?Scenario=Scenario_Forest_TDM", "Forest Team Deathmatch"),
    ("Forest?Scenario=Scenario_Forest_Domination", "Forest Domination"),
    ("Forest?Scenario=Scenario_Forest_Frontline", "Forest Frontline"),
    ("Forest?Scenario=Scenario_Forest_Skirmish", "Forest Skirmish"),
    ("Forest?Scenario=Scenario_Forest_Checkpoint_Insurgents", "Forest Checkpoint Insurgents"),
    ("Forest?Scenario=Scenario_Forest_Checkpoint_Security", "Forest Checkpoint Security"),
    ("Forest?Scenario=Scenario_Forest_Outpost", "Forest Outpost"),
    ("Gap?Scenario=Scenario_Gap_Ambush", "Gap Ambush"),
    ("Gap?Scenario=Scenario_Gap_Checkpoint_Insurgents", "Gap Checkpoint Insurgents"),
    ("Gap?Scenario=Scenario_Gap_Checkpoint_Security", "Gap Checkpoint Security"),
    ("Gap?Scenario=Scenario_Gap_Domination", "Gap Domination"),
    ("Gap?Scenario=Scenario_Gap_Firefight", "Gap Firefight"),
    ("Gap?Scenario=Scenario_Gap_Frontline", "Gap Frontline"),
    ("Gap?Scenario=Scenario_Gap_Outpost", "Gap Outpost"),
    ("Gap?Scenario=Scenario_Gap_Push_Insurgents", "Gap Push Insurgents"),
    ("Gap?Scenario=Scenario_Gap_Push_Security", "Gap Push Security"),
    ("Gap?Scenario=Scenario_Gap_Survival", "Gap Survival"),
    ("Gap?Scenario=Scenario_Gap_Defusal", "Gap Defusal"),
    ("Town?Scenario=Scenario_Hideout_Ambush", "Hideout Ambush"),
    ("Town?Scenario=Scenario_Hideout_Checkpoint_Insurgents", "Hideout Checkpoint Insurgents"),
    ("Town?Scenario=Scenario_Hideout_Checkpoint_Security", "Hideout Checkpoint Security"),
    ("Town?Scenario=Scenario_Hideout_Domination", "Hideout Domination"),
    ("Town?Scenario=Scenario_Hideout_Firefight_East", "Hideout Firefight East"),
    ("Town?Scenario=Scenario_Hideout_Firefight_West", "Hideout Firefight West"),
    ("Town?Scenario=Scenario_Hideout_Frontline", "Hideout Frontline"),
    ("Town?Scenario=Scenario_Hideout_Push_Insurgents", "Hideout Push Insurgents"),
    ("Town?Scenario=Scenario_Hideout_Push_Security", "Hideout Push Security"),
    ("Town?Scenario=Scenario_Hideout_Skirmish", "Hideout Skirmish"),
    ("Town?Scenario=Scenario_Hideout_Survival", "Hideout Survival"),
    ("Town?Scenario=Scenario_Hideout_Team_Deathmatch", "Hideout Team Deathmatch"),
    ("Sinjar?Scenario=Scenario_Hillside_Ambush", "Hillside Ambush"),
    ("Sinjar?Scenario=Scenario_Hillside_Checkpoint_Insurgents", "Hillside Checkpoint Insurgents"),
    ("Sinjar?Scenario=Scenario_Hillside_Checkpoint_Security", "Hillside Checkpoint Security"),
    ("Sinjar?Scenario=Scenario_Hillside_Domination", "Hillside Domination"),
    ("Sinjar?Scenario=Scenario_Hillside_Firefight_East", "Hillside Firefight East"),
    ("Sinjar?Scenario=Scenario_Hillside_Firefight_West", "Hillside Firefight West"),
    ("Sinjar?Scenario=Scenario_Hillside_Frontline", "Hillside Frontline"),
    ("Sinjar?Scenario=Scenario_Hillside_Outpost", "Hillside Outpost"),
    ("Sinjar?Scenario=Scenario_Hillside_Push_Insurgents", "Hillside Push Insurgents"),
    ("Sinjar?Scenario=Scenario_Hillside_Push_Security", "Hillside Push Security"),
    ("Sinjar?Scenario=Scenario_Hillside_Skirmish", "Hillside Skirmish"),
    ("Sinjar?Scenario=Scenario_Hillside_Survival", "Hillside Survival"),
    ("Sinjar?Scenario=Scenario_Hillside_Team_Deathmatch", "Hillside Team Deathmatch"),
    ("LastLight?Scenario=Scenario_LastLight_Push_Security", "LastLight Push Security"),
    ("LastLight?Scenario=Scenario_LastLight_Checkpoint_Insurgents", "LastLight Checkpoint Insurgents"),
    ("LastLight?Scenario=Scenario_LastLight_Checkpoint_Security", "LastLight Checkpoint Security"),
    ("LastLight?Scenario=Scenario_LastLight_Domination", "LastLight Domination"),
    ("LastLight?Scenario=Scenario_LastLight_Firefight", "LastLight Firefight"),
    ("LastLight?Scenario=Scenario_LastLight_Ambush", "LastLight Ambush"),
    ("LastLight?Scenario=Scenario_LastLight_Survival", "LastLight Survival"),
    ("LastLight?Scenario=Scenario_LastLight_Push_Insurgents", "LastLight Push Insurgents"),
    ("LastLight?Scenario=Scenario_LastLight_Outpost", "LastLight Outpost"),
    ("LastLight?Scenario=Scenario_LastLight_Defusal", "LastLight Defusal"),
    ("LastLight?Scenario=Scenario_LastLight_Frontline", "LastLight Frontline"),
    ("LastLight?Scenario=Scenario_LastLight_Team_Deathmatch", "LastLight Team Deathmatch"),
    ("Ministry?Scenario=Scenario_Ministry_Ambush", "Ministry Ambush"),
    ("Ministry?Scenario=Scenario_Ministry_Checkpoint_Insurgents", "Ministry Checkpoint Insurgents"),
    ("Ministry?Scenario=Scenario_Ministry_Checkpoint_Security", "Ministry Checkpoint Security"),
    ("Ministry?Scenario=Scenario_Ministry_Domination", "Ministry Domination"),
    ("Ministry?Scenario=Scenario_Ministry_Firefight_A", "Ministry Firefight"),
    ("Ministry?Scenario=Scenario_Ministry_Skirmish", "Ministry Skirmish"),
    ("Ministry?Scenario=Scenario_Ministry_Team_Deathmatch", "Ministry Team Deathmatch"),
    ("Compound?Scenario=Scenario_Outskirts_Checkpoint_Insurgents", "Outskirts Checkpoint Insurgents"),
    ("Compound?Scenario=Scenario_Outskirts_Checkpoint_Security", "Outskirts Checkpoint Security"),
    ("Compound?Scenario=Scenario_Outskirts_Firefight_East", "Outskirts Firefight East"),
    ("Compound?Scenario=Scenario_Outskirts_Firefight_West", "Outskirts Firefight West"),
    ("Compound?Scenario=Scenario_Outskirts_Frontline", "Outskirts Frontline"),
    ("Compound?Scenario=Scenario_Outskirts_Push_Insurgents", "Outskirts Push Insurgents"),
    ("Compound?Scenario=Scenario_Outskirts_Push_Security", "Outskirts Push Security"),
    ("Compound?Scenario=Scenario_Outskirts_Skirmish", "Outskirts Skirmish"),
    ("Compound?Scenario=Scenario_Outskirts_Team_Deathmatch", "Outskirts Team Deathmatch"),
    ("Compound?Scenario=Scenario_Outskirts_Survival", "Outskirts Survival"),
    ("Compound?Scenario=Scenario_Outskirts_Defusal", "Outskirts Defusal"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Ambush", "PowerPlant Ambush"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Checkpoint_Insurgents", "PowerPlant Checkpoint Insurgents"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Checkpoint_Security", "PowerPlant Checkpoint Security"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Domination", "PowerPlant Domination"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Firefight_East", "PowerPlant Firefight East"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Firefight_West", "PowerPlant Firefight West"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Push_Insurgents", "PowerPlant Push Insurgents"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Push_Security", "PowerPlant Push Security"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Survival", "PowerPlant Survival"),
    ("PowerPlant?Scenario=Scenario_PowerPlant_Frontline", "PowerPlant Frontline"),
    ("Precinct?Scenario=Scenario_Precinct_Ambush", "Precinct Ambush"),
    ("Precinct?Scenario=Scenario_Precinct_Checkpoint_Insurgents", "Precinct Checkpoint Insurgents"),
    ("Precinct?Scenario=Scenario_Precinct_Checkpoint_Security", "Precinct Checkpoint Security"),
    ("Precinct?Scenario=Scenario_Precinct_Firefight_East", "Precinct Firefight East"),
    ("Precinct?Scenario=Scenario_Precinct_Firefight_West", "Precinct Firefight West"),
    ("Precinct?Scenario=Scenario_Precinct_Frontline", "Precinct Frontline"),
    ("Precinct?Scenario=Scenario_Precinct_Push_Insurgents", "Precinct Push Insurgents"),
    ("Precinct?Scenario=Scenario_Precinct_Push_Security", "Precinct Push Security"),
    ("Precinct?Scenario=Scenario_Precinct_Skirmish", "Precinct Skirmish"),
    ("Precinct?Scenario=Scenario_Precinct_Team_Deathmatch", "Precinct Team Deathmatch"),
    ("Precinct?Scenario=Scenario_Precinct_Survival", "Precinct Survival"),
    ("Precinct?Scenario=Scenario_Precinct_Defusal", "Precinct Defusal"),
    ("Prison?Scenario=Scenario_Prison_Push_Security", "Prison Push Security"),
    ("Prison?Scenario=Scenario_Prison_Checkpoint_Insurgents", "Prison Checkpoint Insurgents"),
    ("Prison?Scenario=Scenario_Prison_Checkpoint_Security", "Prison Checkpoint Security"),
    ("Prison?Scenario=Scenario_Prison_Domination", "Prison Domination"),
    ("Prison?Scenario=Scenario_Prison_Firefight", "Prison Firefight"),
    ("Prison?Scenario=Scenario_Prison_Ambush", "Prison Ambush"),
    ("Prison?Scenario=Scenario_Prison_Survival", "Prison Survival"),
    ("Prison?Scenario=Scenario_Prison_Push_Insurgents", "Prison Push Insurgents"),
    ("Prison?Scenario=Scenario_Prison_Defusal", "Prison Defusal"),
    ("Oilfield?Scenario=Scenario_Refinery_Ambush", "Refinery Ambush"),
    ("Oilfield?Scenario=Scenario_Refinery_Checkpoint_Insurgents", "Refinery Checkpoint Insurgents"),
    ("Oilfield?Scenario=Scenario_Refinery_Checkpoint_Security", "Refinery Checkpoint Security"),
    ("Oilfield?Scenario=Scenario_Refinery_Domination", "Refinery Domination"),
    ("Oilfield?Scenario=Scenario_Refinery_Firefight_West", "Refinery Firefight West"),
    ("Oilfield?Scenario=Scenario_Refinery_Frontline", "Refinery Frontline"),
    ("Oilfield?Scenario=Scenario_Refinery_Push_Insurgents", "Refinery Push Insurgents"),
    ("Oilfield?Scenario=Scenario_Refinery_Push_Security", "Refinery Push Security"),
    ("Oilfield?Scenario=Scenario_Refinery_Skirmish", "Refinery Skirmish"),
    ("Oilfield?Scenario=Scenario_Refinery_Survival", "Refinery Survival"),
    ("Mountain?Scenario=Scenario_Summit_Ambush", "Summit Ambush"),
    ("Mountain?Scenario=Scenario_Summit_Checkpoint_Insurgents", "Summit Checkpoint Insurgents"),
    ("Mountain?Scenario=Scenario_Summit_Checkpoint_Security", "Summit Checkpoint Security"),
    ("Mountain?Scenario=Scenario_Summit_Firefight_East", "Summit Firefight East"),
    ("Mountain?Scenario=Scenario_Summit_Firefight_West", "Summit Firefight West"),
    ("Mountain?Scenario=Scenario_Summit_Frontline", "Summit Frontline"),
    ("Mountain?Scenario=Scenario_Summit_Push_Insurgents", "Summit Push Insurgents"),
    ("Mountain?Scenario=Scenario_Summit_Push_Security", "Summit Push Security"),
    ("Mountain?Scenario=Scenario_Summit_Skirmish", "Summit Skirmish"),
    ("Mountain?Scenario=Scenario_Summit_Team_Deathmatch", "Summit Team Deathmatch"),
    ("Mountain?Scenario=Scenario_Summit_Survival", "Summit Survival"),
    ("Tell?Scenario=Scenario_Tell_Ambush", "Tell Ambush"),
    ("Tell?Scenario=Scenario_Tell_Checkpoint_Insurgents", "Tell Checkpoint Insurgents"),
    ("Tell?Scenario=Scenario_Tell_Checkpoint_Security", "Tell Checkpoint Security"),
    ("Tell?Scenario=Scenario_Tell_Domination", "Tell Domination"),
    ("Tell?Scenario=Scenario_Tell_Firefight_East", "Tell Firefight East"),
    ("Tell?Scenario=Scenario_Tell_Firefight_West", "Tell Firefight West"),
    ("Tell?Scenario=Scenario_Tell_Outpost", "Tell Outpost"),
    ("Tell?Scenario=Scenario_Tell_Push_Insurgents", "Tell Push Insurgents"),
    ("Tell?Scenario=Scenario_Tell_Push_Security", "Tell Push Security"),
    ("Tell?Scenario=Scenario_Tell_Survival", "Tell Survival"),
    ("Tell?Scenario=Scenario_Tell_Frontline", "Tell Frontline"),
    ("Buhriz?Scenario=Scenario_Tideway_Checkpoint_Insurgents", "Tideway Checkpoint Insurgents"),
    ("Buhriz?Scenario=Scenario_Tideway_Checkpoint_Security", "Tideway Checkpoint Security"),
    ("Buhriz?Scenario=Scenario_Tideway_Domination", "Tideway Domination"),
    ("Buhriz?Scenario=Scenario_Tideway_Firefight_West", "Tideway Firefight West"),
    ("Buhriz?Scenario=Scenario_Tideway_Frontline", "Tideway Frontline"),
    ("Buhriz?Scenario=Scenario_Tideway_Push_Insurgents", "Tideway Push Insurgents"),
    ("Buhriz?Scenario=Scenario_Tideway_Push_Security", "Tideway Push Security"),
    ("Buhriz?Scenario=Scenario_Tideway_Survival", "Tideway Survival"),
    ("Trainyard?Scenario=Scenario_Trainyard_Push_Security", "Trainyard Push Security"),
    ("Trainyard?Scenario=Scenario_Trainyard_Push_Insurgents", "Trainyard Push Insurgents"),
    ("Trainyard?Scenario=Scenario_Trainyard_Firefight_West", "Trainyard Firefight West"),
    ("Trainyard?Scenario=Scenario_Trainyard_Firefight_East", "Trainyard Firefight East"),
    ("Trainyard?Scenario=Scenario_Trainyard_Domination_West", "Trainyard Domination West"),
    ("Trainyard?Scenario=Scenario_Trainyard_Domination_East", "Trainyard Domination East"),
    ("Trainyard?Scenario=Scenario_Trainyard_Frontline", "Trainyard Frontline"),
    ("Trainyard?Scenario=Scenario_Trainyard_Ambush_East", "Trainyard Ambush East"),
    ("Trainyard?Scenario=Scenario_Trainyard_Ambush_West", "Trainyard Ambush West"),
    ("Trainyard?Scenario=Scenario_Trainyard_Defusal_West", "Trainyard Defusal West"),
    ("Trainyard?Scenario=Scenario_Trainyard_Checkpoint_Security", "Trainyard Checkpoint Security"),
    ("Trainyard?Scenario=Scenario_Trainyard_Checkpoint_Insurgents", "Trainyard Checkpoint Insurgents"),
    ("Trainyard?Scenario=Scenario_Trainyard_Outpost", "Trainyard Outpost"),
    ("Trainyard?Scenario=Scenario_Trainyard_Survival", "Trainyard Survival"),
]

# ============================================================
# STRUCTURED MAP DATA FOR MAPCYCLE EDITOR
# ============================================================

MAP_DATA = {
    "Bab": {
        "display_name": "Bab",
        "scenarios": [
            {"id": "Scenario_Bab_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Bab_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Bab_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Bab_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Bab_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Bab_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Bab_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Bab_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Bab_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Bab_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Crossing": {
        "display_name": "Crossing (Canyon)",
        "scenarios": [
            {"id": "Scenario_Crossing_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Crossing_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Crossing_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Crossing_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Crossing_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Crossing_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Farmhouse": {
        "display_name": "Farmhouse",
        "scenarios": [
            {"id": "Scenario_Farmhouse_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Farmhouse_Range", "name": "Range", "mode": "Other", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Hideout": {
        "display_name": "Hideout (Town)",
        "scenarios": [
            {"id": "Scenario_Hideout_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": True},
            {"id": "Scenario_Hideout_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": True},
            {"id": "Scenario_Hideout_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": True},
            {"id": "Scenario_Hideout_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": True},
            {"id": "Scenario_Hideout_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": True},
            {"id": "Scenario_Hideout_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": True},
        ]
    },
    "Summit": {
        "display_name": "Summit (Mountain)",
        "scenarios": [
            {"id": "Scenario_Summit_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Summit_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Summit_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Summit_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Summit_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Ambush_West", "name": "Ambush West", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Summit_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Refinery": {
        "display_name": "Refinery (Oilfield)",
        "scenarios": [
            {"id": "Scenario_Refinery_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Refinery_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Refinery_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Refinery_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Refinery_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Refinery_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Precinct": {
        "display_name": "Precinct",
        "scenarios": [
            {"id": "Scenario_Precinct_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Precinct_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Precinct_Domination_West", "name": "Domination West", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Domination_East", "name": "Domination East", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Precinct_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Precinct_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Precinct_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Ministry": {
        "display_name": "Ministry",
        "scenarios": [
            {"id": "Scenario_Ministry_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Ministry_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Ministry_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Firefight_A", "name": "Firefight", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Ministry_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Outskirts": {
        "display_name": "Outskirts (Compound)",
        "scenarios": [
            {"id": "Scenario_Outskirts_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Outskirts_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Hillside": {
        "display_name": "Hillside (Sinjar)",
        "scenarios": [
            {"id": "Scenario_Hillside_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Hillside_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Hillside_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Hillside_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Hillside_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Hillside_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "PowerPlant": {
        "display_name": "Power Plant",
        "scenarios": [
            {"id": "Scenario_PowerPlant_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_PowerPlant_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Tell": {
        "display_name": "Tell",
        "scenarios": [
            {"id": "Scenario_Tell_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Tell_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Tell_Domination_East", "name": "Domination East", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Domination_West", "name": "Domination West", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Tell_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Tell_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Ambush_West", "name": "Ambush West", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tell_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Tideway": {
        "display_name": "Tideway (Buhriz)",
        "scenarios": [
            {"id": "Scenario_Tideway_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Tideway_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Tideway_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Tideway_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Tideway_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Tideway_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Trainyard": {
        "display_name": "Trainyard",
        "scenarios": [
            {"id": "Scenario_Trainyard_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Domination_East", "name": "Domination East", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Domination_West", "name": "Domination West", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Ambush_East", "name": "Ambush East", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Ambush_West", "name": "Ambush West", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Defusal_East", "name": "Defusal East", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Trainyard_Defusal_West", "name": "Defusal West", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Forest": {
        "display_name": "Forest",
        "scenarios": [
            {"id": "Scenario_Forest_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Forest_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Forest_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Forest_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Forest_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Forest_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Gap": {
        "display_name": "Gap",
        "scenarios": [
            {"id": "Scenario_Gap_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Gap_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Gap_Domination_East", "name": "Domination East", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Domination_West", "name": "Domination West", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Firefight_East", "name": "Firefight East", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Firefight_West", "name": "Firefight West", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Gap_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Gap_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Gap_TDM", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Prison": {
        "display_name": "Prison",
        "scenarios": [
            {"id": "Scenario_Prison_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Prison_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Prison_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Firefight", "name": "Firefight", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Prison_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Prison_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_FFA", "name": "Free For All", "mode": "FFA", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_TDM", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Prison_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
        ]
    },
    "LastLight": {
        "display_name": "LastLight",
        "scenarios": [
            {"id": "Scenario_LastLight_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_LastLight_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_LastLight_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Firefight", "name": "Firefight", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_LastLight_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_LastLight_Skirmish", "name": "Skirmish", "mode": "Skirmish", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_LastLight_Team_Deathmatch", "name": "Team Deathmatch", "mode": "TDM", "teams": "Both", "supports_lighting": False},
        ]
    },
    "Citadel": {
        "display_name": "Citadel",
        "scenarios": [
            {"id": "Scenario_Citadel_Checkpoint_Insurgents", "name": "Checkpoint Insurgents", "mode": "Checkpoint", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Citadel_Checkpoint_Security", "name": "Checkpoint Security", "mode": "Checkpoint", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Citadel_Domination", "name": "Domination", "mode": "Domination", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Firefight", "name": "Firefight", "mode": "Firefight", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Frontline", "name": "Frontline", "mode": "Frontline", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Outpost", "name": "Outpost", "mode": "Outpost", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Push_Insurgents", "name": "Push Insurgents", "mode": "Push", "teams": "Insurgents", "supports_lighting": False},
            {"id": "Scenario_Citadel_Push_Security", "name": "Push Security", "mode": "Push", "teams": "Security", "supports_lighting": False},
            {"id": "Scenario_Citadel_Survival", "name": "Survival", "mode": "Survival", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Ambush", "name": "Ambush", "mode": "Ambush", "teams": "Both", "supports_lighting": False},
            {"id": "Scenario_Citadel_Defusal", "name": "Defusal", "mode": "Defusal", "teams": "Both", "supports_lighting": False},
        ]
    }
}

# Game mode categories for filtering
GAME_MODES = ["All", "Checkpoint", "Push", "Firefight", "Frontline", "Skirmish", "Survival", "Outpost", "Domination", "TDM", "Ambush", "Defusal", "FFA"]

# Map thumbnail folder - users can place map images here
MAP_PICTURES_DIR = os.path.join(SCRIPT_DIR, "mappictures")

# Map key to thumbnail filename mapping
MAP_THUMBNAIL_NAMES = {
    "Bab": "bab",
    "Crossing": "crossing",
    "Farmhouse": "farmhouse",
    "Hideout": "hideout",
    "Summit": "summit",
    "Refinery": "refinery",
    "Precinct": "precinct",
    "Ministry": "ministry",
    "Outskirts": "outskirts",
    "Hillside": "hillside",
    "PowerPlant": "powerplant",
    "Tell": "tell",
    "Tideway": "tideway",
    "Trainyard": "trainyard",
    "Forest": "forest",
    "Gap": "gap",
    "Prison": "prison",
    "LastLight": "lastlight",
    "Citadel": "citadel",
}

# Map name translations (internal name -> display name)
MAP_TRANSLATIONS = {
    "Crossing": "Canyon",
    "Hideout": "Town",
    "Hillside": "Sinjar",
    "Outskirts": "Compound",
    "Summit": "Mountain",
    "Tideway": "Buhriz",
    "Refinery": "Oilfield",
}

# ============================================================
# SERVER MANAGEMENT CLASS
# ============================================================

class ServerManager:
    """Handles server installation, starting, stopping via shell commands"""
    
    def __init__(self):
        self._server_dir = None
        self._steamcmd_dir = None
        self._presets_file = None
        self.app_id = APP_ID
        self.session_name = SESSION_NAME
        self.multiplexer = MULTIPLEXER
    
    @property
    def server_dir(self):
        if self._server_dir is None:
            self._server_dir = bot.conf.get('server_dir', DEFAULT_SERVER_DIR)
        return self._server_dir
    
    @property
    def steamcmd_dir(self):
        if self._steamcmd_dir is None:
            self._steamcmd_dir = bot.conf.get('steamcmd_dir', DEFAULT_STEAMCMD_DIR)
        return self._steamcmd_dir
    
    @property
    def presets_file(self):
        if self._presets_file is None:
            self._presets_file = bot.conf.get('presets_file', DEFAULT_PRESETS_FILE)
        return self._presets_file
    
    def refresh_paths(self):
        """Refresh paths from config"""
        self._server_dir = None
        self._steamcmd_dir = None
        self._presets_file = None
        
    @property
    def home(self):
        return bot.conf.get('home', HOME)
    
    @property
    def watchdog_pid_file(self):
        return f"{self.home}/.sandstorm_watchdog.pid"
    
    @property
    def last_launched_preset_file(self):
        return f"{self.home}/.sandstorm_last_launched_preset.txt"
    
    @property
    def watchdog_log_file(self):
        return f"{self.home}/sandstorm_watchdog.log"
    
    def is_installed(self):
        binary = f"{self.server_dir}/Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping"
        return os.path.exists(binary)
    
    def is_running(self):
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def install_steamcmd(self):
        """Install SteamCMD"""
        global INSTALLATION_STATUS
        
        if os.path.exists(self.steamcmd_dir):
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["steamcmd"] = {"running": False, "complete": True, "output": "SteamCMD already installed at " + self.steamcmd_dir + "\n", "error": ""}
            return {"success": True, "message": "SteamCMD already installed"}
        
        with INSTALLATION_LOCK:
            INSTALLATION_STATUS["steamcmd"] = {"running": True, "complete": False, "output": "Starting SteamCMD installation...\n", "error": ""}
        
        try:
            os.makedirs(self.steamcmd_dir, exist_ok=True)
            # Download steamcmd - capture output in real-time (removed -q to see progress)
            process = subprocess.Popen(
                f"cd {self.steamcmd_dir} && "
                "wget --progress=bar:force:noscroll https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz 2>&1 && "
                "tar -xf steamcmd_linux.tar.gz && rm steamcmd_linux.tar.gz",
                shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            
            output = ""
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                output += line
                with INSTALLATION_LOCK:
                    INSTALLATION_STATUS["steamcmd"]["output"] += line
            
            process.wait()
            
            with INSTALLATION_LOCK:
                if process.returncode == 0:
                    INSTALLATION_STATUS["steamcmd"]["output"] += "SteamCMD installed successfully!\n"
                    INSTALLATION_STATUS["steamcmd"]["complete"] = True
                    INSTALLATION_STATUS["steamcmd"]["running"] = False
                    return {"success": True, "message": "SteamCMD installed successfully"}
                else:
                    INSTALLATION_STATUS["steamcmd"]["error"] = output
                    INSTALLATION_STATUS["steamcmd"]["complete"] = True
                    INSTALLATION_STATUS["steamcmd"]["running"] = False
                    return {"success": False, "message": f"Failed: {output[-200:]}"}
        except Exception as e:
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["steamcmd"]["error"] = str(e)
                INSTALLATION_STATUS["steamcmd"]["complete"] = True
                INSTALLATION_STATUS["steamcmd"]["running"] = False
            return {"success": False, "message": str(e)}
    
    def install_server(self, validate=True):
        """Download/Install Sandstorm server"""
        global INSTALLATION_STATUS
        
        if not os.path.exists(self.steamcmd_dir):
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["server"] = {"running": False, "complete": True, "output": "SteamCMD not installed. Run installation first.\n", "error": "SteamCMD not found"}
            return {"success": False, "message": "SteamCMD not installed. Run installation first."}
        
        with INSTALLATION_LOCK:
            INSTALLATION_STATUS["server"] = {"running": True, "complete": False, "output": "Starting Sandstorm server installation...\n", "error": ""}
        
        try:
            cmd = f"{self.steamcmd_dir}/steamcmd.sh +force_install_dir {self.server_dir} +login anonymous +app_update {self.app_id}"
            if validate:
                cmd += " validate"
            cmd += " +quit"
            
            # Run with real-time output capture
            process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            
            output = ""
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                output += line
                with INSTALLATION_LOCK:
                    INSTALLATION_STATUS["server"]["output"] += line
            
            process.wait()
            
            with INSTALLATION_LOCK:
                if "Success" in output or "already up to date" in output.lower():
                    INSTALLATION_STATUS["server"]["output"] += "\nServer installed/updated successfully!\n"
                    INSTALLATION_STATUS["server"]["complete"] = True
                    INSTALLATION_STATUS["server"]["running"] = False
                    # Create default presets file if not exists
                    if not os.path.exists(PRESETS_FILE):
                        self.create_presets_file()
                    return {"success": True, "message": "Server installed/updated successfully"}
                else:
                    error_msg = output[-500:] if len(output) > 500 else output
                    INSTALLATION_STATUS["server"]["error"] = error_msg
                    INSTALLATION_STATUS["server"]["complete"] = True
                    INSTALLATION_STATUS["server"]["running"] = False
                    return {"success": False, "message": f"Installation failed: {error_msg}"}
        except subprocess.TimeoutExpired:
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["server"]["error"] = "Installation timed out"
                INSTALLATION_STATUS["server"]["complete"] = True
                INSTALLATION_STATUS["server"]["running"] = False
            return {"success": False, "message": "Installation timed out"}
        except Exception as e:
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["server"]["error"] = str(e)
                INSTALLATION_STATUS["server"]["complete"] = True
                INSTALLATION_STATUS["server"]["running"] = False
            return {"success": False, "message": str(e)}
    
    def create_presets_file(self):
        """Create default presets configuration file"""
        content = '''# --- Insurgency: Sandstorm Server Presets ---
# Each preset is a Python list of arguments

DefaultCoop_args = [
    "Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security?MaxPlayers=8",
    "-Port=27102",
    "-QueryPort=27131",
    "-log",
    "-hostname=My First Coop Server",
    "-MapCycle=MapCycle.txt",
    "-AdminList=Admins.txt",
]

DefaultPvP_args = [
    "Precinct?Scenario=Scenario_Precinct_Push_Security?MaxPlayers=28",
    "-Port=27102",
    "-QueryPort=27131",
    "-log",
    "-hostname=My First PvP Server",
    "-MapCycle=MapCycle.txt",
    "-AdminList=Admins.txt",
]
'''
        with open(PRESETS_FILE, 'w') as f:
            f.write(content)
        return True
    
    def load_presets(self):
        """Load presets from file - handles both Python list and Bash array formats"""
        presets = {}
        
        # Try possible locations (both bash and Python format)
        possible_files = [
            self.presets_file,
            os.path.join(os.path.expanduser('~'), 'sandstorm_presets.conf'),
            'sandstorm_presets.conf',
            'PYthonsandstorm_presets.conf',
            os.path.join(SCRIPT_DIR, 'PYthonsandstorm_presets.conf'),
            os.path.join(SCRIPT_DIR, '6', 'PYthonsandstorm_presets.conf'),
        ]
        
        preset_file = None
        for f in possible_files:
            if os.path.exists(f):
                preset_file = f
                break
        
        if not preset_file:
            return presets
        
        try:
            with open(preset_file, 'r') as f:
                content = f.read()
            
            # Method 1: Python list format
            pattern = r'^(\w+)_args\s*=\s*\[(.*?)\]'
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                name = match.group(1)
                args_str = match.group(2)
                
                args = []
                for line in args_str.split('\n'):
                    line = line.strip().strip(',').strip('"').strip("'")
                    if line:
                        line = line.replace('\\?', '?').replace('\\=', '=').replace('\\ ', ' ')
                        args.append(line)
                
                presets[name] = args
            
            # Method 2: Bash array format PRESET_args=(
            bash_pattern = r'(\w+)_args\s*=\s*\(\s*\n(.*?)\n\s*\)'
            for match in re.finditer(bash_pattern, content, re.MULTILINE | re.DOTALL):
                name = match.group(1)
                args_block = match.group(2)
                
                args = []
                for line in args_block.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        line = line.rstrip(')').strip()
                        line = line.strip('"').strip("'")
                        line = line.replace('\\?', '?').replace('\\=', '=').replace('\\ ', ' ').replace('\\,', ',')
                        if line:
                            args.append(line)
                
                presets[name] = args
                
        except Exception as e:
            print(f"Error loading presets: {e}")
        
        return presets
    
    def start_server(self, preset_name):
        """Start server with a preset"""
        if self.is_running():
            return {"success": False, "message": "Server is already running"}
        
        presets = self.load_presets()
        if preset_name not in presets:
            return {"success": False, "message": f"Preset '{preset_name}' not found"}
        
        args = presets[preset_name]
        server_binary = f"{self.server_dir}/Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping"
        
        if not os.path.exists(server_binary):
            return {"success": False, "message": "Server binary not found. Install server first."}
        
        try:
            # Build command
            cmd_parts = [server_binary] + args
            cmd_str = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)
            
            # Start in tmux
            subprocess.run(
                f"tmux new-session -d -s {self.session_name} {cmd_str}",
                shell=True, check=True
            )
            
            time.sleep(3)
            if self.is_running():
                # Apply timerslack hack to reduce ModioBackground CPU usage
                system_user = self.conf.get('timerslack_system_user', '')
                hack_enabled = self.conf.get('timerslack_enabled', True)
                if system_user and hack_enabled:
                    apply_timerslack_hack(system_user, hack_enabled)
                return {"success": True, "message": f"Server started with preset '{preset_name}'"}
            else:
                return {"success": False, "message": "Server failed to start"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def stop_server(self):
        """Stop the running server"""
        if not self.is_running():
            return {"success": False, "message": "Server is not running"}
        
        try:
            subprocess.run(f"tmux kill-session -t {self.session_name}", shell=True, check=True)
            time.sleep(1)
            return {"success": True, "message": "Server stopped"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_status(self):
        """Get server status"""
        running = self.is_running()
        installed = self.is_installed()
        
        # Get watchdog status - check both the PID file and if the watchdog thread is alive
        watchdog_active = False
        pid_file = self.watchdog_pid_file
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    watchdog_active = os.path.exists("/proc/" + str(pid))
                    if not watchdog_active:
                        # Clean up stale PID file
                        try:
                            os.remove(pid_file)
                        except:
                            pass
            except:
                pass
        
        # Also check if the watchdog thread is running (in-process watchdog)
        if not watchdog_active:
            import threading
            for t in threading.enumerate():
                if 'watchdog' in t.name.lower() or (hasattr(t, '_target') and t._target and 'watchdog' in str(t._target).lower()):
                    watchdog_active = True
                    break
        
        return {
            "running": running,
            "installed": installed,
            "watchdog_active": watchdog_active,
            "session_name": self.session_name,
            "server_dir": self.server_dir
        }
    
    def get_console_output(self):
        """Get last lines from server console"""
        if not self.is_running():
            return "Server is not running"
        
        try:
            result = subprocess.run(
                f"tmux capture-pane -t {self.session_name} -p | tail -50",
                shell=True, capture_output=True, text=True
            )
            return result.stdout if result.stdout else "No output"
        except Exception as e:
            return str(e)
    
    def start_watchdog(self, preset_name):
        """Start server with watchdog monitoring"""
        if self.is_running():
            return {"success": False, "message": "Server already running"}
        
        # Save the preset to use
        with open(LAST_LAUNCHED_PRESET_FILE, 'w') as f:
            f.write(preset_name)
        
        # Start the watchdog thread
        def watchdog_loop():
            while True:
                if not self.is_running():
                    logging.info("Watchdog: Server not running, starting...")
                    result = self.start_server(preset_name)
                    logging.info(f"Watchdog: {result}")
                    time.sleep(WATCHDOG_CHECK_INTERVAL + 10)
                else:
                    time.sleep(WATCHDOG_CHECK_INTERVAL)
        
        threading.Thread(target=watchdog_loop, daemon=True, name="sandstorm_watchdog").start()
        
        # Initial start
        result = self.start_server(preset_name)
        if result["success"]:
            # Save watchdog PID
            with open(WATCHDOG_PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
        
        return result
    
    def stop_watchdog(self):
        """Stop watchdog and server"""
        try:
            if os.path.exists(WATCHDOG_PID_FILE):
                os.remove(WATCHDOG_PID_FILE)
        except:
            pass
        
        if self.is_running():
            return self.stop_server()
        return {"success": True, "message": "Watchdog stopped"}


# ============================================================
# SOURCE QUERY MODULE (A2S)
# ============================================================

class SourceQuery:
    def __init__(self, addr, port, timeout=2.0):
        self.ip = addr
        self.port = int(port)
        self.timeout = timeout
        self.sock = None

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def connect(self):
        self.disconnect()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))

    def get_info(self):
        A2S_INFO = b'\xFF\xFF\xFF\xFFTSource Engine Query\x00'
        if not self.sock: 
            self.connect()
        
        try:
            self.sock.send(A2S_INFO)
            start = time.time()
            data = self.sock.recv(4096)
            end = time.time()
            ping = int((end - start) * 1000)
            
            data = data[4:]
            header = data[0]
            data = data[1:]
            
            res = {'Ping': ping}
            
            def get_byte(d): return d[0], d[1:]
            def get_short(d): return struct.unpack('<h', d[0:2])[0], d[2:]
            def get_string(d):
                s = b""
                while d[0] != 0:
                    s += bytes([d[0]])
                    d = d[1:]
                return s.decode('utf-8', 'ignore'), d[1:]

            if header == 0x49:
                res['Protocol'], data = get_byte(data)
                res['Hostname'], data = get_string(data)
                res['Map'], data = get_string(data)
                return res
        except Exception:
            pass
        return None


# ============================================================
# RCON CLIENT
# ============================================================

class RCONClient:
    def __init__(self, ip, port, password):
        self.ip = ip
        self.port = int(port)
        self.password = password
        self.lock = threading.Lock()
    
    def send(self, command):
        with self.lock:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3)
                    sock.connect((self.ip, self.port))
                    sock.send(self._pack(3, self.password))
                    if not self._receive(sock): return "Auth Failed"
                    sock.send(self._pack(2, command))
                    response = self._receive(sock)
                    if response: return response[2].decode('utf-8', errors='ignore')
                    return ""
            except Exception as e: return f"Error: {e}"
    
    def _pack(self, packet_type, body):
        body_encoded = body.encode('utf-8')
        size = len(body_encoded) + 10
        return (size.to_bytes(4, 'little') + int(0).to_bytes(4, 'little') + packet_type.to_bytes(4, 'little') + body_encoded + b'\x00\x00')
    
    def _receive(self, sock):
        try:
            raw_size = sock.recv(4)
            if not raw_size: return None
            size = int.from_bytes(raw_size, 'little')
            if size < 10 or size > 8192: return None
            packet = sock.recv(size)
            if len(packet) < size: return None
            return (int.from_bytes(packet[:4], 'little'), int.from_bytes(packet[4:8], 'little'), packet[8:-2])
        except: return None


# ============================================================
# STEAM RESOLVER
# ============================================================

class SteamResolver:
    def __init__(self, api_key):
        self.api_key = api_key
        self.cache = {}
        self.base_url = "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        self.default_avatar = "https://avatars.akamai.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_medium.jpg"
    
    def _fetch(self, steam_id):
        if not self.api_key or len(str(steam_id)) < 17: return None
        try:
            params = {"key": self.api_key, "steamids": steam_id}
            resp = requests.get(self.base_url, params=params, timeout=1)
            if resp.status_code == 200:
                data = resp.json().get('response', {}).get('players', [])
                if data:
                    self.cache[steam_id] = {
                        'name': data[0].get('personaname', steam_id),
                        'avatar': data[0].get('avatarmedium', self.default_avatar)
                    }
                    return self.cache[steam_id]
        except: pass
        return None
    
    def get_data(self, steam_id):
        if steam_id in self.cache: return self.cache[steam_id]
        res = self._fetch(steam_id)
        return res if res else {'name': steam_id, 'avatar': self.default_avatar}
    
    def get_name(self, steam_id): return self.get_data(steam_id)['name']
    def get_avatar(self, steam_id): return self.get_data(steam_id)['avatar']


# ============================================================
# MAIN BOT CLASS
# ============================================================

class SandstormBot:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.start_time = datetime.now()
        self.reload_config()
        
        self.players_db = {"players": {}}
        self.rtv_votes = set()
        self.rtv_filter = None
        self.rtv_filter_lighting = None
        self.map_pool = []
        
        self.live_state_lock = threading.Lock()
        self.live_players = []
        self.live_player_count = 0
        self.live_chat_buffer = []
        
        self.live_server_details = {"name": "Loading...", "map": "Loading...", "ping": 0}
        
        self.rcon = RCONClient(self.conf['rcon']['ip'], self.conf['rcon']['port'], self.conf['rcon']['password'])
        q_port = self.conf.get('query_port', int(self.conf['rcon']['port']) + 1)
        self.query_client = SourceQuery(self.conf['rcon']['ip'], q_port)
        
        self.steam = SteamResolver(self.conf.get("steam_api_key"))
        self.server_manager = ServerManager()
        
        self.load_data()
        self.load_mapcycle()
    
    def reload_config(self):
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
        
        with open(self.config_file, 'r') as f:
            self.conf = json.load(f)
        
        self.log_path = self.conf.get("log_file_path")
        self.data_path = self.conf.get("data_file_path", "player_data.json")
        self.rtv_thresh = float(self.conf.get("rtv_threshold_percent", 0.6))
        self.min_players = int(self.conf.get("rtv_min_players", 1))
        self.map_mode = int(self.conf.get("map_source_mode", 0))
        
        # Reload map cycle when config is reloaded
        self.load_mapcycle()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.conf, f, indent=2)
        self.reload_config()
        self.rcon = RCONClient(self.conf['rcon']['ip'], self.conf['rcon']['port'], self.conf['rcon']['password'])
        self.query_client = SourceQuery(self.conf['rcon']['ip'], self.conf['query_port'])
        self.steam.api_key = self.conf.get("steam_api_key")
        self.load_mapcycle()
    
    def load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f:
                    self.players_db = json.load(f)
            except:
                pass
    
    def save_data(self):
        def _save():
            try:
                with open(self.data_path, 'w') as f:
                    json.dump(self.players_db, f, indent=2)
            except:
                pass
        threading.Thread(target=_save, daemon=True).start()
    
    def inject_chat(self, name, message):
        readable_ts = datetime.now().strftime("%H:%M:%S")
        with self.live_state_lock:
            self.live_chat_buffer.append({
                "timestamp": readable_ts,
                "name": name,
                "message": message
            })
            if len(self.live_chat_buffer) > 20:
                self.live_chat_buffer.pop(0)
    
    def load_mapcycle(self):
        self.map_pool = []
        
        if self.map_mode == 1:
            self.map_pool = [m[0] for m in HARDCODED_MAPS]
            return
        
        map_translation = {
            "Crossing": "Canyon",
            "Hideout": "Town",
            "Hillside": "Sinjar",
            "Outskirts": "Compound",
            "Summit": "Mountain",
            "Tideway": "Buhriz",
            "Refinery": "Oilfield",
        }
        
        raw_paths = self.conf.get("mapcycle_file_path", "").split(';')
        for path in raw_paths:
            path = path.strip()
            if not os.path.exists(path):
                continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith(("//", "#")):
                            continue
                        
                        if "?Scenario" in line:
                            self.map_pool.append(line)
                            continue
                        
                        scen_match = re.search(r'Scenario="([^"]+)"', line, re.IGNORECASE)
                        if scen_match:
                            scenario_name = scen_match.group(1)
                            lighting = "Day"
                            light_match = re.search(r'Lighting="([^"]+)"', line, re.IGNORECASE)
                            if light_match:
                                lighting = light_match.group(1)
                            
                            parts = scenario_name.split('_')
                            if len(parts) > 1:
                                map_key = parts[1]
                                map_file = map_translation.get(map_key, map_key)
                                full_string = f"{map_file}?Scenario={scenario_name}?Lighting={lighting}"
                                self.map_pool.append(full_string)
                        else:
                            # Handle simple format: Scenario_Refinery_Push_Security
                            simple_match = re.search(r'^(Scenario_\w+)', line)
                            if simple_match:
                                scenario_name = simple_match.group(1)
                                parts = scenario_name.split('_')
                                if len(parts) > 1:
                                    map_key = parts[1]
                                    map_file = map_translation.get(map_key, map_key)
                                    full_string = f"{map_file}?Scenario={scenario_name}?Lighting=Day"
                                    self.map_pool.append(full_string)
            except Exception as e:
                print(f"Error parsing map file {path}: {e}")
        
        random.shuffle(self.map_pool)
    
    def background_poller(self):
        rcon_timer = 0
        while True:
            # Fast polling (A2S Query)
            try:
                info = self.query_client.get_info()
                if info:
                    with self.live_state_lock:
                        self.live_server_details = {
                            "name": info['Hostname'],
                            "map": info['Map'],
                            "ping": info['Ping']
                        }
            except Exception:
                pass
            
            # RCON polling every 4 seconds
            if rcon_timer >= 2:
                try:
                    resp = self.rcon.send("listplayers")
                    if resp:
                        count = len(re.findall(r'SteamNWI:\d+', resp))
                        
                        new_players = []
                        matches = re.findall(r'\d+\s*\|\s*([^|]+?)\s*\|\s*(SteamNWI:\d+)', resp)
                        for name, netid in matches:
                            name = name.strip()
                            netid = netid.strip()
                            if "INVALID" not in netid:
                                raw_id = netid.replace('SteamNWI:', '')
                                s_data = self.steam.get_data(raw_id)
                                new_players.append({'name': name, 'netid': netid, 'avatar': s_data['avatar']})
                        
                        with self.live_state_lock:
                            self.live_players = new_players
                            self.live_player_count = count
                except:
                    pass
                rcon_timer = 0
            
            rcon_timer += 1
            time.sleep(2)
    
    def process_chat(self, name, sid, msg):
        readable_ts = datetime.now().strftime("%H:%M:%S")
        if sid not in self.players_db['players']:
            self.players_db['players'][sid] = {"chat_history": []}
        self.players_db['players'][sid]['chat_history'].append({"timestamp": readable_ts, "message": msg})
        if len(self.players_db['players'][sid]['chat_history']) > 50:
            self.players_db['players'][sid]['chat_history'].pop(0)
        self.save_data()
        
        with self.live_state_lock:
            self.live_chat_buffer.append({"timestamp": readable_ts, "name": name, "message": msg})
            if len(self.live_chat_buffer) > 20:
                self.live_chat_buffer.pop(0)
        
        if msg.startswith("!"):
            parts = msg.split()
            cmd = parts[0].lower()
            if cmd == "!rtv":
                self.handle_rtv(sid, name, parts[1:])
            elif cmd == "!help":
                self.rcon.send("say Commands: !rtv [map] [day/night]")
    
    def handle_rtv(self, steam_id, name, args):
        if steam_id in self.rtv_votes:
            return
        
        self.rtv_votes.add(steam_id)
        search_terms = []
        lighting_request = None
        
        for arg in args:
            low = arg.lower()
            if low == 'night':
                lighting_request = 'Night'
            elif low == 'day':
                lighting_request = 'Day'
            else:
                search_terms.append(low)
        
        nom_text = ""
        if search_terms and not self.rtv_filter:
            matches = [m for m in self.map_pool if all(term in m.lower() for term in search_terms)]
            if matches:
                self.rtv_filter = search_terms
                nom_text = f" (Nominated: {' '.join(search_terms)})"
        
        if lighting_request:
            nom_text += f" [{lighting_request}]"
            self.rtv_filter_lighting = lighting_request
        elif not getattr(self, 'rtv_filter_lighting', None):
            self.rtv_filter_lighting = None
        
        with self.live_state_lock:
            p_count = self.live_player_count
        
        base_count = max(p_count, len(self.rtv_votes), self.min_players)
        req = math.ceil(base_count * self.rtv_thresh)
        self.rcon.send(f"say {name} voted RTV! ({len(self.rtv_votes)}/{req}){nom_text}")
        
        if len(self.rtv_votes) >= req:
            self.change_map()
    
    def change_map(self, specific_map=None):
        target = specific_map
        if not target:
            pool = self.map_pool
            if self.rtv_filter:
                if isinstance(self.rtv_filter, list):
                    f = [m for m in pool if all(term in m.lower() for term in self.rtv_filter)]
                else:
                    f = [m for m in pool if self.rtv_filter.lower() in m.lower()]
                if f:
                    pool = f
            
            if not pool:
                self.rcon.send("say Error: No maps found.")
                return
            
            target = random.choice(pool)
        
        lighting_pref = getattr(self, 'rtv_filter_lighting', None)
        if lighting_pref == 'Night':
            if "?Lighting=" not in target:
                target += "?Lighting=Night"
        elif lighting_pref == 'Day':
            if "?Lighting=" in target:
                target = target.split('?Lighting=')[0]
            target += "?Lighting=Day"
        
        display_name = target.split('?')[0]
        if "?Lighting=Night" in target:
            display_name += " (Night)"
        
        self.rcon.send(f"say RTV Passed! Changing to {display_name} in 5s...")
        self.rtv_votes.clear()
        self.rtv_filter = None
        self.rtv_filter_lighting = None
        
        def _exec():
            time.sleep(5)
            self.rcon.send(f"travel {target}")
        threading.Thread(target=_exec, daemon=True).start()
    
    def run_log_loop(self):
        if not os.path.exists(self.log_path):
            return
        
        f = open(self.log_path, 'r', encoding='utf-8', errors='replace')
        f.seek(0, 2)
        cur_ino = os.fstat(f.fileno()).st_ino
        
        while True:
            line = f.readline()
            
            if not line:
                time.sleep(1)
                
                try:
                    stat_data = os.stat(self.log_path)
                    if stat_data.st_ino != cur_ino:
                        print("Log file rotated (Inode change). Re-opening...")
                        f.close()
                        f = open(self.log_path, 'r', encoding='utf-8', errors='replace')
                        cur_ino = os.fstat(f.fileno()).st_ino
                        continue
                    
                    if f.tell() > stat_data.st_size:
                        print("Log file truncated. Resetting to start...")
                        f.seek(0)
                        continue
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logging.error(f"Error checking log rotation: {e}")
                
                continue
            
            # Handle both "Global Chat:" and "Team Chat:" formats
            m = re.search(r'LogChat:\s*Display:\s*(.+?)\((\d+)\).*?\s+(Global|Team)\s+Chat:\s*(.*)', line)
            if m:
                print(f"[CHAT DETECTED] {m.group(1)}: {m.group(4)}")
                self.process_chat(m.group(1), m.group(2), m.group(4).strip())


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
bot = SandstormBot()

# HTML Templates
HTML_BASE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sandstorm Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #1a1d20; color: #e9ecef; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        .card { border: 1px solid #343a40; background-color: #212529; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .card-header { background-color: #2c3035; border-bottom: 1px solid #343a40; font-weight: 600; }
        .stat-card h3 { font-weight: 700; margin: 0; }
        .stat-card small { text-transform: uppercase; letter-spacing: 1px; font-size: 0.7rem; opacity: 0.8; }
        #liveChatBox { height: 300px; overflow-y: auto; background-color: #000; border: 1px solid #495057; padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
        .chat-line { margin-bottom: 4px; line-height: 1.4; }
        .chat-time { color: #6c757d; margin-right: 8px; font-size: 0.75rem; }
        .chat-name { color: #0dcaf0; font-weight: bold; }
        .chat-msg { color: #fff; }
        .player-avatar { width: 28px; height: 28px; border-radius: 50%; margin-right: 8px; border: 2px solid #495057; object-fit: cover; }
        .table-custom td { vertical-align: middle; padding: 0.5rem; }
        .nav-link { cursor: pointer; }
        .server-status { padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        .status-running { background-color: #198754; }
        .status-stopped { background-color: #dc3545; }
        .console-output { background-color: #000; color: #0f0; font-family: 'JetBrains Mono', monospace; padding: 10px; height: 300px; overflow-y: auto; white-space: pre-wrap; font-size: 0.75rem; }
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark border-bottom border-secondary mb-4">
  <div class="container-fluid">
    <a class="navbar-brand fw-bold" href="/">SANDSTORM<span class="text-primary">MANAGER</span></a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav">
        <li class="nav-item"><a class="nav-link" href="/"><i class="bi bi-speedometer2"></i> Dashboard</a></li>
        <li class="nav-item"><a class="nav-link" href="/server"><i class="bi bi-hdd-stack"></i> Server</a></li>
        <li class="nav-item"><a class="nav-link" href="/mapcycle"><i class="bi bi-shuffle"></i> MapCycle</a></li>
        <li class="nav-item"><a class="nav-link" href="/maps"><i class="bi bi-map"></i> Maps</a></li>
        <li class="nav-item"><a class="nav-link" href="/bans"><i class="bi bi-shield-slash"></i> Bans</a></li>
        <li class="nav-item"><a class="nav-link" href="/settings"><i class="bi bi-gear"></i> Settings</a></li>
      </ul>
    </div>
  </div>
</nav>
<div class="container-fluid px-4">
    <!-- CONTENT_PLACEHOLDER -->
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

DASHBOARD_CONTENT = """
<div class="row mb-4">
    <div class="col-12 mb-3">
        <div class="card bg-dark border-secondary">
            <div class="card-body d-flex justify-content-between align-items-center py-2">
                <div>
                    <h5 class="mb-0 text-white" id="srv-name">Connecting...</h5>
                    <small class="text-muted" id="srv-map">Waiting for query...</small>
                </div>
                <div class="text-end">
                    <span class="badge bg-success" id="srv-ping">0ms</span>
                </div>
            </div>
        </div>
    </div>

    <div class="col-md-3">
        <div class="card stat-card text-white bg-primary bg-gradient h-100">
            <div class="card-body text-center d-flex flex-column justify-content-center">
                <h3 id="stat-players">-</h3> <small>Active Players</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card text-white bg-success bg-gradient h-100">
            <div class="card-body text-center d-flex flex-column justify-content-center">
                <h3 id="stat-votes">-</h3> <small>RTV Votes</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card text-white bg-secondary bg-gradient h-100">
            <div class="card-body text-center d-flex flex-column justify-content-center">
                <h3 id="stat-uptime">-</h3> <small>Uptime</small>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card bg-dark border-danger h-100">
            <div class="card-body d-flex align-items-center justify-content-center">
                <a href="/force_rtv" class="btn btn-outline-danger fw-bold w-100 h-100 d-flex align-items-center justify-content-center">
                    FORCE RANDOM ROTATION
                </a>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-lg-7">
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-people-fill"></i> Active Players</span>
                <span class="badge bg-primary" id="player-badge">0</span>
            </div>
            <div class="card-body p-0 table-responsive" style="max-height: 400px; overflow-y: auto;">
                <table class="table table-dark table-hover mb-0 table-custom">
                    <thead><tr><th>Player</th><th>NetID</th><th>Actions</th></tr></thead>
                    <tbody id="player-table-body">
                        <tr><td colspan="3" class="text-center text-muted py-3">Loading live data...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header">Live Server Chat</div>
            <div class="card-body p-0">
                <div id="liveChatBox"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">Quick RCON</div>
            <div class="card-body">
                <form id="rconForm" class="d-flex gap-2 mb-2">
                    <input type="text" id="rconCmd" class="form-control font-monospace" placeholder="say Hello...">
                    <button type="submit" class="btn btn-warning">Send</button>
                </form>
                <div id="rconResponse" class="alert alert-secondary d-none font-monospace p-2 mb-0" style="white-space: pre-wrap; font-size: 0.8rem;"></div>
            </div>
        </div>
    </div>

    <div class="col-lg-5">
        <div class="card mb-3 border-info">
            <div class="card-header bg-info text-dark">Direct Travel (Hardcoded)</div>
            <div class="card-body">
                <form action="/travel" method="post">
                    <div class="mb-2">
                        <select name="map_name" class="form-select form-select-sm">
                            <option value="" disabled selected>Select a map...</option>
                            {% for code, name in all_maps %}
                            <option value="{{ code }}">{{ name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" name="night_mode" id="nightModeSwitch">
                            <label class="form-check-label" for="nightModeSwitch">Night Mode</label>
                        </div>
                        <button type="submit" class="btn btn-primary btn-sm">Travel Now</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- RTV Quick Controls -->
        <div class="card mb-3 border-secondary">
            <div class="card-header bg-dark py-2 d-flex justify-content-between align-items-center">
                <span><i class="bi bi-sliders"></i> RTV Settings</span>
                <button class="btn btn-sm btn-outline-secondary" id="rtvSettingsToggle" onclick="document.getElementById('rtvSettingsBody').classList.toggle('d-none')"><i class="bi bi-chevron-down"></i></button>
            </div>
            <div class="card-body py-2 d-none" id="rtvSettingsBody">
                <form action="/api/rtv_settings" method="post" id="rtvSettingsForm" class="row g-2 align-items-end">
                    <div class="col-md-4">
                        <label class="form-label small mb-1">RTV Threshold (0-1)</label>
                        <input type="number" step="0.05" min="0" max="1" name="rtv_threshold_percent" id="rtvThreshold" class="form-control form-control-sm" value="{{ rtv_thresh }}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small mb-1">Min Players</label>
                        <input type="number" min="1" name="rtv_min_players" id="rtvMinPlayers" class="form-control form-control-sm" value="{{ rtv_min_players }}">
                    </div>
                    <div class="col-md-4">
                        <button type="submit" class="btn btn-primary btn-sm w-100">Save</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Active MapCycle -->
        <div class="card" style="height: 520px; display:flex; flex-direction:column;">
            <div class="card-header d-flex justify-content-between align-items-center py-2">
                <div>
                    <i class="bi bi-list-ol"></i> Active RTV MapCycle
                    <span class="badge bg-secondary ms-1">{{ maps|length }}</span>
                </div>
                <div class="d-flex gap-1">
                    <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="modal" data-bs-target="#selectMapcycleModal"><i class="bi bi-folder2-open"></i> Switch</button>
                    <a href="/mapcycle" class="btn btn-info btn-sm"><i class="bi bi-pencil"></i> Edit</a>
                </div>
            </div>
            <div class="p-2 border-bottom border-secondary bg-dark">
                <input type="text" id="mapSearch" class="form-control form-control-sm" placeholder="Filter..." onkeyup="filterMaps()">
            </div>
            <div style="overflow-y: auto; flex: 1;">
                <div id="mapList">
                    {% for map in maps %}
                    {% set parts = map.split('?') %}
                    {% set scenario = '' %}
                    {% set lighting = 'Day' %}
                    {% for p in parts %}
                        {% if p.startswith('Scenario=') %}{% set scenario = p[9:] %}{% endif %}
                        {% if p.startswith('Lighting=') %}{% set lighting = p[9:] %}{% endif %}
                    {% endfor %}
                    <div class="d-flex align-items-center gap-2 px-2 py-1 border-bottom border-secondary" style="font-size:0.8rem;" data-search="{{ map }}">
                        <span class="badge" style="background:{% if lighting == 'Night' %}#0d1b2a;color:#7eb8f7;border:1px solid #1a3a5c{% else %}#ffc10722;color:#ffc107;border:1px solid #ffc10744{% endif %};font-size:0.6rem;min-width:36px;">
                            {% if lighting == 'Night' %}<i class="bi bi-moon-stars-fill"></i>{% else %}<i class="bi bi-sun-fill"></i>{% endif %}
                        </span>
                        <div class="flex-grow-1 text-truncate font-monospace" style="font-size:0.72rem;">{{ fmt(map) }}</div>
                        <form action="/travel" method="post" class="flex-shrink-0">
                            <input type="hidden" name="map_name" value="{{ map }}">
                            <button type="submit" class="btn btn-primary btn-sm py-0 px-2" style="font-size:0.65rem;">▶</button>
                        </form>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Select MapCycle Modal -->
<div class="modal fade" id="selectMapcycleModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-folder2-open"></i> Switch MapCycle</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p class="text-muted small">Select a mapcycle file to use as the active rotation. This updates the config and reloads the pool.</p>
                <div id="dashMapcycleFiles">
                    <div class="text-muted text-center py-2">Loading...</div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function updateDashboard() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('srv-name').innerText = data.server_name;
            document.getElementById('srv-map').innerText = "Current Map: " + data.current_map;
            document.getElementById('srv-ping').innerText = data.server_ping + "ms";

            document.getElementById('stat-players').innerText = data.player_count;
            document.getElementById('stat-votes').innerText = `${data.rtv_current} / ${data.rtv_req}`;
            document.getElementById('stat-uptime').innerText = data.uptime;
            document.getElementById('player-badge').innerText = data.player_count;

            const tbody = document.getElementById('player-table-body');
            if (data.players.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3">No players online</td></tr>';
            } else {
                let html = '';
                data.players.forEach(p => {
                    html += `<tr>
                        <td class="fw-bold"><img src="${p.avatar}" class="player-avatar" alt="?">${p.name}</td>
                        <td class="font-monospace text-muted" style="font-size: 0.8rem;">${p.netid}</td>
                        <td>
                            <div class="btn-group">
                                <form action="/kick" method="post" style="display:inline;">
                                    <input type="hidden" name="netid" value="${p.netid}">
                                    <button class="btn btn-warning btn-xs py-0" style="font-size: 0.7rem;" onclick="return confirm('Kick?')">Kick</button>
                                </form>
                                <form action="/ban" method="post" style="display:inline; margin-left: 2px;">
                                    <input type="hidden" name="netid" value="${p.netid}">
                                    <input type="hidden" name="name" value="${p.name}">
                                    <button class="btn btn-danger btn-xs py-0" style="font-size: 0.7rem;" onclick="return confirm('Ban?')">Ban</button>
                                </form>
                            </div>
                        </td>
                    </tr>`;
                });
                tbody.innerHTML = html;
            }

            const chatBox = document.getElementById('liveChatBox');
            if (data.chat_log.length > 0) {
                chatBox.innerHTML = '';
                data.chat_log.forEach(c => {
                    chatBox.innerHTML += `<div class="chat-line"><span class="chat-time">[${c.timestamp}]</span> <span class="chat-name">${c.name}:</span> <span class="chat-msg">${c.message}</span></div>`;
                });
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        })
        .catch(err => console.error("Polling error:", err));
}

setInterval(updateDashboard, 2000);
updateDashboard();

function filterMaps() {
    var input = document.getElementById("mapSearch").value.toUpperCase();
    var list = document.getElementById("mapList");
    var items = list.querySelectorAll("[data-search]");
    items.forEach(function(item) {
        var txt = item.getAttribute("data-search");
        item.style.display = txt && txt.toUpperCase().indexOf(input) > -1 ? "" : "none";
    });
}

document.getElementById('rconForm').addEventListener('submit', function(e) {
    e.preventDefault();
    var cmd = document.getElementById('rconCmd').value;
    var respBox = document.getElementById('rconResponse');

    fetch('/api/rcon', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'command=' + encodeURIComponent(cmd)
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        respBox.innerText = d.output;
        respBox.classList.remove('d-none');
        document.getElementById('rconCmd').value = '';
    });
});

// Switch MapCycle modal
var dashMcFiles = [];
document.getElementById('selectMapcycleModal').addEventListener('show.bs.modal', function() {
    var container = document.getElementById('dashMapcycleFiles');
    container.innerHTML = '<div class="text-muted text-center py-2">Loading...</div>';
    
    fetch('/api/mapcycle/list_files')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        dashMcFiles = data.files || [];
        if (dashMcFiles.length === 0) {
            container.innerHTML = '<div class="text-muted text-center py-2">No mapcycle files found</div>';
            return;
        }
        var html = '';
        dashMcFiles.forEach(function(f, idx) {
            html += '<div class="d-flex align-items-center gap-2 p-2 border-bottom border-secondary">';
            html += '<div class="flex-grow-1"><strong class="small">' + f.name + '</strong>';
            if (f.is_mapcycle) html += ' <span class="badge bg-success">' + f.entry_count + ' maps</span>';
            html += '<div class="text-muted" style="font-size:0.7rem;">' + f.dir + '</div></div>';
            html += '<button class="btn btn-primary btn-sm dash-mc-select" data-idx="' + idx + '">Use This</button>';
            html += '</div>';
        });
        container.innerHTML = html;
        
        container.querySelectorAll('.dash-mc-select').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var f = dashMcFiles[parseInt(this.dataset.idx)];
                if (!f) return;
                
                fetch('/api/set_mapcycle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({file_path: f.path})
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.success) {
                        var modal = bootstrap.Modal.getInstance(document.getElementById('selectMapcycleModal'));
                        modal.hide();
                        location.reload();
                    }
                });
            });
        });
    });
});
</script>
"""

SERVER_PAGE = """
<!-- Setup Assistant: Status Cards -->
<div class="row mb-4">
    <div class="col-12">
        <h4><i class="bi bi-gear-wide-connected"></i> Server Setup</h4>
        <p class="text-muted">Manage your Insurgency: Sandstorm dedicated server</p>
    </div>
    
    <!-- Status Cards Row -->
    <div class="col-md-4">
        <div class="card border-{{ 'success' if server_status.installed else 'warning' }} mb-3">
            <div class="card-body text-center">
                <h1><i class="bi bi-{{ 'check-circle-fill text-success' if server_status.installed else 'hourglass-split text-warning' }}"></i></h1>
                <h5>Server Files</h5>
                <p class="text-muted mb-2">{{ 'Installed' if server_status.installed else 'Not Installed' }}</p>
                {% if not server_status.installed %}
                <form action="/server/install_server" method="post">
                    <button class="btn btn-warning btn-sm" type="submit">Install Server</button>
                </form>
                {% else %}
                <form action="/server/install_server" method="post">
                    <button class="btn btn-outline-secondary btn-sm" type="submit">Update</button>
                </form>
                {% endif %}
                <button class="btn btn-link btn-sm" data-bs-toggle="modal" data-bs-target="#helpSteamCMD"><i class="bi bi-question-circle"></i> Help</button>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card border-{{ 'success' if server_status.running else 'secondary' }} mb-3">
            <div class="card-body text-center">
                <h1><i class="bi bi-{{ 'play-fill text-success' if server_status.running else 'stop-fill text-secondary' }}"></i></h1>
                <h5>Server Status</h5>
                <p class="text-muted mb-2">{{ 'Running' if server_status.running else 'Stopped' }}</p>
                {% if server_status.running %}
                <form action="/server/stop" method="post">
                    <button class="btn btn-danger btn-sm" type="submit">Stop Server</button>
                </form>
                {% else %}
                <form action="/server/start" method="post" class="d-inline">
                    <div class="input-group input-group-sm mb-1">
                        <select name="preset" class="form-select form-select-sm">
                            {% for pname in presets %}
                            <option value="{{ pname }}">{{ pname }}</option>
                            {% endfor %}
                        </select>
                        <button class="btn btn-success btn-sm" type="submit">Start</button>
                    </div>
                </form>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card border-info mb-3">
            <div class="card-body text-center">
                <h1><i class="bi bi-list-check text-info"></i></h1>
                <h5>MapCycle</h5>
                <p class="text-muted mb-2">{{ mapcycle_count }} entries in cycle</p>
                <a href="/mapcycle" class="btn btn-info btn-sm">Open Editor</a>
                <button class="btn btn-link btn-sm" data-bs-toggle="modal" data-bs-target="#helpMapCycle"><i class="bi bi-question-circle"></i> Help</button>
            </div>
        </div>
    </div>
</div>

<!-- Help Modals -->
<div class="modal fade" id="helpSteamCMD" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-question-circle"></i> Server Installation Help</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <h6>What is SteamCMD?</h6>
                <p>SteamCMD is a command-line tool for installing and updating Steam game servers. It's required to download the Insurgency: Sandstorm dedicated server files (App ID: 581330).</p>
                <h6>Installation Steps:</h6>
                <ol>
                    <li>Click <strong>Install Server</strong> to download the server files</li>
                    <li>Wait for the download to complete (may take 10-30 minutes, ~30GB)</li>
                    <li>Once installed, create a preset and start your server</li>
                </ol>
                <h6>Port Forwarding:</h6>
                <p>Forward both TCP and UDP for your game port (default 27102) and query port (default 27131).</p>
                <h6>Enabling Stats (XP):</h6>
                <p>To enable XP/stats, you need both a <strong>GSLT Token</strong> (from <a href="https://steamcommunity.com/dev/managegameservers" target="_blank" class="text-info">Steam Game Server Account Management</a>, App ID 581320) and a <strong>GameStats Token</strong> (from <a href="https://gamestats.sandstorm.game/" target="_blank" class="text-info">GameStats Token Generator</a>). Store them in the Global Tokens section below.</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="helpMapCycle" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-question-circle"></i> MapCycle Help</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <h6>What is MapCycle?</h6>
                <p>The MapCycle defines which maps will rotate on your server. When a round ends, the server loads the next map in the cycle.</p>
                <h6>How to use the MapCycle Editor:</h6>
                <ol>
                    <li>Browse available maps by expanding map categories</li>
                    <li>Click maps to add them to your rotation</li>
                    <li>Drag and drop to reorder maps</li>
                    <li>Set lighting (Day/Night) per map</li>
                    <li>Click <strong>Save MapCycle</strong> when done</li>
                </ol>
                <h6>File Location:</h6>
                <p>The MapCycle file is saved to: <code>Insurgency/Config/Server/MapCycle.txt</code></p>
                <p>Reference it in your preset with: <code>-MapCycle=MapCycle.txt</code></p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>

<!-- Global Tokens Modal -->
<div class="modal fade" id="globalTokensModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-key"></i> Global Tokens (GSLT &amp; GameStats)</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p class="text-muted small">Store your tokens here once and they'll be available to auto-fill in all presets. Required for XP/stats to work.</p>
                <form action="/server/save_global_tokens" method="post" id="globalTokensForm">
                    <div class="mb-3">
                        <label class="form-label fw-bold">GSLT Token <span class="text-muted small">(Steam Game Server Login Token)</span></label>
                        <input type="text" name="global_gslt_token" class="form-control font-monospace" value="{{ global_gslt }}" placeholder="e.g. 41F81BD33067494B43BA7987E3A809D9">
                        <div class="form-text">Get from: <a href="https://steamcommunity.com/dev/managegameservers" target="_blank" class="text-info">Steam Game Server Account Management</a> (App ID: 581320). One token per server.</div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">GameStats Token <span class="text-muted small">(for XP/stats)</span></label>
                        <input type="text" name="global_gamestats_token" class="form-control font-monospace" value="{{ global_gamestats }}" placeholder="e.g. 1417264D1C6549CC95E10CA1E9BE8F09">
                        <div class="form-text">Get from: <a href="https://gamestats.sandstorm.game/" target="_blank" class="text-info">GameStats Token Generator</a>. Do not share this token.</div>
                    </div>
                    <button type="submit" class="btn btn-primary w-100"><i class="bi bi-save"></i> Save Global Tokens</button>
                </form>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-md-6">
        <!-- Global Tokens Banner -->
        <div class="card mb-3 border-warning">
            <div class="card-body py-2 d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi bi-key text-warning"></i>
                    <strong class="ms-1">Global Tokens</strong>
                    <span class="ms-2 text-muted small">
                        GSLT: {% if global_gslt %}<span class="text-success">✓ Set</span>{% else %}<span class="text-danger">✗ Not set</span>{% endif %}
                        &nbsp;|&nbsp;
                        GameStats: {% if global_gamestats %}<span class="text-success">✓ Set</span>{% else %}<span class="text-danger">✗ Not set</span>{% endif %}
                    </span>
                </div>
                <button class="btn btn-warning btn-sm" data-bs-toggle="modal" data-bs-target="#globalTokensModal">
                    <i class="bi bi-pencil"></i> Edit Tokens
                </button>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header"><i class="bi bi-hdd-stack"></i> Server Controls</div>
            <div class="card-body">
                <h6>Start with Watchdog</h6>
                <p class="text-muted small">Watchdog will automatically restart the server if it crashes</p>
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <form action="/server/start_watchdog" method="post" class="d-inline">
                        <div class="input-group input-group-sm">
                            <select name="preset" class="form-select form-select-sm">
                                {% for pname in presets %}
                                <option value="{{ pname }}">{{ pname }}</option>
                                {% endfor %}
                            </select>
                            <button class="btn btn-primary btn-sm" type="submit"><i class="bi bi-shield-check"></i> Watchdog</button>
                        </div>
                    </form>
                    {% if server_status.watchdog_active %}
                    <form action="/server/stop_watchdog" method="post" class="d-inline">
                        <button class="btn btn-warning btn-sm" type="submit"><i class="bi bi-shield-x"></i> Stop Watchdog</button>
                    </form>
                    {% endif %}
                </div>
                <h6>Server Info</h6>
                <table class="table table-dark table-sm">
                    <tr><td>Session</td><td>{{ server_status.session_name }}</td></tr>
                    <tr><td>Watchdog</td><td>{{ 'Active' if server_status.watchdog_active else 'Inactive' }}</td></tr>
                </table>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-terminal"></i> Server Console</span>
                <span id="consoleStatus" class="badge bg-secondary">Checking...</span>
            </div>
            <div class="card-body p-0">
                <div id="serverConsole" class="console-output">{{ console_output }}</div>
            </div>
        </div>

        <div class="card mb-4" id="installationCard" style="display: none;">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-download"></i> Installation Progress</span>
                <span id="installStatus" class="badge bg-info">Running</span>
            </div>
            <div class="card-body p-0">
                <div id="installationLog" class="console-output" style="height: 200px;"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-info-circle"></i> Server Info</span>
                <a href="/settings?tab=paths" class="btn btn-sm btn-outline-secondary"><i class="bi bi-gear"></i> Configure Paths</a>
            </div>
            <div class="card-body">
                <table class="table table-dark table-sm">
                    <tr><td>Server Directory</td><td><small>{{ configured_paths.server_dir }}</small></td></tr>
                    <tr><td>SteamCMD Directory</td><td><small>{{ configured_paths.steamcmd_dir }}</small></td></tr>
                    <tr><td>Presets File</td><td><small>{{ configured_paths.presets_file }}</small></td></tr>
                    <tr><td>App ID</td><td>{{ app_id }}</td></tr>
                    <tr><td>Multiplexer</td><td>{{ multiplexer }}</td></tr>
                </table>
            </div>
        </div>
    </div>

    <div class="col-md-6">
        <!-- Create New Preset -->
        <div class="card mb-4 border-success">
            <div class="card-header bg-success text-white d-flex justify-content-between align-items-center">
                <span><i class="bi bi-plus-circle"></i> Create New Preset</span>
                <button class="btn btn-sm btn-light" type="button" data-bs-toggle="collapse" data-bs-target="#createPresetForm">
                    <i class="bi bi-chevron-down"></i>
                </button>
            </div>
            <div class="collapse show" id="createPresetForm">
            <div class="card-body">
                <form action="/server/create_preset" method="post">
                    <!-- Basic Info -->
                    <div class="row g-2 mb-3">
                        <div class="col-12">
                            <label class="form-label fw-bold">Preset Name <span class="text-muted small">(spaces/slashes auto-converted to underscores)</span></label>
                            <input type="text" name="preset_name" class="form-control" placeholder="My_Coop_Server" required>
                        </div>
                    </div>

                    <!-- Map Selection -->
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-header py-1 small text-info"><i class="bi bi-map"></i> Starting Map</div>
                        <div class="card-body py-2">
                            <div class="row g-2 mb-2">
                                <div class="col-md-6">
                                    <label class="form-label small">Map</label>
                                    <select name="map_key" id="cp_map_key" class="form-select form-select-sm" onchange="updateScenarios()">
                                        <option value="">-- Select Map --</option>
                                        {% for mk, minfo in map_scenario_data.items() %}
                                        <option value="{{ mk }}">{{ minfo.display_name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small">Scenario / Game Mode</label>
                                    <select name="scenario_id" id="cp_scenario_id" class="form-select form-select-sm">
                                        <option value="">-- Select Map First --</option>
                                    </select>
                                </div>
                            </div>
                            <div class="row g-2">
                                <div class="col-md-4">
                                    <label class="form-label small">Max Players</label>
                                    <input type="number" name="max_players" class="form-control form-control-sm" value="28" min="1" max="64">
                                </div>
                                <div class="col-md-8">
                                    <label class="form-label small">Server Password <span class="text-muted">(optional)</span></label>
                                    <input type="text" name="server_password" class="form-control form-control-sm" placeholder="Leave blank for public">
                                </div>
                            </div>
                            <div class="mt-2">
                                <label class="form-label small text-muted">Or enter manually:</label>
                                <input type="text" name="map_url_manual" class="form-control form-control-sm font-monospace" placeholder="Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security?MaxPlayers=8">
                                <div class="form-text">Manual entry overrides dropdowns above</div>
                            </div>
                        </div>
                    </div>

                    <!-- Network -->
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-header py-1 small text-info"><i class="bi bi-wifi"></i> Network &amp; Identity</div>
                        <div class="card-body py-2">
                            <div class="row g-2 mb-2">
                                <div class="col-md-4">
                                    <label class="form-label small">Game Port</label>
                                    <input type="number" name="port" class="form-control form-control-sm" value="27102">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small">Query Port</label>
                                    <input type="number" name="query_port" class="form-control form-control-sm" value="27131">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small">RCON Port</label>
                                    <input type="number" name="rcon_port" class="form-control form-control-sm" value="27015">
                                </div>
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">Server Name (hostname)</label>
                                <input type="text" name="hostname" class="form-control form-control-sm" placeholder="My Sandstorm Server">
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">RCON Password <span class="text-muted">(enables RCON if set)</span></label>
                                <input type="text" name="rcon_password" class="form-control form-control-sm" placeholder="Leave blank to disable RCON">
                            </div>
                        </div>
                    </div>

                    <!-- Files -->
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-header py-1 small text-info"><i class="bi bi-file-earmark-text"></i> Config Files</div>
                        <div class="card-body py-2">
                            <div class="row g-2">
                                <div class="col-md-6">
                                    <label class="form-label small">MapCycle File</label>
                                    <input type="text" name="mapcycle_file" class="form-control form-control-sm" value="MapCycle.txt">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small">Admin List File</label>
                                    <input type="text" name="admin_list" class="form-control form-control-sm" value="Admins.txt">
                                </div>
                                <div class="col-12">
                                    <label class="form-label small">MOTD File <span class="text-muted">(optional)</span></label>
                                    <input type="text" name="motd_file" class="form-control form-control-sm" placeholder="Motd.txt">
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Tokens -->
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-header py-1 small text-warning"><i class="bi bi-key"></i> Tokens (GSLT &amp; GameStats for XP)</div>
                        <div class="card-body py-2">
                            <div class="mb-2">
                                <div class="form-check form-switch mb-1">
                                    <input class="form-check-input" type="checkbox" name="use_global_gslt" id="cp_use_global_gslt" {% if global_gslt %}checked{% endif %} onchange="toggleTokenField('cp_gslt_token', this.checked, '{{ global_gslt }}')">
                                    <label class="form-check-label small" for="cp_use_global_gslt">Use Global GSLT Token {% if global_gslt %}<span class="text-success">✓</span>{% else %}<span class="text-muted">(not set)</span>{% endif %}</label>
                                </div>
                                <input type="text" name="gslt_token" id="cp_gslt_token" class="form-control form-control-sm font-monospace" placeholder="GSLT Token (or use global above)" {% if global_gslt %}disabled value="{{ global_gslt }}"{% endif %}>
                            </div>
                            <div class="mb-2">
                                <div class="form-check form-switch mb-1">
                                    <input class="form-check-input" type="checkbox" name="use_global_gamestats" id="cp_use_global_gamestats" {% if global_gamestats %}checked{% endif %} onchange="toggleTokenField('cp_gamestats_token', this.checked, '{{ global_gamestats }}')">
                                    <label class="form-check-label small" for="cp_use_global_gamestats">Use Global GameStats Token {% if global_gamestats %}<span class="text-success">✓</span>{% else %}<span class="text-muted">(not set)</span>{% endif %}</label>
                                </div>
                                <input type="text" name="gamestats_token" id="cp_gamestats_token" class="form-control form-control-sm font-monospace" placeholder="GameStats Token (or use global above)" {% if global_gamestats %}disabled value="{{ global_gamestats }}"{% endif %}>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" name="enable_gamestats" id="cp_enable_gamestats" {% if global_gslt and global_gamestats %}checked{% endif %}>
                                <label class="form-check-label small" for="cp_enable_gamestats">Enable GameStats (-GameStats flag)</label>
                            </div>
                        </div>
                    </div>

                    <!-- Flags & Mutators -->
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-header py-1 small text-info"><i class="bi bi-toggles"></i> Flags &amp; Mutators</div>
                        <div class="card-body py-2">
                            <div class="row g-2 mb-2">
                                <div class="col-6">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" name="enable_log" id="cp_log" checked>
                                        <label class="form-check-label small" for="cp_log">Enable Log (-log)</label>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" name="enable_mods" id="cp_mods">
                                        <label class="form-check-label small" for="cp_mods">Enable Mods (-Mods)</label>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" name="official_rules" id="cp_official">
                                        <label class="form-check-label small" for="cp_official">Official Rules</label>
                                    </div>
                                </div>
                            </div>
                            <label class="form-label small">Mutators <span class="text-muted">(Ctrl+click for multiple)</span></label>
                            <select name="mutators" multiple class="form-select form-select-sm" style="height: 100px;">
                                {% for m in mutators_list %}
                                <option value="{{ m }}">{{ m }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <!-- Extra Args -->
                    <div class="mb-3">
                        <label class="form-label small">Extra Arguments <span class="text-muted">(space-separated)</span></label>
                        <input type="text" name="extra_args" class="form-control form-control-sm font-monospace" placeholder="-CmdModList=123,456">
                    </div>

                    <button type="submit" class="btn btn-success w-100"><i class="bi bi-plus-circle"></i> Create Preset</button>
                </form>
            </div>
            </div>
        </div>

        <!-- Existing Presets -->
        <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span><i class="bi bi-card-list"></i> Server Presets</span>
                <span class="badge bg-secondary">{{ presets|length }}</span>
            </div>
            <div class="card-body p-0" style="max-height: 500px; overflow-y: auto;">
                <div class="table-responsive">
                    <table class="table table-dark table-sm table-hover mb-0">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Map</th>
                                <th>Port</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for pname, args in presets.items() %}
                            <tr>
                                <td><strong>{{ pname }}</strong></td>
                                <td><small class="text-truncate d-inline-block" style="max-width:120px;" title="{{ args[0] if args else '' }}">{{ args[0][:35] if args else 'N/A' }}</small></td>
                                <td><small>{{ get_port(args) }}</small></td>
                                <td>
                                    <div class="btn-group btn-group-sm">
                                        <a href="/server?edit={{ pname }}" class="btn btn-info btn-sm py-0" title="Edit"><i class="bi bi-pencil"></i></a>
                                        <form action="/server/duplicate_preset" method="post" class="d-inline">
                                            <input type="hidden" name="preset_name" value="{{ pname }}">
                                            <button class="btn btn-secondary btn-sm py-0" title="Duplicate"><i class="bi bi-copy"></i></button>
                                        </form>
                                        <form action="/server/start" method="post" class="d-inline">
                                            <input type="hidden" name="preset" value="{{ pname }}">
                                            <button class="btn btn-success btn-sm py-0" title="Start"><i class="bi bi-play-fill"></i></button>
                                        </form>
                                        <form action="/server/delete_preset" method="post" class="d-inline">
                                            <input type="hidden" name="preset_name" value="{{ pname }}">
                                            <button class="btn btn-danger btn-sm py-0" title="Delete" onclick="return confirm('Delete preset {{ pname }}?')"><i class="bi bi-trash"></i></button>
                                        </form>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Preset Edit Panel -->
        {% if selected_preset and selected_preset in presets %}
        {% set ep_args = presets[selected_preset] %}
        {% set ep_map_url, ep_map_part, ep_scenario, ep_maxp = get_map_url_parts(ep_args) %}
        <div class="card mb-4 border-info">
            <div class="card-header bg-info text-dark d-flex justify-content-between align-items-center">
                <span><i class="bi bi-pencil"></i> Edit Preset: {{ selected_preset }}</span>
                <a href="/server" class="btn btn-sm btn-dark">✕ Close</a>
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-3" id="editPresetTabs">
                    <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#editStructured">Structured</a></li>
                    <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#editRaw">Raw Args</a></li>
                </ul>
                <div class="tab-content">
                    <!-- Structured Edit -->
                    <div class="tab-pane fade show active" id="editStructured">
                        <form action="/server/update_preset_structured" method="post">
                            <input type="hidden" name="preset_name" value="{{ selected_preset }}">
                            <div class="mb-2">
                                <label class="form-label small">Map URL</label>
                                <input type="text" name="map_url" class="form-control form-control-sm font-monospace" value="{{ ep_map_url }}">
                            </div>
                            <div class="row g-2 mb-2">
                                <div class="col-md-4">
                                    <label class="form-label small">Port</label>
                                    <input type="text" name="port" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-Port') or '27102' }}">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small">Query Port</label>
                                    <input type="text" name="query_port" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-QueryPort') or '27131' }}">
                                </div>
                                <div class="col-md-4">
                                    <label class="form-label small">RCON Port</label>
                                    <input type="text" name="rcon_port" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-RconListenPort') or '27015' }}">
                                </div>
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">Hostname</label>
                                <input type="text" name="hostname" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-hostname') }}">
                            </div>
                            <div class="row g-2 mb-2">
                                <div class="col-md-6">
                                    <label class="form-label small">MapCycle File</label>
                                    <input type="text" name="mapcycle_file" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-MapCycle') or 'MapCycle.txt' }}">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small">Admin List</label>
                                    <input type="text" name="admin_list" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-AdminList') or 'Admins.txt' }}">
                                </div>
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">RCON Password</label>
                                <input type="text" name="rcon_password" class="form-control form-control-sm" value="{{ get_preset_field(ep_args, '-RconPassword') }}">
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">GSLT Token</label>
                                <div class="input-group input-group-sm">
                                    <input type="text" name="gslt_token" id="ep_gslt" class="form-control form-control-sm font-monospace" value="{{ get_preset_field(ep_args, '-GSLTToken') }}">
                                    {% if global_gslt %}
                                    <button type="button" class="btn btn-outline-warning btn-sm" onclick="document.getElementById('ep_gslt').value='{{ global_gslt }}'">Use Global</button>
                                    {% endif %}
                                </div>
                            </div>
                            <div class="mb-2">
                                <label class="form-label small">GameStats Token</label>
                                <div class="input-group input-group-sm">
                                    <input type="text" name="gamestats_token" id="ep_gamestats" class="form-control form-control-sm font-monospace" value="{{ get_preset_field(ep_args, '-GameStatsToken') }}">
                                    {% if global_gamestats %}
                                    <button type="button" class="btn btn-outline-warning btn-sm" onclick="document.getElementById('ep_gamestats').value='{{ global_gamestats }}'">Use Global</button>
                                    {% endif %}
                                </div>
                            </div>
                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" name="enable_gamestats" id="ep_gamestats_flag" {% if '-GameStats' in ep_args %}checked{% endif %}>
                                        <label class="form-check-label small" for="ep_gamestats_flag">-GameStats</label>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" name="enable_mods" id="ep_mods" {% if '-Mods' in ep_args %}checked{% endif %}>
                                        <label class="form-check-label small" for="ep_mods">-Mods</label>
                                    </div>
                                </div>
                            </div>
                            <button type="submit" class="btn btn-info w-100"><i class="bi bi-save"></i> Save Changes</button>
                        </form>
                    </div>
                    <!-- Raw Edit -->
                    <div class="tab-pane fade" id="editRaw">
                        <form action="/server/update_preset" method="post">
                            <input type="hidden" name="preset_name" value="{{ selected_preset }}">
                            <div class="mb-2">
                                <label class="form-label small">Full Arguments (one per line)</label>
                                <textarea name="preset_args" class="form-control font-monospace" rows="10" style="font-size:0.8rem;">{{ ep_args|join('\n') }}</textarea>
                            </div>
                            <button type="submit" class="btn btn-warning w-100"><i class="bi bi-save"></i> Save Raw Args</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
</div>

<script>
// Map/Scenario data for dropdowns
const mapScenarioData = {{ map_scenario_data | tojson }};

function updateScenarios() {
    const mapKey = document.getElementById('cp_map_key').value;
    const scenSelect = document.getElementById('cp_scenario_id');
    scenSelect.innerHTML = '<option value="">-- Select Scenario --</option>';
    if (mapKey && mapScenarioData[mapKey]) {
        mapScenarioData[mapKey].scenarios.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name + ' (' + s.mode + ')';
            scenSelect.appendChild(opt);
        });
    }
}

function toggleTokenField(fieldId, useGlobal, globalValue) {
    const field = document.getElementById(fieldId);
    if (useGlobal) {
        field.disabled = true;
        field.value = globalValue;
    } else {
        field.disabled = false;
        field.value = '';
    }
}

// Console auto-refresh functionality
let consoleInterval = null;
let installInterval = null;

function updateConsole() {
    fetch('/api/console')
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        const consoleDiv = document.getElementById('serverConsole');
        const statusBadge = document.getElementById('consoleStatus');
        if (consoleDiv && data.console !== undefined) {
            if (consoleDiv.textContent !== data.console) {
                consoleDiv.textContent = data.console;
                consoleDiv.scrollTop = consoleDiv.scrollHeight;
            }
        }
        if (statusBadge) {
            if (data.running) {
                statusBadge.textContent = 'Running';
                statusBadge.className = 'badge bg-success';
            } else {
                statusBadge.textContent = 'Stopped';
                statusBadge.className = 'badge bg-secondary';
            }
        }
    })
    .catch(err => {
        const statusBadge = document.getElementById('consoleStatus');
        if (statusBadge) { statusBadge.textContent = 'Error'; statusBadge.className = 'badge bg-warning'; }
    });
}

function updateInstallationStatus() {
    fetch('/api/installation_status')
    .then(response => { if (!response.ok) throw new Error('Network response was not ok'); return response.json(); })
    .then(data => {
        const installCard = document.getElementById('installationCard');
        const installLog = document.getElementById('installationLog');
        const installStatus = document.getElementById('installStatus');
        if (!installCard || !installLog || !installStatus) return;
        const steamcmd = data.steamcmd || {};
        const server = data.server || {};
        const steamcmdActive = steamcmd.running || false;
        const serverActive = server.running || false;
        const anyRunning = steamcmdActive || serverActive;
        const anyComplete = steamcmd.complete || server.complete;
        let output = '';
        let status = 'Idle';
        if (serverActive) { output = server.output || ''; status = 'Installing Server...'; }
        else if (steamcmdActive) { output = steamcmd.output || ''; status = 'Installing SteamCMD...'; }
        else if (anyComplete) {
            if (server.complete && server.output) { output = server.output; status = server.error ? 'Error' : 'Server Install Complete'; }
            else if (steamcmd.complete && steamcmd.output) { output = steamcmd.output; status = steamcmd.error ? 'Error' : 'SteamCMD Install Complete'; }
        }
        if (output && output.length > 0) {
            installCard.style.display = 'block';
            if (installLog.textContent !== output) { installLog.textContent = output; installLog.scrollTop = installLog.scrollHeight; }
            if (anyRunning) { installStatus.textContent = status; installStatus.className = 'badge bg-primary'; }
            else if (anyComplete) { installStatus.textContent = status; installStatus.className = server.error || steamcmd.error ? 'badge bg-danger' : 'badge bg-success'; }
        } else if (!anyRunning && !anyComplete) { installCard.style.display = 'none'; }
    })
    .catch(err => console.error('Installation status error:', err));
}

document.addEventListener('DOMContentLoaded', function() {
    consoleInterval = setInterval(updateConsole, 2000);
    installInterval = setInterval(updateInstallationStatus, 1000);
    updateConsole();
    updateInstallationStatus();
});
</script>
"""

SETTINGS_TEMPLATE = """
<ul class="nav nav-tabs mb-4">
    <li class="nav-item">
        <a class="nav-link {% if tab == 'general' %}active{% endif %}" href="/settings?tab=general">General</a>
    </li>
    <li class="nav-item">
        <a class="nav-link {% if tab == 'paths' %}active{% endif %}" href="/settings?tab=paths">Paths</a>
    </li>
    <li class="nav-item">
        <a class="nav-link {% if tab == 'performance' %}active{% endif %}" href="/settings?tab=performance">Performance</a>
    </li>
</ul>

{% if tab == 'paths' %}
<div class="row">
    <div class="col-lg-8">
        <div class="card border-warning">
            <div class="card-header bg-warning text-dark">
                <i class="bi bi-folder2"></i> Directory Configuration
            </div>
            <div class="card-body">
                <form method="post" action="/save_settings">
                    <input type="hidden" name="tab" value="paths">
                    
                    <div class="mb-4">
                        <label class="form-label fw-bold">Home Directory</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="bi bi-house"></i></span>
                            <input type="text" name="home" id="home_path" class="form-control font-monospace" value="{{ config.get('home', defaults.home) }}">
                            <button type="button" class="btn btn-outline-secondary" onclick="browsePath('home_path')"><i class="bi bi-folder2-open"></i> Browse</button>
                        </div>
                        <div class="form-text">Base directory for server files (default: ~/)</div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">SteamCMD Directory</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="bi bi-download"></i></span>
                            <input type="text" name="steamcmd_dir" id="steamcmd_path" class="form-control font-monospace" value="{{ config.get('steamcmd_dir', defaults.steamcmd_dir) }}">
                            <button type="button" class="btn btn-outline-secondary" onclick="browsePath('steamcmd_path')"><i class="bi bi-folder2-open"></i> Browse</button>
                        </div>
                        <div class="form-text">Where SteamCMD will be installed</div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">Server Directory</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="bi bi-hdd"></i></span>
                            <input type="text" name="server_dir" id="server_path" class="form-control font-monospace" value="{{ config.get('server_dir', defaults.server_dir) }}">
                            <button type="button" class="btn btn-outline-secondary" onclick="browsePath('server_path')"><i class="bi bi-folder2-open"></i> Browse</button>
                        </div>
                        <div class="form-text">Where the Sandstorm server files will be installed</div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">Presets File</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="bi bi-file-earmark-text"></i></span>
                            <input type="text" name="presets_file" id="presets_path" class="form-control font-monospace" value="{{ config.get('presets_file', defaults.presets_file) }}">
                            <button type="button" class="btn btn-outline-secondary" onclick="browsePath('presets_path')"><i class="bi bi-folder2-open"></i> Browse</button>
                        </div>
                        <div class="form-text">Location of server presets configuration file</div>
                    </div>

                    <button type="submit" class="btn btn-warning w-100"><i class="bi bi-save"></i> Save Paths</button>
                </form>
            </div>
        </div>
    </div>
</div>

<!-- Directory Browser Modal -->
<div class="modal fade" id="dirBrowserModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-folder2-open"></i> Browse Directory</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <div class="input-group">
                        <button class="btn btn-outline-secondary" onclick="navigateUp()"><i class="bi bi-arrow-up"></i> Up</button>
                        <input type="text" id="browser_current_path" class="form-control font-monospace" readonly>
                    </div>
                </div>
                <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                    <table class="table table-dark table-hover" id="dir_browser_table">
                        <thead><tr><th>Name</th><th>Type</th></tr></thead>
                        <tbody id="dir_browser_body">
                            <tr><td colspan="2" class="text-center">Loading...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="selectCurrentPath()">Select This Folder</button>
            </div>
        </div>
    </div>
</div>

<script>
let currentInputId = '';
let currentBrowserPath = '/';

function browsePath(inputId) {
    currentInputId = inputId;
    const input = document.getElementById(inputId);
    currentBrowserPath = input.value || '/';
    
    if (!currentBrowserPath.startsWith('/')) {
        currentBrowserPath = '/';
    }
    
    loadDirectory(currentBrowserPath);
    var modal = new bootstrap.Modal(document.getElementById('dirBrowserModal'));
    modal.show();
}

function loadDirectory(path) {
    fetch('/api/browse_directory?path=' + encodeURIComponent(path))
        .then(r => r.json())
        .then(data => {
            document.getElementById('browser_current_path').value = data.current_path || path;
            currentBrowserPath = data.current_path || path;
            
            const tbody = document.getElementById('dir_browser_body');
            if (data.error) {
                tbody.innerHTML = '<tr><td colspan="2" class="text-danger">' + data.error + '</td></tr>';
                return;
            }
            
            let html = '';
            data.items.forEach(item => {
                const icon = item.is_dir ? '<i class="bi bi-folder-fill text-warning"></i>' : '<i class="bi bi-file-earmark text-secondary"></i>';
                const type = item.is_dir ? 'Folder' : 'File';
                const onclick = item.is_dir ? 'onclick="loadDirectory(\'' + item.path + '\')"' : '';
                const style = item.is_dir ? 'cursor: pointer;' : '';
                html += '<tr style="' + style + '" ' + onclick + '>';
                html += '<td>' + icon + ' ' + item.name + '</td>';
                html += '<td>' + type + '</td>';
                html += '</tr>';
            });
            
            if (data.items.length === 0) {
                html = '<tr><td colspan="2" class="text-muted">Empty directory</td></tr>';
            }
            
            tbody.innerHTML = html;
        });
}

function navigateUp() {
    const parent = currentBrowserPath.split('/').slice(0, -1).join('/') || '/';
    loadDirectory(parent || '/');
}

function selectCurrentPath() {
    document.getElementById(currentInputId).value = currentBrowserPath;
    var modal = bootstrap.Modal.getInstance(document.getElementById('dirBrowserModal'));
    modal.hide();
}
</script>

{% elif tab == 'general' %}

<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card">
            <div class="card-header">Server Configuration</div>
            <div class="card-body">
                <form method="post" action="/save_settings">
                    <input type="hidden" name="tab" value="general">
                    
                    <h5 class="mb-3 text-info">RTV Settings</h5>
                    <div class="mb-3">
                        <label class="form-label">RTV Threshold</label>
                        <input type="number" step="0.05" name="rtv_threshold_percent" class="form-control" value="{{ config.rtv_threshold_percent }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Min Players</label>
                        <input type="number" name="rtv_min_players" class="form-control" value="{{ config.rtv_min_players }}">
                    </div>
                    
                    <hr>
                    <h5 class="mb-3 text-info">Connection</h5>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">IP Address</label>
                            <input type="text" name="rcon_ip" class="form-control" value="{{ config.rcon.ip }}">
                        </div>
                        <div class="col-md-3 mb-3">
                            <label class="form-label">RCON Port</label>
                            <input type="number" name="rcon_port" class="form-control" value="{{ config.rcon.port }}">
                        </div>
                        <div class="col-md-3 mb-3">
                            <label class="form-label">Query Port</label>
                            <input type="number" name="query_port" class="form-control" value="{{ config.query_port }}">
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">RCON Password</label>
                        <input type="password" name="rcon_password" class="form-control" value="{{ config.rcon.password }}">
                    </div>

                    <hr>
                    <h5 class="mb-3 text-info">Map Rotation</h5>
                    <div class="mb-3">
                        <label class="form-label">Map Mode</label>
                        <select name="map_source_mode" class="form-select">
                            <option value="0" {% if config.map_source_mode == 0 %}selected{% endif %}>Mode 0: Load from Config Files</option>
                            <option value="1" {% if config.map_source_mode == 1 %}selected{% endif %}>Mode 1: Use Hardcoded List (All Maps)</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Log File Path</label>
                        <input type="text" name="log_file_path" class="form-control font-monospace" value="{{ config.log_file_path }}">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Map Cycle Files</label>
                        <textarea name="mapcycle_file_path" class="form-control font-monospace" rows="3">{{ config.mapcycle_file_path }}</textarea>
                    </div>

                    <hr>
                    <h5 class="mb-3 text-info">Steam API</h5>
                    <div class="mb-3">
                        <label class="form-label">Steam API Key</label>
                        <input type="text" name="steam_api_key" class="form-control font-monospace" value="{{ config.steam_api_key }}">
                        <div class="form-text">Get a key from https://steamcommunity.com/dev/apikey</div>
                    </div>

                    <hr>
                    <h5 class="mb-3 text-warning"><i class="bi bi-key"></i> Global Tokens (GSLT &amp; GameStats)</h5>
                    <p class="text-muted small">Store your tokens here once and they'll auto-fill in all server presets. Required for XP/stats.</p>
                    <div class="mb-3">
                        <label class="form-label">GSLT Token <span class="text-muted small">(Steam Game Server Login Token)</span></label>
                        <input type="text" name="global_gslt_token" class="form-control font-monospace" value="{{ config.get('global_gslt_token', '') }}" placeholder="e.g. 41F81BD33067494B43BA7987E3A809D9">
                        <div class="form-text">Get from: <a href="https://steamcommunity.com/dev/managegameservers" target="_blank">Steam Game Server Account Management</a> (App ID: 581320). One token per server.</div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">GameStats Token <span class="text-muted small">(for XP/stats)</span></label>
                        <input type="text" name="global_gamestats_token" class="form-control font-monospace" value="{{ config.get('global_gamestats_token', '') }}" placeholder="e.g. 1417264D1C6549CC95E10CA1E9BE8F09">
                        <div class="form-text">Get from: <a href="https://gamestats.sandstorm.game/" target="_blank">GameStats Token Generator</a>. Do not share this token.</div>
                    </div>

                    <button type="submit" class="btn btn-primary w-100">Save Configuration</button>
                </form>
            </div>
        </div>
    </div>
</div>

{% endif %}

{% if tab == 'performance' %}
<div class="row">
    <div class="col-lg-8">
        <div class="card border-info">
            <div class="card-header bg-info text-white">
                <i class="bi bi-speedometer2"></i> Performance Settings
            </div>
            <div class="card-body">
                <form method="post" action="/save_settings">
                    <input type="hidden" name="tab" value="performance">
                    
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i> <strong>ModioBackground CPU Hack</strong>
                        <p class="mb-0 small">This hack reduces high CPU usage caused by a bug in the ModioBackground thread. 
                        It sets the timer slack to 200ms instead of the default 1ms. This is applied automatically 
                        when the server starts.</p>
                    </div>
                    
                    <div class="mb-3">
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" name="timerslack_enabled" id="timerslack_enabled" 
                                {% if config.get('timerslack_enabled', True) %}checked{% endif %}>
                            <label class="form-check-label" for="timerslack_enabled">
                                Enable ModioBackground CPU Hack
                            </label>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label fw-bold">System User</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="bi bi-person"></i></span>
                            <input type="text" name="timerslack_system_user" id="timerslack_user" class="form-control" 
                                value="{{ config.get('timerslack_system_user', '') }}" 
                                placeholder="e.g., sandstorm-ds">
                        </div>
                        <div class="form-text">Enter the system user that runs the Sandstorm server process.
                        This is required for the hack to find and modify the ModioBackground thread.</div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100">Save Performance Settings</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endif %}
"""

MAPS_PAGE = """
<div class="row">
    <div class="col-md-6">
        <div class="card mb-4">
            <div class="card-header">All Available Maps ({{ maps|length }})</div>
            <div class="card-body p-0" style="max-height: 500px; overflow-y: auto;">
                <div class="p-2 border-bottom bg-dark">
                    <input type="text" id="mapSearch" class="form-control form-control-sm" placeholder="Search maps..." onkeyup="filterMaps()">
                </div>
                <table class="table table-dark table-sm table-hover mb-0">
                    <thead><tr><th>Map Code</th><th>Display Name</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for code, name in all_maps %}
                        <tr data-search="{{ name.lower() }}">
                            <td><small>{{ code[:30] }}...</small></td>
                            <td>{{ name }}</td>
                            <td>
                                <form action="/travel" method="post" class="d-inline">
                                    <input type="hidden" name="map_name" value="{{ code }}">
                                    <button class="btn btn-primary btn-sm py-0" type="submit">Travel</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card mb-4">
            <div class="card-header">Current Rotation Pool ({{ pool|length }} maps)</div>
            <div class="card-body p-0" style="max-height: 500px; overflow-y: auto;">
                <table class="table table-dark table-sm mb-0">
                    <thead><tr><th>#</th><th>Map</th></tr></thead>
                    <tbody>
                        {% for map in pool %}
                        <tr><td>{{ loop.index }}</td><td><small>{{ map }}</small></td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
function filterMaps() {
    var input = document.getElementById("mapSearch").value.toLowerCase();
    var rows = document.querySelectorAll("tbody tr[data-search]");
    rows.forEach(function(row) {
        var search = row.getAttribute("data-search");
        row.style.display = search.indexOf(input) > -1 ? "" : "none";
    });
}
</script>
"""

def render_page(content):
    return HTML_BASE.replace("<!-- CONTENT_PLACEHOLDER -->", content)

def format_map_display(map_str):
    if isinstance(map_str, tuple):
        return map_str[1]
    
    parts = map_str.split('?')
    scen = map_str
    light = ""
    
    for p in parts:
        if p.startswith("Scenario="):
            scen = p.replace("Scenario=", "").replace("Scenario_", "")
        if p.startswith("Lighting="):
            light = p.replace("Lighting=", "")
    
    if light:
        return f"{scen} [{light}]"
    return scen

def get_port(args):
    """Extract port from preset args"""
    if not args:
        return "N/A"
    for arg in args:
        if arg.startswith("-Port="):
            return arg.replace("-Port=", "")
    return "27102"

def sanitize_preset_name(name):
    """Sanitize preset name: replace spaces and slashes with underscores, remove other invalid chars"""
    name = name.strip()
    name = re.sub(r'[\s/\\]+', '_', name)
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    if not name:
        name = "Preset"
    return name

def get_preset_field(args, flag):
    """Extract a flag value from preset args list, e.g. get_preset_field(args, '-Port') -> '27102'"""
    for arg in args:
        if arg.startswith(flag + '='):
            return arg[len(flag)+1:]
    return ''

def get_map_url_parts(args):
    """Extract map URL (first arg) and parse MaxPlayers from it"""
    if not args:
        return '', '', '', ''
    map_url = args[0]
    # map_url like: Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security?MaxPlayers=8
    map_part = map_url.split('?')[0]
    scenario = ''
    max_players = '28'
    for part in map_url.split('?')[1:]:
        if part.startswith('Scenario='):
            scenario = part[9:]
        elif part.startswith('MaxPlayers='):
            max_players = part[11:]
    return map_url, map_part, scenario, max_players

def count_mapcycle_entries(mapcycle_path):
    """Count entries in a mapcycle file"""
    if not mapcycle_path:
        return 0
    # Try multiple path resolutions
    paths_to_try = [mapcycle_path]
    if not os.path.isabs(mapcycle_path):
        paths_to_try.append(os.path.join(SERVER_DIR, "Insurgency", "Config", "Server", mapcycle_path))
        paths_to_try.append(os.path.join(SCRIPT_DIR, mapcycle_path))
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    lines = [l.strip() for l in f if l.strip() and not l.strip().startswith(('#', '//'))]
                return len(lines)
            except:
                pass
    return 0


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def dashboard():
    return render_page(render_template_string(
        DASHBOARD_CONTENT,
        maps=bot.map_pool,
        map_mode=bot.map_mode,
        all_maps=HARDCODED_MAPS,
        fmt=format_map_display,
        rtv_thresh=bot.rtv_thresh,
        rtv_min_players=bot.min_players
    ))

@app.route("/api/set_mapcycle", methods=["POST"])
def api_set_mapcycle():
    """Set the active mapcycle file path and reload"""
    data = request.json
    file_path = data.get('file_path', '').strip()
    if not file_path:
        return jsonify({"success": False, "message": "No file path"})
    bot.conf['mapcycle_file_path'] = file_path
    bot.save_config()
    bot.load_mapcycle()
    return jsonify({"success": True, "message": "MapCycle updated"})

@app.route("/api/rtv_settings", methods=["POST"])
def api_rtv_settings():
    """Update RTV settings from dashboard"""
    try:
        bot.conf['rtv_threshold_percent'] = float(request.form.get('rtv_threshold_percent', 0.6))
        bot.conf['rtv_min_players'] = int(request.form.get('rtv_min_players', 1))
        bot.save_config()
        return redirect(url_for('dashboard'))
    except Exception as e:
        return redirect(url_for('dashboard'))

@app.route("/server")
def server_page():
    status = bot.server_manager.get_status()
    presets = bot.server_manager.load_presets()
    console = bot.server_manager.get_console_output()
    selected_preset = request.args.get('edit')
    duplicate_preset = request.args.get('duplicate')
    
    # Get paths from config
    configured_paths = {
        'server_dir': bot.conf.get('server_dir', DEFAULT_SERVER_DIR),
        'steamcmd_dir': bot.conf.get('steamcmd_dir', DEFAULT_STEAMCMD_DIR),
        'presets_file': bot.conf.get('presets_file', DEFAULT_PRESETS_FILE),
        'home': bot.conf.get('home', HOME)
    }
    
    # Count mapcycle entries from actual file
    mapcycle_path = bot.conf.get('mapcycle_file_path', '')
    mapcycle_count = count_mapcycle_entries(mapcycle_path)
    
    # Global tokens
    global_gslt = bot.conf.get('global_gslt_token', '')
    global_gamestats = bot.conf.get('global_gamestats_token', '')
    
    # Build map/scenario data for dropdowns
    map_scenario_data = {}
    for map_key, map_info in MAP_DATA.items():
        map_scenario_data[map_key] = {
            'display_name': map_info['display_name'],
            'scenarios': [{'id': s['id'], 'name': s['name'], 'mode': s['mode']} for s in map_info['scenarios']]
        }
    
    # Mutators list
    mutators_list = [
        "AllYouCanEat", "AntiMaterielRiflesOnly", "BoltActionsOnly", "ArmsRace",
        "Broke", "BudgetAntiquing", "BulletSponge", "Competitive", "CompetitiveLoadouts",
        "DesertEaglesOnly", "FastMovement", "Frenzy", "FullyLoaded", "GrenadeLaunchersOnly",
        "Guerrillas", "Gunslingers", "Hardcore", "HeadshotOnly", "HotPotato",
        "LMGOnly", "LockedAim", "MakarovsOnly", "NoAim", "NoDeathCam", "NoDrops",
        "NoThirdPerson", "OfficialRules", "PistolsOnly", "Poor", "ShotgunsOnly",
        "SlowCaptureTimes", "SlowMovement", "SmallFirefight", "SoldierOfFortune",
        "SpecialOperations", "Strapped", "TacticalVoiceChat", "TieBreaker",
        "Ultralethal", "Vampirism", "Warlords", "Welrods", "WelrodsOnly"
    ]
    
    return render_page(render_template_string(
        SERVER_PAGE,
        server_status=status,
        presets=presets,
        presets_file=bot.server_manager.presets_file,
        console_output=console,
        app_id=APP_ID,
        multiplexer=MULTIPLEXER,
        selected_preset=selected_preset,
        duplicate_preset=duplicate_preset,
        get_port=get_port,
        get_preset_field=get_preset_field,
        get_map_url_parts=get_map_url_parts,
        configured_paths=configured_paths,
        preset_count=len(presets),
        mapcycle_count=mapcycle_count,
        global_gslt=global_gslt,
        global_gamestats=global_gamestats,
        map_scenario_data=map_scenario_data,
        mutators_list=mutators_list
    ))

# ============================================================
# MAPCYCLE EDITOR TEMPLATE
# ============================================================

MAPCYCLE_EDITOR_PAGE = """
<style>
.map-card {
    cursor: pointer;
    transition: all 0.15s ease;
    border: 2px solid transparent;
    border-radius: 8px;
    overflow: hidden;
    background: #2c3035;
    position: relative;
}
.map-card:hover { border-color: #0d6efd; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(13,110,253,0.3); }
.map-card.selected { border-color: #198754; background: #1a2e1a; }
.map-card .map-thumb {
    width: 100%;
    height: 70px;
    object-fit: cover;
    display: block;
    background: linear-gradient(135deg, #1a1d20 0%, #343a40 100%);
}
.map-card .map-thumb-placeholder {
    width: 100%;
    height: 70px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    color: #6c757d;
}
.map-card .map-card-body { padding: 6px 8px; }
.map-card .map-card-title { font-size: 0.75rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.map-card .map-card-mode { font-size: 0.65rem; color: #6c757d; }
.map-card .map-card-check {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #198754;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    color: white;
}
.map-card.selected .map-card-check { display: flex; }
.rotation-item {
    background: #2c3035;
    border: 1px solid #343a40;
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 8px 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: background 0.1s;
}
.rotation-item:hover { background: #343a40; }
.rotation-item .drag-handle { cursor: grab; color: #6c757d; font-size: 1.1rem; flex-shrink: 0; }
.rotation-item .map-mini-thumb {
    width: 48px;
    height: 32px;
    border-radius: 4px;
    object-fit: cover;
    flex-shrink: 0;
    background: linear-gradient(135deg, #1a1d20 0%, #343a40 100%);
}
.rotation-item .map-mini-thumb-placeholder {
    width: 48px;
    height: 32px;
    border-radius: 4px;
    background: linear-gradient(135deg, #1a1d20 0%, #343a40 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    color: #6c757d;
    flex-shrink: 0;
}
.lighting-btn { font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; }
.lighting-day { background: #ffc107; color: #000; border: none; }
.lighting-night { background: #0d1b2a; color: #7eb8f7; border: 1px solid #1a3a5c; }
.mode-badge { font-size: 0.65rem; padding: 2px 6px; border-radius: 10px; }
.map-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 8px; }
.section-header { font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #6c757d; padding: 8px 0 4px; border-bottom: 1px solid #343a40; margin-bottom: 8px; }
.sortable-ghost { opacity: 0.4; background: #0d6efd22 !important; border: 2px dashed #0d6efd !important; }
.sortable-chosen { background: #343a40 !important; }
.sortable-drag { opacity: 0.9; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
#rotationList { min-height: 40px; }
</style>

<div class="row mb-3">
    <div class="col-12 d-flex justify-content-between align-items-center">
        <div>
            <h4 class="mb-0"><i class="bi bi-shuffle"></i> MapCycle Editor</h4>
            <p class="text-muted mb-0 small">Build your server's map rotation — drag to reorder, click to add/remove</p>
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-outline-info btn-sm" onclick="loadMapCycle()"><i class="bi bi-folder-symlink"></i> Load File</button>
            <button class="btn btn-primary btn-sm" onclick="saveMapCycle()"><i class="bi bi-save"></i> Save MapCycle</button>
        </div>
    </div>
</div>

<!-- Main Layout -->
<div class="row mb-2">
    <div class="col-md-6">
        <div class="d-flex gap-2 flex-wrap align-items-center">
            <select id="modeFilter" class="form-select form-select-sm" style="width:auto;" onchange="filterMaps()">
                <option value="All">All Modes</option>
                {% for mode in game_modes[1:] %}
                <option value="{{ mode }}">{{ mode }}</option>
                {% endfor %}
            </select>
            <select id="mapFilter" class="form-select form-select-sm" style="width:auto;" onchange="filterMaps()">
                <option value="">All Maps</option>
                {% for mk, minfo in map_categories.items() %}
                <option value="{{ mk }}">{{ minfo.display_name }}</option>
                {% endfor %}
            </select>
        </div>
    </div>
    <div class="col-md-6">
        <input type="text" id="mapSearch" class="form-control form-control-sm" placeholder="Search scenarios..." oninput="filterMaps()">
    </div>
</div>

<div class="row">
    <!-- LEFT: Available Maps Panel -->
    <div class="col-lg-5 col-md-6">
        <div class="card" style="height: calc(100vh - 280px); min-height: 500px; display: flex; flex-direction: column;">
            <div class="card-header bg-dark d-flex justify-content-between align-items-center py-2">
                <span><i class="bi bi-collection"></i> Available Scenarios</span>
                <div class="d-flex gap-1">
                    <button class="btn btn-outline-secondary btn-sm" onclick="quickAddMode('Checkpoint')" title="Add all Checkpoint">CP</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="quickAddMode('Push')" title="Add all Push">Push</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="quickAddMode('Firefight')" title="Add all Firefight">FF</button>
                    <button class="btn btn-success btn-sm ms-1" id="addSelectedBtn"><i class="bi bi-plus-lg"></i> Add</button>
                </div>
            </div>
            <div style="overflow-y: auto; flex: 1; padding: 8px;">
                {% for map_key, map_data in map_categories.items() %}
                <div class="map-section mb-3" data-map-section="{{ map_key }}">
                    <div class="section-header d-flex justify-content-between align-items-center">
                        <span>
                            <span class="map-color-dot" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{{ loop.cycle('#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b','#795548','#ff9800','#673ab7','#009688','#f44336','#2196f3') }};margin-right:6px;"></span>
                            <strong>{{ map_data.display_name }}</strong>
                        </span>
                        <div>
                            <input type="checkbox" class="form-check-input" id="selAll{{ map_key }}" onchange="toggleSelectAll('{{ map_key }}', this.checked)" title="Select all {{ map_data.display_name }}">
                            <label class="form-check-label small text-muted ms-1" for="selAll{{ map_key }}">All</label>
                        </div>
                    </div>
                    <div class="map-grid" id="grid_{{ map_key }}">
                        {% for scenario in map_data.scenarios %}
                        <div class="map-card map-item"
                             data-mode="{{ scenario.mode }}"
                             data-map="{{ map_key }}"
                             data-map-key="{{ map_key }}"
                             data-scenario-id="{{ scenario.id }}"
                             data-scenario-name="{{ scenario.name }}"
                             data-supports-lighting="{{ scenario.supports_lighting }}"
                             onclick="toggleCardSelect(this)"
                             title="{{ scenario.name }} ({{ scenario.mode }})">
                            <div class="map-thumb-placeholder" style="background: linear-gradient(135deg, {{ loop.cycle('#1a2a3a','#1a3a2a','#2a1a3a','#3a2a1a','#1a3a3a','#3a1a2a') }} 0%, #343a40 100%);">
                                <i class="bi bi-{{ 'shield-fill' if scenario.mode == 'Checkpoint' else 'arrow-right-circle-fill' if scenario.mode == 'Push' else 'crosshair' if scenario.mode == 'Firefight' else 'flag-fill' if scenario.mode == 'Frontline' else 'lightning-fill' if scenario.mode == 'Skirmish' else 'heart-pulse-fill' if scenario.mode == 'Survival' else 'house-fill' if scenario.mode == 'Outpost' else 'circle-fill' if scenario.mode == 'Domination' else 'people-fill' if scenario.mode == 'TDM' else 'eye-fill' if scenario.mode == 'Ambush' else 'bomb' if scenario.mode == 'Defusal' else 'person-fill' if scenario.mode == 'FFA' else 'map' }}" style="font-size:1.4rem; color: {{ '#5bc0de' if scenario.mode == 'Checkpoint' else '#5cb85c' if scenario.mode == 'Push' else '#d9534f' if scenario.mode == 'Firefight' else '#f0ad4e' if scenario.mode == 'Frontline' else '#9b59b6' if scenario.mode == 'Skirmish' else '#1abc9c' if scenario.mode == 'Survival' else '#e67e22' if scenario.mode == 'Outpost' else '#3498db' if scenario.mode == 'Domination' else '#e74c3c' if scenario.mode == 'TDM' else '#95a5a6' if scenario.mode == 'Ambush' else '#e91e63' if scenario.mode == 'Defusal' else '#ff9800' if scenario.mode == 'FFA' else '#6c757d' }};"></i>
                                {% if scenario.supports_lighting %}
                                <i class="bi bi-moon-stars-fill" style="font-size:0.6rem;color:#7eb8f7;position:absolute;top:4px;left:4px;" title="Supports Night"></i>
                                {% endif %}
                            </div>
                            <div class="map-card-body">
                                <div class="map-card-title">{{ scenario.name }}</div>
                                <div class="map-card-mode">{{ scenario.mode }}</div>
                            </div>
                            <div class="map-card-check"><i class="bi bi-check-lg"></i></div>
                            <input type="checkbox" class="map-checkbox d-none"
                                   data-map-key="{{ map_key }}"
                                   data-scenario-id="{{ scenario.id }}"
                                   data-scenario-name="{{ scenario.name }}"
                                   data-mode="{{ scenario.mode }}"
                                   data-supports-lighting="{{ scenario.supports_lighting }}">
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- RIGHT: Rotation + Controls -->
    <div class="col-lg-7 col-md-6">
        <!-- Rotation Panel -->
        <div class="card mb-3" style="height: calc(100vh - 480px); min-height: 300px; display: flex; flex-direction: column;">
            <div class="card-header bg-dark d-flex justify-content-between align-items-center py-2">
                <span><i class="bi bi-list-ol"></i> Rotation &mdash; <span id="rotationCount" class="text-primary fw-bold">0</span> maps</span>
                <div class="d-flex gap-1">
                    <button class="btn btn-outline-secondary btn-sm" onclick="setAllLighting('Day')" title="Set all to Day"><i class="bi bi-sun"></i> All Day</button>
                    <button class="btn btn-outline-info btn-sm" onclick="setAllLighting('Night')" title="Set all to Night"><i class="bi bi-moon-stars"></i> All Night</button>
                    <button class="btn btn-outline-warning btn-sm" onclick="shuffleRotation()" title="Shuffle"><i class="bi bi-shuffle"></i></button>
                    <button class="btn btn-outline-danger btn-sm" onclick="clearRotation()" title="Clear All"><i class="bi bi-trash"></i></button>
                </div>
            </div>
            <div style="overflow-y: auto; flex: 1; padding: 8px;" id="rotationContainer">
                <div id="rotationList"></div>
                <div id="emptyRotation" class="text-center text-muted py-4">
                    <i class="bi bi-arrow-left-circle" style="font-size:2rem;"></i>
                    <p class="mt-2">Select scenarios from the left and click <strong>Add</strong></p>
                </div>
            </div>
        </div>

        <!-- MapCycle File Browser -->
        <div class="card mb-2">
            <div class="card-header bg-dark py-1 small d-flex justify-content-between align-items-center">
                <span><i class="bi bi-folder2"></i> MapCycle Files</span>
                <button class="btn btn-outline-secondary btn-sm py-0" onclick="refreshMapcycleFiles()"><i class="bi bi-arrow-clockwise"></i></button>
            </div>
            <div class="card-body p-2" id="mapcycleFilesContainer">
                <div class="text-muted small text-center py-1">Loading files...</div>
            </div>
        </div>

        <!-- Save Row -->
        <div class="row g-2 mb-2">
            <div class="col-md-8">
                <div class="input-group input-group-sm">
                    <span class="input-group-text"><i class="bi bi-file-earmark-text"></i></span>
                    <input type="text" class="form-control font-monospace" id="outputFile" value="{{ mapcycle_path }}" placeholder="MapCycle.txt">
                </div>
                <div class="form-text">Format: <code>(Scenario="...",Lighting="Day/Night")</code></div>
            </div>
            <div class="col-md-4 d-flex gap-1 align-items-start">
                <button class="btn btn-primary btn-sm flex-fill" onclick="saveMapCycle()"><i class="bi bi-save"></i> Save</button>
                <button class="btn btn-outline-info btn-sm flex-fill" onclick="loadMapCycle()"><i class="bi bi-folder-symlink"></i> Load</button>
                <button class="btn btn-outline-secondary btn-sm" onclick="loadMapCycleFromFile()" title="Upload local file"><i class="bi bi-upload"></i></button>
            </div>
        </div>
        <div id="saveStatus" class="mb-2"></div>

        <!-- Quick Presets + Saved Presets Row -->
        <div class="row g-2">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-dark py-1 small"><i class="bi bi-lightning"></i> Quick Presets</div>
                    <div class="card-body py-2">
                        <div class="d-flex flex-wrap gap-1">
                            <button class="btn btn-outline-success btn-sm preset-btn" data-preset="pvp_push">PvP Push</button>
                            <button class="btn btn-outline-success btn-sm preset-btn" data-preset="coop">Coop Night</button>
                            <button class="btn btn-outline-success btn-sm preset-btn" data-preset="tdm">TDM</button>
                            <button class="btn btn-outline-success btn-sm preset-btn" data-preset="skirmish">Skirmish</button>
                            <button class="btn btn-outline-info btn-sm quick-add-btn" data-mode="Survival">+ Survival</button>
                            <button class="btn btn-outline-info btn-sm quick-add-btn" data-mode="Outpost">+ Outpost</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-dark py-1 small d-flex justify-content-between align-items-center">
                        <span><i class="bi bi-bookmark-star"></i> Saved Presets</span>
                        <button class="btn btn-success btn-sm py-0" onclick="saveNamedPreset()"><i class="bi bi-bookmark-plus"></i> Save</button>
                    </div>
                    <div class="card-body p-2" id="namedPresetsContainer" style="max-height:120px;overflow-y:auto;">
                        <div class="text-muted small text-center py-1" id="noNamedPresets">No saved presets</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Custom Scenarios -->
        <div class="card mt-2">
            <div class="card-header bg-dark py-1 small d-flex justify-content-between align-items-center">
                <span><i class="bi bi-plus-square"></i> Custom Scenarios <span class="text-muted">(mod maps, custom scenarios)</span></span>
                <button class="btn btn-outline-success btn-sm py-0" data-bs-toggle="collapse" data-bs-target="#customScenariosPanel"><i class="bi bi-chevron-down"></i></button>
            </div>
            <div class="collapse" id="customScenariosPanel">
                <div class="card-body p-2">
                    <div class="row g-1 mb-2">
                        <div class="col-md-4">
                            <input type="text" id="cs_scenario_id" class="form-control form-control-sm font-monospace" placeholder="Scenario_MyMap_Checkpoint_Security">
                        </div>
                        <div class="col-md-3">
                            <input type="text" id="cs_scenario_name" class="form-control form-control-sm" placeholder="Display Name">
                        </div>
                        <div class="col-md-2">
                            <input type="text" id="cs_map_key" class="form-control form-control-sm" placeholder="MapKey">
                        </div>
                        <div class="col-md-2">
                            <input type="text" id="cs_mode" class="form-control form-control-sm" placeholder="Mode">
                        </div>
                        <div class="col-md-1">
                            <button class="btn btn-success btn-sm w-100" onclick="addCustomScenario()"><i class="bi bi-plus"></i></button>
                        </div>
                    </div>
                    <div id="customScenariosContainer">
                        <div class="text-muted small text-center py-1">Loading...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Custom Scenario Add to Rotation Modal -->
<div class="modal fade" id="addCustomToRotationModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title">Add Custom Scenario</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="addCustomModalBody"></div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-success" onclick="confirmAddCustom()">Add to Rotation</button>
            </div>
        </div>
    </div>
</div>

<!-- Hidden file input for loading -->
<input type="file" id="fileInput" accept=".txt" style="display: none;">

<!-- Save Named Preset Modal -->
<div class="modal fade" id="saveNamedPresetModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-bookmark-plus"></i> Save MapCycle Preset</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <label class="form-label">Preset Name</label>
                <input type="text" id="namedPresetName" class="form-control" placeholder="e.g. Weekend PvP Rotation">
                <div class="form-text">Current rotation has <span id="namedPresetCount">0</span> maps</div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-success" onclick="confirmSaveNamedPreset()">Save Preset</button>
            </div>
        </div>
    </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.15.0/Sortable.min.js"></script>
<script>
// ============================================================
// MAPCYCLE EDITOR - Complete rewrite (no backtick template literals)
// ============================================================
let rotationData = [];
let sortableInstance = null;
var mapThumbnails = {}; // map_key -> URL

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Sortable on the rotation list
    sortableInstance = new Sortable(document.getElementById('rotationList'), {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        handle: '.drag-handle',
        forceFallback: false,
        onEnd: function() { updateRotationFromDOM(); }
    });
    
    // Load map thumbnails
    fetch('/api/map_thumbnails').then(function(r) { return r.json(); }).then(function(data) {
        mapThumbnails = data;
        // Update existing map cards with thumbnails
        Object.keys(mapThumbnails).forEach(function(mapKey) {
            var placeholders = document.querySelectorAll('.map-section[data-map-section="' + mapKey + '"] .map-thumb-placeholder');
            placeholders.forEach(function(ph) {
                var img = document.createElement('img');
                img.src = mapThumbnails[mapKey];
                img.className = 'map-thumb';
                img.alt = mapKey;
                img.onerror = function() { this.style.display = 'none'; ph.style.display = 'flex'; };
                ph.parentNode.insertBefore(img, ph);
                ph.style.display = 'none';
            });
        });
    }).catch(function() {});
    
    // Load existing map cycle from file
    loadCurrentRotation();
    
    // Load named presets
    loadNamedPresets();
    
    // Load mapcycle file list
    refreshMapcycleFiles();
    
    // Load custom scenarios
    loadCustomScenarios();
    
    // Setup file input
    document.getElementById('fileInput').addEventListener('change', handleFileLoad);
    
    // Setup Add Selected button
    document.getElementById('addSelectedBtn').addEventListener('click', addSelectedToRotation);
    
    // Setup Quick Add buttons
    document.querySelectorAll('.quick-add-btn').forEach(function(btn) {
        btn.addEventListener('click', function() { quickAddMode(this.dataset.mode); });
    });
    
    // Setup Preset buttons
    document.querySelectorAll('.preset-btn').forEach(function(btn) {
        btn.addEventListener('click', function() { loadPreset(this.dataset.preset); });
    });
});

function loadCurrentRotation() {
    fetch('/api/mapcycle/current')
        .then(r => r.json())
        .then(data => {
            if (data.rotation && data.rotation.length > 0) {
                rotationData = data.rotation;
                renderRotation();
            }
        })
        .catch(err => console.error('Error loading rotation:', err));
}

// Mode color map
var modeColors = {
    'Checkpoint': '#5bc0de', 'Push': '#5cb85c', 'Firefight': '#d9534f',
    'Frontline': '#f0ad4e', 'Skirmish': '#9b59b6', 'Survival': '#1abc9c',
    'Outpost': '#e67e22', 'Domination': '#3498db', 'TDM': '#e74c3c',
    'Ambush': '#95a5a6', 'Defusal': '#e91e63', 'FFA': '#ff9800'
};

function getModeColor(mode) {
    return modeColors[mode] || '#6c757d';
}

function renderRotation() {
    var list = document.getElementById('rotationList');
    var emptyDiv = document.getElementById('emptyRotation');
    var countSpan = document.getElementById('rotationCount');
    
    countSpan.textContent = rotationData.length;
    
    if (rotationData.length === 0) {
        list.innerHTML = '';
        emptyDiv.style.display = '';
        return;
    }
    emptyDiv.style.display = 'none';
    
    list.innerHTML = '';
    rotationData.forEach(function(map, index) {
        var div = document.createElement('div');
        div.className = 'rotation-item';
        div.dataset.index = index;
        div.dataset.scenarioId = map.scenario_id;
        
        // Lighting toggle - always shown, defaults to Day
        var lighting = map.lighting || 'Day';
        var isNight = (lighting === 'Night');
        var lightingHtml = '<button class="lighting-btn ' + (isNight ? 'lighting-night' : 'lighting-day') + ' ms-1 toggle-lighting" data-index="' + index + '" title="Click to toggle Day/Night">' +
            (isNight ? '<i class="bi bi-moon-stars-fill"></i> Night' : '<i class="bi bi-sun-fill"></i> Day') + '</button>';
        
        // Mode badge
        var modeColor = getModeColor(map.mode);
        var modeBadge = '<span class="mode-badge ms-1" style="background:' + modeColor + '22;color:' + modeColor + ';border:1px solid ' + modeColor + '44;">' + (map.mode || '') + '</span>';
        
        // Thumbnail
        var thumbHtml;
        var thumbUrl = mapThumbnails[map.map_key] || mapThumbnails[map.scenario_id ? map.scenario_id.split('_')[1] : ''];
        if (thumbUrl) {
            thumbHtml = '<img src="' + thumbUrl + '" class="map-mini-thumb map-thumb-img" alt="' + (map.map_key || '') + '">' +
                '<div class="map-mini-thumb-placeholder map-thumb-fallback" style="display:none;"><i class="bi bi-map" style="color:' + modeColor + ';"></i></div>';
        } else {
            thumbHtml = '<div class="map-mini-thumb-placeholder"><i class="bi bi-map" style="color:' + modeColor + ';"></i></div>';
        }
        
        div.innerHTML = 
            '<span class="drag-handle"><i class="bi bi-grip-vertical"></i></span>' +
            '<span class="badge bg-dark border border-secondary me-1" style="min-width:24px;">' + (index + 1) + '</span>' +
            thumbHtml +
            '<div class="flex-grow-1 ms-1" style="min-width:0;">' +
                '<div style="font-size:0.8rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + (map.map_name || map.map_key || '') + '</div>' +
                '<div style="font-size:0.7rem;color:#adb5bd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + (map.scenario_name || '') + modeBadge + '</div>' +
            '</div>' +
            lightingHtml +
            '<button class="btn btn-outline-danger btn-sm ms-1 py-0 remove-btn" data-index="' + index + '" style="font-size:0.7rem;"><i class="bi bi-x-lg"></i></button>';
        
        list.appendChild(div);
    });
    
    // Event listeners
    list.querySelectorAll('.remove-btn').forEach(function(btn) {
        btn.addEventListener('click', function() { removeFromRotation(parseInt(this.dataset.index)); });
    });
    list.querySelectorAll('.toggle-lighting').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var idx = parseInt(this.dataset.index);
            rotationData[idx].lighting = (rotationData[idx].lighting === 'Night') ? 'Day' : 'Night';
            renderRotation();
        });
    });
    // Handle thumbnail load errors
    list.querySelectorAll('.map-thumb-img').forEach(function(img) {
        img.addEventListener('error', function() {
            this.style.display = 'none';
            var fallback = this.nextElementSibling;
            if (fallback && fallback.classList.contains('map-thumb-fallback')) {
                fallback.style.display = 'flex';
            }
        });
    });
}

function toggleCardSelect(card) {
    var cb = card.querySelector('.map-checkbox');
    if (!cb) return;
    cb.checked = !cb.checked;
    card.classList.toggle('selected', cb.checked);
}

function addSelectedToRotation() {
    var checkboxes = document.querySelectorAll('.map-checkbox:checked');
    checkboxes.forEach(function(cb) {
        var mapKey = cb.dataset.mapKey;
        var scenarioId = cb.dataset.scenarioId;
        var scenarioName = cb.dataset.scenarioName;
        var mode = cb.dataset.mode;
        var supportsLighting = cb.dataset.supportsLighting === 'true';
        
        if (!rotationData.some(function(m) { return m.scenario_id === scenarioId; })) {
            rotationData.push({
                map_key: mapKey,
                map_name: mapKey,
                scenario_id: scenarioId,
                scenario_name: scenarioName,
                mode: mode,
                lighting: 'Day',
                supports_lighting: supportsLighting,
                max_players: 28
            });
        }
    });
    
    // Deselect all cards
    document.querySelectorAll('.map-card.selected').forEach(function(c) { c.classList.remove('selected'); });
    document.querySelectorAll('.map-checkbox').forEach(function(cb) { cb.checked = false; });
    
    renderRotation();
}

function quickAddMode(mode) {
    document.querySelectorAll('.map-item[data-mode="' + mode + '"] .map-checkbox').forEach(function(cb) {
        cb.checked = true;
        var card = cb.closest('.map-card');
        if (card) card.classList.add('selected');
    });
    addSelectedToRotation();
}

function setAllLighting(lighting) {
    rotationData.forEach(function(m) {
        if (m.lighting !== null && m.lighting !== undefined) m.lighting = lighting;
    });
    renderRotation();
}

function removeFromRotation(index) {
    rotationData.splice(index, 1);
    renderRotation();
}

function clearRotation() {
    if (confirm('Clear all maps from rotation?')) {
        rotationData = [];
        renderRotation();
    }
}

function shuffleRotation() {
    for (let i = rotationData.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [rotationData[i], rotationData[j]] = [rotationData[j], rotationData[i]];
    }
    renderRotation();
}

function updateMapOption(index, key, value) {
    rotationData[index][key] = value;
}

function updateRotationFromDOM() {
    var items = document.querySelectorAll('#rotationList .rotation-item');
    var newRotation = [];
    items.forEach(function(item) {
        if (item.dataset.scenarioId) {
            var existing = null;
            for (var i = 0; i < rotationData.length; i++) {
                if (rotationData[i].scenario_id === item.dataset.scenarioId) { existing = rotationData[i]; break; }
            }
            if (existing) newRotation.push(existing);
        }
    });
    rotationData = newRotation;
    // Update index badges without full re-render (avoids losing DOM elements)
    items.forEach(function(item, idx) {
        var badge = item.querySelector('.badge');
        if (badge) badge.textContent = (idx + 1);
        item.dataset.index = idx;
        // Update toggle-lighting data-index
        var toggleBtn = item.querySelector('.toggle-lighting');
        if (toggleBtn) toggleBtn.dataset.index = idx;
        var removeBtn = item.querySelector('.remove-btn');
        if (removeBtn) removeBtn.dataset.index = idx;
    });
    document.getElementById('rotationCount').textContent = rotationData.length;
}

function filterMaps() {
    var search = document.getElementById('mapSearch').value.toLowerCase();
    var modeFilter = document.getElementById('modeFilter').value;
    var mapFilter = document.getElementById('mapFilter').value;
    
    document.querySelectorAll('.map-item').forEach(function(item) {
        var text = item.textContent.toLowerCase();
        var mode = item.dataset.mode || '';
        var map = item.dataset.map || '';
        var modeOk = (modeFilter === 'All' || modeFilter === '' || mode === modeFilter);
        var mapOk = (mapFilter === '' || map === mapFilter);
        var searchOk = (search === '' || text.indexOf(search) > -1);
        item.style.display = (modeOk && mapOk && searchOk) ? '' : 'none';
    });
    
    // Show/hide map sections
    document.querySelectorAll('.map-section').forEach(function(section) {
        var visible = section.querySelectorAll('.map-item:not([style*="none"])').length;
        section.style.display = visible > 0 ? '' : 'none';
    });
}

function toggleSelectAll(mapKey, checked) {
    document.querySelectorAll('[data-map-key="' + mapKey + '"]').forEach(function(cb) {
        cb.checked = checked;
        var card = cb.closest('.map-card');
        if (card) card.classList.toggle('selected', checked);
    });
}

function saveMapCycle() {
    var outputFile = document.getElementById('outputFile').value;
    var statusDiv = document.getElementById('saveStatus');
    
    if (rotationData.length === 0) {
        statusDiv.innerHTML = '<div class="alert alert-warning">No maps in rotation to save!</div>';
        return;
    }
    
    fetch('/api/mapcycle/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            rotation: rotationData,
            output_file: outputFile,
            format: 'advanced'
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            statusDiv.innerHTML = '<div class="alert alert-success"><i class="bi bi-check-circle"></i> ' + data.message + '</div>';
        } else {
            statusDiv.innerHTML = '<div class="alert alert-danger"><i class="bi bi-x-circle"></i> ' + data.message + '</div>';
        }
    })
    .catch(err => {
        statusDiv.innerHTML = '<div class="alert alert-danger"><i class="bi bi-x-circle"></i> Error: ' + err + '</div>';
    });
}

function loadMapCycle() {
    // Load from the configured mapcycle file on the server
    const outputFile = document.getElementById('outputFile').value;
    const statusDiv = document.getElementById('saveStatus');
    statusDiv.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split"></i> Loading from server file...</div>';
    
    fetch('/api/mapcycle/load_file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({file_path: outputFile})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.rotation) {
            rotationData = data.rotation;
            renderRotation();
            statusDiv.innerHTML = '<div class="alert alert-success"><i class="bi bi-check-circle"></i> Loaded ' + data.rotation.length + ' maps from ' + outputFile + '</div>';
        } else {
            statusDiv.innerHTML = '<div class="alert alert-warning"><i class="bi bi-exclamation-triangle"></i> ' + (data.message || 'File not found or empty') + '. You can also load from a local file:</div>';
            document.getElementById('fileInput').click();
        }
    })
    .catch(err => {
        statusDiv.innerHTML = '<div class="alert alert-danger">Error: ' + err + '</div>';
    });
}

function loadMapCycleFromFile() {
    document.getElementById('fileInput').click();
}

function handleFileLoad(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        fetch('/api/mapcycle/parse', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content: content})
        })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.rotation) {
                rotationData = data.rotation;
                renderRotation();
                document.getElementById('saveStatus').innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Loaded ' + data.rotation.length + ' maps from file</div>';
            }
        });
    };
    reader.readAsText(file);
    event.target.value = '';
}

function browseOutputFile() {
    document.getElementById('outputFile').focus();
}

// Named MapCycle Presets
function loadNamedPresets() {
    fetch('/api/mapcycle/named_presets')
    .then(r => r.json())
    .then(data => {
        const container = document.getElementById('namedPresetsContainer');
        const noPresets = document.getElementById('noNamedPresets');
        const presets = data.presets || {};
        const names = Object.keys(presets);
        
        if (names.length === 0) {
            container.innerHTML = '<div class="text-muted small text-center py-2" id="noNamedPresets">No saved presets yet</div>';
            return;
        }
        
        var html = '';
        names.forEach(function(name) {
            var count = presets[name].length;
            html += '<div class="d-flex justify-content-between align-items-center p-1 border-bottom border-secondary">';
            html += '<div><strong class="small">' + name + '</strong> <span class="badge bg-secondary">' + count + ' maps</span></div>';
            html += '<div class="btn-group btn-group-sm">';
            html += '<button class="btn btn-outline-info btn-sm py-0 named-preset-load" data-name="' + name.replace(/"/g, '&quot;') + '"><i class="bi bi-folder2-open"></i></button>';
            html += '<button class="btn btn-outline-danger btn-sm py-0 named-preset-delete" data-name="' + name.replace(/"/g, '&quot;') + '"><i class="bi bi-trash"></i></button>';
            html += '</div></div>';
        });
        container.innerHTML = html;
        
        // Attach event listeners
        container.querySelectorAll('.named-preset-load').forEach(function(btn) {
            btn.addEventListener('click', function() { loadNamedPreset(this.dataset.name); });
        });
        container.querySelectorAll('.named-preset-delete').forEach(function(btn) {
            btn.addEventListener('click', function() { deleteNamedPreset(this.dataset.name); });
        });
    });
}

// Custom Scenarios
var pendingCustomScenario = null;

function loadCustomScenarios() {
    fetch('/api/custom_scenarios')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var container = document.getElementById('customScenariosContainer');
        var scenarios = data.scenarios || [];
        
        if (scenarios.length === 0) {
            container.innerHTML = '<div class="text-muted small text-center py-1">No custom scenarios yet. Add mod maps or custom scenarios above.</div>';
            return;
        }
        
        var html = '';
        scenarios.forEach(function(s, idx) {
            html += '<div class="d-flex align-items-center gap-1 mb-1 p-1 border border-secondary rounded" style="background:#1a1d20;">';
            html += '<div class="flex-grow-1"><span class="small font-monospace text-info">' + s.scenario_id + '</span>';
            if (s.scenario_name && s.scenario_name !== s.scenario_id) {
                html += ' <span class="text-muted small">(' + s.scenario_name + ')</span>';
            }
            html += '</div>';
            html += '<button class="btn btn-outline-success btn-sm py-0 px-1 cs-add-btn" data-idx="' + idx + '" title="Add to rotation"><i class="bi bi-plus-lg"></i></button>';
            html += '<button class="btn btn-outline-danger btn-sm py-0 px-1 cs-del-btn" data-idx="' + idx + '" title="Delete"><i class="bi bi-trash"></i></button>';
            html += '</div>';
        });
        container.innerHTML = html;
        
        container.querySelectorAll('.cs-add-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var s = scenarios[parseInt(this.dataset.idx)];
                if (s) {
                    rotationData.push({
                        map_key: s.map_key || 'Custom',
                        map_name: s.map_key || 'Custom',
                        scenario_id: s.scenario_id,
                        scenario_name: s.scenario_name || s.scenario_id,
                        mode: s.mode || 'Custom',
                        lighting: 'Day',
                        max_players: 28
                    });
                    renderRotation();
                }
            });
        });
        container.querySelectorAll('.cs-del-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var s = scenarios[parseInt(this.dataset.idx)];
                if (s && confirm('Delete custom scenario "' + s.scenario_id + '"?')) {
                    fetch('/api/custom_scenarios/delete', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({scenario_id: s.scenario_id})
                    }).then(function() { loadCustomScenarios(); });
                }
            });
        });
    });
}

function addCustomScenario() {
    var scenarioId = document.getElementById('cs_scenario_id').value.trim();
    var scenarioName = document.getElementById('cs_scenario_name').value.trim();
    var mapKey = document.getElementById('cs_map_key').value.trim();
    var mode = document.getElementById('cs_mode').value.trim();
    
    if (!scenarioId) { alert('Scenario ID is required'); return; }
    
    fetch('/api/custom_scenarios/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scenario_id: scenarioId, scenario_name: scenarioName, map_key: mapKey, mode: mode || 'Custom'})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            document.getElementById('cs_scenario_id').value = '';
            document.getElementById('cs_scenario_name').value = '';
            document.getElementById('cs_map_key').value = '';
            document.getElementById('cs_mode').value = '';
            loadCustomScenarios();
        } else {
            alert(data.message || 'Error saving');
        }
    });
}

// MapCycle File Browser
var mapcycleFilesList = [];

function refreshMapcycleFiles() {
    var container = document.getElementById('mapcycleFilesContainer');
    container.innerHTML = '<div class="text-muted small text-center py-1">Loading...</div>';
    
    fetch('/api/mapcycle/list_files')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        mapcycleFilesList = data.files || [];
        
        if (mapcycleFilesList.length === 0) {
            container.innerHTML = '<div class="text-muted small text-center py-1">No mapcycle .txt files found in Config/Server</div>';
            return;
        }
        
        var html = '<div class="d-flex flex-wrap gap-1">';
        mapcycleFilesList.forEach(function(f, idx) {
            var badge = f.is_mapcycle ? 
                '<span class="badge bg-success" style="font-size:0.6rem;">' + f.entry_count + '</span>' :
                '<span class="badge bg-secondary" style="font-size:0.6rem;">?</span>';
            html += '<div class="d-flex align-items-center border border-secondary rounded px-2 py-1" style="background:#1a1d20;gap:4px;">';
            html += '<span class="small font-monospace" style="color:#0dcaf0;">' + f.name + '</span>';
            html += badge;
            html += '<button class="btn btn-outline-info btn-sm py-0 px-1 mc-load-btn" data-idx="' + idx + '" title="Load this file"><i class="bi bi-folder2-open"></i></button>';
            html += '<button class="btn btn-outline-primary btn-sm py-0 px-1 mc-select-btn" data-idx="' + idx + '" title="Set as save target"><i class="bi bi-pencil"></i></button>';
            html += '</div>';
        });
        html += '</div>';
        container.innerHTML = html;
        
        // Attach event listeners
        container.querySelectorAll('.mc-load-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var f = mapcycleFilesList[parseInt(this.dataset.idx)];
                if (f) loadMapcycleFile(f.path, f.name);
            });
        });
        container.querySelectorAll('.mc-select-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var f = mapcycleFilesList[parseInt(this.dataset.idx)];
                if (f) document.getElementById('outputFile').value = f.path;
            });
        });
    })
    .catch(function(err) {
        container.innerHTML = '<div class="text-danger small">Error: ' + err + '</div>';
    });
}

function loadMapcycleFile(path, name) {
    document.getElementById('outputFile').value = path;
    var statusDiv = document.getElementById('saveStatus');
    statusDiv.innerHTML = '<div class="alert alert-info py-1 small"><i class="bi bi-hourglass-split"></i> Loading ' + name + '...</div>';
    
    fetch('/api/mapcycle/load_file', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({file_path: path})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success && data.rotation) {
            rotationData = data.rotation;
            renderRotation();
            statusDiv.innerHTML = '<div class="alert alert-success py-1 small"><i class="bi bi-check-circle"></i> Loaded ' + data.rotation.length + ' maps from ' + name + '</div>';
        } else {
            statusDiv.innerHTML = '<div class="alert alert-warning py-1 small">' + (data.message || 'File empty or not found') + '</div>';
        }
    })
    .catch(function(err) {
        statusDiv.innerHTML = '<div class="alert alert-danger py-1 small">Error: ' + err + '</div>';
    });
}

function saveNamedPreset() {
    document.getElementById('namedPresetCount').textContent = rotationData.length;
    document.getElementById('namedPresetName').value = '';
    var modal = new bootstrap.Modal(document.getElementById('saveNamedPresetModal'));
    modal.show();
}

function confirmSaveNamedPreset() {
    const name = document.getElementById('namedPresetName').value.trim();
    if (!name) { alert('Please enter a preset name'); return; }
    
    fetch('/api/mapcycle/named_presets/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, rotation: rotationData})
    })
    .then(r => r.json())
    .then(data => {
        var modal = bootstrap.Modal.getInstance(document.getElementById('saveNamedPresetModal'));
        modal.hide();
        if (data.success) {
            document.getElementById('saveStatus').innerHTML = '<div class="alert alert-success"><i class="bi bi-check-circle"></i> ' + data.message + '</div>';
            loadNamedPresets();
        }
    });
}

function loadNamedPreset(name) {
    fetch('/api/mapcycle/named_presets')
    .then(r => r.json())
    .then(data => {
        if (data.presets && data.presets[name]) {
            rotationData = JSON.parse(JSON.stringify(data.presets[name]));
            renderRotation();
            document.getElementById('saveStatus').innerHTML = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> Loaded preset: ' + name + '</div>';
        }
    });
}

function deleteNamedPreset(name) {
    if (!confirm('Delete preset "' + name + '"?')) return;
    fetch('/api/mapcycle/named_presets/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name})
    })
    .then(r => r.json())
    .then(data => { loadNamedPresets(); });
}

// Preset cycles
const presetCycles = {
    pvp_push: [
        {map_key: 'Farmhouse', scenario_id: 'Scenario_Farmhouse_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
        {map_key: 'Crossing', scenario_id: 'Scenario_Crossing_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
        {map_key: 'Hideout', scenario_id: 'Scenario_Hideout_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
        {map_key: 'Precinct', scenario_id: 'Scenario_Precinct_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
        {map_key: 'Summit', scenario_id: 'Scenario_Summit_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
        {map_key: 'Refinery', scenario_id: 'Scenario_Refinery_Push_Security', scenario_name: 'Push Security', mode: 'Push'},
    ],
    coop: [
        {map_key: 'Farmhouse', scenario_id: 'Scenario_Farmhouse_Checkpoint_Security', scenario_name: 'Checkpoint Security', mode: 'Checkpoint', lighting: 'Night'},
        {map_key: 'Hideout', scenario_id: 'Scenario_Hideout_Checkpoint_Security', scenario_name: 'Checkpoint Security', mode: 'Checkpoint', lighting: 'Night'},
        {map_key: 'Crossing', scenario_id: 'Scenario_Crossing_Checkpoint_Security', scenario_name: 'Checkpoint Security', mode: 'Checkpoint', lighting: 'Night'},
    ],
    tdm: [
        {map_key: 'Ministry', scenario_id: 'Scenario_Ministry_Team_Deathmatch', scenario_name: 'Team Deathmatch', mode: 'TDM'},
        {map_key: 'Crossing', scenario_id: 'Scenario_Crossing_Team_Deathmatch', scenario_name: 'Team Deathmatch', mode: 'TDM'},
        {map_key: 'Farmhouse', scenario_id: 'Scenario_Farmhouse_Team_Deathmatch', scenario_name: 'Team Deathmatch', mode: 'TDM'},
    ],
    skirmish: [
        {map_key: 'Crossing', scenario_id: 'Scenario_Crossing_Skirmish', scenario_name: 'Skirmish', mode: 'Skirmish'},
        {map_key: 'Farmhouse', scenario_id: 'Scenario_Farmhouse_Skirmish', scenario_name: 'Skirmish', mode: 'Skirmish'},
        {map_key: 'Hideout', scenario_id: 'Scenario_Hideout_Skirmish', scenario_name: 'Skirmish', mode: 'Skirmish'},
        {map_key: 'Precinct', scenario_id: 'Scenario_Precinct_Skirmish', scenario_name: 'Skirmish', mode: 'Skirmish'},
    ]
};

function loadPreset(presetName) {
    if (presetCycles[presetName]) {
        rotationData = JSON.parse(JSON.stringify(presetCycles[presetName]));
        rotationData.forEach(m => {
            m.max_players = 28;
        });
        renderRotation();
    }
}
</script>
"""

@app.route("/mapcycle")
def mapcycle_editor():
    """MapCycle Editor page"""
    mapcycle_path = bot.conf.get('mapcycle_file_path', 'MapCycle.txt')
    return render_page(render_template_string(
        MAPCYCLE_EDITOR_PAGE,
        map_categories=MAP_DATA,
        game_modes=GAME_MODES,
        mapcycle_path=mapcycle_path
    ))

@app.route("/maps")
def maps_page():
    return render_page(render_template_string(
        MAPS_PAGE,
        all_maps=HARDCODED_MAPS,
        pool=bot.map_pool
    ))

@app.route("/settings")
def settings():
    tab = request.args.get('tab', 'general')
    return render_page(render_template_string(SETTINGS_TEMPLATE, config=bot.conf, tab=tab, defaults=DEFAULT_CONFIG))

@app.route("/save_settings", methods=["POST"])
def save_settings():
    tab = request.form.get('tab', 'general')
    
    if tab == 'paths':
        bot.conf['server_dir'] = request.form.get('server_dir')
        bot.conf['steamcmd_dir'] = request.form.get('steamcmd_dir')
        bot.conf['presets_file'] = request.form.get('presets_file')
        bot.conf['home'] = request.form.get('home')
        # Refresh server manager paths
        bot.server_manager.refresh_paths()
    elif tab == 'performance':
        # Checkbox handling - if not present in form, it's unchecked
        bot.conf['timerslack_enabled'] = request.form.get('timerslack_enabled') == 'on'
        bot.conf['timerslack_system_user'] = request.form.get('timerslack_system_user', '')
    else:
        bot.conf['rtv_threshold_percent'] = float(request.form.get('rtv_threshold_percent'))
        bot.conf['rtv_min_players'] = int(request.form.get('rtv_min_players'))
        bot.conf['steam_api_key'] = request.form.get('steam_api_key')
        bot.conf['log_file_path'] = request.form.get('log_file_path')
        bot.conf['mapcycle_file_path'] = request.form.get('mapcycle_file_path')
        bot.conf['map_source_mode'] = int(request.form.get('map_source_mode'))
        bot.conf['rcon']['ip'] = request.form.get('rcon_ip')
        bot.conf['rcon']['port'] = int(request.form.get('rcon_port'))
        bot.conf['rcon']['password'] = request.form.get('rcon_password')
        bot.conf['query_port'] = int(request.form.get('query_port'))
        # Global tokens
        if request.form.get('global_gslt_token') is not None:
            bot.conf['global_gslt_token'] = request.form.get('global_gslt_token', '').strip()
        if request.form.get('global_gamestats_token') is not None:
            bot.conf['global_gamestats_token'] = request.form.get('global_gamestats_token', '').strip()
    
    bot.save_config()
    return redirect(url_for('settings', tab=tab))

@app.route("/api/custom_scenarios", methods=["GET"])
def api_custom_scenarios_get():
    """Get all custom scenarios"""
    return jsonify({"success": True, "scenarios": bot.conf.get('custom_scenarios', [])})

@app.route("/api/custom_scenarios/save", methods=["POST"])
def api_custom_scenarios_save():
    """Save a custom scenario"""
    data = request.json
    scenario_id = data.get('scenario_id', '').strip()
    scenario_name = data.get('scenario_name', '').strip()
    map_key = data.get('map_key', '').strip()
    mode = data.get('mode', 'Custom').strip()
    
    if not scenario_id:
        return jsonify({"success": False, "message": "Scenario ID required"})
    
    if 'custom_scenarios' not in bot.conf:
        bot.conf['custom_scenarios'] = []
    
    # Check if already exists
    existing = [s for s in bot.conf['custom_scenarios'] if s.get('scenario_id') == scenario_id]
    if existing:
        return jsonify({"success": False, "message": "Scenario already exists"})
    
    bot.conf['custom_scenarios'].append({
        'scenario_id': scenario_id,
        'scenario_name': scenario_name or scenario_id,
        'map_key': map_key or scenario_id.split('_')[1] if '_' in scenario_id else 'Custom',
        'mode': mode,
        'lighting': 'Day'
    })
    bot.save_config()
    return jsonify({"success": True, "message": "Custom scenario saved"})

@app.route("/api/custom_scenarios/delete", methods=["POST"])
def api_custom_scenarios_delete():
    """Delete a custom scenario"""
    data = request.json
    scenario_id = data.get('scenario_id', '').strip()
    
    if 'custom_scenarios' in bot.conf:
        bot.conf['custom_scenarios'] = [s for s in bot.conf['custom_scenarios'] if s.get('scenario_id') != scenario_id]
        bot.save_config()
    
    return jsonify({"success": True})

@app.route("/mappictures/<path:filename>")
def serve_map_picture(filename):
    """Serve map thumbnail images from the mappictures directory"""
    from flask import send_from_directory, abort
    if not os.path.exists(MAP_PICTURES_DIR):
        abort(404)
    return send_from_directory(MAP_PICTURES_DIR, filename)

@app.route("/api/map_thumbnails")
def api_map_thumbnails():
    """Get available map thumbnails"""
    available = {}
    if os.path.exists(MAP_PICTURES_DIR):
        for map_key, base_name in MAP_THUMBNAIL_NAMES.items():
            for ext in ['png', 'jpg', 'jpeg', 'webp']:
                fname = base_name + '.' + ext
                if os.path.exists(os.path.join(MAP_PICTURES_DIR, fname)):
                    available[map_key] = '/mappictures/' + fname
                    break
    return jsonify(available)

@app.route("/api/browse_directory")
def browse_directory():
    """API endpoint to browse directories"""
    path = request.args.get('path', '/')
    
    # Security: only allow browsing within allowed paths
    try:
        # Resolve the path
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(abs_path):
            return jsonify({'error': 'Path does not exist', 'items': []})
        
        if not os.path.isdir(abs_path):
            return jsonify({'error': 'Not a directory', 'items': []})
        
        items = []
        try:
            for item in os.listdir(abs_path):
                item_path = os.path.join(abs_path, item)
                is_dir = os.path.isdir(item_path)
                items.append({
                    'name': item,
                    'path': item_path,
                    'is_dir': is_dir
                })
        except PermissionError:
            return jsonify({'error': 'Permission denied', 'items': []})
        
        # Sort: directories first, then files
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
        return jsonify({'current_path': abs_path, 'items': items})
    except Exception as e:
        return jsonify({'error': str(e), 'items': []})

# Server Management Routes
@app.route("/server/install_steamcmd", methods=["POST"])
def install_steamcmd():
    # Run installation in background thread to allow polling
    def background_install():
        try:
            bot.server_manager.install_steamcmd()
        except Exception as e:
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["steamcmd"]["error"] = str(e)
                INSTALLATION_STATUS["steamcmd"]["complete"] = True
                INSTALLATION_STATUS["steamcmd"]["running"] = False
    
    threading.Thread(target=background_install, daemon=False).start()
    return redirect(url_for('server_page'))

@app.route("/server/install_server", methods=["POST"])
def install_server():
    # Run installation in background thread to allow polling
    def background_install():
        try:
            bot.server_manager.install_server()
        except Exception as e:
            with INSTALLATION_LOCK:
                INSTALLATION_STATUS["server"]["error"] = str(e)
                INSTALLATION_STATUS["server"]["complete"] = True
                INSTALLATION_STATUS["server"]["running"] = False
    
    threading.Thread(target=background_install, daemon=False).start()
    return redirect(url_for('server_page'))

@app.route("/server/start", methods=["POST"])
def start_server():
    preset = request.form.get('preset')
    result = bot.server_manager.start_server(preset)
    return redirect(url_for('server_page'))

@app.route("/server/start_watchdog", methods=["POST"])
def start_watchdog():
    preset = request.form.get('preset')
    result = bot.server_manager.start_watchdog(preset)
    return redirect(url_for('server_page'))

@app.route("/server/stop", methods=["POST"])
def stop_server():
    result = bot.server_manager.stop_server()
    return redirect(url_for('server_page'))

@app.route("/server/stop_watchdog", methods=["POST"])
def stop_watchdog():
    result = bot.server_manager.stop_watchdog()
    return redirect(url_for('server_page'))

# API Endpoints for real-time updates
@app.route("/api/console")
def api_console():
    """Get server console output"""
    console = bot.server_manager.get_console_output()
    running = bot.server_manager.is_running()
    return jsonify({"console": console, "running": running})

@app.route("/api/installation_status")
def api_installation_status():
    """Get installation status and logs"""
    global INSTALLATION_STATUS
    
    with INSTALLATION_LOCK:
        status = deepcopy(INSTALLATION_STATUS)
    
    # Try to read from steamcmd log file as fallback
    steamcmd_log = os.path.join(STEAMCMD_DIR, "logs", "console_log.txt")
    if os.path.exists(steamcmd_log):
        try:
            with open(steamcmd_log, 'r') as f:
                log_content = f.read()
                # Append log content if we have it
                if log_content and not status["server"]["running"]:
                    if status["server"]["output"] and len(status["server"]["output"]) < 100:
                        status["server"]["output"] += "\n--- Log file content ---\n" + log_content[-2000:]
        except:
            pass
    
    return jsonify(status)

# ============================================================
# MAPCYCLE EDITOR API ENDPOINTS
# ============================================================

@app.route("/api/mapcycle/current")
def api_mapcycle_current():
    """Get current map rotation from the actual mapcycle file"""
    mapcycle_path = bot.conf.get('mapcycle_file_path', '')
    
    # Try to find and read the actual mapcycle file
    content = None
    paths_to_try = [mapcycle_path]
    if mapcycle_path and not os.path.isabs(mapcycle_path):
        server_dir = bot.conf.get('server_dir', SERVER_DIR)
        paths_to_try.append(os.path.join(server_dir, "Insurgency", "Config", "Server", mapcycle_path))
        paths_to_try.append(os.path.join(SCRIPT_DIR, mapcycle_path))
    
    for path in paths_to_try:
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                break
            except:
                pass
    
    if content:
        rotation = _parse_mapcycle_content(content)
    else:
        rotation = []
    
    return jsonify({
        "success": True,
        "rotation": rotation,
        "source_file": mapcycle_path
    })

@app.route("/api/mapcycle/save", methods=["POST"])
def api_mapcycle_save():
    """Save map cycle to file"""
    data = request.json
    rotation = data.get('rotation', [])
    output_file = data.get('output_file', 'MapCycle.txt')
    format_type = data.get('format', 'simple')
    
    # Resolve the full path
    if os.path.isabs(output_file):
        full_path = output_file
    else:
        # Relative to server dir
        full_path = os.path.join(SERVER_DIR, "Insurgency", "Config", "Server", output_file)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    try:
        lines = []
        for map_data in rotation:
            scenario_id = map_data.get('scenario_id', '')
            lighting = map_data.get('lighting') or 'Day'
            
            if not scenario_id:
                continue
            
            # Always use proper format: (Scenario="...",Lighting="...")
            params = []
            params.append('Scenario="' + scenario_id + '"')
            params.append('Lighting="' + lighting + '"')
            lines.append('(' + ','.join(params) + ')')
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        # Update config if it's the default path
        if output_file == 'MapCycle.txt' or output_file.endswith('/MapCycle.txt'):
            bot.conf['mapcycle_file_path'] = full_path
            bot.save_config()
        
        return jsonify({
            "success": True,
            "message": f"Saved {len(rotation)} maps to {output_file}"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error saving: {str(e)}"
        })

@app.route("/api/mapcycle/list_files")
def api_mapcycle_list_files():
    """List .txt files in the Config/Server directory that are likely mapcycle files"""
    server_dir = bot.conf.get('server_dir', SERVER_DIR)
    config_server_dir = os.path.join(server_dir, "Insurgency", "Config", "Server")
    
    # Also check the script directory's Config/Server
    alt_dirs = [
        config_server_dir,
        os.path.join(SCRIPT_DIR, "Config", "Server"),
        os.path.join(SCRIPT_DIR, "Config"),
    ]
    
    # Known non-mapcycle files to exclude
    excluded_names = {
        'admins.txt', 'admin.txt', 'bans.txt', 'ban.txt', 'motd.txt',
        'mods.txt', 'mod.txt', 'game.ini', 'engine.ini', 'gameusersettings.ini',
        'input.ini', 'scalability.ini', 'hardware.ini'
    }
    
    files = []
    for dir_path in alt_dirs:
        if os.path.isdir(dir_path):
            try:
                for fname in sorted(os.listdir(dir_path)):
                    if fname.lower().endswith('.txt') and fname.lower() not in excluded_names:
                        full_path = os.path.join(dir_path, fname)
                        # Check if it looks like a mapcycle (contains Scenario_ lines)
                        is_mapcycle = False
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(2000)
                                if 'Scenario_' in content or 'Scenario=' in content:
                                    is_mapcycle = True
                        except:
                            pass
                        
                        # Count entries
                        entry_count = count_mapcycle_entries(full_path)
                        
                        files.append({
                            'name': fname,
                            'path': full_path,
                            'dir': dir_path,
                            'is_mapcycle': is_mapcycle,
                            'entry_count': entry_count
                        })
            except PermissionError:
                pass
    
    return jsonify({'success': True, 'files': files, 'config_server_dir': config_server_dir})

@app.route("/api/mapcycle/load_file", methods=["POST"])
def api_mapcycle_load_file():
    """Load a mapcycle from a specific file path"""
    data = request.json
    file_path = data.get('file_path', '')
    
    if not file_path:
        return jsonify({"success": False, "message": "No file path provided"})
    
    # Try to resolve path
    paths_to_try = [file_path]
    if not os.path.isabs(file_path):
        server_dir = bot.conf.get('server_dir', SERVER_DIR)
        paths_to_try.append(os.path.join(server_dir, "Insurgency", "Config", "Server", file_path))
        paths_to_try.append(os.path.join(SCRIPT_DIR, file_path))
    
    content = None
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                break
            except:
                pass
    
    if content is None:
        return jsonify({"success": False, "message": f"File not found: {file_path}"})
    
    # Parse the content using same logic as api_mapcycle_parse
    rotation = _parse_mapcycle_content(content)
    return jsonify({"success": True, "rotation": rotation, "count": len(rotation)})

@app.route("/api/mapcycle/named_presets", methods=["GET"])
def api_mapcycle_named_presets_get():
    """Get all named mapcycle presets"""
    presets = bot.conf.get('mapcycle_presets', {})
    return jsonify({"success": True, "presets": presets})

@app.route("/api/mapcycle/named_presets/save", methods=["POST"])
def api_mapcycle_named_presets_save():
    """Save current rotation as a named mapcycle preset"""
    data = request.json
    preset_name = data.get('name', '').strip()
    rotation = data.get('rotation', [])
    
    if not preset_name:
        return jsonify({"success": False, "message": "Preset name required"})
    
    if 'mapcycle_presets' not in bot.conf:
        bot.conf['mapcycle_presets'] = {}
    
    bot.conf['mapcycle_presets'][preset_name] = rotation
    bot.save_config()
    
    return jsonify({"success": True, "message": f"Saved preset '{preset_name}' with {len(rotation)} maps"})

@app.route("/api/mapcycle/named_presets/delete", methods=["POST"])
def api_mapcycle_named_presets_delete():
    """Delete a named mapcycle preset"""
    data = request.json
    preset_name = data.get('name', '').strip()
    
    if preset_name and 'mapcycle_presets' in bot.conf:
        bot.conf['mapcycle_presets'].pop(preset_name, None)
        bot.save_config()
    
    return jsonify({"success": True})

def _parse_mapcycle_content(content):
    """Parse mapcycle file content into rotation list"""
    rotation = []
    map_trans = {
        "Crossing": "Canyon", "Hideout": "Town", "Hillside": "Sinjar",
        "Outskirts": "Compound", "Summit": "Mountain", "Tideway": "Buhriz", "Refinery": "Oilfield",
    }
    
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith(('//', '#')):
            continue
        
        scenario_id = ""
        lighting = None
        max_players = None
        
        if line.startswith('('):
            scen_match = re.search(r'Scenario="([^"]+)"', line)
            if scen_match:
                scenario_id = scen_match.group(1)
            light_match = re.search(r'Lighting="([^"]+)"', line)
            if light_match:
                lighting = light_match.group(1)
            mp_match = re.search(r'MaxPlayers=(\d+)', line)
            if mp_match:
                max_players = int(mp_match.group(1))
        else:
            scenario_id = line
        
        if scenario_id:
            parts = scenario_id.split('_')
            if len(parts) >= 2:
                map_key = parts[1]
                map_name = map_trans.get(map_key, map_key)
                scenario_name = scenario_id.replace('Scenario_', '').replace('_', ' ')
                mode = "Unknown"
                supports_lighting = False
                cat_key = map_key
                
                for ck, cat_data in MAP_DATA.items():
                    for scen in cat_data.get('scenarios', []):
                        if scen['id'] == scenario_id:
                            scenario_name = scen['name']
                            mode = scen['mode']
                            supports_lighting = scen['supports_lighting']
                            cat_key = ck
                            break
                
                rotation.append({
                    'map_key': cat_key,
                    'map_name': map_name,
                    'scenario_id': scenario_id,
                    'scenario_name': scenario_name,
                    'mode': mode,
                    'lighting': lighting or 'Day',
                    'supports_lighting': supports_lighting,
                    'max_players': max_players or 28
                })
    return rotation

@app.route("/api/mapcycle/parse", methods=["POST"])
def api_mapcycle_parse():
    """Parse map cycle content from file"""
    data = request.json
    content = data.get('content', '')
    rotation = _parse_mapcycle_content(content)
    return jsonify({
        "success": True,
        "rotation": rotation
    })

def _write_presets_file(presets):
    """Write presets dict to the presets file"""
    presets_file = bot.server_manager.presets_file
    with open(presets_file, 'w') as f:
        f.write("# --- Insurgency: Sandstorm Server Presets ---\n")
        for name, preset_args in presets.items():
            f.write(f"\n{name}_args = [\n")
            for arg in preset_args:
                f.write(f'    "{arg}",\n')
            f.write("]\n")

@app.route("/server/create_preset", methods=["POST"])
def create_preset():
    preset_name = request.form.get('preset_name', '').strip()
    # Sanitize preset name: replace spaces/slashes with underscores
    preset_name = sanitize_preset_name(preset_name)
    
    # Build map URL from dropdowns or manual entry
    map_url_manual = request.form.get('map_url_manual', '').strip()
    map_key = request.form.get('map_key', '').strip()
    scenario_id = request.form.get('scenario_id', '').strip()
    max_players = request.form.get('max_players', '28').strip()
    server_password = request.form.get('server_password', '').strip()
    
    if map_url_manual:
        map_url = map_url_manual
    elif map_key and scenario_id:
        map_url = f"{map_key}?Scenario={scenario_id}?MaxPlayers={max_players}"
        if server_password:
            map_url += f"?Password={server_password}"
    else:
        return redirect(url_for('server_page'))
    
    port = request.form.get('port', '27102').strip()
    query_port = request.form.get('query_port', '27131').strip()
    hostname = request.form.get('hostname', 'Sandstorm Server').strip()
    rcon_password = request.form.get('rcon_password', '').strip()
    rcon_port = request.form.get('rcon_port', '27015').strip()
    mapcycle_file = request.form.get('mapcycle_file', 'MapCycle.txt').strip()
    admin_list = request.form.get('admin_list', 'Admins.txt').strip()
    motd_file = request.form.get('motd_file', '').strip()
    
    # Tokens - use global if checkbox checked
    gslt_token = request.form.get('gslt_token', '').strip()
    gamestats_token = request.form.get('gamestats_token', '').strip()
    use_global_gslt = request.form.get('use_global_gslt') == 'on'
    use_global_gamestats = request.form.get('use_global_gamestats') == 'on'
    if use_global_gslt:
        gslt_token = bot.conf.get('global_gslt_token', '')
    if use_global_gamestats:
        gamestats_token = bot.conf.get('global_gamestats_token', '')
    
    # Mutators
    mutators = request.form.getlist('mutators')
    
    # Extra flags
    enable_log = request.form.get('enable_log') == 'on'
    enable_gamestats = request.form.get('enable_gamestats') == 'on'
    enable_mods = request.form.get('enable_mods') == 'on'
    official_rules = request.form.get('official_rules') == 'on'
    
    extra_args = request.form.get('extra_args', '').strip()
    
    if not preset_name:
        return redirect(url_for('server_page'))
    
    # Build preset arguments
    args = [map_url]
    args.append(f"-Port={port}")
    args.append(f"-QueryPort={query_port}")
    if enable_log:
        args.append("-log")
    args.append(f"-hostname={hostname}")
    if mapcycle_file:
        args.append(f"-MapCycle={mapcycle_file}")
    if admin_list:
        args.append(f"-AdminList={admin_list}")
    if motd_file:
        args.append(f"-motd={motd_file}")
    if rcon_password:
        args.append("-Rcon")
        args.append(f"-RconPassword={rcon_password}")
        args.append(f"-RconListenPort={rcon_port}")
    if gslt_token:
        args.append(f"-GSLTToken={gslt_token}")
    if gamestats_token:
        args.append(f"-GameStatsToken={gamestats_token}")
    if enable_gamestats:
        args.append("-GameStats")
    if enable_mods:
        args.append("-Mods")
    if official_rules:
        args.append("-ruleset=OfficialRules")
    if mutators:
        args.append(f"-mutators={','.join(mutators)}")
    if extra_args:
        for part in extra_args.split():
            args.append(part)
    
    # Save to presets file
    presets = bot.server_manager.load_presets()
    presets[preset_name] = args
    _write_presets_file(presets)
    
    return redirect(url_for('server_page'))

@app.route("/server/delete_preset", methods=["POST"])
def delete_preset():
    preset_name = request.form.get('preset_name', '').strip()
    
    if preset_name:
        presets = bot.server_manager.load_presets()
        if preset_name in presets:
            del presets[preset_name]
            _write_presets_file(presets)
    
    return redirect(url_for('server_page'))

@app.route("/server/duplicate_preset", methods=["POST"])
def duplicate_preset():
    preset_name = request.form.get('preset_name', '').strip()
    
    if preset_name:
        presets = bot.server_manager.load_presets()
        if preset_name in presets:
            # Find a unique name
            new_name = preset_name + "_copy"
            counter = 2
            while new_name in presets:
                new_name = f"{preset_name}_copy{counter}"
                counter += 1
            presets[new_name] = list(presets[preset_name])
            _write_presets_file(presets)
    
    return redirect(url_for('server_page'))

@app.route("/server/update_preset", methods=["POST"])
def update_preset():
    preset_name = request.form.get('preset_name', '').strip()
    preset_args_str = request.form.get('preset_args', '').strip()
    
    if preset_name and preset_args_str:
        # Parse the args (one per line)
        args = []
        for line in preset_args_str.split('\n'):
            line = line.strip().strip(',').strip('"').strip("'")
            if line:
                args.append(line)
        
        # Update in file
        presets = bot.server_manager.load_presets()
        presets[preset_name] = args
        _write_presets_file(presets)
    
    return redirect(url_for('server_page'))

@app.route("/server/save_global_tokens", methods=["POST"])
def save_global_tokens():
    """Save global GSLT and GameStats tokens"""
    bot.conf['global_gslt_token'] = request.form.get('global_gslt_token', '').strip()
    bot.conf['global_gamestats_token'] = request.form.get('global_gamestats_token', '').strip()
    bot.save_config()
    return redirect(url_for('server_page'))

@app.route("/server/update_preset_structured", methods=["POST"])
def update_preset_structured():
    """Update a preset using the structured form fields"""
    preset_name = request.form.get('preset_name', '').strip()
    if not preset_name:
        return redirect(url_for('server_page'))
    
    map_url = request.form.get('map_url', '').strip()
    port = request.form.get('port', '27102').strip()
    query_port = request.form.get('query_port', '27131').strip()
    rcon_port = request.form.get('rcon_port', '27015').strip()
    hostname = request.form.get('hostname', '').strip()
    mapcycle_file = request.form.get('mapcycle_file', 'MapCycle.txt').strip()
    admin_list = request.form.get('admin_list', 'Admins.txt').strip()
    rcon_password = request.form.get('rcon_password', '').strip()
    gslt_token = request.form.get('gslt_token', '').strip()
    gamestats_token = request.form.get('gamestats_token', '').strip()
    enable_gamestats = request.form.get('enable_gamestats') == 'on'
    enable_mods = request.form.get('enable_mods') == 'on'
    
    args = []
    if map_url:
        args.append(map_url)
    args.append(f"-Port={port}")
    args.append(f"-QueryPort={query_port}")
    args.append("-log")
    if hostname:
        args.append(f"-hostname={hostname}")
    if mapcycle_file:
        args.append(f"-MapCycle={mapcycle_file}")
    if admin_list:
        args.append(f"-AdminList={admin_list}")
    if rcon_password:
        args.append("-Rcon")
        args.append(f"-RconPassword={rcon_password}")
        args.append(f"-RconListenPort={rcon_port}")
    if gslt_token:
        args.append(f"-GSLTToken={gslt_token}")
    if gamestats_token:
        args.append(f"-GameStatsToken={gamestats_token}")
    if enable_gamestats:
        args.append("-GameStats")
    if enable_mods:
        args.append("-Mods")
    
    presets = bot.server_manager.load_presets()
    presets[preset_name] = args
    _write_presets_file(presets)
    
    return redirect(url_for('server_page', edit=preset_name))

# API Routes
@app.route("/api/status")
def api_status():
    with bot.live_state_lock:
        p_count = bot.live_player_count
        players = deepcopy(bot.live_players)
        chats = list(bot.live_chat_buffer)
        srv = bot.live_server_details
    
    req = math.ceil(max(bot.min_players, p_count) * bot.rtv_thresh)
    uptime = str(datetime.now() - bot.start_time).split('.')[0]
    
    return jsonify({
        "player_count": p_count,
        "players": players,
        "rtv_current": len(bot.rtv_votes),
        "rtv_req": req,
        "uptime": uptime,
        "chat_log": chats,
        "server_name": srv['name'],
        "current_map": srv['map'],
        "server_ping": srv['ping']
    })

@app.route("/api/rcon", methods=["POST"])
def api_rcon():
    cmd = request.form.get('command')
    if not cmd:
        return jsonify({"output": "No command provided"})
    
    output = bot.rcon.send(cmd)
    
    if cmd.lower().startswith("say "):
        clean_msg = cmd[4:].strip()
        bot.inject_chat("Admin", clean_msg)
    else:
        bot.inject_chat("Admin [CMD]", cmd)
    
    return jsonify({"output": output})

# RTV and Game Routes
@app.route("/force_rtv")
def force_rtv():
    bot.change_map()
    return redirect(url_for('dashboard'))

@app.route("/travel", methods=["POST"])
def travel():
    target = request.form.get('map_name')
    is_night = (request.form.get('night_mode') == 'on')
    if target:
        if is_night:
            if "?Lighting=" not in target:
                target += "?Lighting=Night"
        else:
            if "?Lighting=" in target:
                target = target.split('?Lighting=')[0]
            target += "?Lighting=Day"
        bot.change_map(target)
    return redirect(url_for('dashboard'))

@app.route("/kick", methods=["POST"])
def kick():
    bot.rcon.send(f"kick {request.form.get('netid')} Admin_Kick")
    return redirect(url_for('dashboard'))

@app.route("/ban", methods=["POST"])
def ban():
    bot.rcon.send(f"banid {request.form.get('netid')} 60 Admin_Ban")
    return redirect(url_for('dashboard'))

@app.route("/bans")
def bans():
    resp = bot.rcon.send("listbans")
    b = re.findall(r'(SteamNWI:\d+)', resp) if resp else []
    HTML = """
    <div class="card">
        <div class="card-header">Ban Manager</div>
        <div class="card-body p-0">
            <table class="table table-dark table-hover mb-0">
                <thead><tr><th>Steam ID</th><th>Action</th></tr></thead>
                <tbody>
                {% for i in b %}
                <tr>
                    <td>{{i}}</td>
                    <form action="/unban" method="post">
                        <input type="hidden" name="netid" value="{{i}}">
                        <td><button class="btn btn-sm btn-success">Unban</button></td>
                    </form>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_page(render_template_string(HTML, b=b))

@app.route("/unban", methods=["POST"])
def unban():
    bot.rcon.send(f"unban {request.form.get('netid')}")
    return redirect(url_for('bans'))


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Start background threads
    threading.Thread(target=bot.run_log_loop, daemon=True).start()
    threading.Thread(target=bot.background_poller, daemon=True).start()
    
    # Run Flask app
    port = bot.conf.get('web_port', 5000)
    print(f"Starting Sandstorm Manager Web on port {port}...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
