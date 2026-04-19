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

# Sabit Kanal ID'leri
DUYURU_KANAL_ID = 1494733087689674840
SES_KANAL_ID = 1495031512729518242

invites = {}
giveaways = {}

# ================= VERİTABANI SİSTEMİ =================
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
            description=f"Merhaba {interaction.user.mention}, talebiniz alındı. **Worsy** yetkilileri yakında ilgilenecektir.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"Ticket kanalınız oluşturuldu: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ================= 7/24 SES BAĞLANTISI =================
async def stay_in_voice():
    channel = bot.get_channel(SES_KANAL_ID)
    if not channel:
        print(f"❌ HATA: {SES_KANAL_ID} ID'li ses kanalı bulunamadı!")
        return

    vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    
    if not vc:
        try:
            await channel.connect(reconnect=True, timeout=20)
            print(f"🔊 {channel.name} kanalına giriş yapıldı.")
        except Exception as e:
            print(f"❌ Ses bağlantı hatası: {e}")
    elif vc.channel.id != SES_KANAL_ID:
        await vc.move_to(channel)

# ================= BOT EVENTS =================
@bot.event
async def on_ready():
    await stay_in_voice()

    for guild in bot.guilds:
        try:
            invites[guild.id] = await guild.invites()
        except:
            pass

    if not check_giveaways.is_running():
        check_giveaways.start()

    await bot.tree.sync()
    print(f"✅ {bot.user} (Worsy) Aktif ve Seste!")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        await asyncio.sleep(5)
        await stay_in_voice()

@bot.event
async def on_member_join(member):
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

@bot.tree.command(name="duyuru-at", description="Worsy duyuru kanalına mesaj gönderir.")
@app_commands.checks.has_permissions(administrator=True)
async def duyuru_at(interaction: discord.Interaction, mesaj: str):
    channel = bot.get_channel(DUYURU_KANAL_ID)
    if not channel:
        return await interaction.response.send_message("Hata: Duyuru kanalı bulunamadı!", ephemeral=True)
    
    embed = discord.Embed(title="📢 Worsy | DUYURU", description=mesaj, color=discord.Color.red())
    embed.set_footer(text="Worsy Yönetimi")
    await channel.send(content="@everyone", embed=embed)
    await interaction.response.send_message("Duyuru başarıyla paylaşıldı.", ephemeral=True)

@bot.tree.command(name="partner-paylaş", description="Partnerlik mesajı paylaşır.")
@app_commands.checks.has_permissions(manage_channels=True)
async def partner_paylas(interaction: discord.Interaction, kanal: discord.TextChannel, mesaj: str):
    embed = discord.Embed(title="🤝 Yeni Partnerlik!", description=mesaj, color=discord.Color.purple())
    embed.set_footer(text=f"Yetkili: {interaction.user.name}")
    await kanal.send(embed=embed)
    await interaction.response.send_message(f"Partnerlik {kanal.mention} kanalında paylaşıldı.", ephemeral=True)

@bot.tree.command(name="ticket-kur", description="Worsy ticket sistemini başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Worsy | Destek Sistemi",
        description="Aşağıdaki menüden bir kategori seçerek destek talebi oluşturabilirsiniz.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Ticket sistemi kuruldu.", ephemeral=True)

@bot.tree.command(name="oylama", description="Hızlı oylama başlatır.")
async def oylama(interaction: discord.Interaction, soru: str):
    embed = discord.Embed(title="📊 Worsy | Oylama", description=soru, color=discord.Color.orange())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("Oylama başlatıldı.", ephemeral=True)

@bot.tree.command(name="warn", description="Kullanıcıyı uyarır.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, user: discord.Member, sebep: str = "Belirtilmedi"):
    db = load_db(WARN_DB)
    uid = str(user.id)
    if uid not in db: db[uid] = []
    db[uid].append(sebep)
    save_db(WARN_DB, db)
    await interaction.response.send_message(f"⚠️ {user.mention} uyarıldı. (Toplam: {len(db[uid])})")

@bot.tree.command(name="inviteler", description="Davet sayınızı gösterir.")
async def inviteler(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    db = load_db(INVITE_DB)
    count = db.get(str(user.id), 0)
    await interaction.response.send_message(f"📩 {user.mention} toplam davet: **{count}**")

@bot.tree.command(name="çekiliş", description="Çekiliş başlatır.")
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    embed = discord.Embed(title="🎉 Worsy | Çekiliş!", description=f"Ödül: **{odul}**\nSüre: {saniye}s", color=discord.Color.random())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"end": saniye, "channel": interaction.channel.id, "reward": odul}
    await interaction.response.send_message("Çekiliş başladı!", ephemeral=True)

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
                    winner = random.choice(users).mention if users else "Yeterli katılım yok."
                    await channel.send(f"🎊 Çekiliş Sonuçlandı! Ödül: **{giveaways[msg_id]['reward']}** | Kazanan: {winner}")
                except: pass
            del giveaways[msg_id]

# ================= ÇALIŞTIR =================
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("HATA: TOKEN değişkeni bulunamadı!")
