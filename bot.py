import os, json, random, asyncio, aiohttp, re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import discord
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN", "PUT_TOKEN_HERE")
CONFIG_FILE = "config.json"
DISBOARD_BASE = "https://disboard.org"

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"log_channels": {}}, f, indent=2)

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def account_age_days(created):
    return (datetime.now(timezone.utc) - created).total_seconds()/86400

def risk_score(name, desc, tags, members, age_days, verification):
    score = 0
    reasons = []
    keywords = ["free nitro","robux","crypto","giveaway","steam gift","airdrop","verification required"]
    text = " ".join([name, desc, " ".join(tags)]).lower()
    hits = [k for k in keywords if k in text]
    if hits:
        score += 3
        reasons.append("suspicious keywords: "+", ".join(hits))
    if members < 20:
        score += 2; reasons.append("very small server")
    if age_days < 7:
        score += 2; reasons.append("new server")
    if verification in ["none","low"]:
        score += 1; reasons.append("low verification")
    return score, reasons

def get_log_channel(guild_id):
    cfg = load_config()
    cid = cfg.get("log_channels", {}).get(str(guild_id))
    return cid

async def fetch_disboard_page(session, page=1):
    url = f"{DISBOARD_BASE}/servers?sort=recent&page={page}"
    async with session.get(url) as r:
        return await r.text()

async def parse_server_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for li in soup.select("div.server-card"):
        name_tag = li.select_one("h3.server-name a")
        if not name_tag:
            continue
        name = name_tag.text.strip()
        link = DISBOARD_BASE + name_tag["href"]
        desc_tag = li.select_one("div.server-description")
        desc = desc_tag.text.strip() if desc_tag else ""
        tag_elements = li.select("div.tag")
        tags = [t.text.strip() for t in tag_elements]
        members_tag = li.select_one("div.server-members span.count")
        members = int(members_tag.text.replace(",","")) if members_tag else 0
        icon_tag = li.select_one("img.server-icon")
        icon = icon_tag["src"] if icon_tag else None
        results.append({"name":name,"desc":desc,"tags":tags,"link":link,"members":members,"icon":icon})
    return results

async def fetch_invite_info(session, invite_url):
    m = re.search(r"(discord\.gg|discord\.com/invite)/([a-zA-Z0-9-]+)", invite_url)
    if not m:
        return None
    code = m.group(2)
    api = f"https://discord.com/api/v10/invites/{code}?with_counts=true"
    headers = {"User-Agent":"Mozilla/5.0"}
    try:
        async with session.get(api, headers=headers) as r:
            if r.status == 200:
                return await r.json()
    except: pass
    return None

@tree.command(name="setlogchannel", description="Set where Revenant logs found servers")
@app_commands.describe(channel="Select the log channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    cfg = load_config()
    cfg["log_channels"][str(interaction.guild.id)] = channel.id
    save_config(cfg)
    e = discord.Embed(title="Revenant Log Channel Set", description=f"Logs will be posted in {channel.mention}", color=0x8b0000, timestamp=datetime.now(timezone.utc))
    await interaction.response.send_message(embed=e, ephemeral=True)

@setlogchannel.error
async def setlogchannel_error(interaction, error):
    try: await interaction.response.send_message("You lack permission.", ephemeral=True)
    except: pass

@tree.command(name="scan", description="Scan Disboard for suspicious servers")
async def scan(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    cfg = load_config()
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
        await ch.send(embed=discord.Embed(description=random.choice(intro_texts), color=0x8b0000, timestamp=datetime.now(timezone.utc)))
    async with aiohttp.ClientSession() as session:
        all_servers = []
        for page in range(1,4):
            html = await fetch_disboard_page(session,page)
            servers = await parse_server_listing(html)
            all_servers.extend(servers)
        for s in all_servers:
            info = await fetch_invite_info(session, s["link"])
            if info:
                created = datetime.fromtimestamp(info.get("guild", {}).get("id",0)>>22/1000 + 1420070400, tz=timezone.utc)
                age_days = account_age_days(created)
                verification = info.get("guild", {}).get("verification_level","none")
            else:
                created = datetime.now(timezone.utc)
                age_days = 0
                verification = "none"
            score,reasons = risk_score(s["name"], s["desc"], s["tags"], s["members"], age_days, verification)
            if score >= 4 and ch:
                e = discord.Embed(title="Suspicious Server Detected", color=0xdc143c, timestamp=datetime.now(timezone.utc))
                e.add_field(name="Server", value=f"{s['name']}", inline=False)
                e.add_field(name="Server Link", value=f"[Join]({s['link']})", inline=False)
                e.add_field(name="Members", value=str(s["members"]), inline=True)
                e.add_field(name="Age (days)", value=f"{age_days:.1f}", inline=True)
                e.add_field(name="Tags", value=", ".join(s["tags"]) or "None", inline=False)
                e.add_field(name="Risk Score", value=str(score), inline=True)
                e.add_field(name="Reasons", value=", ".join(reasons) or "None", inline=False)
                if s["icon"]:
                    e.set_thumbnail(url=s["icon"])
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
