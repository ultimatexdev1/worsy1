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

INVITE_DB = "invites.json"
WARN_DB = "warns.json"
invites = {}
giveaways = {}

# ================= VERİTABANI YÖNETİMİ =================
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

# ================= TICKET SİSTEMİ (SELECT MENU) =================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticketı Kapat", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Kanal kapatılıyor...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ekip Alımı", description="Klanımıza katılmak için başvurun.", emoji="⚔️"),
            discord.SelectOption(label="Yetkili Alımı", description="Rehber/Mod başvurusu.", emoji="🛡️"),
            discord.SelectOption(label="Şikayet", description="Oyuncu veya durum şikayeti.", emoji="🚫"),
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
            description=f"Merhaba {interaction.user.mention}, talebiniz alındı. Yetkililer yakında ilgilenecektir.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"Ticket kanalınız oluşturuldu: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ================= BOT EVENTS =================
@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            invites[guild.id] = await guild.invites()
        except:
            pass

    if not check_giveaways.is_running():
        check_giveaways.start()

    await bot.tree.sync()
    print(f"✅ {bot.user} Aktif! Railway üzerinde çalışıyor.")

@bot.event
async def on_member_join(member):
    db = load_db(INVITE_DB)
    try:
        guild_invs_before = invites.get(member.guild.id, [])
        guild_invs_after = await member.guild.invites()
        invites[member.guild.id] = guild_invs_after

        for inv in guild_invs_after:
            for old_inv in guild_invs_before:
                if inv.code == old_inv.code and inv.uses > old_inv.uses:
                    inviter_id = str(inv.inviter.id)
                    db[inviter_id] = db.get(inviter_id, 0) + 1
                    save_db(INVITE_DB, db)
                    return
    except:
        pass

# ================= KOMUTLAR =================

@bot.tree.command(name="oylama", description="Hızlı bir oylama başlatır.")
async def oylama(interaction: discord.Interaction, soru: str):
    embed = discord.Embed(title="📊 Klan Oylaması", description=soru, color=discord.Color.blue())
    embed.set_footer(text=f"Başlayan: {interaction.user.name}")
    await interaction.response.send_message("Oylama oluşturuldu!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

@bot.tree.command(name="ticket-kur", description="Kategorili ticket sistemini kurar.")
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Klan Destek & Başvuru",
        description="Lütfen işlem yapmak istediğiniz kategoriyi aşağıdaki menüden seçin.",
        color=discord.Color.dark_grey()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Sistem kuruldu.", ephemeral=True)

@bot.tree.command(name="warn", description="Bir kullanıcıyı uyarır.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, user: discord.Member, sebep: str = "Belirtilmedi"):
    db = load_db(WARN_DB)
    uid = str(user.id)
    if uid not in db: db[uid] = []
    db[uid].append(sebep)
    save_db(WARN_DB, db)
    await interaction.response.send_message(f"⚠️ {user.mention} uyarıldı. Toplam Uyarı: {len(db[uid])}")

@bot.tree.command(name="warnlar", description="Bir kullanıcının uyarılarını listeler.")
async def warnlar(interaction: discord.Interaction, user: discord.Member):
    db = load_db(WARN_DB)
    warn_list = db.get(str(user.id), [])
    text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(warn_list)]) if warn_list else "Uyarı yok."
    await interaction.response.send_message(f"📋 **{user.name} Uyarıları:**\n{text}")

@bot.tree.command(name="inviteler", description="Davet sayınızı gösterir.")
async def inviteler(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    db = load_db(INVITE_DB)
    count = db.get(str(user.id), 0)
    await interaction.response.send_message(f"📩 {user.mention} toplam **{count}** davete sahip.")

@bot.tree.command(name="çekiliş", description="Çekiliş başlatır (saniye cinsinden).")
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    embed = discord.Embed(title="🎉 Çekiliş!", description=f"Ödül: **{odul}**\nSüre: {saniye}s", color=discord.Color.random())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"end": saniye, "channel": interaction.channel.id, "reward": odul}
    await interaction.response.send_message("Başladı!", ephemeral=True)

@tasks.loop(seconds=10)
async def check_giveaways():
    for msg_id in list(giveaways.keys()):
        giveaways[msg_id]["end"] -= 10
        if giveaways[msg_id]["end"] <= 0:
            channel = bot.get_channel(giveaways[msg_id]["channel"])
            if channel:
                try:
                    msg = await channel.fetch_message(msg_id)
                    users = [u async for u in msg.reactions[0].users() if not u.bot]
                    winner = random.choice(users).mention if users else "Kimse"
                    await channel.send(f"🎊 Ödül: **{giveaways[msg_id]['reward']}** | Kazanan: {winner}")
                except: pass
            del giveaways[msg_id]

# ================= ÇALIŞTIR =================
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("HATA: Railway panelinden 'TOKEN' değişkenini eklemediniz!")
