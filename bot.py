import os, json, random, aiohttp, asyncio
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN", "PUT_TOKEN_HERE")
LOG_FILE = "revenant_log_channels.json"

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Ensure JSON log file exists
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

TRIGGER_WORDS = [
    "free nitro","robux","crypto","giveaway","steam gift","airdrop","verification required",
    "egirls","18+","nsfw","sexy","hot","onlyfans","camgirl","leak","leaks","password",
    "token","discord token","nitro scam","credit card","hacked","hack","cheat","cheats",
    "exploit","phishing","raider","raid","porn","xxx","sex","adult","cam","cams","18 plus",
    "18+","18plus","free robux","free v bucks","steam key","gift card","cryptocurrency",
    "bitcoin","eth","ethereum","wallet","scam","fraud","malware","virus","trojan","keylogger",
    "apk","mod","cheat engine","botting","spam","spammer","server nuker","raid bot","selfbot",
    "alts","sell accounts","selling accounts","account sale","account giveaway","onlyfans leak",
    "nsfw leaks","leaked","hack tool","generator","valorant cheats","roblox exploits"
]

def risk_score(name, desc, tags, members):
    score = 0
    reasons = []
    text = " ".join([name, desc, " ".join(tags)]).lower()
    hits = [word for word in TRIGGER_WORDS if word in text]
    if hits:
        score += 3
        reasons.append(f"Suspicious keywords: {', '.join(hits)}")
    if members < 20:
        score += 1
        reasons.append("Very small server")
    return score, reasons

async def fetch_disboard(session, pages=3):
    servers = []
    base = "https://disboard.org/servers?sort=recent&page="
    for page in range(1, pages+1):
        async with session.get(base+str(page)) as r:
            html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
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
                servers.append({"name":name,"desc":desc,"tags":tags,"link":link,"members":members,"icon":icon})
    return servers

@bot.command()
async def setlogchannel(ctx, channel: discord.TextChannel):
    set_log_channel(ctx.guild.id, channel.id)
    await ctx.send(f"Revenant log channel set to {channel.mention}")

@bot.command()
async def scan(ctx):
    log_channel_id = get_log_channel(ctx.guild.id)
    if not log_channel_id:
        await ctx.send("Log channel not set. Use !setlogchannel <channel>.")
        return

    log_channel = ctx.guild.get_channel(log_channel_id)
    if not log_channel:
        await ctx.send("Invalid log channel. Set a valid channel first.")
        return

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
    await log_channel.send(embed=discord.Embed(description=random.choice(intro_texts), color=0x8b0000, timestamp=datetime.now(timezone.utc)))

    total_scanned = 0
    total_flagged = 0
    async with aiohttp.ClientSession() as session:
        servers = await fetch_disboard(session, pages=3)
        for s in servers:
            total_scanned += 1
            score, reasons = risk_score(s["name"], s["desc"], s["tags"], s["members"])
            if score >= 2:
                total_flagged += 1
                e = discord.Embed(title="Suspicious Server Detected", color=0xdc143c, timestamp=datetime.now(timezone.utc))
                e.add_field(name="Server", value=s["name"], inline=False)
                e.add_field(name="Server Link", value=f"[Join]({s['link']})", inline=False)
                e.add_field(name="Members", value=str(s["members"]), inline=True)
                e.add_field(name="Tags", value=", ".join(s["tags"]) or "None", inline=False)
                e.add_field(name="Score", value=str(score), inline=True)
                e.add_field(name="Reasons", value=", ".join(reasons) or "None", inline=False)
                if s["icon"]:
                    e.set_thumbnail(url=s["icon"])
                await log_channel.send(embed=e)

    summary = discord.Embed(title="Scan Complete", color=0x8b0000)
    summary.add_field(name="Total Servers Scanned", value=str(total_scanned))
    summary.add_field(name="Suspicious Servers Found", value=str(total_flagged))
    if total_flagged == 0:
        summary.description = "Revenant reports: no victims yet..."
    await log_channel.send(embed=summary)
    await ctx.send("Scan finished.")

bot.run(TOKEN)
