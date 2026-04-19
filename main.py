import os
import json
import discord
import asyncio
import random
from discord.ext import commands, tasks
from discord import app_commands

# --- AYARLAR VE VERİTABANI ---
intents = discord.Intents.all()

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Bot her başladığında eski butonların/menülerin çalışmasını sağlar
        self.add_view(TicketView())
        self.add_view(TicketControlView())

bot = MyBot()

INVITE_DB = "invites.json"
WARN_DB = "warns.json"
DUYURU_KANAL_ID = 1494733087689674840
SES_KANAL_ID = 1495031512729518242

invites_cache = {}
giveaways = {}

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

# --- TICKET SİSTEMİ ---
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
            discord.SelectOption(label="Partnerlik Ve Merge", description="Ortaklık görüşmeleri.", emoji="🤝"),
            discord.SelectOption(label="Destek", description="Genel yardım ve sorular.", emoji="🎫")
        ]
        super().__init__(placeholder="Bir kategori seçin...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category_name = self.values[0]
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

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

# --- SES SİSTEMİ ---
async def stay_in_voice():
    await bot.wait_until_ready()
    channel = bot.get_channel(SES_KANAL_ID)
    if not channel:
        return

    vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if not vc:
        try:
            await channel.connect(reconnect=True)
        except Exception as e:
            print(f"Bağlantı hatası: {e}")
    elif vc.channel.id != SES_KANAL_ID:
        await vc.move_to(channel)

# --- EVENTLER ---
@bot.event
async def on_ready():
    await stay_in_voice()

    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except:
            pass

    if not check_giveaways.is_running():
        check_giveaways.start()

    await bot.tree.sync()
    print(f"✅ {bot.user} Aktif ve Görev Başında!")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        await asyncio.sleep(5)
        await stay_in_voice()

@bot.event
async def on_member_join(member):
    db = load_db(INVITE_DB)
    try:
        before = invites_cache.get(member.guild.id, [])
        after = await member.guild.invites()
        invites_cache[member.guild.id] = after
        
        for i in after:
            for j in before:
                if i.code == j.code and i.uses > j.uses:
                    uid = str(i.inviter.id)
                    db[uid] = db.get(uid, 0) + 1
                    save_db(INVITE_DB, db)
                    return
    except:
        pass

# --- SLASH KOMUTLAR ---
@bot.tree.command(name="duyuru-at", description="Duyuru kanalına mesaj gönderir.")
@app_commands.checks.has_permissions(administrator=True)
async def duyuru_at(interaction: discord.Interaction, mesaj: str):
    channel = bot.get_channel(DUYURU_KANAL_ID)
    if not channel:
        return await interaction.response.send_message("Hata: Duyuru kanalı bulunamadı!", ephemeral=True)
    
    embed = discord.Embed(title="📢 DUYURU", description=mesaj, color=discord.Color.red())
    await channel.send(content="@everyone", embed=embed)
    await interaction.response.send_message("Duyuru başarıyla paylaşıldı.", ephemeral=True)

@bot.tree.command(name="ticket-kur", description="Ticket sistemini başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Worsy | Destek Sistemi",
        description="Aşağıdaki menüden bir kategori seçerek destek talebi oluşturabilirsiniz.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Sistem kuruldu.", ephemeral=True)

@bot.tree.command(name="warn", description="Kullanıcıyı uyarır.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, user: discord.Member, sebep: str = "Belirtilmedi"):
    db = load_db(WARN_DB)
    uid = str(user.id)
    if uid not in db: db[uid] = []
    db[uid].append(sebep)
    save_db(WARN_DB, db)
    await interaction.response.send_message(f"⚠️ {user.mention} uyarıldı. (Toplam Uyarı: {len(db[uid])})")

@bot.tree.command(name="inviteler", description="Davet sayınızı gösterir.")
async def inviteler(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    db = load_db(INVITE_DB)
    count = db.get(str(user.id), 0)
    await interaction.response.send_message(f"📩 {user.mention} toplam davet: **{count}**")

@bot.tree.command(name="çekiliş", description="Çekiliş başlatır.")
@app_commands.checks.has_permissions(manage_guild=True)
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    embed = discord.Embed(title="🎉 Çekiliş!", description=f"Ödül: **{odul}**\nSüre: {saniye}s\nKatılmak için 🎉 tepkisine basın!", color=discord.Color.gold())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"end": saniye, "channel": interaction.channel.id, "reward": odul}
    await interaction.response.send_message("Çekiliş başlatıldı!", ephemeral=True)

@tasks.loop(seconds=10)
async def check_giveaways():
    for msg_id in list(giveaways.keys()):
        giveaways[msg_id]["end"] -= 10
        if giveaways[msg_id]["end"] <= 0:
            channel = bot.get_channel(giveaways[msg_id]["channel"])
            if channel:
                try:
                    msg = await channel.fetch_message(msg_id)
                    reaction = discord.utils.get(msg.reactions, emoji="🎉")
                    users = [u async for u in reaction.users() if not u.bot]
                    
                    if users:
                        winner = random.choice(users).mention
                        await channel.send(f"🎊 Çekiliş Sonuçlandı! Ödül: **{giveaways[msg_id]['reward']}** | Kazanan: {winner}")
                    else:
                        await channel.send(f"❌ Çekiliş Sonuçlandı (**{giveaways[msg_id]['reward']}**), ancak yeterli katılım olmadı.")
                except Exception as e:
                    print(f"Çekiliş hatası: {e}")
            del giveaways[msg_id]

# --- BAŞLATMA ---
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("HATA: TOKEN bulunamadı!")
