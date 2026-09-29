from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import os
import random

# --- RENDER PORT HATASI ÖNLEME (WEB SERVICE KEEP-ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "T.C. Kamu Sistemi ve Bot Aktif!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
# ---------------------------------------------------------

# Bot Niyetleri (Intents)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

MIN_ACCOUNT_AGE_DAYS = 15

# --- SAHTE VERİTABANI (Basit bakiye ve cooldown takibi) ---
kullanici_bakiyeleri = {}
maas_cooldown = {}

@bot.event
async def on_ready():
    print(f"🇹🇷 {bot.user.name} Tüm T.C. Devlet Modülleri Aktif Edildi!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="T.C. Kamu Güvenliği & Hazine"))
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} Slash komutu senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

# ==========================================
# 🛡️ 1. EGM GUARD - HESAP YAŞI & KÜFÜR KONTROLÜ
# ==========================================

@bot.event
async def on_member_join(member):
    now = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now - member.created_at).days

    if account_age < MIN_ACCOUNT_AGE_DAYS:
        egm_dm_message = (
            "🇹🇷 **T.C. İÇİŞLERİ BAKANLIĞI**\n"
            "🛡️ **EMNİYET GENEL MÜDÜRLÜĞÜ (EGM GUARD)**\n"
            "Güvenlik Kararnamesi | Karar No: 2026/112\n\n"
            "> 🚨 **KAMU GÜVENLİĞİ VE AĞ TEDBİRLERİ UYARISI**\n"
            "> ══════════════════════════════════════════════════════════════\n"
            "> **SAYIN KULLANICI,**\n"
            "> Sunucumuzun kamu düzeni ve siber güvenlik protokolleri gereğince; yeni oluşturulmuş hesaplar "
            f"(hesap yaşı alt sınırı olan **{MIN_ACCOUNT_AGE_DAYS} günü** karşılamayan) EGM Guard güvenlik modülü tarafından potansiyel risk olarak değerlendirilmiştir.\n"
            "> Otomatik güvenlik filtresi uyarınca hesabınız sunucudan geçici olarak uzaklaştırılmıştır (Kick).\n\n"
            "📑 **NE YAPMALISINIZ?**\n"
            f" * Discord hesabınızın güvenliğini sağladıktan ve en az {MIN_ACCOUNT_AGE_DAYS} günlük kullanım süresini doldurduktan sonra sunucuya tekrar katılım sağlayabilirsiniz.\n"
            " * Hesabınızın yanlışlıkla engellendiğini düşünüyorsanız, hesap yaşınızı doğrulayarak idari birimlerimizle iletişime geçebilirsiniz.\n\n"
            "> ⚖️ *Kamu huzuru ve kamu düzeninin sürekliliği için alınan bu tedbir T.C. Siber Suçlarla Mücadele ve EGM Guard mevzuatı uyarınca yürütüldüğünü bilgilerinize arz ederiz.*"
        )
        try:
            await member.send(egm_dm_message)
        except discord.Forbidden:
            pass
        try:
            await member.kick(reason=f"EGM Guard: Hesap yaşı 15 günden küçük ({account_age} gün).")
        except discord.Forbidden:
            print(f"⚠️ HATA: {member.name} atılamadı. Bot rolünü kontrol edin.")
    else:
        kayitsiz_rol = discord.utils.get(member.guild.roles, name="Kayıtsız")
        if kayitsiz_rol:
            await member.add_roles(kayitsiz_rol)

KUFUR_LISTESI = ["amk", "aq", "oç", "piç", "sik", "yarrak", "orospu"]

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.lower()
    if any(kufur in msg_content for kufur in KUFUR_LISTESI):
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention}, T.C. Kamu Düzeni uyarınca hakaret/küfür içeren mesajlar yasaklanmıştır!", delete_after=5)
        return

    await bot.process_commands(message)

# ==========================================
# ⚖️ 2. MAHKEME & TICKET (DESTEK) SİSTEMİ
# ==========================================

class DavaKapatButon(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚖️ Davayı/Talebi Sonlandır", style=discord.ButtonStyle.red, custom_id="dava_kapat_btn")
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🏛️ Dava dosyası arşivleniyor, kanal 5 saniye içinde kapatılacak...")
        await discord.utils.sleep_until(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5))
        await interaction.channel.delete()

class MahkemeBasvuruView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚖️ Mahkeme/Destek Talebi Aç", style=discord.ButtonStyle.primary, custom_id="mahkeme_ac_btn")
    async def talep_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # Kanal İzinleri
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Yetkili / Hakim Rolü Varsa Ekle
        hakim_rol = discord.utils.get(guild.roles, name="Hakim") or discord.utils.get(guild.roles, name="Yetkili")
        if hakim_rol:
            overwrites[hakim_rol] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"dava-{user.name}"
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        
        if existing_channel:
            await interaction.response.send_message(f"❌ Zaten açık bir dava/destek kanalınız var: {existing_channel.mention}", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        embed = discord.Embed(
            title="🏛️ T.C. YARGITAY & MAHKEME SALONU",
            description=f"Sayın {user.mention},\n\nTalebiniz/Davanız işleme alınmıştır. Lütfen şikayetinizi veya konuyu detaylıca yazınız. Adalet birimleri en kısa sürede müdahil olacaktır.",
            color=discord.Color.gold()
        )
        await ticket_channel.send(embed=embed, view=DavaKapatButon())
        await interaction.response.send_message(f"✅ Dava/Destek kanalınız oluşturuldu: {ticket_channel.mention}", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def mahkemekur(ctx):
    """Yetkilinin Mahkeme Başvuru Panelini Kurmasını Sağlar"""
    embed = discord.Embed(
        title="🏛️ T.C. ADALET BAKANLIĞI MAHKEME VE BAŞVURU PANELİ",
        description="Sunucu içi anlaşmazlıklar, şikayetler veya genel destek talepleriniz için aşağıdaki butona basarak gizli oturum açabilirsiniz.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, view=MahkemeBasvuruView())

# ==========================================
# 💰 3. T.C. HAZİNE & BORSA (EKONOMİ) SİSTEMİ
# ==========================================

@bot.tree.command(name="cuzdan", description="T.C. Merkez Bankası hesabınızdaki bakiyeyi gösterir.")
async def cuzdan(interaction: discord.Interaction):
    user_id = interaction.user.id
    bakiye = kullanici_bakiyeleri.get(user_id, 0)
    
    embed = discord.Embed(title="💳 T.C. MERKEZ BANKASI HESAP HAREKETLERİ", color=discord.Color.green())
    embed.add_field(name="Vatandaş:", value=interaction.user.mention, inline=False)
    embed.add_field(name="Toplu Bakiye:", value=f"**{bakiye:,} ₺**", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="maas", description="Günlük devlet vatandaşlık maaşınızı alırsınız.")
async def maas(interaction: discord.Interaction):
    user_id = interaction.user.id
    today = datetime.date.today()
    
    if kullanici_bakiyeleri.get(f"{user_id}_maas") == today:
        await interaction.response.send_message("❌ Bugünlük devlet maaşınızı zaten aldınız! Yarın tekrar bekleriz.", ephemeral=True)
        return
        
    kullanici_bakiyeleri[user_id] = kullanici_bakiyeleri.get(user_id, 0) + 1500
    kullanici_bakiyeleri[f"{user_id}_maas"] = today
    
    await interaction.response.send_message(f"💵 **1,500 ₺** günlük vatandaşlık maaşı hesabınıza aktarılmıştır! Güncel bakiyeniz: **{kullanici_bakiyeleri[user_id]:,} ₺**")

@bot.tree.command(name="paragonder", description="Başka bir vatandaşa para transferi yaparsınız.")
async def paragonder(interaction: discord.Interaction, alici: discord.Member, miktar: int):
    gonderen_id = interaction.user.id
    gonderen_bakiye = kullanici_bakiyeleri.get(gonderen_id, 0)
    
    if miktar <= 0:
        await interaction.response.send_message("❌ Geçersiz miktar!", ephemeral=True)
        return
        
    if gonderen_bakiye < miktar:
        await interaction.response.send_message("❌ Hesabınızda yeterli bakiye bulunmamaktadır!", ephemeral=True)
        return
        
    kullanici_bakiyeleri[gonderen_id] -= miktar
    kullanici_bakiyeleri[alici.id] = kullanici_bakiyeleri.get(alici.id, 0) + miktar
    
    await interaction.response.send_message(f"💸 {interaction.user.mention}, {alici.mention} kullanıcısına **{miktar:,} ₺** başarıyla transfer etti!")

@bot.tree.command(name="borsa", description="T.C. Borsa İstanbul canlı endeks durumunu gösterir.")
async def borsa(interaction: discord.Interaction):
    bist100 = random.randint(8500, 10500)
    degisim = round(random.uniform(-3.5, 4.5), 2)
    durum_emoji = "📈" if degisim >= 0 else "📉"
    
    embed = discord.Embed(title="📊 T.C. BORSA İSTANBUL (BIST 100)", color=discord.Color.blue() if degisim >= 0 else discord.Color.red())
    embed.add_field(name="Endeks Puanı:", value=f"**{bist100}**", inline=True)
    embed.add_field(name="Günlük Değişim:", value=f"**%{degisim} {durum_emoji}**", inline=True)
    
    await interaction.response.send_message(embed=embed)

# BOTU ÇALIŞTIRMA
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token.strip())
else:
    print("❌ HATA: DISCORD_TOKEN bulunamadı!")
    
