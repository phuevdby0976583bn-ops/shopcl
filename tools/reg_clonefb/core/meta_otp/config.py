import os

# Terminal colors
WHITE = "\033[1;97m"
GREEN = "\033[1;92m"
RED = "\033[1;91m"
CYAN = "\033[1;96m"
YELLOW = "\033[1;93m"
BLUE = "\033[1;94m"
MAGENTA = "\033[1;95m"
ORANGE = "\x1b[38;5;208m"
GOLD = "\x1b[38;5;220m"
VIOLET = "\x1b[38;5;141m"
RESET = "\033[0m"

# UI elements
EKL = f"{CYAN}:{WHITE}"
LINE = f"{CYAN}•{'━'*47}•"
opt_labels = [f"{GREEN}[{RED}{str(i).zfill(2)}{GREEN}]" for i in range(1, 12)]

def clear_logo():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"""{GREEN}
      .d8888.  db    db  d8888b. 
      88'  YP  `8b  d8'  88  `8D 
      `8bo.     `8bd8'   88oobY' 
        `Y8b.   .dPYb.   88`8b   
      db   8D  .8P  Y8.  88 `88. 
      `8888Y'  YP    YP  88   YD   {ORANGE}V-1.0
{LINE}
 {GREEN}[{RED}●{GREEN}] TOOL         {EKL} OTP SENDER
 {GREEN}[{RED}●{GREEN}] DEVELOPER    {EKL} Masudur Rahman Sifat
 {GREEN}[{RED}●{GREEN}] STATUS       {EKL} ACTIVE
{LINE}""")
