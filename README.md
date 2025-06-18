- [русский](README_ru.md)

## Step 1: Clone the repository

First, clone the repository from GitHub to your local computer.

1.  **Open a terminal (Command Prompt or PowerShell on Windows).**
    
2.  **Run the command:**
       
    `git clone https://github.com/gradinazz/CSFloat-Auto-Trade.git` 
            
3.  **Go to the project directory:**
           
    `cd CSFloat-Auto-Trade` 
      

## Step 2: Install Dependencies

Install the required packages listed in `requirements.txt`.

1.  **Make sure you are in the project directory and the Python virtual environment is activated.**
    
2.  **Run the command:**
      
    `pip install -r requirements.txt` 
      

## Step 3: Script Configuration

Before running the script, you need to configure the configuration file `steam.json`.

 -  **Edit the `steam.json` file in the root of the project.**
    
 -  **Add the following parameters to it:**
            
    -   `csfloat_api_key`: Your CSFloat API key.
    -   `steam_api_key`: Your Steam API key.
    -   `steam_id64`: Your Steam ID64(example: `76561198034388123`).
    -   `steam_login`: Your Steam username.
    -   `steam_password`: Your Steam password.
    -   `shared_secret` and `identity_secret`: Secrets needed to confirm trade offers. Can be obtained from maFile.
    -   `cilent_proxy`: Optional: Set the proxy(example: `http://127.0.0.1:20122`).
    -   `steam_use_proxy`: Optional: Apply proxy for steam cilent if setted to "true".
    -   `check_interval_seconds`: Optional: Set the interval in seconds bewteen checks.
    -   `check_interval_seconds_random`: Optional: Enable randomizing the interval bewteen checks if setted to "true".
    -   `check_interval_seconds_random_min`: Optional: Set the minimum randomized interval in seconds bewteen checks.
    -   `check_interval_seconds_random_max`: Optional: Set the maximum randomized interval in seconds bewteen checks.
    
    **Important:** Never share these keys and secrets. Keep them in a safe place.
    

## Step 4: Run the script

Now you are ready to run the script.
    
1.  **Run the command:**
      
    `python CSFloat-Auto-Trade.py` 
      
2.  **The script will start executing and will check for new trade offers every 5 minutes (by default).**
    
