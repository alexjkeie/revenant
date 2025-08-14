import os, json, random, asyncio, aiohttp
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import discord
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN", "PUT_TOKEN_HERE")
LOG_FILE = "revenant_log_channels.json"

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_log_channel(guild_id):
    cfg = load_json(LOG_FILE)
    return cfg.get(str(guild_id))

def set_log_channel(guild_id, channel_id):
    cfg = load_json(LOG_FILE)
    cfg[str(guild_id)] = channel_id
    save_json(LOG_FILE, cfg)

def risk_score(name, desc, tags, members):
    score = 0
    reasons = []
    keywords = [
        "free nitro","robux","crypto","giveaway","steam gift","airdrop",
        "verification required","egirls","18+","nsfw","sexy","hot","onlyfans","camgirl",
        "leak","leaks","password","token","discord token","nitro scam","credit card",
        "hacked","hack","cheat","cheats","exploit","phishing","raider","raid","porn",
        "xxx","sex","adult","cam","cams","camgirl","18 plus","18+","18plus",
        "free robux","free v bucks","free valorant points","steam key","gift card",
        "airdrop","cryptocurrency","bitcoin","eth","ethereum","wallet","scam","fraud",
        "malware","virus","trojan","keylogger","apk","mod","cheat engine","botting",
        "spam","spammer","server nuker","raid bot","selfbot","alts","sell accounts",
        "selling accounts","account sale","account giveaway","onlyfans leak",
        "nsfw leaks","leaked","hack tool","generator","valorant cheats","roblox exploits"
    ]
    text = " ".join([name, desc, " ".join(tags)]).lower()
    hits = [k for k in keywords if k in text]
    if hits:
        score += 3
        reasons.append("suspicious keywords: "+", ".join(hits))
    if members < 20:
        score += 1
        reasons.append("very small server")
    return score, reasons

async def fetch_page(session, url):
    async with session.get(url) as r:
        return await r.text()

async def parse_disboard(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for li in soup.select("div.server-card"):
        name_tag = li.select_one("h3.server-name a")
        if not name_tag: continue
        name = name_tag.text.strip()
        link = "https://disboard.org" + name_tag["href"]
        desc_tag = li.select_one("div.server-description")
        desc = desc_tag.text.strip() if desc_tag else ""
        tags = [t.text.strip() for t in li.select("div.tag")]
        members_tag = li.select_one("div.server-members span.count")
        members = int(members_tag.text.replace(",","")) if members_tag else 0
        icon_tag = li.select_one("img.server-icon")
        icon = icon_tag["src"] if icon_tag else None
        results.append({"name": name,"desc": desc,"tags": tags,"link": link,"members": members,"icon": icon})
    return results

async def parse_discordservers(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for card in soup.select("div.server-card"):
        name_tag = card.select_one("h3 a")
        if not name_tag: continue
        name = name_tag.text.strip()
        link = name_tag["href"]
        desc_tag = card.select_one("p.description")
        desc = desc_tag.text.strip() if desc_tag else ""
        tags = [t.text.strip() for t in card.select("span.tag")]
        members_tag = card.select_one("span.members")
        members = int(members_tag.text.replace(",","")) if members_tag else 0
        icon_tag = card.select_one("img.server-icon")
        icon = icon_tag["src"] if icon_tag else None
        results.append({"name": name,"desc": desc,"tags": tags,"link": link,"members": members,"icon": icon})
    return results

@tree.command(name="setlogchannel", description="Set where Revenant logs found servers")
@app_commands.describe(channel="Select the log channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    set_log_channel(interaction.guild.id, channel.id)
    e = discord.Embed(title="Revenant Log Channel Set",
                      description=f"Logs will be posted in {channel.mention}",
                      color=0x8b0000, timestamp=datetime.now(timezone.utc))
    await interaction.response.send_message(embed=e, ephemeral=True)

@setlogchannel.error
async def setlogchannel_error(interaction, error):
    try: await interaction.response.send_message("You lack permission.", ephemeral=True)
    except: pass

@tree.command(name="scan", description="Scan multiple sites for suspicious servers")
async def scan(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ch_id = get_log_channel(interaction.guild.id)
    ch = interaction.guild.get_channel(ch_id) if ch_id else None

    intro_texts = [
        "Revenant is crawling through the web, finding victims...",
        "Scanning the shadows for my next kill...",
        "Targets are hiding. I’ll drag them into the light.",
        "I smell fear in these servers. Let’s hunt.",
        "Hunting servers like prey in the dark.",
        "The hunt begins. No one is safe.",
        "Slicing through the web for suspicious activity.",
        "My claws reach far and wide. Targets detected soon."
    ]
    if ch:
        await ch.send(embed=discord.Embed(description=random.choice(intro_texts),
                                          color=0x8b0000,
                                          timestamp=datetime.now(timezone.utc)))
    async with aiohttp.ClientSession() as session:
        all_servers = []

        # Disboard pages
        for page in range(1, 6):
            html = await fetch_page(session, f"https://disboard.org/servers?sort=recent&page={page}")
            all_servers.extend(await parse_disboard(html))

        # DiscordServers pages
        for page in range(1, 6):
            html = await fetch_page(session, f"https://discordservers.com/browse?page={page}")
            all_servers.extend(await parse_discordservers(html))

        found = False
        for s in all_servers:
            score, reasons = risk_score(s["name"], s["desc"], s["tags"], s["members"])
            if score >= 2 and ch:
                found = True
                e = discord.Embed(title="Suspicious Server Detected", color=0xdc143c,
                                  timestamp=datetime.now(timezone.utc))
                e.add_field(name="Server", value=f"{s['name']}", inline=False)
                e.add_field(name="Server Link", value=f"[Join]({s['link']})", inline=False)
                e.add_field(name="Members", value=str(s["members"]), inline=True)
                e.add_field(name="Tags", value=", ".join(s["tags"]) or "None", inline=False)
                e.add_field(name="Risk Score", value=str(score), inline=True)
                e.add_field(name="Reasons", value=", ".join(reasons) or "None", inline=False)
                if s["icon"]:
                    e.set_thumbnail(url=s["icon"])
                await ch.send(embed=e)

        if not found and ch:
            e = discord.Embed(title="No Victims Found",
                              description="Revenant reports: no victims yet...",
                              color=0x8b0000, timestamp=datetime.now(timezone.utc))
            await ch.send(embed=e)
    try:
        await interaction.followup.send("Scan finished.", ephemeral=True)
    except: pass

@client.event
async def on_ready():
    try:
        await tree.sync()
    except: pass

async def main():
    async with client:
        await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
