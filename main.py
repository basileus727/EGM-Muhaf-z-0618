import os
import time
import random
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
import io

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

# --- WEB SERVICE KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- INTENTS VE BOT TANIMLAMASI ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- SQLite VERİTABANI VE İNDEKSLEME ---
db = sqlite3.connect("tc_merkez_altyapi.db")
cursor = db.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS bakiye (
    user_id INTEGER PRIMARY KEY,
    para INTEGER DEFAULT 0,
    maas INTEGER DEFAULT 500
);

CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    seviye INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cooldown (
    user_id INTEGER PRIMARY KEY,
    son_maas REAL
);

CREATE TABLE IF NOT EXISTS sicil (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ceza_turu TEXT,
    sebep TEXT,
    tarih TEXT,
    yetkili_id INTEGER
);

CREATE TABLE IF NOT EXISTS vatandas (
    user_id INTEGER PRIMARY KEY,
    tc_no TEXT,
    kayit_tarihi TEXT,
    durum TEXT DEFAULT 'Aktif'
);

CREATE TABLE IF NOT EXISTS ihbarlar (
    ihbar_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bildiren_id INTEGER,
    supheli_id INTEGER,
    sebep TEXT,
    durum TEXT DEFAULT 'İnceleniyor'
);

CREATE TABLE IF NOT EXISTS ozel_odalar (
    user_id INTEGER PRIMARY KEY,
    channel_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_bakiye_user ON bakiye(user_id);
CREATE INDEX IF NOT EXISTS idx_sicil_user ON sicil(user_id);
CREATE INDEX IF NOT EXISTS idx_vatandas_user ON vatandas(user_id);
CREATE INDEX IF NOT EXISTS idx_xp_user ON xp(user_id);
""")
db.commit()

# --- VERİTABANI YARDIMCI FONKSİYONLARI ---
def db_bakiye_getir(user_id):
    cursor.execute("SELECT para FROM bakiye WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def db_bakiye_ayarla(user_id, miktar):
    cursor.execute("INSERT OR REPLACE INTO bakiye (user_id, para, maas) VALUES (?, ?, COALESCE((SELECT maas FROM bakiye WHERE user_id = ?), 500))", (user_id, miktar, user_id))
    db.commit()

def db_sicil_ekle(user_id, ceza_turu, sebep, yetkili_id=None):
    tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute("INSERT INTO sicil (user_id, ceza_turu, sebep, tarih, yetkili_id) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, ceza_turu, sebep, tarih, yetkili_id))
    db.commit()

# --- GLOBAL HATA YAKALAYICI (COMMAND ERROR HANDLER) ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(title="❌ Yetki Hatası", description="Bu komutu kullanmak için gerekli yetkilere sahip değilsiniz.", color=discord.Color.red())
    elif isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(title="⏳ Süre Aşımı", description=f"Lütfen **{error.retry_after:.1f}** saniye sonra tekrar deneyin.", color=discord.Color.orange())
    else:
        embed = discord.Embed(title="⚠️ Sistem Uyarısı", description="Komut yürütülürken beklenmeyen bir hata oluştu.", color=discord.Color.dark_red())
    
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- KÜFÜR VE LOG KANALLARI ---
KÜFÜR_LİSTESİ = ["orospu", "piç", "amk", "aq", "sik", "anan", "gerizekalı", "mal"]

KANALLAR = {
    "yetkili_denetim": 1554567298034180157,
    "siberay_log": 1553836787175264266,
    "sicil_kayitlari": 1554567289930649622,
    "nufus_mudurlugu": 1554567292283658374,
    "evrak_duzenleme": 1554567291352383578,
    "imha_evraklar": 1554567294095589458,
    "nufus_hareketleri": 1554567295924310127,
    "telsiz_dinleme": 1554567290000000000
}

async def ozel_kanal_logla(guild, kanal_adi, embed):
    kanal_id = KANALLAR.get(kanal_adi)
    if kanal_id:
        kanal = guild.get_channel(kanal_id)
        if not kanal:
            try:
                kanal = await guild.fetch_channel(kanal_id)
            except Exception:
                pass
        if kanal:
            try:
                await kanal.send(embed=embed)
            except Exception:
                pass

@bot.event
async def on_ready():
    bot.add_view(MahkemeBasvuruView())
    bot.add_view(DavaKapatButon())
    bot.add_view(RolSecimView())
    bot.add_view(VatandasKayitView())
    bot.add_view(TicketCreateView())
    bot.add_view(TicketCloseView())
    bot.add_view(GiveawayView())

    print(f"[ALTYAPI AKTİF] {bot.user} sistemde aktif ve tüm modüller devrede!")
    if not enflasyon_duyuru.is_running():
        enflasyon_duyuru.start()
    if not ses_odul_dongusu.is_running():
        ses_odul_dongusu.start()

    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} komut senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

# --- ARKA PLAN GÖREVLERİ ---
@tasks.loop(hours=24)
async def enflasyon_duyuru():
    cursor.execute("UPDATE bakiye SET para = para + maas")
    db.commit()

@tasks.loop(minutes=1)
async def ses_odul_dongusu():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if vc.id == guild.afk_channel_id:
                continue
            for member in vc.members:
                if member.bot:
                    continue
                cursor.execute("SELECT seviye, xp FROM xp WHERE user_id = ?", (member.id,))
                row = cursor.fetchone()
                seviye = row[0] if row else 1
                xp = (row[1] if row else 0) + 5
                
                if xp >= seviye * 100:
                    seviye += 1
                    xp = 0
                cursor.execute("INSERT OR REPLACE INTO xp (user_id, seviye, xp) VALUES (?, ?, ?)", (member.id, seviye, xp))
                
                guncel_para = db_bakiye_getir(member.id) + 10
                db_bakiye_ayarla(member.id, guncel_para)
    db.commit()

# --- 1. OTOMATİK SUNUCU KURULUM KOMUTU (Görsellerdeki Şablona Göre) ---
@bot.tree.command(name="kurulum", description="Görsellerdeki tüm kategori ve kanalları tek komutla kusursuz kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def kurulum(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    # Kurulacak Yapı (Kategori ve Kanallar Sözlüğü)
    sunucu_yapisi = {
        "🏛️️ İDARİ MAKAMLAR VE İLETİŞİM": [
            "🏛️・mahkeme-salonu",
            "🗳️・seçim-sandığı",
            "⚖️・adalet-sarayı"
        ],
        "🏛️ VATANDAŞLIK VE NÜFUS İŞLERİ": [
            "🪪・vatandaşlık-başvurusu",
            "📄・kayıt-rehberi"
        ],
        "🏛️ RESMİ GAZETE": [
            "⚖️・anayasa",
            "📜・resmi-gazete",
            "📜・roller-ve-hiyerarşi",
            "🎖️・hibe-ve-ikramiye"
        ],
        "🏛️ MECLİS": [
            "💬・genel-kurul",
            "☕・millet-kıraathanesi",
            "📸・fotoğraf-albümü",
            "🤖・bot-komut"
        ],
        "🎓 MİLLİ EĞİTİM & KÜLTÜR BAKANLIĞI": [
            "📚・millet-kütüphanesi",
            "🎬・devlet-tiyatroları",
            "🎨・güzel-sanatlar-galerisi",
            "🎵・trt-müzik"
        ],
        "💼 HAZİNE VE MALİYE BAKANLIĞI": [
            "💰・türkiye-iş-bankası",
            "📈・borsa-istanbul",
            "🎲・milli-piyango"
        ],
        "⚽ GENÇLİK VE SPOR BAKANLIĞI": [
            "🏟️・olimpiyat-stadyumu",
            "🎮・e-spor-federasyonu",
            "🦋・yaşam-albümü"
        ],
        "🔊 DEVLET MAFİLLERİ (SES)": [
            "🔊・Çankaya Köşkü",
            "🔊・Bakanlar Kurulu",
            "🔊・Cumhurbaşkanlığı Makamı",
            "🔊・Yargıtay Duruşma Salonu"
        ],
        "🔊 MİLLİ PARKLAR (SES)": [
            "🔊・Kahvehane",
            "🔊・Millet Kütüphanesi",
            "🔊・EGM Telsiz - Asayiş",
            "🔊・EGM Telsiz - Devriye",
            "🔊・F1 Odası"
        ]
    }

    for kat_adi, kanallar in sunucu_yapisi.items():
        # Ses kategorileri için ses kanalı, diğerleri için metin kanalı oluşturma mantığı
        is_voice_category = "SES" in kat_adi
        
        # Kategoriyi oluştur
        kategori = await guild.create_category(kat_adi)
        
        for k_adi in kanallar:
            if is_voice_category:
                if not discord.utils.get(guild.voice_channels, name=k_adi):
                    await guild.create_voice_channel(k_adi, category=kategori)
            else:
                if not discord.utils.get(guild.text_channels, name=k_adi):
                    await guild.create_text_channel(k_adi, category=kategori)

    await interaction.followup.send("✅ Türkiye Cumhuriyeti sunucu altyapısı görsellere uygun olarak eksiksiz kuruldu!", ephemeral=True)

@bot.tree.command(name="duyuru", description="Resmi kamu duyurusu gönderir.")
@app_commands.describe(kanal="Kanal", baslik="Başlık", mesaj="İçerik", etiketle="Etiketlensin mi?")
@app_commands.checks.has_permissions(manage_messages=True)
async def duyuru(interaction: discord.Interaction, kanal: discord.TextChannel, baslik: str, mesaj: str, etiketle: str = "hayır"):
    embed = discord.Embed(title=f"📢 {baslik}", description=mesaj, color=discord.Color.blue())
    embed.set_footer(text=f"Yetkili: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
    content = "@everyone" if etiketle.lower() in ["evet", "yes", "e"] else None
    await kanal.send(content=content, embed=embed)
    await interaction.response.send_message("✅ Duyuru başarıyla gönderildi.", ephemeral=True)

# --- 2. E-DEVLET / VATANDAŞLIK KAYIT SİSTEMİ ---
class VatandasKayitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="TC Vatandaşlık Kaydını Başlat", style=discord.ButtonStyle.green, custom_id="vatandas_kayit_btn_persistent")
    async def kayit_ol(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT * FROM vatandas WHERE user_id = ?", (interaction.user.id,))
        if cursor.fetchone():
            await interaction.response.send_message("❌ Sistemde zaten vatandaşlık kaydınız bulunmaktadır.", ephemeral=True)
            return

        rastgele_tc = f"TC-{random.randint(100000000, 999999999)}"
        simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("INSERT INTO vatandas (user_id, tc_no, kayit_tarihi) VALUES (?, ?, ?)", (interaction.user.id, rastgele_tc, simdi))
        db_bakiye_ayarla(interaction.user.id, 1000)
        
        rol = discord.utils.get(interaction.guild.roles, name="T.C. Vatandaşı")
        if rol:
            await interaction.user.add_roles(rol)

        embed = discord.Embed(title="📜 T.C. Vatandaşlık Belgesi", description="Resmi kayıt işlemleriniz başarıyla tamamlandı.", color=discord.Color.blue())
        embed.add_field(name="Kimlik No", value=f"`{rastgele_tc}`", inline=True)
        embed.add_field(name="Başlangıç İkramiyesi", value="1000 ₺ Hazineden Yatırıldı.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="vatandas-panel", description="e-Devlet Vatandaşlık kayıt panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def vatandas_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🇹🇷 Türkiye Cumhuriyeti Vatandaşlık Kayıt Portalı", description="Kaydolmak için aşağıdaki butona tıklayın.", color=discord.Color.red())
    await interaction.channel.send(embed=embed, view=VatandasKayitView())
    await interaction.response.send_message("✅ Kayıt paneli kuruldu.", ephemeral=True)

# --- 3. EKONOMİ VE BORSA SİSTEMİ ---
@bot.tree.command(name="maas", description="Günlük devlet maaşınızı alırsınız.")
async def maas(interaction: discord.Interaction):
    user_id = interaction.user.id
    simdi = time.time()
    
    cursor.execute("SELECT son_maas FROM cooldown WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    son_maas = row[0] if row else 0
    
    if simdi - son_maas < 86400:
        kalan = int(86400 - (simdi - son_maas))
        saat, dakika = kalan // 3600, (kalan % 3600) // 60
        await interaction.response.send_message(f"⏳ Maaş almak için **{saat} saat {dakika} dakika** beklemelisiniz.", ephemeral=True)
        return

    guncel = db_bakiye_getir(user_id) + 1500
    db_bakiye_ayarla(user_id, guncel)
    cursor.execute("INSERT OR REPLACE INTO cooldown (user_id, son_maas) VALUES (?, ?)", (user_id, simdi))
    db.commit()
    
    await interaction.response.send_message("💰 **1500 ₺** devlet maaşınız hesabınıza yatırıldı!")

@bot.tree.command(name="yatirim", description="Devlet borsasında yatırım yaparsınız.")
@app_commands.describe(miktar="Yatırılacak miktar")
async def yatirim(interaction: discord.Interaction, miktar: int):
    bakiye = db_bakiye_getir(interaction.user.id)
    if miktar <= 0 or bakiye < miktar:
        await interaction.response.send_message("❌ Geçersiz miktar veya yetersiz bakiye.", ephemeral=True)
        return
        
    if random.choice(["kazanc", "kayip"]) == "kazanc":
        kazanc = int(miktar * random.uniform(0.1, 0.8))
        db_bakiye_ayarla(interaction.user.id, bakiye + kazanc)
        await interaction.response.send_message(f"📈 Borsa Yükseldi! **+{kazanc} ₺** kazandınız.")
    else:
        kayip = int(miktar * random.uniform(0.1, 0.5))
        db_bakiye_ayarla(interaction.user.id, bakiye - kayip)
        await interaction.response.send_message(f"📉 Borsa Düştü! **-{kayip} ₺** zarar ettiniz.")

@bot.tree.command(name="gonder", description="Başka bir vatandaşa para transferi yaparsınız.")
async def gonder(interaction: discord.Interaction, kime: discord.Member, miktar: int):
    if miktar <= 0 or interaction.user.id == kime.id:
        await interaction.response.send_message("❌ Hatalı işlem.", ephemeral=True)
        return
    g_bakiye = db_bakiye_getir(interaction.user.id)
    if g_bakiye < miktar:
        await interaction.response.send_message("❌ Yetersiz bakiye.", ephemeral=True)
        return
        
    db_bakiye_ayarla(interaction.user.id, g_bakiye - miktar)
    db_bakiye_ayarla(kime.id, db_bakiye_getir(kime.id) + miktar)
    await interaction.response.send_message(f"✅ Başarıyla {kime.mention} adlı kullanıcıya **{miktar} ₺** gönderildi.")

@bot.tree.command(name="zenginler", description="Sunucunun en zengin vatandaşlarını listeler.")
async def zenginler(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, para FROM bakiye ORDER BY para DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await interaction.response.send_message("❌ Kayıtlı veri bulunmuyor.", ephemeral=True)
        return
    desc = ""
    for idx, (uid, para) in enumerate(rows, 1):
        member = interaction.guild.get_member(uid)
        name = member.mention if member else f"ID: {uid}"
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
        desc += f"{medal} {name} — **{para} ₺**\n"
    embed = discord.Embed(title="💰 T.C. Hazine Servet Sıralaması", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bordro", description="Maaş bordronuzu ve bilonçonuzu görüntülersiniz.")
async def bordro(interaction: discord.Interaction):
    para = db_bakiye_getir(interaction.user.id)
    embed = discord.Embed(title="📊 Maaş ve Hazine Bordrosu", description=f"Vatandaş: {interaction.user.mention}\nBakiyeniz: **{para} ₺**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 4. MAHKEME VE DAVA YÖNETİM SİSTEMİ ---
class DavaKapatButon(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Davayı Kapat", style=discord.ButtonStyle.danger, custom_id="dava_kapat_btn_persistent")
    async def davayi_kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Bu butonu sadece yetkililer kullanabilir.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Bu dava kanalı arşivleniyor...", ephemeral=True)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

class MahkemeBasvuruView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚖️️ Mahkeme Başvurusu Aç", style=discord.ButtonStyle.primary, custom_id="mahkeme_basvuru_btn_persistent")
    async def mahkeme_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        kanal_adi = f"mahkeme-{interaction.user.name}".lower().replace(" ", "-")
        ek_kanal = await guild.create_text_channel(kanal_adi, overwrites=overwrites)
        
        embed = discord.Embed(title="⚖️ Mahkeme Dosyası Açıldı", description=f"Sayın {interaction.user.mention}, dava talebiniz alınmıştır.", color=discord.Color.gold())
        await ek_kanal.send(content=interaction.user.mention, embed=embed, view=DavaKapatButon())
        await interaction.response.send_message(f"✅ Mahkeme kanalınız oluşturuldu: {ek_kanal.mention}", ephemeral=True)

@bot.tree.command(name="mahkemepaneli", description="Mahkeme başvuru panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def mahkemepaneli(interaction: discord.Interaction):
    embed = discord.Embed(title="🏛 T.C. MAHKEME VE DAVA MERKEZİ", description="Dava açmak için aşağıdaki butona tıklayın.", color=discord.Color.dark_blue())
    await interaction.channel.send(embed=embed, view=MahkemeBasvuruView())
    await interaction.response.send_message("✅ Mahkeme paneli kuruldu.", ephemeral=True)

# --- 5. ROL SEÇİM PANELİ ---
class RolSecimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔔 Duyuru Rolü Al/Bırak", style=discord.ButtonStyle.secondary, custom_id="rol_duyuru_btn_persistent")
    async def rol_duyuru(self, interaction: discord.Interaction, button: discord.ui.Button):
        rol = discord.utils.get(interaction.guild.roles, name="Duyuru Habercisi")
        if not rol:
            await interaction.response.send_message("❌ 'Duyuru Habercisi' rolü bulunamadı.", ephemeral=True)
            return
        if rol in interaction.user.roles:
            await interaction.user.remove_roles(rol)
            await interaction.response.send_message("❌ Duyuru rolü alındı.", ephemeral=True)
        else:
            await interaction.user.add_roles(rol)
            await interaction.response.send_message("✅ Duyuru rolü eklendi.", ephemeral=True)

@bot.tree.command(name="rolpaneli", description="Rol seçim panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def rolpaneli(interaction: discord.Interaction):
    embed = discord.Embed(title="📌 ROL SEÇİM MERKEZİ", description="Rol almak için butona tıklayın.", color=discord.Color.purple())
    await interaction.channel.send(embed=embed, view=RolSecimView())
    await interaction.response.send_message("✅ Rol paneli kuruldu.", ephemeral=True)

# --- 6. MODERASYON VE SİCİL SİSTEMİ ---
@bot.tree.command(name="ban", description="Kullanıcıyı uzaklaştırır.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, kullanici: discord.Member, sebep: str = "Belirtilmedi"):
    await kullanici.ban(reason=sebep)
    db_sicil_ekle(kullanici.id, "BAN", sebep, interaction.user.id)
    embed = discord.Embed(title="🔨 Kullanıcı Uzaklaştırıldı (BAN)", color=discord.Color.dark_red())
    embed.add_field(name="Üye", value=kullanici.mention, inline=False)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await interaction.response.send_message(embed=embed)
    await ozel_kanal_logla(interaction.guild, "imha_evraklar", embed)

@bot.tree.command(name="kick", description="Kullanıcıyı sunucudan atar.")
@app_commands.describe(kullanici="Atılacak üye", sebep="Atılma sebebi")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, kullanici: discord.Member, sebep: str = "Belirtilmedi"):
    await kullanici.kick(reason=sebep)
    db_sicil_ekle(kullanici.id, "KICK", sebep, interaction.user.id)
    
    embed = discord.Embed(title="👢 Kullanıcı Sunucudan Atıldı (KICK)", color=discord.Color.orange())
    embed.add_field(name="Atılan Üye", value=kullanici.mention, inline=False)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.add_field(name="İşlemi Yapan", value=interaction.user.mention, inline=False)
    embed.set_footer(text="T.C. Emniyet Genel Müdürlüğü Disiplin Servisi")
    
    await interaction.response.send_message(embed=embed)
    await ozel_kanal_logla(interaction.guild, "imha_evraklar", embed)

@bot.tree.command(name="uyari", description="Kullanıcıyı uyarır.")
@app_commands.checks.has_permissions(manage_messages=True)
async def uyari(interaction: discord.Interaction, kullanici: discord.Member, sebep: str):
    db_sicil_ekle(kullanici.id, "UYARI", sebep, interaction.user.id)
    embed = discord.Embed(title="⚠️️ Resmi Kamu Uyarısı", description=f"Sebep: {sebep}", color=discord.Color.gold())
    try:
        await kullanici.send(embed=embed)
    except Exception:
        pass
    await interaction.response.send_message(f"✅ {kullanici.mention} uyarıldı.", ephemeral=True)
    await ozel_kanal_logla(interaction.guild, "sicil_kayitlari", embed)

@bot.tree.command(name="sicil", description="Sicil geçmişini gösterir.")
async def sicil(interaction: discord.Interaction, vatandas: discord.Member = None):
    target = vatandas or interaction.user
    cursor.execute("SELECT ceza_turu, sebep, tarih FROM sicil WHERE user_id = ?", (target.id,))
    rows = cursor.fetchall()
    embed = discord.Embed(title=f"📜 Sicil Dosyası: {target.name}", color=discord.Color.dark_red())
    if not rows:
        embed.description = "✅ Vatandaşın adli sicil kaydı tertemiz."
    else:
        desc = ""
        for ct, sebep, tarih in rows:
            desc += f"• **{ct}** | {sebep} *({tarih})*\n"
        embed.description = desc
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="af", description="Sicili temizler.")
@app_commands.checks.has_permissions(administrator=True)
async def af(interaction: discord.Interaction, uye: discord.Member):
    cursor.execute("DELETE FROM sicil WHERE user_id = ?", (uye.id,))
    db.commit()
    embed = discord.Embed(title="📜 Sicil Affı", description=f"{uye.mention} sicili temizlendi.", color=discord.Color.green())
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Sicil temizlendi.", ephemeral=True)

@bot.tree.command(name="temizle", description="Mesaj siler.")
@app_commands.checks.has_permissions(manage_messages=True)
async def temizle(interaction: discord.Interaction, adet: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=adet)
    await interaction.followup.send(f"🧹 **{len(deleted)}** mesaj silindi.", ephemeral=True)

@bot.tree.command(name="yavasmod", description="Yavaş mod ayarlar.")
@app_commands.checks.has_permissions(manage_channels=True)
async def yavasmod(interaction: discord.Interaction, saniye: int):
    await interaction.channel.edit(slowmode_delay=saniye)
    await interaction.response.send_message(f"⏳ Yavaş mod **{saniye}** saniye yapıldı.", ephemeral=True)

# --- 7. TICKET SİSTEMİ ---
class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Destek Talebi Oluştur", style=discord.ButtonStyle.blurple, custom_id="create_ticket_btn_persistent")
    async def ticket_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="TİCKET KANALLARI") or await guild.create_category("TİCKET KANALLARI")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f"destek-{interaction.user.name}", category=category, overwrites=overwrites)
        embed = discord.Embed(title="🛡️ Destek Masası", description="Yetkililer ilgilenecektir.", color=discord.Color.blue())
        await channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Destek kanalı açıldı: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Talebi Kapat", style=discord.ButtonStyle.red, custom_id="close_ticket_btn_persistent")
    async def ticket_kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Kanal kapatılıyor...", ephemeral=True)
        import asyncio
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="ticket-panel", description="Destek paneli kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🏛️ Resmi Destek Paneli", description="Destek açmak için tıklayın.", color=discord.Color.gold())
    await interaction.channel.send(embed=embed, view=TicketCreateView())
    await interaction.response.send_message("✅ Panel kuruldu.", ephemeral=True)

# --- 8. SEVİYE KARTI (RANK CARD) ---
@bot.tree.command(name="kimlik", description="Kimlik kartını gösterir.")
async def kimlik(interaction: discord.Interaction):
    cursor.execute("SELECT seviye, xp FROM xp WHERE user_id = ?", (interaction.user.id,))
    row = cursor.fetchone()
    seviye = row[0] if row else 1
    xp = row[1] if row else 0

    if Image is None:
        embed = discord.Embed(title="🪪 Kimlik Kartı", description=f"Seviye: {seviye} | XP: {xp}", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    img = Image.new("RGB", (600, 200), color=(25, 25, 35))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 590, 190], outline=(200, 50, 50), width=3)
    draw.text((30, 30), "T.C. KİMLİK & SEVİYE KARTI", fill=(255, 255, 255))
    draw.text((30, 80), f"Vatandaş: {interaction.user.display_name}", fill=(200, 200, 200))
    draw.text((30, 120), f"Seviye: {seviye}   |   XP: {xp}", fill=(100, 255, 100))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(buffer, filename="kimlik.png")
    embed = discord.Embed(title="🪪 e-Devlet Kartı", color=discord.Color.red())
    embed.set_image(url="attachment://kimlik.png")
    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

# --- 9. ÖZEL ODA VE TELSİZ SİSTEMİ ---
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    guild = member.guild
    if after.channel and after.channel.name == "Özel Oda Oluştur":
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True),
            member: discord.PermissionOverwrite(manage_channels=True, mute_members=True)
        }
        yeni = await guild.create_voice_channel(name=f"🔒 {member.display_name} Odası", category=after.channel.category, overwrites=overwrites)
        await member.move_to(yeni)
        cursor.execute("INSERT OR REPLACE INTO ozel_odalar (user_id, channel_id) VALUES (?, ?)", (member.id, yeni.id))
        db.commit()

    if before.channel and before.channel.name.startswith("🔒") and len(before.channel.members) == 0:
        await before.channel.delete()

    embed = discord.Embed(title="🎙 Telsiz Hareketi", color=discord.Color.orange())
    embed.add_field(name="Personel", value=member.mention, inline=False)
    if before.channel is None and after.channel is not None:
        embed.description = f"Giriş: {after.channel.name}"
        await ozel_kanal_logla(guild, "telsiz_dinleme", embed)
    elif before.channel is not None and after.channel is None:
        embed.description = f"Çıkış: {before.channel.name}"
        await ozel_kanal_logla(guild, "telsiz_dinleme", embed)

# --- 10. ÇEKİLİŞ SİSTEMİ ---
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.katilanlar = set()

    @discord.ui.button(label="🎉 Çekilişe Katıl", style=discord.ButtonStyle.green, custom_id="gw_btn_persistent")
    async def katil(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.katilanlar:
            await interaction.response.send_message("❌ Zaten katıldınız!", ephemeral=True)
            return
        self.katilanlar.add(interaction.user.id)
        await interaction.response.send_message("✅ Katıldınız!", ephemeral=True)

@bot.tree.command(name="cekilis", description="Çekiliş başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def cekilis(interaction: discord.Interaction, odul: str):
    embed = discord.Embed(title="🎁 Resmi Çekiliş", description=f"Ödül: **{odul}**", color=discord.Color.gold())
    await interaction.channel.send(embed=embed, view=GiveawayView())
    await interaction.response.send_message("✅ Çekiliş başlatıldı.", ephemeral=True)

# --- 11. KÜFÜR FİLTRESİ VE LOGLAR ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    for kufur in KÜFÜR_LİSTESİ:
        if kufur in message.content.lower():
            try:
                await message.delete()
                await message.author.timeout(timedelta(minutes=1), reason="Küfür filtresi")
                db_sicil_ekle(message.author.id, "TIMEOUT", "Küfür kullanımı")
                log_emb = discord.Embed(title="⚠️ Küfür Tespiti", description=f"Yazan: {message.author.mention}\nMesaj: {message.content}", color=discord.Color.red())
                await ozel_kanal_logla(message.guild, "imha_evraklar", log_emb)
            except Exception:
                pass
            return
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    embed = discord.Embed(title="🗑️ Mesaj Silindi", description=f"Yazar: {message.author.mention}\nKanal: {message.channel.mention}\nİçerik: {message.content}", color=discord.Color.orange())
    await ozel_kanal_logla(message.guild, "siberay_log", embed)

@bot.event
async def on_member_update(before, after):
    if before.timed_out_until and not after.timed_out_until:
        embed = discord.Embed(title="⏱️ Zaman Aşımı Bitti", description=f"Vatandaş {after.mention} cezası sona erdi.", color=discord.Color.green())
        await ozel_kanal_logla(after.guild, "imha_evraklar", embed)

# --- BOTU BAŞLATMA ---
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token.strip())
    else:
        print("❌ HATA: DISCORD_TOKEN bulunamadı!")
