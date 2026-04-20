import os
import json
import discord
import asyncio
import random
from discord.ext import commands, tasks
from discord import app_commands

# ================= AYARLAR & INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Veritabanı Dosyaları
INVITE_DB = "invites.json"
WARN_DB = "warns.json"

# Sabit ID'ler
DUYURU_KANAL_ID = 1494765464000397473
SES_KANAL_ID = 1468699538540855330
OTO_ROL_ID = 1456546396814573681

invites = {}
giveaways = {}

# ================= VERİTABANI =================
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

# ================= SES SİSTEMİ =================
async def stay_in_voice():
    try:
        channel = await bot.fetch_channel(SES_KANAL_ID)

        if not channel:
            print("Ses kanalı bulunamadı")
            return

        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)

        if not vc:
            await channel.connect(reconnect=True, timeout=20, self_deaf=True, self_mute=True)
            print("🔊 Sese bağlandı")
        elif vc.channel.id != SES_KANAL_ID:
            await vc.move_to(channel)

    except Exception as e:
        print(f"Ses hatası: {e}")

# 🔥 YENİ: sürekli kontrol
@tasks.loop(seconds=60)
async def voice_guard():
    await stay_in_voice()

# ================= TICKET =================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticketı Kapat", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Kanal 3 saniye içinde kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ekip Alımı", description="Klanımıza katılmak için başvurun.", emoji="⚔️"),
            discord.SelectOption(label="Yetkili Alımı", description="Rehber/Mod başvurusu.", emoji="🛡️"),
            discord.SelectOption(label="Partnerlik ve Merge", description="Ortaklık talepleri.", emoji="🤝"),
            discord.SelectOption(label="Destek", description="Genel yardım ve sorular.", emoji="🎫")
        ]
        super().__init__(placeholder="Bir kategori seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category_name = self.values[0]
        support_role = discord.utils.get(guild.roles, name="Support")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await guild.create_text_channel(
            name=f"{category_name.lower()}-{interaction.user.name}",
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"🎫 {category_name} Talebi",
            description=f"Merhaba {interaction.user.mention}, talebiniz alındı.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"Ticket: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ================= EVENTS =================
@bot.event
async def on_ready():
    await asyncio.sleep(3)
    await stay_in_voice()

    for guild in bot.guilds:
        try:
            invites[guild.id] = await guild.invites()
        except:
            pass

    if not check_giveaways.is_running():
        check_giveaways.start()

    # 🔥 EKLENDİ
    if not voice_guard.is_running():
        voice_guard.start()

    await bot.tree.sync()
    print(f"✅ {bot.user} aktif")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        await asyncio.sleep(5)
        await stay_in_voice()

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(OTO_ROL_ID)
    if role:
        await member.add_roles(role)

    db = load_db(INVITE_DB)
    try:
        before = invites.get(member.guild.id, [])
        after = await member.guild.invites()
        invites[member.guild.id] = after

        for i in after:
            for j in before:
                if i.code == j.code and i.uses > j.uses:
                    uid = str(i.inviter.id)
                    db[uid] = db.get(uid, 0) + 1
                    save_db(INVITE_DB, db)
                    return
    except:
        pass

# ================= KOMUTLAR =================
@bot.tree.command(name="ticket-kur")
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(title="Destek Sistemi")
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Kuruldu", ephemeral=True)

@bot.tree.command(name="oylama")
async def oylama(interaction: discord.Interaction, soru: str):
    msg = await interaction.channel.send(soru)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("Başladı", ephemeral=True)

@bot.tree.command(name="warn")
async def warn(interaction: discord.Interaction, user: discord.Member, sebep: str):
    db = load_db(WARN_DB)
    uid = str(user.id)
    db.setdefault(uid, []).append(sebep)
    save_db(WARN_DB, db)
    await interaction.response.send_message("Uyarıldı")

@bot.tree.command(name="inviteler")
async def inviteler(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    db = load_db(INVITE_DB)
    await interaction.response.send_message(f"{db.get(str(user.id),0)} davet")

@bot.tree.command(name="çekiliş")
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    msg = await interaction.channel.send(f"🎉 {odul}")
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"end": saniye, "channel": interaction.channel.id, "reward": odul}
    await interaction.response.send_message("Başladı", ephemeral=True)

@tasks.loop(seconds=10)
async def check_giveaways():
    for msg_id in list(giveaways.keys()):
        giveaways[msg_id]["end"] -= 10
        if giveaways[msg_id]["end"] <= 0:
            channel = bot.get_channel(giveaways[msg_id]["channel"])
            msg = await channel.fetch_message(msg_id)
            users = [u async for u in msg.reactions[0].users() if not u.bot]
            winner = random.choice(users).mention if users else "Katılım yok"
            await channel.send(f"Kazanan: {winner}")
            del giveaways[msg_id]

# ================= RUN =================
bot.run(os.getenv("TOKEN"))
