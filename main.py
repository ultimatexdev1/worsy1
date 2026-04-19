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
        # Botun butonları/menüleri hafızasında tutmasını sağlar (Persistent Views)
        self.add_view(TicketView())
        self.add_view(TicketControlView())

bot = MyBot()

INVITE_DB = "invites.json"
WARN_DB = "warns.json"
# Kanal ID'lerini tırnak içinde değil, sayı olarak yazmak daha sağlıklıdır
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

    @discord.ui.button(label="Ticketı Kapat", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Yetki kontrolü (Opsiyonel: Sadece yetkililer kapatsın dersen buraya eklenebilir)
        await interaction.response.send_message("Kanal 3 saniye içinde siliniyor...", ephemeral=False)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except:
            pass

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ekip Alımı", description="Klanımıza katılmak için başvurun.", emoji="⚔️"),
            discord.SelectOption(label="Yetkili Alımı", description="Rehber/Mod başvurusu.", emoji="🛡️"),
            discord.SelectOption(label="Partnerlik Ve Merge", description="Ortaklık görüşmeleri.", emoji="🤝"),
            discord.SelectOption(label="Destek", description="Genel yardım ve sorular.", emoji="🎫")
        ]
        # custom_id eklemek bot resetlendiğinde çalışması için ŞARTTIR
        super().__init__(placeholder="Bir kategori seçin...", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        # CRITICAL FIX: "Etkileşim başarısız" hatasını önlemek için defer kullanıyoruz
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        category_name = self.values[0]
        
        # 'Support' rolünü kontrol et, yoksa hata almamak için güvenli al
        support_role = discord.utils.get(guild.roles, name="Support")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            # Kanal oluşturma
            channel = await guild.create_text_channel(
                name=f"{category_name.lower()}-{interaction.user.name}",
                overwrites=overwrites
            )

            embed = discord.Embed(
                title=f"🎫 {category_name} Talebi",
                description=f"Merhaba {interaction.user.mention}, talebiniz alındı. Yetkililer kısa süre içinde burada olacaktır.",
                color=discord.Color.green()
            )
            await channel.send(embed=embed, view=TicketControlView())
            
            # Defer kullandığımız için artık followup kullanmalıyız
            await interaction.followup.send(f"✅ Ticket kanalınız açıldı: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Kanal oluşturulurken bir hata oluştu: {e}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# --- SES VE INVITE SİSTEMİ ---
async def stay_in_voice():
    await bot.wait_until_ready()
    channel = bot.get_channel(SES_KANAL_ID)
    if not channel:
        print("❌ Ses kanalı bulunamadı, ID kontrol edin.")
        return

    vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if not vc:
        try:
            await channel.connect(reconnect=True)
        except Exception as e:
            print(f"Ses bağlantı hatası: {e}")

@bot.event
async def on_ready():
    await stay_in_voice()

    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except:
            print(f"{guild.name} sunucusunda davet yetkisi yok.")

    if not check_giveaways.is_running():
        check_giveaways.start()

    await bot.tree.sync()
    print(f"✅ {bot.user} sistemi başarıyla yüklendi!")

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
@bot.tree.command(name="ticket-kur", description="Ticket sistemini başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Worsy | Destek Sistemi",
        description="Aşağıdaki menüden bir kategori seçerek destek talebi oluşturabilirsiniz.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Ticket sistemi başarıyla kuruldu.", ephemeral=True)

@bot.tree.command(name="duyuru-at", description="Duyuru kanalına mesaj gönderir.")
@app_commands.checks.has_permissions(administrator=True)
async def duyuru_at(interaction: discord.Interaction, mesaj: str):
    channel = bot.get_channel(DUYURU_KANAL_ID)
    if not channel:
        return await interaction.response.send_message("Hata: Duyuru kanalı bulunamadı!", ephemeral=True)
    
    embed = discord.Embed(title="📢 DUYURU", description=mesaj, color=discord.Color.red())
    await channel.send(content="@everyone", embed=embed)
    await interaction.response.send_message("Duyuru gönderildi.", ephemeral=True)

@bot.tree.command(name="çekiliş", description="Çekiliş başlatır.")
@app_commands.checks.has_permissions(manage_guild=True)
async def cekilis(interaction: discord.Interaction, saniye: int, odul: str):
    embed = discord.Embed(title="🎉 Çekiliş!", description=f"Ödül: **{odul}**\nSüre: {saniye}s\nKatılmak için 🎉 tepkisine basın!", color=discord.Color.gold())
    await interaction.response.send_message("Çekiliş başladı!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[msg.id] = {"end": saniye, "channel": interaction.channel.id, "reward": odul}

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
                        await channel.send(f"❌ Çekiliş (**{giveaways[msg_id]['reward']}**) katılım olmadığı için iptal edildi.")
                except:
                    pass
            del giveaways[msg_id]

# --- BAŞLATMA ---
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("HATA: Sunucuda TOKEN değişkeni tanımlı değil!")
