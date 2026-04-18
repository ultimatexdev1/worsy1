import os
import json
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE =================
def load_db(name):
    if not os.path.exists(name):
        with open(name, "w") as f:
            json.dump({}, f)
    with open(name, "r") as f:
        return json.load(f)

def save_db(name, data):
    with open(name, "w") as f:
        json.dump(data, f, indent=4)

# ================= READY =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} aktif!")

# ================= WARN SYSTEM =================
@bot.tree.command(name="warn")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str = "Yok"):
    db = load_db("warns.json")
    uid = str(user.id)

    if uid not in db:
        db[uid] = []

    db[uid].append(reason)
    save_db("warns.json", db)

    await interaction.response.send_message(f"{user} uyarıldı.")

@bot.tree.command(name="warnlar")
async def warnlar(interaction: discord.Interaction, user: discord.Member):
    db = load_db("warns.json")
    uid = str(user.id)

    if uid not in db:
        await interaction.response.send_message("Warn yok.")
        return

    warns = "\n".join(db[uid])
    await interaction.response.send_message(f"{user} warnları:\n{warns}")

# ================= INVITE SYSTEM =================
invites = {}
invite_db_file = "invites.json"

@bot.event
async def on_ready():
    for guild in bot.guilds:
        invites[guild.id] = await guild.invites()

@bot.event
async def on_member_join(member):
    db = load_db(invite_db_file)
    before = invites[member.guild.id]
    after = await member.guild.invites()
    invites[member.guild.id] = after

    for i in after:
        for j in before:
            if i.code == j.code and i.uses > j.uses:
                inviter = str(i.inviter.id)
                db[inviter] = db.get(inviter, 0) + 1
                save_db(invite_db_file, db)

@bot.tree.command(name="invite-kontrol")
async def invite_kontrol(interaction: discord.Interaction, user: discord.Member):
    db = load_db(invite_db_file)
    count = db.get(str(user.id), 0)
    await interaction.response.send_message(f"{user} davet sayısı: {count}")

# ================= TICKET =================
class TicketView(discord.ui.View):
    @discord.ui.button(label="Ticket Aç", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name="Support")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True)
        }
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
        await channel.send(f"{interaction.user.mention} ticket açtı.")
        await interaction.response.send_message("Açıldı!", ephemeral=True)

@bot.tree.command(name="ticket-kur")
async def ticket_kur(interaction: discord.Interaction):
    await interaction.channel.send("Ticket:", view=TicketView())
    await interaction.response.send_message("Kuruldu", ephemeral=True)

@bot.tree.command(name="ticket-kapat")
async def ticket_kapat(interaction: discord.Interaction):
    messages = [msg async for msg in interaction.channel.history(limit=100)]
    content = "\n".join([f"{m.author}: {m.content}" for m in messages])

    with open("transcript.txt", "w", encoding="utf-8") as f:
        f.write(content)

    await interaction.channel.send("Transcript alındı.")
    await interaction.channel.delete()

# ================= GIVEAWAY =================
giveaways = {}

@bot.tree.command(name="çekiliş")
async def cekilis(interaction: discord.Interaction, sure: int, odul: str):
    embed = discord.Embed(title="🎉 Çekiliş", description=odul)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")

    giveaways[msg.id] = {"end": sure, "channel": interaction.channel.id}

    await interaction.response.send_message("Başladı!", ephemeral=True)

@tasks.loop(seconds=10)
async def check_giveaways():
    for msg_id in list(giveaways.keys()):
        giveaways[msg_id]["end"] -= 10
        if giveaways[msg_id]["end"] <= 0:
            channel = bot.get_channel(giveaways[msg_id]["channel"])
            msg = await channel.fetch_message(msg_id)
            users = [u async for u in msg.reactions[0].users() if not u.bot]
            if users:
                winner = random.choice(users)
                await channel.send(f"Kazanan: {winner.mention}")
            else:
                await channel.send("Katılım yok.")
            del giveaways[msg_id]

@bot.event
async def on_ready():
    check_giveaways.start()

bot.run(os.getenv("TOKEN"))
