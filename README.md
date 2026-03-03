Quick scrpit to Get an Insurgency Sandstorm Server running. Auto Downloads steamcmd and the game, ports for UFW, and additional option files, mapcycles and startup parameters in the Ubuntu CLI. 

### Option 1: Using `curl` (Recommended for macOS and most Linux)
Run this command:
```bash
curl -O https://raw.githubusercontent.com/extremelystiff/autosergency-server/main/sandstorm_manager.sh
```
*(Note: That is a capital letter `O`, which tells curl to save the file with its original name).*

### Option 2: Using `wget` (Common on Linux)
Run this command:
```bash
wget https://raw.githubusercontent.com/extremelystiff/autosergency-server/main/sandstorm_manager.sh
```

---

### Next Steps (Running the script)
Since this is a bash script (`.sh`), you will likely need to make it executable before you can run it. 

After downloading, run these two commands:

1. Make it executable:
```bash
chmod +x sandstorm_manager.sh
```

2. Run the script:
```bash
./sandstorm_manager.sh
```


It won't launch the server if you run the script as sudo.

<img width="470" height="388" alt="image" src="https://github.com/user-attachments/assets/57245fa5-f5a6-4cd3-847c-1bf02a212849" />
