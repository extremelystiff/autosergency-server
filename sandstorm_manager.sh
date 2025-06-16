#!/bin/bash

#================================================================
# Insurgency: Sandstorm - Linux Server Management Script
# Author: ExtremelyStiff
# Version: 1.7 - Enhanced Preset Editor (Stats, Rules, Mutators)
#================================================================

# --- Script Configuration ---
# CHOOSE YOUR MULTIPLEXER: "tmux" or "screen"
MULTIPLEXER="tmux"

STEAMCMD_DIR="$HOME/steamcmd"
SERVER_DIR="$HOME/sandstorm_server"
PRESETS_FILE="$HOME/sandstorm_presets.conf"
APP_ID="581330" # App ID for server download
SESSION_NAME="sandstorm"

# --- Color Codes for UI ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Master Scenario List (unchanged) ---
SCENARIO_LIST=$(cat << "EOF"
Scenario_Bab_Checkpoint_Insurgents
Scenario_Bab_Checkpoint_Security
Scenario_Bab_Domination
Scenario_Bab_Firefight_East
Scenario_Bab_Outpost
Scenario_Bab_Push_Insurgents
Scenario_Bab_Push_Security
Scenario_Bab_Ambush
Scenario_Bab_Survival
Scenario_Bab_Defusal
Scenario_Citadel_Ambush
Scenario_Citadel_Checkpoint_Insurgents
Scenario_Citadel_Checkpoint_Security
Scenario_Citadel_Domination
Scenario_Citadel_Firefight_East
Scenario_Citadel_Outpost
Scenario_Citadel_Push_Insurgents
Scenario_Citadel_Push_Security
Scenario_Citadel_Survival
Scenario_Citadel_Defusal
Scenario_Citadel_TDM_Small
Scenario_Citadel_Frontline
Scenario_Crossing_Ambush
Scenario_Crossing_Checkpoint_Insurgents
Scenario_Crossing_Checkpoint_Security
Scenario_Crossing_Domination
Scenario_Crossing_Firefight_West
Scenario_Crossing_Frontline
Scenario_Crossing_Outpost
Scenario_Crossing_Push_Insurgents
Scenario_Crossing_Push_Security
Scenario_Crossing_Skirmish
Scenario_Crossing_Team_Deathmatch
Scenario_Crossing_Defusal
Scenario_Crossing_FFA
Scenario_Farmhouse_Ambush
Scenario_Farmhouse_Checkpoint_Insurgents
Scenario_Farmhouse_Checkpoint_Security
Scenario_Farmhouse_Domination
Scenario_Farmhouse_Firefight_East
Scenario_Farmhouse_Firefight_West
Scenario_Farmhouse_Frontline
Scenario_Farmhouse_Push_Insurgents
Scenario_Farmhouse_Push_Security
Scenario_Farmhouse_Skirmish
Scenario_Farmhouse_Survival
Scenario_Farmhouse_Team_Deathmatch
Scenario_Farmhouse_Outpost
Scenario_Farmhouse_Defusal
Scenario_Gap_Ambush
Scenario_Gap_Checkpoint_Insurgents
Scenario_Gap_Checkpoint_Security
Scenario_Gap_Domination
Scenario_Gap_Firefight
Scenario_Gap_Frontline
Scenario_Gap_Outpost
Scenario_Gap_Push_Insurgents
Scenario_Gap_Push_Security
Scenario_Gap_Survival
Scenario_Gap_Defusal
Scenario_Gap_TDM
Scenario_LastLight_Push_Insurgents
Scenario_LastLight_Push_Security
Scenario_LastLight_Checkpoint_Insurgents
Scenario_LastLight_Checkpoint_Security
Scenario_LastLight_Domination
Scenario_LastLight_Ambush
Scenario_LastLight_Firefight
Scenario_LastLight_Survival
Scenario_LastLight_Frontline
Scenario_LastLight_Outpost
Scenario_LastLight_Defusal
Scenario_LastLight_Team_Deathmatch
Scenario_LastLight_Skirmish
Scenario_Hideout_Ambush
Scenario_Hideout_Checkpoint_Insurgents
Scenario_Hideout_Checkpoint_Security
Scenario_Hideout_Domination
Scenario_Hideout_Firefight_East
Scenario_Hideout_Firefight_West
Scenario_Hideout_Frontline
Scenario_Hideout_Push_Insurgents
Scenario_Hideout_Push_Security
Scenario_Hideout_Skirmish
Scenario_Hideout_Survival
Scenario_Hideout_Team_Deathmatch
Scenario_Hideout_Outpost
Scenario_Hideout_Defusal
Scenario_Hillside_Ambush
Scenario_Hillside_Checkpoint_Insurgents
Scenario_Hillside_Checkpoint_Security
Scenario_Hillside_Domination
Scenario_Hillside_Firefight_East
Scenario_Hillside_Firefight_West
Scenario_Hillside_Frontline
Scenario_Hillside_Outpost
Scenario_Hillside_Push_Insurgents
Scenario_Hillside_Push_Security
Scenario_Hillside_Skirmish
Scenario_Hillside_Survival
Scenario_Hillside_Team_Deathmatch
Scenario_Ministry_Ambush
Scenario_Ministry_Checkpoint_Insurgents
Scenario_Ministry_Checkpoint_Security
Scenario_Ministry_Domination
Scenario_Ministry_Firefight_A
Scenario_Ministry_Skirmish
Scenario_Ministry_Team_Deathmatch
Scenario_Ministry_Outpost
Scenario_Ministry_Survival
Scenario_Ministry_Defusal
Scenario_Outskirts_Checkpoint_Insurgents
Scenario_Outskirts_Checkpoint_Security
Scenario_Outskirts_Firefight_East
Scenario_Outskirts_Firefight_West
Scenario_Outskirts_Frontline
Scenario_Outskirts_Push_Insurgents
Scenario_Outskirts_Push_Security
Scenario_Outskirts_Skirmish
Scenario_Outskirts_Team_Deathmatch
Scenario_Outskirts_Survival
Scenario_Outskirts_Defusal
Scenario_Outskirts_Domination
Scenario_Outskirts_Outpost
Scenario_Outskirts_Ambush
Scenario_Precinct_Ambush
Scenario_Precinct_Checkpoint_Insurgents
Scenario_Precinct_Checkpoint_Security
Scenario_Precinct_Firefight_East
Scenario_Precinct_Firefight_West
Scenario_Precinct_Frontline
Scenario_Precinct_Push_Insurgents
Scenario_Precinct_Push_Security
Scenario_Precinct_Skirmish
Scenario_Precinct_Team_Deathmatch
Scenario_Precinct_Survival
Scenario_Precinct_Defusal
Scenario_Precinct_Domination_West
Scenario_Precinct_Domination_East
Scenario_Precinct_Outpost
Scenario_Precinct_FFA
Scenario_Refinery_Ambush
Scenario_Refinery_Checkpoint_Insurgents
Scenario_Refinery_Checkpoint_Security
Scenario_Refinery_Firefight_West
Scenario_Refinery_Frontline
Scenario_Refinery_Push_Insurgents
Scenario_Refinery_Push_Security
Scenario_Refinery_Skirmish
Scenario_Refinery_Team_Deathmatch
Scenario_Refinery_Survival
Scenario_Refinery_Defusal
Scenario_Refinery_Domination
Scenario_Refinery_Outpost
Scenario_Summit_Ambush_West
Scenario_Summit_Checkpoint_Insurgents
Scenario_Summit_Checkpoint_Security
Scenario_Summit_Firefight_East
Scenario_Summit_Firefight_West
Scenario_Summit_Frontline
Scenario_Summit_Push_Insurgents
Scenario_Summit_Push_Security
Scenario_Summit_Skirmish
Scenario_Summit_Team_Deathmatch
Scenario_Summit_Survival
Scenario_Summit_Domination
Scenario_Summit_Outpost
Scenario_Summit_Defusal
Scenario_Powerplant_Ambush
Scenario_PowerPlant_Checkpoint_Insurgents
Scenario_PowerPlant_Checkpoint_Security
Scenario_PowerPlant_Domination
Scenario_PowerPlant_Firefight_East
Scenario_PowerPlant_Firefight_West
Scenario_PowerPlant_Push_Insurgents
Scenario_PowerPlant_Push_Security
Scenario_PowerPlant_Survival
Scenario_PowerPlant_Frontline
Scenario_PowerPlant_Outpost
Scenario_PowerPlant_FFA
Scenario_PowerPlant_Skirmish
Scenario_Tell_Ambush_West
Scenario_Tell_Checkpoint_Insurgents
Scenario_Tell_Checkpoint_Security
Scenario_Tell_Domination_East
Scenario_Tell_Firefight_East
Scenario_Tell_Firefight_West
Scenario_Tell_Outpost
Scenario_Tell_Push_Insurgents
Scenario_Tell_Push_Security
Scenario_Tell_Survival
Scenario_Tell_Frontline
Scenario_Tell_Defusal
Scenario_Tell_FFA
Scenario_Tideway_Checkpoint_Insurgents
Scenario_Tideway_Checkpoint_Security
Scenario_Tideway_Domination
Scenario_Tideway_Firefight_West
Scenario_Tideway_Frontline
Scenario_Tideway_Push_Insurgents
Scenario_Tideway_Push_Security
Scenario_Tideway_Survival
Scenario_Tideway_Outpost
Scenario_Tideway_Ambush
Scenario_Tideway_Defusal
Scenario_Prison_Checkpoint_Insurgents
Scenario_Prison_Checkpoint_Security
Scenario_Prison_Domination
Scenario_Prison_Firefight
Scenario_Prison_Ambush
Scenario_Prison_Survival
Scenario_Prison_Push_Insurgents
Scenario_Prison_Push_Security
Scenario_Prison_Defusal
Scenario_Prison_TDM
Scenario_Prison_FFA
Scenario_Prison_Skirmish
Scenario_Trainyard_Checkpoint_Insurgents
Scenario_Trainyard_Checkpoint_Security
Scenario_Trainyard_Push_Insurgents
Scenario_Trainyard_Push_Security
Scenario_Trainyard_Firefight_West
Scenario_Trainyard_Domination_West
Scenario_Trainyard_Frontline
Scenario_Trainyard_Defusal_West
Scenario_Trainyard_Survival
Scenario_Trainyard_Outpost
Scenario_Trainyard_Firefight_East
Scenario_Trainyard_Domination_East
Scenario_Trainyard_Defusal_East
Scenario_Forest_Push_Insurgents
Scenario_Forest_Push_Security
Scenario_Forest_Firefight_East
Scenario_Forest_Firefight_West
Scenario_Forest_Survival
Scenario_Forest_Ambush
Scenario_Forest_FFA
Scenario_Forest_Defusal
Scenario_Forest_TDM
Scenario_Forest_Domination
Scenario_Forest_Frontline
Scenario_Forest_Skirmish
Scenario_Forest_Checkpoint_Insurgents
Scenario_Forest_Checkpoint_Security
Scenario_Forest_Outpost
EOF
)

# --- Mutator List ---
# Based on the "Mutator Name" column from the provided documentation
# Descriptions can be added to an associative array if complex display is needed later.
MUTATOR_LIST_NAMES=(
    "All You Can Eat"
    "Anti-Materiel Only"
    "Bolt-Actions Only"
    "Arm's Race"
    "Broke"
    "Budget Antiquing"
    "Bullet Sponge"
    "Competitive"
    "Competitive Loadouts"
    "Desert Eagles Only"
    "Fast Movement"
    "Frenzy"
    "Fully Loaded"
    "Grenade Launchers Only"
    "Guerrillas"
    "Gunslingers"
    "Hardcore"
    "Headshots Only"
    "Hot Potato"
    "First Blood" # LMGOnly
    "Locked Aim"
    "Makarovs Only"
    "No Aim Down Sights"
    "No Death Camera"
    "No Drops"
    "No Third Person"
    "Official Rules" # Also a mutator name
    "Pistols Only"
    "Poor"
    "Shotguns Only"
    "Slow Capture Times"
    "Slow Movement"
    "Small Firefight"
    "Soldier of Fortune"
    "Special Operations"
    "Strapped"
    "Tactical Voice Chat"
    "Tie Breaker"
    "Ultralethal"
    "Vampirism"
    "Warlords"
    "WELRODS!"
    "Welrods Only"
)


# --- Helper Functions (mostly unchanged, some new ones for presets) ---
command_exists() { command -v "$1" >/dev/null 2>&1; }

ensure_config_files_exist() {
    mkdir -p "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer"
    mkdir -p "$SERVER_DIR/Insurgency/Config/Server"
    touch "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/Game.ini"
    touch "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/Engine.ini"
    touch "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/GameUserSettings.ini"
    touch "$SERVER_DIR/Insurgency/Config/Server/Admins.txt"
    touch "$SERVER_DIR/Insurgency/Config/Server/MapCycle.txt"
    touch "$SERVER_DIR/Insurgency/Config/Server/Mods.txt"
    touch "$SERVER_DIR/Insurgency/Config/Server/Motd.txt"
}

create_presets_file() {
    echo -e "${YELLOW}Creating new presets file with correct format at $PRESETS_FILE...${NC}"
    cat > "$PRESETS_FILE" <<- 'EOL'
# --- Insurgency: Sandstorm Server Presets ---
# This file defines startup configurations for your server.
# Each preset is a BASH ARRAY. This is important for handling arguments with spaces.
#
# FORMAT:
# PRESET_NAME_args=(
#   "MapURL?With?Options"
#   "-Argument1=Value1"
#   "-hostname=Server Name With Spaces"
# )
#
# Note the _args suffix on the variable name. It is required.

DefaultCoop_args=(
  "Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security?MaxPlayers=8"
  "-Port=27102"
  "-QueryPort=27131"
  "-log"
  "-hostname=My First Coop Server"
  "-MapCycle=MapCycle.txt"
  "-AdminList=Admins.txt"
)

DefaultPvP_args=(
  "Precinct?Scenario=Scenario_Precinct_Push_Security?MaxPlayers=28"
  "-Port=27102"
  "-QueryPort=27131"
  "-log"
  "-hostname=My First PvP Server"
  "-MapCycle=MapCycle.txt"
  "-AdminList=Admins.txt"
)
EOL
    echo -e "${GREEN}Presets file created. Please edit it to add your tokens and custom settings.${NC}"
}

_get_unique_maps_from_scenarios() {
    echo "$SCENARIO_LIST" | sed -n 's/^Scenario_\([^_]*\)_.*/\1/p' | sort -u
}

_display_map_cycle_content_simple() {
    local title="$1"
    shift
    local lines_to_display=("${@}")

    if [ ${#lines_to_display[@]} -eq 0 ]; then
        echo -e "${YELLOW}Map cycle is currently empty.${NC}"
        return
    fi
    echo -e "${CYAN}--- $title ---${NC}"
    for i in "${!lines_to_display[@]}"; do
        echo "$((i+1))) ${lines_to_display[$i]}"
    done
    echo "-------------------------"
}

# --- Installation and Updates (unchanged) ---
install_dependencies() {
    echo -e "${YELLOW}Checking/installing dependencies (tmux, screen, lib32gcc-s1)...${NC}"
    sudo apt-get update && sudo apt-get install -y tmux screen lib32gcc-s1
    echo -e "${GREEN}Dependencies are up to date.${NC}"
}
install_steamcmd() {
    if [ -d "$STEAMCMD_DIR" ]; then echo -e "${GREEN}SteamCMD already installed.${NC}"; return; fi
    echo -e "${YELLOW}Installing SteamCMD...${NC}"
    mkdir -p "$STEAMCMD_DIR"; cd "$STEAMCMD_DIR" || exit
    wget https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
    tar -xvf steamcmd_linux.tar.gz; rm steamcmd_linux.tar.gz
    echo -e "${GREEN}SteamCMD installed.${NC}"
}
install_sandstorm() {
    if [ -f "$SERVER_DIR/Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping" ]; then
        read -p "Sandstorm seems installed. Re-install/validate? (y/n): " choice
        if [[ "$choice" != "y" ]]; then return; fi
    fi
    echo -e "${YELLOW}Downloading/Validating Insurgency: Sandstorm server... This may take a while.${NC}"
    "$STEAMCMD_DIR/steamcmd.sh" +force_install_dir "$SERVER_DIR" +login anonymous +app_update "$APP_ID" validate +quit
    if [ ! -f "$PRESETS_FILE" ]; then create_presets_file; fi
    ensure_config_files_exist
    echo -e "${GREEN}Insurgency: Sandstorm server installed/validated successfully.${NC}"
}
update_sandstorm() {
    echo -e "${YELLOW}Updating Insurgency: Sandstorm server...${NC}"
    "$STEAMCMD_DIR/steamcmd.sh" +force_install_dir "$SERVER_DIR" +login anonymous +app_update "$APP_ID" +quit
    echo -e "${GREEN}Update complete.${NC}"
}


# --- Server Management (select_preset and start_server slightly adjusted for sourcing) ---
is_server_running() {
    if [[ "$MULTIPLEXER" == "tmux" ]]; then
        tmux has-session -t "$SESSION_NAME" 2>/dev/null
    else
        screen -list | grep -q "\.$SESSION_NAME\s"
    fi
}

select_preset() {
    if [ ! -f "$PRESETS_FILE" ]; then echo -e "${RED}Presets file not found! Please create it first (Option 7 -> Create or Manually Edit).${NC}"; return 1; fi
    local selected_preset_name_to_return=""
    ( # Subshell to isolate sourcing
      # Ensure preset arrays are loaded from the file for selection
      # This local sourcing won't affect the parent shell's preset arrays used by the manager
      source "$PRESETS_FILE"
      mapfile -t presets < <(compgen -v | grep '_args$' | sed 's/_args$//' | sort)

      if [ ${#presets[@]} -eq 0 ]; then echo -e "${RED}No valid presets found in $PRESETS_FILE. Ensure they end with '_args'.${NC}"; return 1; fi

      echo -e "${YELLOW}Select a startup preset:${NC}" >&2
      local selected_preset_name
      PS3="Select a preset: "
      select preset_name_opt in "${presets[@]}"; do
          if [[ -n "$preset_name_opt" ]]; then
              selected_preset_name_to_return="${preset_name_opt}_args" # This is what will be echoed
              break
          else
              echo -e "${RED}Invalid selection.${NC}"
              PS3="Enter your choice: " # Reset PS3
              return 1 # Error from subshell
          fi
      done
      PS3="Enter your choice: " # Reset PS3
      echo "$selected_preset_name_to_return" # Echo the chosen name for capture by caller
      return 0 # Success from subshell
    ) || return 1 # Propagate failure from subshell (e.g., if no presets found or user cancels)
}


start_server() {
    if is_server_running; then echo -e "${RED}Server is already running!${NC}"; return; fi

    local preset_array_name
    preset_array_name=$(select_preset) # Capture echoed name
    if [[ $? -ne 0 || -z "$preset_array_name" ]]; then
        echo -e "${RED}Preset selection cancelled or failed.${NC}"
        return
    fi


    # Source the presets file in the CURRENT shell to make the specific array accessible by nameref
    # This is important for declare -n to find the array.
    # The manage_startup_presets function handles its own global sourcing.
    source "$PRESETS_FILE"
    if ! declare -p "$preset_array_name" &>/dev/null; then
        echo -e "${RED}Error: Preset array '$preset_array_name' not found after sourcing. Check $PRESETS_FILE.${NC}"
        return
    fi
    declare -n args_array="$preset_array_name" # Bash 4.3+ nameref

    cd "$SERVER_DIR" || exit

    echo -e "${GREEN}Starting server with preset '${preset_array_name/_args/}'...${NC}"
    if [[ "$MULTIPLEXER" == "tmux" ]]; then
        tmux new-session -s "$SESSION_NAME" -d "./Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping" "${args_array[@]}"
    else
        local cmd_string="./Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping"
        for arg in "${args_array[@]}"; do cmd_string+=" \"$arg\""; done
        screen -S "$SESSION_NAME" -dm bash -c "$cmd_string"
    fi

    sleep 2
    if is_server_running; then echo -e "${GREEN}Server started successfully.${NC}"; else echo -e "${RED}Server failed to start. Use the Test-Run option to debug.${NC}"; fi
}

test_run_server() {
    if is_server_running; then echo -e "${RED}A server is already running. Please stop it first.${NC}"; return; fi

    local preset_array_name
    preset_array_name=$(select_preset)
    if [[ $? -ne 0 || -z "$preset_array_name" ]]; then
        echo -e "${RED}Preset selection cancelled or failed.${NC}"
        return
    fi

    source "$PRESETS_FILE"
    if ! declare -p "$preset_array_name" &>/dev/null; then
        echo -e "${RED}Error: Preset array '$preset_array_name' not found after sourcing. Check $PRESETS_FILE.${NC}"
        return
    fi
    declare -n args_array="$preset_array_name"

    cd "$SERVER_DIR" || exit

    clear
    echo -e "${YELLOW}--- TEST RUN ---${NC}"
    echo "Preset: ${preset_array_name/_args/}"
    echo "This will run the server directly in your terminal."
    echo "Any errors will be shown here. This is the best way to debug startup failures."
    echo "Press CTRL+C to stop the server when you are done."
    echo "----------------------------------------------------"
    echo -e "${CYAN}DEBUG: Current directory for execution: $(pwd)${NC}"
    echo -e "${CYAN}DEBUG: Arguments for server: ${args_array[*]}${NC}"
    echo -e "${CYAN}DEBUG: Full command to be executed:${NC}"
    local cmd_display="./Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping"
    for arg_disp in "${args_array[@]}"; do
        if [[ "$arg_disp" == *" "* ]]; then
            cmd_display+=" \"$arg_disp\""
        else
            cmd_display+=" $arg_disp"
        fi
    done
    echo "$cmd_display"
    read -p "Press [Enter] to begin the test run..."

    ./Insurgency/Binaries/Linux/InsurgencyServer-Linux-Shipping "${args_array[@]}"
    local exit_code=$?

    echo -e "${CYAN}DEBUG: Server process exited with code: $exit_code${NC}"
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}DEBUG: Server exited with an error code! Check for messages above.${NC}"
    else
        echo -e "${GREEN}DEBUG: Server exited cleanly (code 0), but it should have stayed running if configured correctly.${NC}"
    fi
    echo -e "\n${YELLOW}--- TEST RUN COMPLETE ---${NC}"
}

stop_server() { # Unchanged
    if ! is_server_running; then echo -e "${RED}Server is not running.${NC}"; return; fi
    echo -e "${YELLOW}Stopping server...${NC}"
    if [[ "$MULTIPLEXER" == "tmux" ]]; then
        tmux kill-session -t "$SESSION_NAME"
    else
        screen -S "$SESSION_NAME" -X quit
    fi
    echo -e "${GREEN}Server stopped.${NC}"
}
status_server() { # Unchanged
    if is_server_running; then
        echo -e "Server Status: ${GREEN}ONLINE${NC} (using $MULTIPLEXER)"
    else
        echo -e "Server Status: ${RED}OFFLINE${NC}"
    fi
}
view_console() { # Unchanged
    if ! is_server_running; then echo -e "${RED}Server is not running. Cannot view console.${NC}"; return; fi
    if [[ "$MULTIPLEXER" == "tmux" ]]; then
        echo -e "${YELLOW}Attaching to tmux session... Press CTRL+B then D to detach.${NC}"
        tmux attach-session -t "$SESSION_NAME"
    else
        echo -e "${YELLOW}Attaching to screen session... Press CTRL+A then D to detach.${NC}"
        screen -r "$SESSION_NAME"
    fi
}


# --- Configuration Management (edit_config_menu, generate_map_cycle unchanged) ---
edit_config_menu() {
    while true; do
        clear; echo "--- Edit Configuration Files ---"
        echo "1) Admins (Admins.txt)"; echo "2) Map Cycle (MapCycle.txt)"; echo "3) Mods List (Mods.txt)"
        echo "4) Message of the Day (Motd.txt)"; echo "5) Game Settings (Game.ini)"; echo "6) Engine Settings (Engine.ini)"
        echo "7) Mod.io/User Settings (GameUserSettings.ini)"; echo "b) Back to Main Menu"
        read -p "Select a file to edit: " choice
        ensure_config_files_exist
        case "$choice" in
            1) nano "$SERVER_DIR/Insurgency/Config/Server/Admins.txt" ;;
            2) nano "$SERVER_DIR/Insurgency/Config/Server/MapCycle.txt" ;;
            3) nano "$SERVER_DIR/Insurgency/Config/Server/Mods.txt" ;;
            4) nano "$SERVER_DIR/Insurgency/Config/Server/Motd.txt" ;;
            5) nano "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/Game.ini" ;;
            6) nano "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/Engine.ini" ;;
            7) nano "$SERVER_DIR/Insurgency/Saved/Config/LinuxServer/GameUserSettings.ini" ;;
            b | B) break ;;
            *) echo -e "${RED}Invalid option.${NC}";;
        esac
    done
}

generate_map_cycle() {
    declare -a current_map_cycle_lines=()
    local map_cycle_file_path=""
    local existing_file_loaded=false

    clear
    echo -e "${CYAN}--- Advanced Map Cycle Generator ---${NC}"
    echo "This tool allows you to create or modify MapCycle.txt files with detailed control."
    echo ""
    echo "1) Create a new map cycle file"
    echo "2) Modify an existing map cycle file"
    echo "b) Back to Main Menu"
    echo -e -n "${YELLOW}Choose an option: ${NC}"
    read create_or_modify_choice

    case "$create_or_modify_choice" in
        1)
            read -p "Enter filename for the new map cycle [MapCycle.txt]: " filename
            filename=${filename:-MapCycle.txt}
            map_cycle_file_path="$SERVER_DIR/Insurgency/Config/Server/$filename"
            echo -e "${YELLOW}Starting new map cycle: ${CYAN}$map_cycle_file_path${NC}"
            mkdir -p "$(dirname "$map_cycle_file_path")"
            current_map_cycle_lines=()
            ;;
        2)
            read -p "Enter filename of the map cycle to modify [MapCycle.txt]: " filename
            filename=${filename:-MapCycle.txt}
            map_cycle_file_path="$SERVER_DIR/Insurgency/Config/Server/$filename"
            if [ -f "$map_cycle_file_path" ]; then
                echo -e "${YELLOW}Loading existing map cycle: ${CYAN}$map_cycle_file_path${NC}"
                mapfile -t current_map_cycle_lines < <(grep -v '^[[:space:]]*$' "$map_cycle_file_path" 2>/dev/null || true)
                existing_file_loaded=true
                _display_map_cycle_content_simple "Loaded Map Cycle" "${current_map_cycle_lines[@]}"
            else
                echo -e "${RED}File '$map_cycle_file_path' not found.${NC}"
                read -p "Create a new map cycle with this name? (y/n): " confirm_create
                if [[ ! "$confirm_create" =~ ^[Yy]$ ]]; then
                    echo -e "${RED}Aborting.${NC}"; return
                fi
                echo -e "${YELLOW}Starting new map cycle: ${CYAN}$map_cycle_file_path${NC}"
                mkdir -p "$(dirname "$map_cycle_file_path")"
                current_map_cycle_lines=()
            fi
            ;;
        b | B) return ;;
        *) echo -e "${RED}Invalid option.${NC}"; return ;;
    esac

    local action_choice
    PS3="Select an option: "
    while true; do
        echo ""
        echo -e "${CYAN}--- Map Cycle Editor ---${NC}"
        echo -e "Editing File: ${GREEN}${map_cycle_file_path##*/}${NC}"
        echo -e "Total Scenarios: ${GREEN}${#current_map_cycle_lines[@]}${NC}"
        echo "--------------------------"
        echo "1) Add Scenario (Guided Selection)"
        echo "2) Add Scenario (Manual Entry)"
        echo "3) Add Multiple Scenarios (Bulk Filter)"
        echo "4) View Current Cycle"
        echo "5) Remove Scenario from Cycle"
        echo "6) Change Lighting for a Scenario"
        echo "7) Reorder Scenarios"
        echo "s) Save and Exit"
        echo "d) Discard Changes and Exit"
        echo -e -n "${YELLOW}Editor Action: ${NC}"
        read action_choice

        case "$action_choice" in
            1) # Add Scenario (Guided)
                local available_maps map_choice selected_map_name
                mapfile -t available_maps < <(_get_unique_maps_from_scenarios)
                if [ ${#available_maps[@]} -eq 0 ]; then echo -e "${RED}No maps found in SCENARIO_LIST!${NC}"; continue; fi

                PS3="Select a Map: "
                select selected_map_name in "${available_maps[@]}"; do
                    if [[ -n "$selected_map_name" ]]; then break; else echo -e "${RED}Invalid map selection.${NC}"; fi
                done

                local friendly_game_modes=("Checkpoint" "Push" "Frontline" "Skirmish" "Domination" "Firefight" "Outpost" "Survival" "Ambush" "Defusal" "Team Deathmatch" "TDM" "FFA")
                local scenario_gamemode_strings=("Checkpoint" "Push" "Frontline" "Skirmish" "Domination" "Firefight" "Outpost" "Survival" "Ambush" "Defusal" "Team_Deathmatch" "TDM" "FFA")
                local selected_mode_friendly selected_mode_scenario_string

                PS3="Select a Game Mode for $selected_map_name: "
                select selected_mode_friendly in "${friendly_game_modes[@]}"; do
                    if [[ -n "$selected_mode_friendly" ]]; then
                        for i in "${!friendly_game_modes[@]}"; do
                            if [[ "${friendly_game_modes[$i]}" == "$selected_mode_friendly" ]]; then
                                selected_mode_scenario_string="${scenario_gamemode_strings[$i]}"
                                break
                            fi
                        done
                        break
                    else echo -e "${RED}Invalid game mode selection.${NC}"; fi
                done

                local filtered_scenarios
                mapfile -t filtered_scenarios < <(echo "$SCENARIO_LIST" | grep -i "^Scenario_${selected_map_name}_.*${selected_mode_scenario_string}")

                if [ ${#filtered_scenarios[@]} -eq 0 ]; then
                    echo -e "${RED}No specific scenarios found for '$selected_map_name' with mode '$selected_mode_friendly'.${NC}"
                    echo -e "${YELLOW}Try Manual Entry or check SCENARIO_LIST for combinations.${NC}"
                    continue
                fi

                local selected_scenario lighting_choice
                PS3="Select a specific Scenario: "
                select selected_scenario in "${filtered_scenarios[@]}"; do
                    if [[ -n "$selected_scenario" ]]; then break; else echo -e "${RED}Invalid scenario selection.${NC}"; fi
                done

                PS3="Select Lighting for $selected_scenario: "
                select lighting_choice in "Day" "Night"; do
                    if [[ -n "$lighting_choice" ]]; then break; else echo -e "${RED}Invalid lighting selection.${NC}"; fi
                done

                current_map_cycle_lines+=("(Scenario=\"$selected_scenario\",Lighting=\"$lighting_choice\")")
                echo -e "${GREEN}Added: (Scenario=\"$selected_scenario\",Lighting=\"$lighting_choice\") ${NC}"
                ;;
            2) # Add Scenario (Manual)
                local manual_scenario lighting_choice
                echo -e "${YELLOW}Enter the full Scenario string (e.g., Scenario_Bab_Checkpoint_Insurgents):${NC}"
                read -r manual_scenario
                if [[ -z "$manual_scenario" ]]; then echo -e "${RED}Scenario string cannot be empty.${NC}"; continue; fi

                if ! grep -q -x -F "$manual_scenario" <<< "$SCENARIO_LIST"; then
                    read -p "${YELLOW}Warning: '$manual_scenario' not found in master list. Add anyway? (y/n): ${NC}" confirm_manual
                    if [[ ! "$confirm_manual" =~ ^[Yy]$ ]]; then continue; fi
                fi

                PS3="Select Lighting for $manual_scenario: "
                select lighting_choice in "Day" "Night"; do
                    if [[ -n "$lighting_choice" ]]; then break; else echo -e "${RED}Invalid lighting selection.${NC}"; fi
                done

                current_map_cycle_lines+=("(Scenario=\"$manual_scenario\",Lighting=\"$lighting_choice\")")
                echo -e "${GREEN}Added: (Scenario=\"$manual_scenario\",Lighting=\"$lighting_choice\") ${NC}"
                ;;
            3) # Add Multiple Scenarios (Bulk Filter)
                local bulk_game_modes_available=("Checkpoint" "Push" "Frontline" "Skirmish" "Domination" "Firefight" "Outpost" "Survival" "Ambush" "Defusal" "Team_Deathmatch" "TDM" "FFA")
                local selected_modes_bulk=()
                echo -e "${YELLOW}Select game modes for bulk add (Select 'Done' to finish filtering).${NC}"
                PS3="Select a game mode to include in filter: "
                select mode_bulk in "${bulk_game_modes_available[@]}" "Done"; do
                    if [[ "$REPLY" == "Done" || "$mode_bulk" == "Done" ]]; then break; fi
                    if [[ -n "$mode_bulk" ]]; then
                        if ! [[ " ${selected_modes_bulk[*]} " =~ " ${mode_bulk} " ]]; then
                            selected_modes_bulk+=("$mode_bulk"); echo -e "${GREEN}Added '$mode_bulk' to filter. Current filter: ${selected_modes_bulk[*]}.${NC}"
                        else echo -e "${YELLOW}'$mode_bulk' is already in filter.${NC}"; fi
                    else echo -e "${RED}Invalid selection.${NC}"; fi
                done

                if [ ${#selected_modes_bulk[@]} -eq 0 ]; then echo -e "${RED}No game modes selected for filter. Aborting bulk add.${NC}"; continue; fi

                local lighting_bulk
                PS3="Select lighting for these bulk-added scenarios: "
                select lighting_bulk in "Day" "Night" "Both"; do
                    if [[ -n "$lighting_bulk" ]]; then break; else echo -e "${RED}Invalid lighting selection.${NC}"; fi
                done

                local grep_pattern_bulk; grep_pattern_bulk=$(IFS='|'; echo "${selected_modes_bulk[*]}")
                local filtered_scenarios_bulk
                mapfile -t filtered_scenarios_bulk < <(echo "$SCENARIO_LIST" | grep -E "_($grep_pattern_bulk)(_|$)")

                if [ ${#filtered_scenarios_bulk[@]} -eq 0 ]; then
                    echo -e "${RED}No scenarios found matching this bulk filter criteria in SCENARIO_LIST.${NC}"; continue
                fi

                local count_added_bulk=0
                for scenario_item in "${filtered_scenarios_bulk[@]}"; do
                    if [[ "$lighting_bulk" == "Day" || "$lighting_bulk" == "Both" ]]; then
                        current_map_cycle_lines+=("(Scenario=\"$scenario_item\",Lighting=\"Day\")")
                        count_added_bulk=$((count_added_bulk + 1))
                    fi
                    if [[ "$lighting_bulk" == "Night" || "$lighting_bulk" == "Both" ]]; then
                        current_map_cycle_lines+=("(Scenario=\"$scenario_item\",Lighting=\"Night\")")
                        count_added_bulk=$((count_added_bulk + 1))
                    fi
                done
                echo -e "${GREEN}Added $count_added_bulk scenario entries based on bulk filter.${NC}"
                ;;
            4) _display_map_cycle_content_simple "Current Map Cycle" "${current_map_cycle_lines[@]}"; read -p "Press [Enter] to continue..." ;;
            5) # Remove Scenario
                if [ ${#current_map_cycle_lines[@]} -eq 0 ]; then echo -e "${RED}Map cycle is empty. Nothing to remove.${NC}"; continue; fi
                _display_map_cycle_content_simple "Select Scenario to Remove" "${current_map_cycle_lines[@]}"
                read -p "Enter number of scenario to remove (or 'c' to cancel): " remove_idx_str
                if [[ "$remove_idx_str" =~ ^[Cc]$ ]]; then continue; fi
                if ! [[ "$remove_idx_str" =~ ^[0-9]+$ ]] || [ $((remove_idx_str)) -lt 1 ] || [ $((remove_idx_str)) -gt ${#current_map_cycle_lines[@]} ]; then echo -e "${RED}Invalid number.${NC}"; continue; fi
                local remove_idx=$((remove_idx_str - 1))
                local item_to_remove="${current_map_cycle_lines[$remove_idx]}"
                unset 'current_map_cycle_lines[$remove_idx]'; current_map_cycle_lines=("${current_map_cycle_lines[@]}")
                echo -e "${YELLOW}Removed: $item_to_remove${NC}"
                ;;
            6) # Change Lighting
                if [ ${#current_map_cycle_lines[@]} -eq 0 ]; then echo -e "${RED}Map cycle is empty. Nothing to change lighting for.${NC}"; continue; fi
                _display_map_cycle_content_simple "Select Scenario to Change Lighting" "${current_map_cycle_lines[@]}"
                read -p "Enter number of scenario to change lighting for (or 'c' to cancel): " change_idx_str
                if [[ "$change_idx_str" =~ ^[Cc]$ ]]; then continue; fi
                if ! [[ "$change_idx_str" =~ ^[0-9]+$ ]] || [ $((change_idx_str)) -lt 1 ] || [ $((change_idx_str)) -gt ${#current_map_cycle_lines[@]} ]; then echo -e "${RED}Invalid number.${NC}"; continue; fi
                local current_entry_idx=$((change_idx_str - 1))
                local current_entry="${current_map_cycle_lines[$current_entry_idx]}"
                local scenario_part=$(echo "$current_entry" | sed -n 's/.*Scenario="\([^"]*\)".*/\1/p')
                local current_lighting=$(echo "$current_entry" | sed -n 's/.*Lighting="\([^"]*\)".*/\1/p')
                local new_lighting
                PS3="Select new lighting for $scenario_part (current: $current_lighting): "
                select new_lighting in "Day" "Night"; do if [[ -n "$new_lighting" ]]; then break; else echo -e "${RED}Invalid lighting selection.${NC}"; fi; done
                current_map_cycle_lines[$current_entry_idx]="(Scenario=\"$scenario_part\",Lighting=\"$new_lighting\")"
                echo -e "${GREEN}Lighting changed for scenario $change_idx_str to $new_lighting.${NC}"
                ;;
            7) # Reorder Scenarios
                if [ ${#current_map_cycle_lines[@]} -lt 2 ]; then echo -e "${YELLOW}Need at least two scenarios to reorder.${NC}"; continue; fi
                _display_map_cycle_content_simple "Current Order - Select item to move" "${current_map_cycle_lines[@]}"
                read -p "Enter number of scenario to move: " item_num_str
                if ! [[ "$item_num_str" =~ ^[0-9]+$ ]] || [ $((item_num_str)) -lt 1 ] || [ $((item_num_str)) -gt ${#current_map_cycle_lines[@]} ]; then echo -e "${RED}Invalid scenario number.${NC}"; continue; fi
                local orig_idx=$((item_num_str - 1)); local item_to_move="${current_map_cycle_lines[$orig_idx]}"
                _display_map_cycle_content_simple "Move '$item_to_move' to which position?" "${current_map_cycle_lines[@]}"
                read -p "Enter new position number (1 to ${#current_map_cycle_lines[@]}): " new_pos_str
                if ! [[ "$new_pos_str" =~ ^[0-9]+$ ]] || [ $((new_pos_str)) -lt 1 ] || [ $((new_pos_str)) -gt ${#current_map_cycle_lines[@]} ]; then echo -e "${RED}Invalid new position.${NC}"; continue; fi
                local new_idx=$((new_pos_str - 1))
                if [ "$orig_idx" -eq "$new_idx" ]; then echo -e "${YELLOW}Item is already at that position.${NC}"; continue; fi
                unset 'current_map_cycle_lines[$orig_idx]'; local temp_array=("${current_map_cycle_lines[@]}")
                current_map_cycle_lines=("${temp_array[@]:0:$new_idx}" "$item_to_move" "${temp_array[@]:$new_idx}")
                echo -e "${GREEN}Scenario reordered.${NC}"; _display_map_cycle_content_simple "Updated Order" "${current_map_cycle_lines[@]}"
                ;;
            s | S)
                if [ -z "$map_cycle_file_path" ]; then echo -e "${RED}Error: Map cycle file path not set.${NC}"; break; fi
                printf "%s\n" "${current_map_cycle_lines[@]}" > "$map_cycle_file_path"
                echo -e "\n${GREEN}Map cycle saved to: ${YELLOW}$map_cycle_file_path${NC}"
                echo -e "To use it, ensure your server startup preset includes: ${YELLOW}-MapCycle=${map_cycle_file_path##*/}${NC}"; break
                ;;
            d | D)
                if [[ "$existing_file_loaded" = false && ${#current_map_cycle_lines[@]} -eq 0 ]]; then echo -e "${YELLOW}No changes to discard. Exiting editor.${NC}"; break; fi
                read -p "${YELLOW}Discard unsaved changes? (y/n): ${NC}" confirm_discard
                if [[ "$confirm_discard" =~ ^[Yy]$ ]]; then echo -e "${YELLOW}Changes discarded. Exiting editor.${NC}"; break; else echo -e "${YELLOW}Continuing editing.${NC}"; fi
                ;;
            *) echo -e "${RED}Invalid action choice. Please try again.${NC}";;
        esac
        PS3="Select an option: "
    done
    PS3="Enter your choice: "
}

# START: Advanced Preset Management Functions (Helpers mostly unchanged)

_parse_map_string_to_assoc() {
    local map_string="$1"; local -n params_ref="$2"; params_ref=()
    IFS='?' read -r first_part rest_params <<< "$map_string"; params_ref["_MAP_NAME_"]="$first_part"
    if [[ -n "$rest_params" ]]; then
        local old_ifs="$IFS"; IFS='?'; local param_pair
        for param_pair in $rest_params; do
            local key val; IFS='=' read -r key val <<< "$param_pair"
            if [[ -n "$key" ]]; then params_ref["$key"]="$val"; fi
        done; IFS="$old_ifs"
    fi
}
_build_map_string_from_assoc() {
    local -n params_ref="$1"; local map_name="${params_ref["_MAP_NAME_"]}"; local query_string=""; local key
    if [[ -n "${params_ref["Scenario"]}" ]]; then query_string+="?Scenario=${params_ref["Scenario"]}"; fi
    for key in "${!params_ref[@]}"; do
        if [[ "$key" == "_MAP_NAME_" || "$key" == "Scenario" ]]; then continue; fi
        if [[ -n "${params_ref[$key]}" ]]; then query_string+="?$key=${params_ref[$key]}"; fi
    done; echo "${map_name}${query_string}"
}
_find_arg_index_in_array() {
    local -n arr_ref="$1"; local arg_pattern="$2"; local exact_match="${3:-false}"
    for i in "${!arr_ref[@]}"; do
        if [[ "$exact_match" == "true" ]]; then
            if [[ "${arr_ref[$i]}" == "$arg_pattern" ]]; then echo "$i"; return 0; fi
        else
            if [[ "${arr_ref[$i]}" == "$arg_pattern"* ]]; then echo "$i"; return 0; fi
        fi
    done; echo "-1"; return 1
}
_get_arg_value_from_array() {
    local -n arr_ref="$1"; local arg_prefix="$2"
    local index=$(_find_arg_index_in_array "$1" "$arg_prefix")
    if [[ $index -ne -1 && "${arr_ref[$index]}" == "$arg_prefix"* ]]; then
        echo "${arr_ref[$index]#"$arg_prefix"}"; return 0
    fi; return 1
}
_set_arg_in_array() {
    local -n arr_ref="$1"; local arg_prefix="$2"; local new_value="$3"; local is_flag="${4:-false}"; local full_arg
    if [[ "$is_flag" == "true" ]]; then full_arg="$arg_prefix"; else full_arg="${arg_prefix}${new_value}"; fi
    local index=$(_find_arg_index_in_array "$1" "$arg_prefix")
    if [[ $index -ne -1 ]]; then arr_ref[$index]="$full_arg"; else arr_ref+=("$full_arg"); fi
}
_remove_arg_from_array() {
    local -n arr_ref="$1"; local arg_to_remove_pattern="$2"; local exact_match="${3:-false}"
    local index=$(_find_arg_index_in_array "$1" "$arg_to_remove_pattern" "$exact_match")
    if [[ $index -ne -1 ]]; then unset 'arr_ref[$index]'; return 0; fi; return 1
}
_toggle_flag_in_array() {
    local -n arr_ref="$1"; local flag_arg="$2"
    local index=$(_find_arg_index_in_array "$1" "$flag_arg" "true")
    if [[ $index -ne -1 ]]; then unset 'arr_ref[$index]'; echo "'$flag_arg' disabled."; else arr_ref+=("$flag_arg"); echo "'$flag_arg' enabled."; fi
}
_select_file_from_server_config_dir() {
    local prompt_msg="$1"; local default_filename="${2:-}"; local selected_file=""
    local config_path="$SERVER_DIR/Insurgency/Config/Server"
    mapfile -t files < <(find "$config_path" -maxdepth 1 -type f -name "*.txt" -printf "%f\n" 2>/dev/null | sort)
    if [ ${#files[@]} -gt 0 ]; then
        echo -e "${CYAN}${prompt_msg}${NC}" >&2; PS3="Select a file (or 'm' for manual, 'c' to clear): "
        select fname in "${files[@]}" "Manual Entry" "Clear/None"; do
            case "$fname" in
                "Manual Entry") read -p "Enter filename: " selected_file; break ;;
                "Clear/None") selected_file=""; break ;;
                *) if [[ -n "$fname" ]]; then selected_file="$fname"; break; else echo -e "${RED}Invalid selection.${NC}"; fi ;;
            esac
        done
    else
        echo -e "${YELLOW}No .txt files found in $config_path.${NC}"; read -p "Enter filename manually (Enter for '$default_filename'): " selected_file
    fi; PS3="Enter your choice: "
    if [[ -z "$selected_file" && -n "$default_filename" && "$fname" != "Clear/None" ]]; then echo "$default_filename"; else echo "$selected_file"; fi
}

# NEW HELPER: Manage Mutators for a preset
_manage_mutators_for_preset() {
    local -n preset_args_ref="$1" # Nameref to the preset's argument array
    local current_mutators_str=$(_get_arg_value_from_array preset_args_ref "-mutators=")
    declare -a selected_mutators_arr=()

    if [[ -n "$current_mutators_str" ]]; then
        IFS=',' read -ra selected_mutators_arr <<< "$current_mutators_str"
    fi

    local mutator_choice
    while true; do
        clear
        echo -e "${CYAN}--- Manage Mutators for Preset ---${NC}"
        if [ ${#selected_mutators_arr[@]} -eq 0 ]; then
            echo -e "${YELLOW}No mutators currently selected.${NC}"
        else
            echo "Selected Mutators:"
            for m in "${selected_mutators_arr[@]}"; do echo "  - $m"; done
        fi
        echo "-------------------------------------"
        echo "1) Add Mutator"
        echo "2) Remove Mutator"
        echo "3) Clear All Mutators"
        echo "b) Back (Save Mutator Changes to Preset)"
        read -rp "Mutator option: " mutator_choice

        case "$mutator_choice" in
            1) # Add Mutator
                local available_mutators_to_add=()
                for mut_name in "${MUTATOR_LIST_NAMES[@]}"; do
                     # Check if mutator is already selected
                    local found=0
                    for sel_mut in "${selected_mutators_arr[@]}"; do
                        if [[ "$sel_mut" == "$mut_name" ]]; then found=1; break; fi
                    done
                    if [[ $found -eq 0 ]]; then available_mutators_to_add+=("$mut_name"); fi
                done

                if [ ${#available_mutators_to_add[@]} -eq 0 ]; then
                    echo -e "${YELLOW}All available mutators already selected or list is empty.${NC}"; sleep 1; continue
                fi

                echo -e "${YELLOW}Select mutators to add (select 'Done' when finished):${NC}"
                PS3="Add mutator: "
                select mut_to_add in "${available_mutators_to_add[@]}" "Done"; do
                    if [[ "$mut_to_add" == "Done" ]]; then break; fi
                    if [[ -n "$mut_to_add" ]]; then
                        selected_mutators_arr+=("$mut_to_add")
                        # Remove from available_mutators_to_add for this session of adding
                        local temp_avail=()
                        for item in "${available_mutators_to_add[@]}"; do [[ "$item" != "$mut_to_add" ]] && temp_avail+=("$item"); done
                        available_mutators_to_add=("${temp_avail[@]}")
                        echo -e "${GREEN}Added '$mut_to_add'. Current: ${selected_mutators_arr[*]}.${NC}"
                        if [ ${#available_mutators_to_add[@]} -eq 0 ]; then echo -e "${YELLOW}No more mutators to add.${NC}"; break; fi # Refresh select options
                        # PS3 needs to be reset if the list changes dynamically for 'select' in some shells
                        # For simplicity, we break and re-enter if multiple adds are common. Or just inform user.
                    else
                        echo -e "${RED}Invalid selection.${NC}"
                    fi
                done
                PS3="Enter your choice: "
                ;;
            2) # Remove Mutator
                if [ ${#selected_mutators_arr[@]} -eq 0 ]; then
                    echo -e "${RED}No mutators to remove.${NC}"; sleep 1; continue
                fi
                echo -e "${YELLOW}Select mutator to remove:${NC}"
                PS3="Remove mutator: "
                select mut_to_remove in "${selected_mutators_arr[@]}" "Cancel"; do
                    if [[ "$mut_to_remove" == "Cancel" ]]; then break; fi
                    if [[ -n "$mut_to_remove" ]]; then
                        local temp_arr=()
                        for item in "${selected_mutators_arr[@]}"; do
                            if [[ "$item" != "$mut_to_remove" ]]; then temp_arr+=("$item"); fi
                        done
                        selected_mutators_arr=("${temp_arr[@]}")
                        echo -e "${GREEN}Removed '$mut_to_remove'.${NC}"
                        break
                    else
                        echo -e "${RED}Invalid selection.${NC}"
                    fi
                done
                PS3="Enter your choice: "
                ;;
            3) # Clear All Mutators
                if [ ${#selected_mutators_arr[@]} -gt 0 ]; then
                    read -p "${YELLOW}Are you sure you want to clear all selected mutators? (y/n): ${NC}" confirm_clear
                    if [[ "$confirm_clear" =~ ^[Yy]$ ]]; then
                        selected_mutators_arr=()
                        echo -e "${GREEN}All mutators cleared.${NC}"
                    else
                        echo -e "${YELLOW}Clear cancelled.${NC}"
                    fi
                else
                    echo -e "${YELLOW}No mutators to clear.${NC}"
                fi
                sleep 1
                ;;
            b|B) # Back and Save
                # Rebuild the -mutators= string
                if [ ${#selected_mutators_arr[@]} -eq 0 ]; then
                    _remove_arg_from_array preset_args_ref "-mutators="
                else
                    local final_mutators_str
                    final_mutators_str=$(IFS=,; echo "${selected_mutators_arr[*]}")
                    _set_arg_in_array preset_args_ref "-mutators=" "$final_mutators_str"
                fi
                echo -e "${GREEN}Mutator settings updated for preset.${NC}"; sleep 1
                return 0
                ;;
            *) echo -e "${RED}Invalid option.${NC}"; sleep 1 ;;
        esac
    done
}


# The core preset editor - UPDATED WITH NEW OPTIONS
_interactive_edit_preset_array() {
    local preset_array_name_var="$1"; local is_new_preset="$2"
    declare -a working_args_copy=()
    if [[ "$is_new_preset" == "false" ]]; then
        declare -n existing_preset_ref="$preset_array_name_var"
        working_args_copy=("${existing_preset_ref[@]}")
    else
        if [ ${#working_args_copy[@]} -eq 0 ]; then
             working_args_copy+=("Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security")
        fi
    fi

    declare -A map_params_assoc
    if [ ${#working_args_copy[@]} -eq 0 ] || [[ -z "${working_args_copy[0]}" ]]; then
        working_args_copy[0]="Farmhouse?Scenario=Scenario_Farmhouse_Checkpoint_Security"
    fi
    _parse_map_string_to_assoc "${working_args_copy[0]}" map_params_assoc

    local temp_ps3="Select parameter to edit for '${preset_array_name_var/_args/}': "
    while true; do
        clear
        echo -e "${CYAN}--- Editing Preset: ${GREEN}${preset_array_name_var/_args/}${NC} ---${NC}"
        echo "-----------------------------------------------------"
        echo -e " [ Map/Scenario Details ]"
        echo -e "   10) Edit Map & Scenario (Current: ${YELLOW}${working_args_copy[0]}${NC})"
        echo "   11) Edit MaxPlayers (in map string)"
        echo "   12) Edit Lighting (in map string)"
        echo "   13) Add/Edit custom map query parameter"
        echo " [ Common Server Settings ]"
        local hostname_val=$(_get_arg_value_from_array working_args_copy "-hostname="); echo -e "   20) Hostname          : ${YELLOW}${hostname_val:-Not Set}${NC}"
        local port_val=$(_get_arg_value_from_array working_args_copy "-Port="); echo -e "   21) Game Port         : ${YELLOW}${port_val:-Not Set}${NC}"
        local queryport_val=$(_get_arg_value_from_array working_args_copy "-QueryPort="); echo -e "   22) Query Port        : ${YELLOW}${queryport_val:-Not Set}${NC}"
        local password_val=$(_get_arg_value_from_array working_args_copy "-Password="); echo -e "   23) Server Password   : ${YELLOW}${password_val:-Not Set}${NC}"
        local rconenabled_idx=$(_find_arg_index_in_array working_args_copy "-RCONEnabled" "true"); local rcon_status=$([[ $rconenabled_idx -ne -1 ]] && echo "Enabled" || echo "Disabled"); echo -e "   24) RCON Enabled      : ${YELLOW}${rcon_status}${NC}"
        local rconport_val=$(_get_arg_value_from_array working_args_copy "-RCONPort="); echo -e "   25) RCON Port         : ${YELLOW}${rconport_val:-Not Set}${NC}"
        local rconpass_val=$(_get_arg_value_from_array working_args_copy "-RCONPassword="); echo -e "   26) RCON Password     : ${YELLOW}${rconpass_val:-Not Set}${NC}"
        local maxplayers_val=$(_get_arg_value_from_array working_args_copy "-MaxPlayers="); echo -e "   27) Max Players (global): ${YELLOW}${maxplayers_val:-Not Set}${NC}"
        local mapcycle_val=$(_get_arg_value_from_array working_args_copy "-MapCycle="); echo -e "   28) MapCycle File     : ${YELLOW}${mapcycle_val:-Not Set}${NC}"
        local adminlist_val=$(_get_arg_value_from_array working_args_copy "-AdminList="); echo -e "   29) AdminList File    : ${YELLOW}${adminlist_val:-Not Set}${NC}"
        local mods_val=$(_get_arg_value_from_array working_args_copy "-Mods="); echo -e "   30) Mods File         : ${YELLOW}${mods_val:-Not Set}${NC}"
        local modio_status_str="Default (Enabled)"; local modio_en_idx=$(_find_arg_index_in_array working_args_copy "-EnableModIO" "true"); local modio_dis_idx=$(_find_arg_index_in_array working_args_copy "-DisableModIO" "true")
        if [[ $modio_en_idx -ne -1 ]]; then modio_status_str="Explicitly Enabled"; elif [[ $modio_dis_idx -ne -1 ]]; then modio_status_str="Explicitly Disabled"; fi
        echo -e "   31) Mod.io            : ${YELLOW}${modio_status_str}${NC}"
        local log_idx=$(_find_arg_index_in_array working_args_copy "-log" "true"); local log_status=$([[ $log_idx -ne -1 ]] && echo "Enabled" || echo "Disabled"); echo -e "   32) Logging (-log)    : ${YELLOW}${log_status}${NC}"
        echo " [ Server Authentication & Stats ]"
        local gslttoken_val=$(_get_arg_value_from_array working_args_copy "-GSLTToken="); echo -e "   35) GSLT Token        : ${YELLOW}${gslttoken_val:-Not Set}${NC}"
        local gamestats_idx=$(_find_arg_index_in_array working_args_copy "-GameStats" "true"); local gs_status=$([[ $gamestats_idx -ne -1 ]] && echo "Enabled" || echo "Disabled"); echo -e "   36) GameStats Report  : ${YELLOW}${gs_status}${NC}"
        local statstoken_val=$(_get_arg_value_from_array working_args_copy "-GameStatsToken="); echo -e "   37) GameStats Token   : ${YELLOW}${statstoken_val:-Not Set}${NC}"
        echo " [ Gameplay Rules & Mutators ]"
        local ruleset_val=$(_get_arg_value_from_array working_args_copy "-ruleset="); local or_status=$([[ "$ruleset_val" == "OfficialRules" ]] && echo "Enabled" || echo "Disabled"); echo -e "   40) Official Rules    : ${YELLOW}${or_status}${NC}"
        local mutators_val=$(_get_arg_value_from_array working_args_copy "-mutators="); echo -e "   41) Manage Mutators   : ${YELLOW}${mutators_val:-None Set}${NC}"
        echo " [ Advanced ]"
        echo "   A) Add/Edit Custom Argument"
        echo "   R) Remove Argument"
        echo "   V) View All Current Arguments"
        echo "-----------------------------------------------------"
        echo -e "${GREEN}S) Save Changes to this Preset and Return${NC}"
        echo -e "${RED}B) Back/Cancel (Discard Changes to this Preset)${NC}"
        echo ""
        read -rp "$temp_ps3" edit_choice

        case "$edit_choice" in
            10) # Edit Map & Scenario
                local available_maps selected_map_name current_map_val="${map_params_assoc["_MAP_NAME_"]}"
                mapfile -t available_maps < <(_get_unique_maps_from_scenarios)
                PS3="Select a Map (current: $current_map_val): "; select selected_map_name in "${available_maps[@]}"; do if [[ -n "$selected_map_name" ]]; then map_params_assoc["_MAP_NAME_"]="$selected_map_name"; break; else echo -e "${RED}Invalid selection.${NC}"; fi; done; PS3="Enter your choice: "
                local friendly_game_modes=("Checkpoint" "Push" "Frontline" "Skirmish" "Domination" "Firefight" "Outpost" "Survival" "Ambush" "Defusal" "Team Deathmatch" "TDM" "FFA" "Custom/Any")
                local scenario_gamemode_strings=("Checkpoint" "Push" "Frontline" "Skirmish" "Domination" "Firefight" "Outpost" "Survival" "Ambush" "Defusal" "Team_Deathmatch" "TDM" "FFA" "")
                local selected_mode_friendly selected_mode_scenario_string current_scenario_gm="${map_params_assoc["Scenario"]}"
                PS3="Select Game Mode for ${map_params_assoc["_MAP_NAME_"]} (current scenario: $current_scenario_gm): "; select selected_mode_friendly in "${friendly_game_modes[@]}"; do if [[ -n "$selected_mode_friendly" ]]; then for i in "${!friendly_game_modes[@]}"; do if [[ "${friendly_game_modes[$i]}" == "$selected_mode_friendly" ]]; then selected_mode_scenario_string="${scenario_gamemode_strings[$i]}"; break; fi; done; break; else echo -e "${RED}Invalid selection.${NC}"; fi; done; PS3="Enter your choice: "
                local filtered_scenarios selected_scenario
                if [[ "$selected_mode_friendly" == "Custom/Any" ]]; then mapfile -t filtered_scenarios < <(echo "$SCENARIO_LIST" | grep "^Scenario_${map_params_assoc["_MAP_NAME_"]}_"); else mapfile -t filtered_scenarios < <(echo "$SCENARIO_LIST" | grep -i "^Scenario_${map_params_assoc["_MAP_NAME_"]}_.*${selected_mode_scenario_string}"); fi
                if [ ${#filtered_scenarios[@]} -eq 0 ]; then echo -e "${RED}No scenarios found for '${map_params_assoc["_MAP_NAME_"]}' mode '$selected_mode_friendly'.${NC}"; read -p "Enter Scenario manually (current '${map_params_assoc["Scenario"]}'): " scenario_input; map_params_assoc["Scenario"]=${scenario_input:-${map_params_assoc["Scenario"]}}; else PS3="Select Scenario (current: ${map_params_assoc["Scenario"]}): "; select selected_scenario in "${filtered_scenarios[@]}"; do if [[ -n "$selected_scenario" ]]; then map_params_assoc["Scenario"]="$selected_scenario"; break; else echo -e "${RED}Invalid selection.${NC}"; fi; done; PS3="Enter your choice: "; fi
                working_args_copy[0]=$(_build_map_string_from_assoc map_params_assoc)
                ;;
            11) read -p "Enter MaxPlayers for map string (current: ${map_params_assoc["MaxPlayers"]}): " map_params_assoc["MaxPlayers"]; working_args_copy[0]=$(_build_map_string_from_assoc map_params_assoc) ;;
            12) PS3="Select Lighting (current: ${map_params_assoc["Lighting"]}): "; select light_opt in "Day" "Night" "Clear"; do if [[ "$light_opt" == "Clear" ]]; then unset map_params_assoc["Lighting"]; break; fi; if [[ -n "$light_opt" ]]; then map_params_assoc["Lighting"]="$light_opt"; break; else echo -e "${RED}Invalid selection.${NC}"; fi; done; PS3="Enter your choice: "; working_args_copy[0]=$(_build_map_string_from_assoc map_params_assoc) ;;
            13) read -p "Enter custom query parameter KEY: " custom_key; if [[ -n "$custom_key" ]]; then read -p "Enter value for '$custom_key' (current: ${map_params_assoc[$custom_key]}): " map_params_assoc["$custom_key"]; working_args_copy[0]=$(_build_map_string_from_assoc map_params_assoc); else echo -e "${RED}Key cannot be empty.${NC}"; fi ;;

            20) read -p "Enter Hostname (current: $hostname_val): " new_hn; _set_arg_in_array working_args_copy "-hostname=" "$new_hn" ;;
            21) read -p "Enter Game Port (current: $port_val): " new_port; _set_arg_in_array working_args_copy "-Port=" "$new_port" ;;
            22) read -p "Enter Query Port (current: $queryport_val): " new_qport; _set_arg_in_array working_args_copy "-QueryPort=" "$new_qport" ;;
            23) read -p "Enter Server Password (blank for none, current: $password_val): " new_pass; if [[ -n "$new_pass" ]]; then _set_arg_in_array working_args_copy "-Password=" "$new_pass"; else _remove_arg_from_array working_args_copy "-Password="; echo "Password cleared."; fi ;;
            24) _toggle_flag_in_array working_args_copy "-RCONEnabled" ;;
            25) read -p "Enter RCON Port (current: ${rconport_val:-Not Set}): " new_rconport; _set_arg_in_array working_args_copy "-RCONPort=" "$new_rconport" ;;
            26) read -p "Enter RCON Password (current: ${rconpass_val:-Not Set}): " new_rconpass; _set_arg_in_array working_args_copy "-RCONPassword=" "$new_rconpass" ;;
            27) read -p "Enter Max Players (global, current: ${maxplayers_val:-Not Set}): " new_mp; if [[ -n "$new_mp" ]]; then _set_arg_in_array working_args_copy "-MaxPlayers=" "$new_mp"; else _remove_arg_from_array working_args_copy "-MaxPlayers="; echo "Global MaxPlayers cleared."; fi ;;
            28) selected_mc_file=$(_select_file_from_server_config_dir "Select MapCycle file (current: ${mapcycle_val:-MapCycle.txt})" "MapCycle.txt"); if [[ -n "$selected_mc_file" ]]; then _set_arg_in_array working_args_copy "-MapCycle=" "$selected_mc_file"; else _remove_arg_from_array working_args_copy "-MapCycle="; echo "MapCycle file cleared."; fi ;;
            29) selected_admin_file=$(_select_file_from_server_config_dir "Select AdminList file (current: ${adminlist_val:-Admins.txt})" "Admins.txt"); if [[ -n "$selected_admin_file" ]]; then _set_arg_in_array working_args_copy "-AdminList=" "$selected_admin_file"; else _remove_arg_from_array working_args_copy "-AdminList="; echo "AdminList file cleared."; fi ;;
            30) selected_mods_file=$(_select_file_from_server_config_dir "Select Mods file (current: ${mods_val:-Mods.txt})" "Mods.txt"); if [[ -n "$selected_mods_file" ]]; then _set_arg_in_array working_args_copy "-Mods=" "$selected_mods_file"; else _remove_arg_from_array working_args_copy "-Mods="; echo "Mods file cleared."; fi ;;
            31) if [[ $modio_en_idx -ne -1 ]]; then _remove_arg_from_array working_args_copy "-EnableModIO" "true"; _set_arg_in_array working_args_copy "-DisableModIO" "" "true"; echo "Mod.io Disabled."; elif [[ $modio_dis_idx -ne -1 ]]; then _remove_arg_from_array working_args_copy "-DisableModIO" "true"; echo "Mod.io set to default (Enabled)."; else _set_arg_in_array working_args_copy "-EnableModIO" "" "true"; echo "Mod.io Enabled."; fi ;;
            32) _toggle_flag_in_array working_args_copy "-log" ;;

            35) # GSLT Token
                read -p "Enter GSLT Token (-GSLTToken, current: ${gslttoken_val:-Not Set}): " new_gslt_token
                if [[ -n "$new_gslt_token" ]]; then _set_arg_in_array working_args_copy "-GSLTToken=" "$new_gslt_token"
                else _remove_arg_from_array working_args_copy "-GSLTToken="; echo "GSLT Token cleared."; fi
                ;;
            36) # Toggle GameStats Reporting
                _toggle_flag_in_array working_args_copy "-GameStats"
                ;;
            37) # GameStats Token
                read -p "Enter GameStats Token (-GameStatsToken, current: ${statstoken_val:-Not Set}): " new_stats_token
                if [[ -n "$new_stats_token" ]]; then _set_arg_in_array working_args_copy "-GameStatsToken=" "$new_stats_token"
                else _remove_arg_from_array working_args_copy "-GameStatsToken="; echo "GameStats Token cleared."; fi
                ;;

            40) # Toggle Official Rules
                if [[ "$ruleset_val" == "OfficialRules" ]]; then # Currently enabled, so disable
                    _remove_arg_from_array working_args_copy "-ruleset="
                    echo "'-ruleset=OfficialRules' disabled."
                else # Currently disabled or different, so enable
                    _set_arg_in_array working_args_copy "-ruleset=" "OfficialRules"
                    echo "'-ruleset=OfficialRules' enabled."
                fi
                ;;
            41) # Manage Mutators
                _manage_mutators_for_preset working_args_copy # Pass nameref
                ;;

            A|a) read -p "Enter custom argument (e.g., -bBots=1 or -MyFlag): " custom_arg; if [[ -n "$custom_arg" ]]; then if [[ "$custom_arg" == *"="* ]]; then local key_part="${custom_arg%%=*}="; local val_part="${custom_arg#*=}"; _set_arg_in_array working_args_copy "$key_part" "$val_part"; else _set_arg_in_array working_args_copy "$custom_arg" "" "true"; fi; echo "Arg '$custom_arg' set/added."; else echo -e "${RED}Arg empty.${NC}"; fi ;;
            R|r)
                if [ ${#working_args_copy[@]} -le 1 ]; then echo -e "${RED}No removable args (map string cannot be removed).${NC}"; sleep 1; continue; fi
                echo -e "${YELLOW}Select argument to remove (excluding map string):${NC}"; local args_for_removal=("${working_args_copy[@]:1}"); PS3="Argument to remove: "
                select arg_to_remove in "${args_for_removal[@]}" "Cancel"; do
                    if [[ "$arg_to_remove" == "Cancel" ]]; then break; fi
                    if [[ -n "$arg_to_remove" ]]; then
                        local temp_new_args=("${working_args_copy[0]}"); for arg_in_copy in "${working_args_copy[@]:1}"; do if [[ "$arg_in_copy" != "$arg_to_remove" ]]; then temp_new_args+=("$arg_in_copy"); fi; done
                        working_args_copy=("${temp_new_args[@]}"); echo "Argument '$arg_to_remove' removed."; break
                    else echo -e "${RED}Invalid selection.${NC}"; fi
                done; PS3="Enter your choice: "
                ;;
            V|v) clear; echo -e "${CYAN}--- Args for ${GREEN}${preset_array_name_var/_args/}${NC} ---${NC}"; for i in "${!working_args_copy[@]}"; do echo "$((i+1))) ${working_args_copy[$i]}"; done; read -p "Press [Enter]..." ;;
            S|s) working_args_copy[0]=$(_build_map_string_from_assoc map_params_assoc); declare -n actual_preset_ref="$preset_array_name_var"; actual_preset_ref=("${working_args_copy[@]}"); echo -e "${GREEN}Preset '${preset_array_name_var/_args/}' updated in memory. Save from main preset menu.${NC}"; sleep 1; return 0 ;;
            B|b) echo -e "${YELLOW}Changes to '${preset_array_name_var/_args/}' discarded.${NC}"; sleep 1; return 1 ;;
            *) echo -e "${RED}Invalid option.${NC}"; sleep 1 ;;
        esac
        _parse_map_string_to_assoc "${working_args_copy[0]}" map_params_assoc
    done
}

# (Other preset management functions: _create_new_preset, _edit_existing_preset, _clone_existing_preset, _delete_existing_preset, _save_all_presets_to_file unchanged)
_create_new_preset() {
    local new_preset_name
    while true; do
        read -p "Enter new preset name (alphanumeric, no spaces, e.g., MyCoopServer): " new_preset_name
        if [[ -z "$new_preset_name" ]]; then echo -e "${RED}Preset name cannot be empty.${NC}"; continue; fi
        if ! [[ "$new_preset_name" =~ ^[A-Za-z0-9_]+$ ]]; then echo -e "${RED}Invalid preset name. Use alphanumeric characters and underscores only.${NC}"; continue; fi
        local new_preset_array_name="${new_preset_name}_args"
        if declare -p "$new_preset_array_name" &>/dev/null; then echo -e "${RED}Preset '$new_preset_name' already exists.${NC}"; else declare -ga "$new_preset_array_name"; _interactive_edit_preset_array "$new_preset_array_name" "true"; break; fi
    done
}
_edit_existing_preset() {
    local -a current_preset_names=("${@}")
    if [ ${#current_preset_names[@]} -eq 0 ]; then echo -e "${RED}No presets to edit.${NC}"; sleep 1; return; fi
    echo -e "${YELLOW}Select a preset to edit:${NC}"; PS3="Preset to edit: "
    select preset_to_edit in "${current_preset_names[@]}" "Cancel"; do
        if [[ "$preset_to_edit" == "Cancel" ]]; then break; fi
        if [[ -n "$preset_to_edit" ]]; then _interactive_edit_preset_array "${preset_to_edit}_args" "false"; break; else echo -e "${RED}Invalid selection.${NC}"; fi
    done; PS3="Enter your choice: "
}
_clone_existing_preset() {
    local -a current_preset_names=("${@}")
    if [ ${#current_preset_names[@]} -eq 0 ]; then echo -e "${RED}No presets to clone.${NC}"; sleep 1; return; fi
    local source_preset_name selected_source_array_name; echo -e "${YELLOW}Select preset to clone:${NC}"; PS3="Preset to clone: "
    select source_preset_name in "${current_preset_names[@]}" "Cancel"; do
        if [[ "$source_preset_name" == "Cancel" ]]; then PS3="Enter your choice: "; return; fi
        if [[ -n "$source_preset_name" ]]; then selected_source_array_name="${source_preset_name}_args"; break; else echo -e "${RED}Invalid selection.${NC}"; fi
    done; PS3="Enter your choice: "
    local new_cloned_name new_cloned_array_name
    while true; do
        read -p "Enter name for the cloned preset: " new_cloned_name
        if [[ -z "$new_cloned_name" ]]; then echo -e "${RED}Name cannot be empty.${NC}"; continue; fi
        if ! [[ "$new_cloned_name" =~ ^[A-Za-z0-9_]+$ ]]; then echo -e "${RED}Invalid preset name. Use alphanumeric and underscores.${NC}"; continue; fi
        new_cloned_array_name="${new_cloned_name}_args"
        if declare -p "$new_cloned_array_name" &>/dev/null; then echo -e "${RED}Preset name '$new_cloned_name' already exists.${NC}"; elif [[ "$new_cloned_name" == "$source_preset_name" ]]; then echo -e "${RED}Cloned name cannot be same as source.${NC}"; else break; fi
    done
    declare -n source_arr_ref="$selected_source_array_name"; declare -ga "$new_cloned_array_name"; declare -n dest_arr_ref="$new_cloned_array_name"; dest_arr_ref=("${source_arr_ref[@]}")
    echo -e "${GREEN}Preset '$source_preset_name' cloned to '$new_cloned_name'.${NC}"; sleep 1
}
_delete_existing_preset() {
    local -a current_preset_names=("${@}")
    if [ ${#current_preset_names[@]} -eq 0 ]; then echo -e "${RED}No presets to delete.${NC}"; sleep 1; return; fi
    local preset_to_delete_name selected_delete_array_name; echo -e "${RED}Select preset to DELETE:${NC}"; PS3="Preset to delete: "
    select preset_to_delete_name in "${current_preset_names[@]}" "Cancel"; do
        if [[ "$preset_to_delete_name" == "Cancel" ]]; then PS3="Enter your choice: "; return; fi
        if [[ -n "$preset_to_delete_name" ]]; then
            selected_delete_array_name="${preset_to_delete_name}_args"
            read -p "${RED}Delete preset '$preset_to_delete_name'? (y/n): ${NC}" confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then unset "$selected_delete_array_name"; echo -e "${GREEN}Preset '$preset_to_delete_name' deleted from memory.${NC}"; else echo -e "${YELLOW}Deletion cancelled.${NC}"; fi; break
        else echo -e "${RED}Invalid selection.${NC}"; fi
    done; PS3="Enter your choice: "; sleep 1
}
_save_all_presets_to_file() {
    echo -e "${YELLOW}Saving presets to $PRESETS_FILE...${NC}"
    if [ -f "$PRESETS_FILE" ]; then local backup_file="$PRESETS_FILE.bak.$(date +%Y%m%d%H%M%S)"; cp "$PRESETS_FILE" "$backup_file"; echo -e "${CYAN}Backup created: $backup_file${NC}"; fi
    cat > "$PRESETS_FILE" <<- 'EOL'
# --- Insurgency: Sandstorm Server Presets ---
# This file defines startup configurations for your server.
# Each preset is a BASH ARRAY. This is important for handling arguments with spaces.
#
# FORMAT:
# PRESET_NAME_args=(
#   "MapURL?With?Options"
#   "-Argument1=Value1"
#   "-hostname=Server Name With Spaces"
# )
#
# Note the _args suffix on the variable name. It is required.
# This file can be managed by the server script's preset manager.

EOL
    mapfile -t preset_array_vars < <(compgen -v | grep '_args$' | sort)
    if [ ${#preset_array_vars[@]} -eq 0 ]; then echo "# No presets currently defined." >> "$PRESETS_FILE"; fi
    for arr_name in "${preset_array_vars[@]}"; do
        declare -n current_arr_ref="$arr_name"; echo "$arr_name=(" >> "$PRESETS_FILE"
        for item in "${current_arr_ref[@]}"; do
            if [[ "$item" == *" "* || "$item" == *'"'* || "$item" == *"'"* || "$item" == *"$"* || "$item" == *"!"* ]]; then printf '  "%s"\n' "$(echo "$item" | sed 's/"/\\"/g')" >> "$PRESETS_FILE"; else printf '  %s\n' "$item" >> "$PRESETS_FILE"; fi
        done; echo ")" >> "$PRESETS_FILE"; echo "" >> "$PRESETS_FILE"
    done; echo -e "${GREEN}Presets saved successfully to $PRESETS_FILE${NC}"
}


manage_startup_presets() { # Main preset manager (unchanged structurally)
    if [ ! -f "$PRESETS_FILE" ]; then
        echo -e "${YELLOW}'$PRESETS_FILE' not found.${NC}"
        read -p "Create a default presets file? (y/n): " create_choice
        if [[ "$create_choice" =~ ^[Yy]$ ]]; then create_presets_file; else echo -e "${RED}Cannot manage presets without presets file.${NC}"; sleep 1; return; fi
    fi
    source "$PRESETS_FILE" # Load presets into current shell

    while true; do
        clear; echo -e "${CYAN}--- Manage Server Startup Presets ---${NC}"
        echo -e "Presets stored in: ${YELLOW}$PRESETS_FILE${NC}"; echo "Changes are in memory until saved."
        echo "-------------------------------------"
        mapfile -t preset_names < <(compgen -v | grep '_args$' | sed 's/_args$//' | sort)
        if [ ${#preset_names[@]} -eq 0 ]; then echo -e "${YELLOW}No presets defined yet.${NC}"; else echo "Current Presets (in memory):"; for i in "${!preset_names[@]}"; do echo "  $((i+1))) ${preset_names[$i]}"; done; fi
        echo "-------------------------------------"
        echo -e "${GREEN}C)${NC} Create New Preset"; echo -e "${YELLOW}E)${NC} Edit Existing Preset"
        echo -e "${CYAN}L)${NC} Clone Existing Preset"; echo -e "${RED}D)${NC} Delete Existing Preset"
        echo "M) Manually Edit $PRESETS_FILE (nano)"
        echo "-------------------------------------"
        echo -e "${GREEN}S)${NC} Save All Changes to File & Back"
        echo -e "${RED}B)${NC} Back (Discard In-Memory Changes)"
        echo ""; read -rp "Enter your choice: " choice

        case "$choice" in
            C|c) _create_new_preset ;;
            E|e) _edit_existing_preset "${preset_names[@]}" ;;
            L|l) _clone_existing_preset "${preset_names[@]}" ;;
            D|d) _delete_existing_preset "${preset_names[@]}" ;;
            M|m) echo -e "${YELLOW}Opening $PRESETS_FILE...${NC}"; nano "$PRESETS_FILE"; echo -e "${YELLOW}Re-sourcing $PRESETS_FILE...${NC}"; source "$PRESETS_FILE"; sleep 1 ;;
            S|s) _save_all_presets_to_file; echo -e "${GREEN}Changes saved.${NC}"; sleep 1; return 0 ;;
            B|b) read -p "${YELLOW}Discard unsaved changes? (y/n): ${NC}" confirm_discard; if [[ "$confirm_discard" =~ ^[Yy]$ ]]; then echo -e "${YELLOW}Changes discarded.${NC}"; sleep 1; return 1; fi ;;
            *) echo -e "${RED}Invalid option.${NC}"; sleep 1 ;;
        esac
    done
}

# END: Advanced Preset Management Functions

configure_firewall() { # Unchanged
    if ! command_exists ufw; then echo -e "${RED}UFW not installed.${NC}"; return; fi
    read -p "Enter Game Port (e.g., 27102): " game_port; read -p "Enter Query Port (e.g., 27131): " query_port
    if [[ -z "$game_port" || -z "$query_port" ]]; then echo -e "${RED}Invalid ports.${NC}"; return; fi
    echo -e "${YELLOW}Adding firewall rules...${NC}"; sudo ufw allow "$game_port"/udp; sudo ufw allow "$game_port"/tcp
    sudo ufw allow "$query_port"/udp; sudo ufw allow "$query_port"/tcp; echo -e "${GREEN}Rules added.${NC}"; sudo ufw status
}


# --- Main Menu (unchanged) ---
show_menu() {
    clear
    echo "================================================="
    echo "  Insurgency: Sandstorm Server Manager (v1.7)"
    echo "================================================="
    status_server
    echo "-------------------------------------------------"
    echo -e "${GREEN}1) Start Server${NC}"
    echo -e "${RED}2) Stop Server${NC}"
    echo -e "${CYAN}3) View Server Console${NC}"
    echo -e "${YELLOW}4) Test-Run a Preset (Debug Startups)${NC}"
    echo "-------------------------------------------------"
    echo "5) Install/Validate Server Files"
    echo "6) Update Server Files"
    echo "-------------------------------------------------"
    echo "7) Manage Server Startup Presets"
    echo "8) Edit Configuration Files (Admins, etc.)"
    echo "9) Advanced Map Cycle Generator"
    echo "10) Configure Firewall (UFW)"
    echo -e "-------------------------------------------------"
    echo "q) Quit"
    echo ""
}

# --- Main Loop (unchanged) ---
while true; do
    show_menu
    echo -e -n "${YELLOW}Enter your choice: ${NC}"
    read choice

    case "$choice" in
        1) start_server ;;
        2) stop_server ;;
        3) view_console ;;
        4) test_run_server ;;
        5) install_dependencies; install_steamcmd; install_sandstorm ;;
        6) update_sandstorm ;;
        7) manage_startup_presets ;;
        8) edit_config_menu ;;
        9) generate_map_cycle ;;
        10) configure_firewall ;;
        q) echo "Exiting."; break ;;
        *) echo -e "${RED}Invalid option, please try again.${NC}" ;;
    esac

    if [[ "$choice" != "3" && "$choice" != "4" && "$choice" != "q" && "$choice" != "7" && "$choice" != "8" && "$choice" != "9" ]]; then
        read -p "Press [Enter] to continue..."
    fi
done
