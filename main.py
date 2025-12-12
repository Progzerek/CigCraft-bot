import discord
import requests
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
from mcstatus import JavaServer
import asyncio

#load from env
load_dotenv()
PUFFER_MC_ID=os.getenv('PUFFER_MC_ID')
MC_ID=os.getenv('MC_ID')
PUFFER_URL = os.getenv('PUFFER_URL')
CLIENT_ID= os.getenv('CLIENT_ID')
CLIENT_SECRET=os.getenv('CLIENT_SECRET')
Puffer_token = f"{PUFFER_URL}/oauth2/token"
dc_token=os.getenv("DISCORD_TOKEN")
dc_id = int(os.getenv('DC_ID'))

#bot permissions
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

def get_puffer_token():
    try:
        print("trying to connect")
        url = Puffer_token
        data = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
        response = requests.post(url, data=data)
        access_token = response.json().get("access_token")
        resp = response.json()
        return access_token, resp
    except:
        print(f"Failed {response.status_code}: {response.text}")
        return None, None
#prefix
mc_bot = commands.Bot(command_prefix='/mc ', intents=intents)

#commands

@mc_bot.event
async def on_ready():
    print (f"{mc_bot.user.name} is started")

@mc_bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}, wanna play minecraft?")

@mc_bot.command()
async def status(ctx):
#puffer conect
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {"Authorization": f"Bearer {token}"}

#status true or false
    status = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/status"
    response_status = requests.get(status, headers=headers)
    data_status = response_status.json()
    status_value = data_status.get('running', True)
    if status_value == True:
    #cpu and ram
        cpu_ram_stat = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/stats"
        response_cpu_ram = requests.get(cpu_ram_stat, headers=headers)
        data_cpu_ram = response_cpu_ram.json()
        raw_cpu = data_cpu_ram.get('cpu', 0)
        cpu = f"{raw_cpu:.2f}"
        raw_ram = data_cpu_ram.get('memory', 0)
        ram_gb = raw_ram / (1024 ** 3)
        ram = f"{ram_gb:.2f}"
    #player list, ping
        try:
            server = JavaServer.lookup(f"{MC_ID}") 
            status = server.status()
            if status.players.sample:
                names = [p.name for p in status.players.sample]
                player_list = "\n".join(names)
            else:
                player_list = " - None"
        except:
            await ctx.send("Could not connect to the Minecraft server")

        await ctx.send(f" **Server Status**\n Status: `{status_value}`\n CPU: `{cpu}%`\n RAM: `{ram} GB`\n Players:\n`{player_list}`")
    elif status_value==False:
        await ctx.send("**Server offline**")
    else:
        await ctx.send("Error")

@mc_bot.command()
async def start(ctx):
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {"Authorization": f"Bearer {token}"}
    
    status = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/status"
    response_status = requests.get(status, headers=headers)
    data_status = response_status.json()
    status_value = data_status.get('running', True)
    if status_value == True:
        return await ctx.send ("**Server is already online**")
 
    #start signal
    url_start = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/start?wait=false"
    resp = requests.post(url_start, headers=headers)
    
    if resp.status_code not in [202, 204]:
        return await ctx.send(f"Start failed: {resp.status_code}")
    msg = await ctx.send("**Sending start command...**")
    
    #log check
    url_console = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
    start_time = asyncio.get_event_loop().time()
    last_snippet_display = ""
    while True:
        await asyncio.sleep(3)
        #Hard Timeout - 3 mins
        if asyncio.get_event_loop().time() - start_time > 180:
             await msg.edit(content="**Start timed out (3m).** Server is slow or stuck.")
             break
        try:
            log_resp = requests.get(url_console, headers=headers)
            if log_resp.status_code == 200:
                try:
                    full_log = log_resp.json().get('logs', '')
                except:
                    full_log = log_resp.text
                
                if full_log:
                    lines = full_log.strip().split('\n')
                    snippet_display = "\n".join(lines[-8:])

                    check_text = full_log[-2000:] 
                    if "Done" in check_text or "For help, type" in check_text:
                        await msg.edit(content=f"**Server is Online!**")
                        return

                    if snippet_display != last_snippet_display:
                        await msg.edit(content=f"**Server Starting...(Please wait)**")
                        last_snippet_display = snippet_display
        except:
            pass

@mc_bot.command()
async def stop(ctx, *, force: str = "normal"):
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {"Authorization": f"Bearer {token}"}
    
    #error handling
    if response not in [202, 204]:
        return await ctx.send(f"Failed {response.status_code}: {response.text}")

    #check status
    try:
        status_url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/status"
        response_status = requests.get(status_url, headers=headers)
        
        if response_status.status_code == 200:
            data_status = response_status.json()
            status_value = data_status.get('running')
            
            if status_value is False:
                await ctx.send("**Server is already offline!**")
                return
    except:
        await ctx.send("Warning: Failed to get server status from PufferPanel. Trying to stop anyway...")
        pass
        
    #player lookup
    try:
        server = JavaServer.lookup(f"{MC_ID}")
        status = server.status()
    except:
        return await ctx.send("Failed to connect to Minecraft")
    
    #player handling
    if status.players.sample:
        names = [p.name for p in status.players.sample]
        player_list = ", ".join(names)
    else:
        player_list = "none"
    
    if player_list != "none" and force=="force":
        if ctx.author.id != dc_id:
            return await ctx.send ("No permission")
        else:
            msg = await ctx.send ("**Kicking out players...**")
    elif player_list != "none":
        return await ctx.send (f"**Players {player_list} are still online!**")
        
    #stop signal
    url_stop = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/stop?wait=false"
    resp = requests.post(url_stop, headers=headers)
    if force=="force":
        msg = await msg.edit (content="**Stopping Server...** (Saving world...)")
    else:
        msg = await ctx.send ("**Stopping Server...** (Saving world...)")
    
    #watch logs
    url_console = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
    start_time = asyncio.get_event_loop().time()
    while True:
        await asyncio.sleep(2)
        
        #Hard timeout - 3 mins
        if asyncio.get_event_loop().time() - start_time > 180:
             await msg.edit(content="**Stop timed out (3m)")
             break
        try:
            #Fetch latest logs
            log_resp = requests.get(url_console, headers=headers)
            if log_resp.status_code == 200:
                try:
                    full_log = log_resp.json().get('logs', '')
                except:
                    full_log = log_resp.text
                
                if full_log:
                    snippet = full_log[-1000:]
                    if "Running post-execution steps" in snippet:
                        await msg.edit(content="**Server Stopped Successfully!**")
                        return
        except:
            pass




@mc_bot.command()
async def helper(ctx):
    msg = """**Help Menu**
`/mc helper` - Shows this list
`/mc hello` - Greet the server
`/mc start` - Start the server
`/mc stop` - Stop the server if no players online
`/mc stop force` - Stop the server with players online (OP)
`/mc status` - Check server stats
`/mc timeout` - Deactivates PVP for 10 mins
`/mc logs` - Check the logs (OP)
`/mc cmd` - write in any command (OP)"""
    await ctx.send (msg)

@mc_bot.command()
async def cmd(ctx, *, command_to_run):
    if ctx.author.id != dc_id:
        return await ctx.send("No permission")
        
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain" 
    }
    
    url_console = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
    response_console = requests.post(url_console, headers=headers, data=command_to_run)
    
    if response_console.status_code == 204:
        await asyncio.sleep(0.5) 
        read_headers = {"Authorization": f"Bearer {token}"}
        log_resp = requests.get(url_console, headers=read_headers)
        output = "Sent."
        if log_resp.status_code == 200:
            try:
                full_log = log_resp.json().get('logs', '')
            except:
                full_log = log_resp.text
                
            if full_log:
                lines = full_log.strip().split('\n')
                last_line = lines[-1]
                output = f"Sent: `{command_to_run}`\nResponse: `{last_line}`"
        await ctx.send(output)
    else:
        await ctx.send(f"Failed {response_console.status_code}: {response_console.text}")

@mc_bot.command()
async def logs(ctx):
    if ctx.author.id != dc_id:
        return await ctx.send("No premission dumass")
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {"Authorization": f"Bearer {token}"}
    
    url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        try:
            content = resp.json().get('logs', '')
        except:
            content = resp.text
        
        if not content:
            return await ctx.send("Log is empty.")
        lines = content.strip().split('\n')
        last_lines = lines[-10:]
        log_text = "\n".join(last_lines)
        await ctx.send(f"**Last 10 logs:**\n```\n{log_text}\n```")
    else:
        await ctx.send(f"Error fetching logs: {resp.status_code}")

@mc_bot.command()
@commands.cooldown(1, 1800, commands.BucketType.guild)
async def timeout(ctx):
    token, response = get_puffer_token()
    if token is None:
        return await ctx.send("**Error:** PufferPanel Auth Failed.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain" 
    }

    url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
    response_console = requests.post(url, headers=headers, data="gamerule pvp false")
    if response_console.status_code == 204:
        await ctx.send(f"**PVP is off for 10 minutes**")
        url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
        response_console = requests.post(url, headers=headers, data="say PVP is inactive for 10 mins")
        await asyncio.sleep(600)

        token, response = get_puffer_token()
        if token is None:
            return await ctx.send("**Error:** PufferPanel Auth Failed.")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain" 
        }
        
        url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
        response_console = requests.post(url, headers=headers, data="gamerule pvp true")
        url = f"{PUFFER_URL}/daemon/server/{PUFFER_MC_ID}/console"
        response_console = requests.post(url, headers=headers, data="say PVP is now active")
        
    else:
        await ctx.send(f"Failed {response_console.status_code}: {response_console.text}")

@timeout.error
async def timeout_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        total_seconds = int(error.retry_after)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        await ctx.send(f"**Cooldown: `{minutes} minutes {seconds} seconds`.")    

mc_bot.run(dc_token, log_handler=handler, log_level=logging.DEBUG)
