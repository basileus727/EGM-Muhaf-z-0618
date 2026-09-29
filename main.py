import os
import time
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- WEB SERVICE KEEP-ALIVE (Render Port Hatası Önleme) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- Bot Niyetleri (Intents) ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

MIN_ACCOUNT_AGE_DAYS = 15
bot_baslangic_zamani = time.time()

# --- SAHTE VERİTABANI VE LİSTELER ---
kullanici_bakiyeleri = {}
kullanici_xp = {}
yetkili_puanlari = {}

KÜFÜR_LİSTESİ = [
    "orospu",
]

KANALLAR = {
    "nufus_mudurlugu": "nufus-müdürlüğü",
    "imha_evraklar": "imha-edilen-evraklar",
    "evrak_duzenleme": "evrak-düzenleme",
    "nufus_hareketleri": "nufus-hareketleri",
    "telsiz_dinleme": "telsiz-dinleme",
    "yetkili_denetim": "yetkili-denetim",
    "siberay_log": "siberay-log",
}

async def ozel_kanal_logla(guild, kanal_adi, embed):
    kanal_ismi = KANALLAR.get(kanal_adi, kanal_adi)
    kanal = discord.utils.get(guild.text_channels, name=kanal_ismi)
    if kanal:
        await kanal.send(embed=embed)

@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı!")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} komut senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

# --- 1. T.C. KAMU ALTYAPI KURULUMU ---
@bot.tree.command(name="kurulum", description="Sunucu altyapısını ve kanalları kurar.")
@app_commands.default_permissions(administrator=True)
async def kurulum(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    kategori = await guild.create_category("T.C. KAMU ALTYAPISI")
    kanal_listesi = [
        "nüfus-müdürlüğü",
        "imha-edilen-evraklar",
        "evrak-düzenleme",
        "nüfus-hareketleri",
        "telsiz-dinleme",
        "yetkili-denetim",
        "siberay-log",
    ]
    for k_adi in kanal_listesi:
        if not discord.utils.get(guild.text_channels, name=k_adi):
            await guild.create_text_channel(k_adi, category=kategori)

    await interaction.followup.send(
        "✅ T.C. Kamu altyapısı eksiksiz olarak kuruldu!", ephemeral=True
    )

# --- DUYURU KOMUTU ---
@bot.tree.command(name="duyuru", description="Belirtilen kanala resmi kamu duyurusu gönderir.")
@app_commands.describe(
    kanal="Duyurunun atılacağı kanal",
    baslik="Başlık",
    mesaj="İçerik",
    etiketle="Herkese etiket atılsın mı?"
)
@app_commands.default_permissions(manage_messages=True)
async def duyuru(interaction: discord.Interaction, kanal: discord.TextChannel, baslik: str, mesaj: str, etiketle: str = "hayır"):
    embed = discord.Embed(title=f"📢 {baslik}", description=mesaj, color=discord.Color.blue())
    embed.set_footer(text=f"Yetkili: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
    
    content = "@everyone" if etiketle.lower() in ["evet", "yes", "e"] else None
    await kanal.send(content=content, embed=embed)
    await interaction.response.send_message("✅ Duyuru başarıyla gönderildi.", ephemeral=True)

# --- 2. T.C. VATANDAŞ KİMLİK / PROFİL SORGULAMA ---
@bot.tree.command(name="kimlik", description="Kullanıcının kimlik ve bakiye bilgilerini gösterir.")
@app_commands.describe(vatandas="Bilgisine bakılacak üye (İsteğe bağlı)")
async def kimlik(interaction: discord.Interaction, vatandas: discord.Member = None):
    target = vatandas or interaction.user
    bakiye = kullanici_bakiyeleri.get(target.id, 0)
    xp_data = kullanici_xp.get(target.id, 0)
    hesap_tarihi = target.created_at.strftime("%d.%m.%Y %H:%M:%S")

    embed = discord.Embed(title="🆔 T.C. VATANDAŞ KİMLİK KAYDI", color=discord.Color.green())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Kullanıcı", value=target.mention, inline=True)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Bakiye", value=f"{bakiye} TL", inline=True)
    embed.add_field(name="Rütbe", value=f"Seviye **{xp_data}**", inline=True)
    embed.add_field(name="Hesap Açılışı", value=hesap_tarihi, inline=False)

    await interaction.response.send_message(embed=embed)

# --- 3. MAHKEME VE DAVA YÖNETİM SİSTEMİ ---
class DavaKapatButon(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Davayı Kapat", style=discord.ButtonStyle.danger, custom_id="dava_kapat_btn")
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

    @discord.ui.button(label="⚖️ Mahkeme Başvurusu Aç", style=discord.ButtonStyle.primary, custom_id="mahkeme_basvuru_btn")
    async def mahkeme_ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        kanal_adi = f"mahkeme-{interaction.user.name}".lower().replace(" ", "-")
        ek_kanal = await guild.create_text_channel(kanal_adi, overwrites=overwrites)
        
        embed = discord.Embed(
            title="⚖️ Mahkeme Dosyası Açıldı",
            description=f"Sayın {interaction.user.mention}, dava talebiniz alınmıştır. Lütfen şikayetinizi ve delillerinizi buraya aktarın.",
            color=discord.Color.gold()
        )
        await ek_kanal.send(content=interaction.user.mention, embed=embed, view=DavaKapatButon())
        await interaction.response.send_message(f"✅ Mahkeme kanalınız oluşturuldu: {ek_kanal.mention}", ephemeral=True)

@bot.tree.command(name="mahkemepaneli", description="Mahkeme başvuru panelini kanala gönderir.")
@app_commands.default_permissions(administrator=True)
async def mahkemepaneli(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏛️ T.C. MAHKEME VE DAVA MERKEZİ",
        description="Hukuki uyuşmazlıklar ve dava açmak için aşağıdaki butona tıklayarak özel mahkeme kanalı oluşturabilirsiniz.",
        color=discord.Color.dark_blue()
    )
    await interaction.channel.send(embed=embed, view=MahkemeBasvuruView())
    await interaction.response.send_message("✅ Mahkeme paneli başarıyla kuruldu.", ephemeral=True)

# --- 4. KÜFÜR FİLTRESİ VE EVENTLER ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    icerik_kucuk = message.content.lower()
    for kufur in KÜFÜR_LİSTESİ:
        if kufur in icerik_kucuk:
            try:
                await message.delete()
                log_embed = discord.Embed(title="⚠️ YASAKLI KELİME TESPİT EDİLDİ", color=discord.Color.red())
                log_embed.add_field(name="Kullanıcı", value=message.author.mention, inline=False)
                log_embed.add_field(name="Kanal", value=message.channel.mention, inline=False)
                log_embed.add_field(name="Mesaj", value=message.content, inline=False)
                await ozel_kanal_logla(message.guild, "imha_evraklar", log_embed)
            except Exception:
                pass
            return

    await bot.process_commands(message)

# --- 5. TELSİZ DİNLEME (SES KANALI) SİSTEMİ ---
@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild
    embed = discord.Embed(title="🎙️ Telsiz Hareketi", color=discord.Color.orange())
    embed.add_field(name="Personel", value=member.mention, inline=False)
    
    if before.channel is None and after.channel is not None:
        embed.description = f"Kullanıcı bir ses kanalına giriş yaptı."
        embed.add_field(name="Kanal", value=after.channel.name, inline=True)
        await ozel_kanal_logla(guild, "telsiz_dinleme", embed)
    elif before.channel is not None and after.channel is None:
        embed.description = f"Kullanıcı ses kanalından ayrıldı."
        embed.add_field(name="Ayrıldığı Kanal", value=before.channel.name, inline=True)
        await ozel_kanal_logla(guild, "telsiz_dinleme", embed)

# --- 6. TEMEL MODERASYON KOMUTLARI ---
@bot.tree.command(name="yavasmod", description="Kanalın yavaş mod süresini ayarlar.")
@app_commands.describe(saniye="Saniye cinsinden yavaş mod (0 = Kapalı)")
@app_commands.default_permissions(manage_channels=True)
async def yavasmod(interaction: discord.Interaction, saniye: int):
    await interaction.channel.edit(slowmode_delay=saniye)
    await interaction.response.send_message(
        f"⏳ Bu kanalın yavaş modu **{saniye}** saniye olarak ayarlandı.", ephemeral=True
    )

@bot.tree.command(name="temizle", description="Belirtilen miktarda mesajı siler.")
@app_commands.describe(adet="Silinecek mesaj sayısı")
@app_commands.default_permissions(manage_messages=True)
async def temizle(interaction: discord.Interaction, adet: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=adet)
    await interaction.followup.send(f"🧹 Başarıyla **{len(deleted)}** mesaj silindi.", ephemeral=True)

# --- 7. VATANDAŞLIK BAŞVURU SİSTEMİ ---
class VatandaslikModal(discord.ui.Modal, title="T.C. Vatandaşlık Başvuru Formu"):
    ad_soyad = discord.ui.TextInput(
        label="Ad & Soyad (Veya Karakter Adı)",
        placeholder="Örnek: Ahmet Yılmaz",
        required=True,
        max_length=50
    )
    yas = discord.ui.TextInput(
        label="Yaş",
        placeholder="Örnek: 20",
        required=True,
        max_length=3
    )
    memleket = discord.ui.TextInput(
        label="Memleket / Doğum Yeri",
        placeholder="Örnek: Ankara",
        required=False,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🇹🇷 **Başvurunuz Alınmıştır!**\n\n"
            f"• **Ad/Soyad:** {self.ad_soyad.value}\n"
            f"• **Yaş:** {self.yas.value}\n"
            f"• **Memleket:** {self.memleket.value if self.memleket.value else 'Belirtilmemiş'}\n\n"
            f"EGM yetkilileri başvurunuzu inceleyip onaylayacaktır.",
            ephemeral=True
        )

class BasvuruView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Başvuru Formunu Doldur", style=discord.ButtonStyle.green, emoji="📋", custom_id="vatandaslik_basvuru_btn")
    async def basvuru_yap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VatandaslikModal())

@bot.tree.command(name="basvuru-kur", description="Vatandaşlık başvuru kanalına formu ve butonu kurar.")
@app_commands.default_permissions(administrator=True)
async def basvuru_kur(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏛️ TÜRKİYE CUMHURİYETİ NÜFUS VE VATANDAŞLIK İŞLERİ 🏛️",
        description=(
            "Devletimizin tüm imkanlarından, kamu kanallarından ve rol alanlarından "
            "yararlanabilmek için T.C. Vatandaşlık kaydınızı tamamlamanız gerekmektedir.\n\n"
            "📝 **Nasıl Başvuru Yapılır?**\n"
            "Aşağıdaki **'Başvuru Formunu Doldur'** butonuna tıklayarak açılan pencereye "
            "bilgilerinizi eksiksiz girin ve gönderin."
        ),
        color=discord.Color.red()
    )
    embed.set_footer(text="EGM Güvenlik Sistemleri", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    await interaction.channel.send(embed=embed, view=BasvuruView())
    await interaction.response.send_message("✅ Başvuru paneli başarıyla kuruldu!", ephemeral=True)

# --- BOTU ÇALIŞTIRMA ---
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token.strip())
    else:
        print("❌ HATA: DISCORD_TOKEN bulunamadı!")
                          
