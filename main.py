import discord
from discord.ext import commands
import json
import os
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
import re

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Data storage
NPC_DATA = {}  # {npc_id: {name, lore, channel_id}}
PLAYER_LORE = {}  # {player_id: lore_text}
CONVERSATION_HISTORY = {}  # Track conversations for context

# Configuration
CONFIG_FILE = "npc_config.json"
PLAYER_LORE_FILE = "player_lore.json"

# Load existing data
def load_data():
    global NPC_DATA, PLAYER_LORE
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            NPC_DATA = json.load(f)
    if os.path.exists(PLAYER_LORE_FILE):
        with open(PLAYER_LORE_FILE, "r") as f:
            PLAYER_LORE = json.load(f)

# Save data
def save_data():
    with open(CONFIG_FILE, "w") as f:
        json.dump(NPC_DATA, f, indent=2)
    with open(PLAYER_LORE_FILE, "w") as f:
        json.dump(PLAYER_LORE, f, indent=2)

# Extract text from Google Docs link
async def fetch_google_doc(doc_url):
    """Fetch content from a Google Doc share link"""
    try:
        # Convert share link to export format
        if "/document/d/" in doc_url:
            doc_id = doc_url.split("/document/d/")[1].split("/")[0]
            export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        else:
            return None
        
        async with aiohttp.ClientSession() as session:
            async with session.get(export_url) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception as e:
        print(f"Error fetching Google Doc: {e}")
    return None

# Parse RP message format
def parse_rp_message(message_content):
    """
    Parse RP message and identify:
    - OOC (parentheses) - bot ignores
    - Action (single *) - action text
    - Narration (double **) - narration text
    - Dialogue ("quotes") - in-character speech
    """
    parsed = {
        "has_ooc": False,
        "actions": [],
        "narration": [],
        "dialogue": []
    }
    
    # Check for OOC (parentheses)
    if "(" in message_content and ")" in message_content:
        parsed["has_ooc"] = True
    
    # Extract double asterisks (narration)
    narration_pattern = r'\*\*(.+?)\*\*'
    parsed["narration"] = re.findall(narration_pattern, message_content)
    
    # Extract single asterisks (actions) - avoid matching double asterisks
    action_pattern = r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)'
    parsed["actions"] = re.findall(action_pattern, message_content)
    
    # Extract quoted dialogue
    dialogue_pattern = r'"(.+?)"'
    parsed["dialogue"] = re.findall(dialogue_pattern, message_content)
    
    return parsed

@bot.event
async def on_ready():
    load_data()
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

@bot.event
async def on_message(message):
    """Main message handler for RP interactions"""
    if message.author == bot.user:
        return
    
    # Parse the message
    parsed = parse_rp_message(message.content)
    
    # Ignore if only OOC
    if parsed["has_ooc"] and not parsed["actions"] and not parsed["narration"] and not parsed["dialogue"]:
        return
    
    # Extract dialogue and actions for NPC response
    rp_content = " ".join(parsed["dialogue"] + parsed["actions"] + parsed["narration"])
    
    if not rp_content:
        return
    
    # Check which NPCs should respond in this channel
    npcs_in_channel = [npc_id for npc_id, npc_data in NPC_DATA.items() 
                       if str(npc_data.get("channel_id")) == str(message.channel.id)]
    
    for npc_id in npcs_in_channel:
        npc = NPC_DATA[npc_id]
        
        # Generate NPC response using context
        response = await generate_npc_response(
            npc_id,
            message.author.name,
            rp_content,
            npc.get("lore", ""),
            message
        )
        
        if response:
            # Format response appropriately
            await message.channel.send(response)

async def generate_npc_response(npc_id, player_name, message_content, npc_lore, message_obj):
    """Generate NPC response based on context and lore"""
    npc = NPC_DATA[npc_id]
    
    # Build context from recent messages
    context = await build_conversation_context(message_obj.channel, limit=5)
    
    # Get player lore if available
    player_id = str(message_obj.author.id)
    player_lore = PLAYER_LORE.get(player_id, "")
    
    prompt = f"""
You are roleplaying as {npc['name']}.

Your Lore/Background:
{npc_lore}

Player Information:
{player_lore if player_lore else 'No lore available'}

Recent Conversation:
{context}

Current message from {player_name}: {message_content}

Respond as your character would. Keep it brief (1-2 sentences). 
Format your response as dialogue in quotes if speaking, or as an action with single asterisk *like this* or narration with double asterisks **like this**.
Stay in character and use the lore provided to inform your response.
"""
    
    try:
        # Using a simple response generator (you can integrate with OpenAI/Claude)
        # For now, return a contextual response
        response = f'*{npc["name"]} responds to {player_name}*\n"{generate_contextual_response(npc, player_name, message_content)}"'
        return response
    except Exception as e:
        print(f"Error generating response: {e}")
        return None

async def build_conversation_context(channel, limit=5):
    """Build context from recent channel messages"""
    context = []
    async for msg in channel.history(limit=limit):
        if msg.author != bot.user:
            context.append(f"{msg.author.name}: {msg.content}")
    return "\n".join(reversed(context))

def generate_contextual_response(npc, player_name, message_content):
    """Generate a simple contextual response based on lore"""
    # This is a placeholder - integrate with OpenAI/Claude for better responses
    npc_name = npc.get("name", "Unknown")
    
    if "hello" in message_content.lower() or "hi" in message_content.lower():
        return f"Oh, hello {player_name}. Nice to see you."
    elif "how are you" in message_content.lower():
        return f"I'm doing well, thanks for asking."
    else:
        return f"Interesting... I'll have to think about that."

# ADMIN COMMANDS

@bot.command(name="npc_create")
@commands.is_owner()
async def create_npc(ctx, npc_name: str, channel: discord.TextChannel, *, lore_doc_url: str = None):
    """Create a new NPC and set their lore"""
    npc_id = f"{npc_name}_{ctx.guild.id}"
    
    lore_text = ""
    if lore_doc_url:
        lore_text = await fetch_google_doc(lore_doc_url)
        if not lore_text:
            await ctx.send("❌ Could not fetch the lore document. Make sure the link is correct and publicly accessible.")
            return
    
    NPC_DATA[npc_id] = {
        "name": npc_name,
        "lore": lore_text,
        "channel_id": channel.id,
        "created_at": datetime.now().isoformat()
    }
    
    save_data()
    await ctx.send(f"✅ NPC **{npc_name}** created in {channel.mention}")

@bot.command(name="npc_delete")
@commands.is_owner()
async def delete_npc(ctx, npc_name: str):
    """Delete a specific NPC"""
    npc_id = f"{npc_name}_{ctx.guild.id}"
    
    if npc_id not in NPC_DATA:
        await ctx.send(f"❌ NPC **{npc_name}** not found.")
        return
    
    del NPC_DATA[npc_id]
    save_data()
    await ctx.send(f"✅ NPC **{npc_name}** has been deleted.")

@bot.command(name="npc_lore")
@commands.is_owner()
async def update_npc_lore(ctx, npc_name: str, *, lore_doc_url: str):
    """Update an NPC's lore from a Google Doc"""
    npc_id = f"{npc_name}_{ctx.guild.id}"
    
    if npc_id not in NPC_DATA:
        await ctx.send(f"❌ NPC **{npc_name}** not found.")
        return
    
    lore_text = await fetch_google_doc(lore_doc_url)
    if not lore_text:
        await ctx.send("❌ Could not fetch the lore document.")
        return
    
    NPC_DATA[npc_id]["lore"] = lore_text
    save_data()
    await ctx.send(f"✅ **{npc_name}**'s lore has been updated.")

@bot.command(name="player_lore")
@commands.is_owner()
async def set_player_lore(ctx, player: discord.Member, *, lore_doc_url: str):
    """Set a player's lore from a Google Doc"""
    player_id = str(player.id)
    
    lore_text = await fetch_google_doc(lore_doc_url)
    if not lore_text:
        await ctx.send("❌ Could not fetch the lore document.")
        return
    
    PLAYER_LORE[player_id] = lore_text
    save_data()
    await ctx.send(f"✅ {player.mention}'s lore has been set.")

@bot.command(name="npc_list")
async def list_npcs(ctx):
    """List all NPCs in the server"""
    guild_npcs = {npc_id: npc for npc_id, npc in NPC_DATA.items() 
                  if str(npc.get("channel_id")) in [str(c.id) for c in ctx.guild.text_channels]}
    
    if not guild_npcs:
        await ctx.send("No NPCs found in this server.")
        return
    
    embed = discord.Embed(title="NPCs in this Server", color=discord.Color.blue())
    for npc_id, npc in guild_npcs.items():
        channel = bot.get_channel(npc["channel_id"])
        embed.add_field(
            name=npc["name"],
            value=f"Channel: {channel.mention if channel else 'Unknown'}\nCreated: {npc.get('created_at', 'Unknown')}",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Run the bot
bot.run("YOUR_BOT_TOKEN")
