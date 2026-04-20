import os
import json
import discord
import asyncio
import random
from discord.ext import commands, tasks
from discord import app_commands

# ================= AYARLAR =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

INVITE_DB = "invites.json"
WARN_DB = "warns.json"

DUYURU_KANAL_ID = 1494765464000397473
OTO_ROL_ID = 1456546396814573681

invites = {}
giveaways = {}

# ================= DATABASE =================
def load_db(name):
    if not os.path.exists(name):
        with open(name, "w") as f:
            json.dump({}, f)
    try:
        with open(name, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(name, data):
    with open(name, "w") as f:
        json.dump(data, f, indent=4)

# ================= TICKET =================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticketı Kapat", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ekip Alımı", emoji="⚔️"),
            discord.SelectOption(label="Yetkili Alımı", emoji="🛡️"),
            discord.SelectOption(label="Partnerlik", emoji="🤝"),
            discord.SelectOption(label="Destek", emoji="🎫")
        ]
        super().__init__(placeholder="Kategori seç...", options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites
        )

        await channel.send(
            f"{interaction.user.mention} talebin alındı.",
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"Oluşturuldu: {channel.mention}", ephemeral=True
        )

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ================= EVENTS =================
@bot.event
async def on_ready():
    await asyncio.sleep(2)

    for guild in bot.guilds:
        try:
            invites[guild.id] = await guild.invites()
            await bot.tree.sync(guild=guild)  # 🔥 ANINDA KOMUT
        except:
            pass

    if not check_giveaways.is_running():
        check_giveaways.start()

    print(f"✅ {bot.user} aktif!")

@bot.event
async def on_app_command_error(interaction, error):
    print("HATA:", error)

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(OTO_ROL_ID)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

# ================= KOMUTLAR =================
@bot.tree.command(name="ticket-kur")
async def ticket_kur(interaction: discord.Interaction):
    await interaction.channel.send(
        "Destek almak için seç:",
        view=TicketView()
    )
    await interaction.response.send_message("Kuruldu", ephemeral=True)

@bot.tree.command(name="duyuru-at")
@app_commands.checks.has_permissions(administrator=True)
async def duyuru(interaction: discord.Interaction, mesaj: str):
    channel = bot.get_channel(DUYURU_KANAL_ID)

    embed = discord.Embed(
        title="📢 Duyuru",
        description=mesaj,
        color=discord.Color.red()
    )

    await channel.send("@everyone", embed=embed)
    await interaction.response.send_message("Atıldı", ephemeral=True)

@bot.tree.command(name="warn")
async def warn(interaction: discord.Interaction, user: discord.Member, sebep: str = "Yok"):
    db = load_db(WARN_DB)
    uid = str(user.id)

    if uid not in db:
        db[uid] = []

    db[uid].append(sebep)
    save_db(WARN_DB, db)

    await interaction.response.send_message(f"Uyarıldı: {user.mention}")

@bot.tree.command(name="inviteler")
async def inviteler(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    db = load_db(INVITE_DB)
    count = db.get(str(user.id), 0)

    await interaction.response.send_message(f"{user.mention}: {count}")

@bot.tree.command(name="çekiliş")
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    msg = await interaction.channel.send(f"🎉 {odul} çekilişi başladı!")

    await msg.add_reaction("🎉")

    giveaways[msg.id] = {
        "end": saniye,
        "channel": interaction.channel.id,
        "reward": odul
    }

    await interaction.response.send_message("Başladı", ephemeral=True)

@tasks.loop(seconds=10)
async def check_giveaways():
    for msg_id in list(giveaways.keys()):
        giveaways[msg_id]["end"] -= 10

        if giveaways[msg_id]["end"] <= 0:
            channel = bot.get_channel(giveaways[msg_id]["channel"])

            try:
                msg = await channel.fetch_message(msg_id)
                users = [u async for u in msg.reactions[0].users() if not u.bot]

                if users:
                    winner = random.choice(users).mention
                else:
                    winner = "Katılım yok"

                await channel.send(f"Kazanan: {winner}")

            except:
                pass

            del giveaways[msg_id]

# ================= BAŞLAT =================
TOKEN = os.getenv("TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("TOKEN YOK!")
