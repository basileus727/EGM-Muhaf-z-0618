import datetime
import json
import os
import random
import time
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- RENDER PORT HATASI ÖNLEME (WEB SERVICE KEEP-ALIVE) ---
app = Flask("")


@app.route("/")
def home():
  return "T.C. Kamu Sistemi ve Bot Aktif!"


def run():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


keep_alive()
# ---------------------------------------------------------

# Bot Niyetleri (Intents)
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
ses_giris_zamanlari = {}
dinamik_yasakli_kelimeler = [
    "amk",
    "aq",
    "oç",
    "piç",
    "sik",
    "yarrak",
    "orospu",
]

# --- ÖZEL KANAL TANIMLAMALARI ---
KANALLAR = {
    "nufus_mudurlugu": "nüfus-müdürlüğü",
    "imha_evraklar": "imha-edilen-evraklar",
    "evrak_duzenleme": "evrak-düzenleme",
    "nufus_hareketleri": "nüfus-hareketleri",
    "telsiz_dinleme": "telsiz-dinleme",
    "yetkili_denetim": "yetkili-denetim",
    "siberay_log": "siberay-log",
}


async def ozel_kanal_logla(guild, kanal_anahtar, embed):
  kanal_adi = KANALLAR.get(kanal_anahtar)
  if not kanal_adi:
    return
  log_kanali = discord.utils.get(guild.text_channels, name=kanal_adi)
  if log_kanali:
    try:
      await log_kanali.send(embed=embed)
    except:
      pass


@bot.event
async def on_ready():
  print(f"🇹🇷 {bot.user.name} Hatasız ve Kararlı Kamu Sistemi Aktif!")
  await bot.change_presence(
      activity=discord.Activity(
          type=discord.ActivityType.watching,
          name="T.C. Kamu Güvenliği & Denetim",
      )
  )
  try:
    synced = await bot.tree.sync()
    print(f"✅ {len(synced)} Slash komutu hatasız senkronize edildi.")
  except Exception as e:
    print(f"Komut senkronizasyon hatası: {e}")


# ==========================================
# 🛡️ 1. EGM GUARD & NÜFUS SİSTEMLERİ
# ==========================================


@bot.event
async def on_member_join(member):
  guild = member.guild
  now = datetime.datetime.now(datetime.timezone.utc)
  account_age = (now - member.created_at).days
  toplam_uye = guild.member_count
  bot_sayisi = sum(1 for m in guild.members if m.bot)
  insan_sayisi = toplam_uye - bot_sayisi

  nufus_hareket_embed = discord.Embed(
      title="📊 NÜFUS HAREKETİ - GİRİŞ",
      color=discord.Color.green(),
      timestamp=now,
  )
  nufus_hareket_embed.add_field(
      name="Katılan Vatandaş",
      value=f"{member.mention} ({member.name})",
      inline=False,
  )
  nufus_hareket_embed.add_field(
      name="Anlık Sunucu İstatistikleri",
      value=(
          f"👥 Toplam Üye: **{toplam_uye}** | 👤 İnsan: **{insan_sayisi}** |"
          f" 🤖 Bot: **{bot_sayisi}**"
      ),
      inline=False,
  )
  await ozel_kanal_logla(guild, "nufus_hareketleri", nufus_hareket_embed)

  if account_age < MIN_ACCOUNT_AGE_DAYS:
    try:
      await member.send(
          "🇹🇷 **T.C. İÇİŞLERİ BAKANLIĞI - EGM GUARD**\nHesap yaşınız"
          f" yetersiz ({account_age}/{MIN_ACCOUNT_AGE_DAYS} gün)."
      )
    except:
      pass
    try:
      await member.kick(reason=f"EGM Guard: Hesap yaşı {account_age} gün.")
    except:
      pass
  else:
    kayitsiz_rol = discord.utils.get(guild.roles, name="Kayıtsız")
    if kayitsiz_rol:
      await member.add_roles(kayitsiz_rol)
    nufus_embed = discord.Embed(
        title="🆔 NÜFUS MÜDÜRLÜĞÜ - YENİ KAYIT",
        color=discord.Color.blue(),
        timestamp=now,
    )
    nufus_embed.add_field(
        name="Vatandaş",
        value=f"{member.mention} sisteme ve sunucuya kaydoldu.",
        inline=False,
    )
    await ozel_kanal_logla(guild, "nufus_mudurlugu", nufus_embed)


@bot.event
async def on_member_remove(member):
  guild = member.guild
  now = datetime.datetime.now(datetime.timezone.utc)
  toplam_uye = guild.member_count
  bot_sayisi = sum(1 for m in guild.members if m.bot)
  insan_sayisi = toplam_uye - bot_sayisi

  nufus_hareket_embed = discord.Embed(
      title="📊 NÜFUS HAREKETİ - ÇIKIŞ",
      color=discord.Color.orange(),
      timestamp=now,
  )
  nufus_hareket_embed.add_field(
      name="Ayrılan Vatandaş", value=f"{member.name}", inline=False
  )
  nufus_hareket_embed.add_field(
      name="Güncel Sunucu İstatistikleri",
      value=(
          f"👥 Toplam Üye: **{toplam_uye}** | 👤 İnsan: **{insan_sayisi}** |"
          f" 🤖 Bot: **{bot_sayisi}**"
      ),
      inline=False,
  )
  await ozel_kanal_logla(guild, "nufus_hareketleri", nufus_hareket_embed)


# ==========================================
# 📑 2. EVRAK, KÜFÜR FİLTRESİ VE XP SİSTEMİ
# ==========================================


@bot.event
async def on_message(message):
  if message.author.bot:
    return

  msg_content = message.content.lower()
  if any(kelime in msg_content for kelime in dinamik_yasakli_kelimeler):
    await message.delete()
    await message.channel.send(
        f"⚠️ {message.author.mention}, T.C. Kamu Düzeni uyarınca bu ifade"
        " yasaktır!",
        delete_after=5,
    )

    embed = discord.Embed(
        title="⚠️ YASAKLI KELİME TESPİTİ",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
    embed.add_field(name="Mesaj", value=message.content, inline=False)
    await ozel_kanal_logla(message.guild, "siberay_log", embed)
    return

  user_id = message.author.id
  if user_id not in yetkili_puanlari:
    yetkili_puanlari[user_id] = {"puan": 0, "ceza": 0}

  yetkili_mi = any(
      "Yetkili" in r.name or "Yönetici" in r.name or "Mod" in r.name
      for r in message.author.roles
  )
  if yetkili_mi:
    yetkili_puanlari[user_id]["puan"] += 1

  current_data = kullanici_xp.get(user_id, {"xp": 0, "level": 1})
  current_data["xp"] += random.randint(5, 15)
  if current_data["xp"] >= current_data["level"] * 100:
    current_data["level"] += 1
    current_data["xp"] = 0
    await message.channel.send(
        f"🎉 Tebrikler {message.author.mention}, **Seviye"
        f" {current_data['level']}** rütbesine yükseldin!",
        delete_after=5,
    )
  kullanici_xp[user_id] = current_data

  await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
  if message.author.bot:
    return
  embed = discord.Embed(
      title="🗑️ İMHA EDİLEN EVRAK (SİLİNEN MESAJ)",
      color=discord.Color.purple(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.add_field(name="Mesaj Sahibi", value=message.author.mention, inline=True)
  embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
  embed.add_field(
      name="İçerik", value=message.content or "Medya/Ek", inline=False
  )
  await ozel_kanal_logla(message.guild, "imha_evraklar", embed)


@bot.event
async def on_message_edit(before, after):
  if before.author.bot or before.content == after.content:
    return
  embed = discord.Embed(
      title="✏️ DÜZENLENEN EVRAK",
      color=discord.Color.gold(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.add_field(name="Kullanıcı", value=before.author.mention, inline=False)
  embed.add_field(name="Kanal", value=before.channel.mention, inline=False)
  embed.add_field(name="Eski Metin", value=before.content or "Boş", inline=False)
  embed.add_field(name="Yeni Metin", value=after.content or "Boş", inline=False)
  await ozel_kanal_logla(before.guild, "evrak_duzenleme", embed)


# ==========================================
# 🔊 3. TELSİZ DİNLEME (SES KANALI) SİSTEMİ
# ==========================================


@bot.event
async def on_voice_state_update(member, before, after):
  guild = member.guild
  now = datetime.datetime.now(datetime.timezone.utc)

  if before.channel is None and after.channel is not None:
    ses_giris_zamanlari[member.id] = now
    embed = discord.Embed(
        title="📻 TELSİZ BAĞLANTISI - GİRİŞ",
        color=discord.Color.green(),
        timestamp=now,
    )
    embed.add_field(name="Personel", value=member.mention, inline=True)
    embed.add_field(name="Kanal", value=after.channel.name, inline=True)
    await ozel_kanal_logla(guild, "telsiz_dinleme", embed)

  elif before.channel is not None and after.channel is None:
    giris_zamani = ses_giris_zamanlari.pop(member.id, None)
    dakika_str = "Bilinmiyor"
    if giris_zamani:
      fark = now - giris_zamani
      dakika_str = f"{int(fark.total_seconds() // 60)} dakika"

    embed = discord.Embed(
        title="📻 TELSİZ BAĞLANTISI - ÇIKIŞ",
        color=discord.Color.red(),
        timestamp=now,
    )
    embed.add_field(name="Personel", value=member.mention, inline=True)
    embed.add_field(name="Ayrıldığı Kanal", value=before.channel.name, inline=True)
    embed.add_field(name="Süre", value=dakika_str, inline=False)
    await ozel_kanal_logla(guild, "telsiz_dinleme", embed)


# ==========================================
# 🏛️ 4. ADALET & MAHKEME SİSTEMİ
# ==========================================


class DavaKapatButon(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="⚖️ Davayı/Talebi Sonlandır",
      style=discord.ButtonStyle.red,
      custom_id="dava_kapat_btn",
  )
  async def kapat(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_message("🏛 Dava arşive kaldırılıyor...")
    await interaction.channel.delete()


class MahkemeBasvuruView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="⚖️ Mahkeme/Destek Talebi Aç",
      style=discord.ButtonStyle.primary,
      custom_id="mahkeme_ac_btn",
  )
  async def talep_ac(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    guild = interaction.guild
    user = interaction.user
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(
            read_messages=True, send_messages=True
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True, send_messages=True
        ),
    }
    channel_name = f"dava-{user.name}"
    if discord.utils.get(guild.channels, name=channel_name):
      await interaction.response.send_message(
          "❌ Zaten açık bir davanız var!", ephemeral=True
      )
      return

    ticket_channel = await guild.create_text_channel(
        name=channel_name, overwrites=overwrites
    )
    embed = discord.Embed(
        title="🏛️ YARGITAY OTURUMU",
        description=f"Sayın {user.mention}, talebiniz alınmıştır.",
        color=discord.Color.gold(),
    )
    await ticket_channel.send(embed=embed, view=DavaKapatButon())
    await interaction.response.send_message(
        f"✅ Dava kanalınız açıldı: {ticket_channel.mention}", ephemeral=True
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def mahkemekur(ctx):
  embed = discord.Embed(
      title="🏛️ ADALET BAKANLIĞI BAŞVURU PANELİ",
      description="Destek veya şikayet için butona basın.",
      color=discord.Color.red(),
  )
  await ctx.send(embed=embed, view=MahkemeBasvuruView())


# ==========================================
# 🚀 5. PROFESYONEL SUNUCU YÖNETİM KOMUTLARI
# ==========================================


@bot.tree.command(
    name="kurulum",
    description="Sunucu için gerekli tüm T.C. Kamu kanal ve rollerini kurar.",
)
@app_commands.default_permissions(administrator=True)
async def kurulum(interaction: discord.Interaction):
  await interaction.response.defer(ephemeral=True)
  guild = interaction.guild

  roller = ["Kayıtsız", "Vatandaş", "Polis", "Yönetici"]
  for r_adi in roller:
    if not discord.utils.get(guild.roles, name=r_adi):
      await guild.create_role(name=r_adi, reason="T.C. Kamu Otomatik Kurulum")

  kategori = await guild.create_category("🇹🇷 T.C. KAMU DEVLET MERKEZİ")
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


@bot.tree.command(
    name="duyuru", description="Belirtilen kanala resmi kamu duyurusu gönderir."
)
@app_commands.describe(
    kanal="Duyurunun atılacağı kanal",
    baslik="Başlık",
    mesaj="İçerik",
    etiketle="Herkese etiket atılsın mı? (Evet/Hayır)",
)
@app_commands.default_permissions(manage_messages=True)
async def duyuru(
    interaction: discord.Interaction,
    kanal: discord.TextChannel,
    baslik: str,
    mesaj: str,
    etiketle: bool = False,
):
  embed = discord.Embed(
      title=f"📢 T.C. RESMİ DUYURU: {baslik}",
      description=mesaj,
      color=discord.Color.blue(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.set_footer(text=f"Yayınlayan: {interaction.user.name}")
  content_str = "@everyone" if etiketle else ""
  await kanal.send(content=content_str, embed=embed)
  await interaction.response.send_message(
      f"✅ Duyuru başarıyla {kanal.mention} kanalına iletildi.", ephemeral=True
  )


@bot.tree.command(
    name="anket", description="Emoji destekli çoktan seçmeli anket açar."
)
@app_commands.describe(
    soru="Anket konusu", secenek1="1. Seçenek", secenek2="2. Seçenek"
)
@app_commands.default_permissions(manage_messages=True)
async def anket(
    interaction: discord.Interaction,
    soru: str,
    secenek1: str,
    secenek2: str,
):
  embed = discord.Embed(
      title="📊 T.C. KAMU ANKETİ",
      description=f"**{soru}**\n\n1️⃣ {secenek1}\n2️⃣ {secenek2}",
      color=discord.Color.dark_gold(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.set_footer(text=f"Başlatan: {interaction.user.name}")
  await interaction.response.send_message("✅ Anket yayınlandı.", ephemeral=True)
  mesaj = await interaction.channel.send(embed=embed)
  await mesaj.add_reaction("1️⃣")
  await mesaj.add_reaction("2️⃣")


@bot.tree.command(
    name="istatistik", description="Sunucu ve bot performans istatistiklerini sunar."
)
async def istatistik(interaction: discord.Interaction):
  guild = interaction.guild
  toplam_uye = guild.member_count
  bot_sayisi = sum(1 for m in guild.members if m.bot)
  insan_sayisi = toplam_uye - bot_sayisi
  sesli_kullanici = sum(
      len(vc.members) for vc in guild.voice_channels if vc.members
  )
  uptime = int(time.time() - bot_baslangic_zamani)

  embed = discord.Embed(
      title="📈 T.C. KAMU - SİSTEM İSTATİSTİKLERİ", color=discord.Color.teal()
  )
  embed.add_field(name="Toplam Üye", value=str(toplam_uye), inline=True)
  embed.add_field(
      name="İnsan / Bot", value=f"👤 {insan_sayisi} | 🤖 {bot_sayisi}", inline=True
  )
  embed.add_field(
      name="Sestekiler", value=f"🔊 {sesli_kullanici} Kişi", inline=True
  )
  embed.add_field(
      name="Gecikme (Ping)", value=f"⚡ {round(bot.latency * 1000)}ms", inline=True
  )
  embed.add_field(
      name="Çalışma Süresi",
      value=f"⏱️ {uptime // 3600} Saat {(uptime % 3600) // 60} Dakika",
      inline=True,
  )
  await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="yasakli-kelime", description="Küfür filtresi listesine kelime ekler/çıkarır."
)
@app_commands.describe(islem="Ekle veya Çıkar", kelime="İşlem yapılacak kelime")
@app_commands.choices(
    islem=[
        app_commands.Choice(name="Ekle", value="ekle"),
        app_commands.Choice(name="Çıkar", value="cikar"),
    ]
)
@app_commands.default_permissions(administrator=True)
async def yasaklikelime(
    interaction: discord.Interaction, islem: str, kelime: str
):
  kelime = kelime.lower().strip()
  if islem == "ekle":
    if kelime not in dinamik_yasakli_kelimeler:
      dinamik_yasakli_kelimeler.append(kelime)
      await interaction.response.send_message(
          f"✅ **{kelime}** yasaklılara eklendi.", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          f"❌ **{kelime}** zaten listede var.", ephemeral=True
      )
  else:
    if kelime in dinamik_yasakli_kelimeler:
      dinamik_yasakli_kelimeler.remove(kelime)
      await interaction.response.send_message(
          f"✅ **{kelime}** listeden çıkarıldı.", ephemeral=True
      )
    else:
      await interaction.response.send_message(
          f"❌ **{kelime}** listede bulunamadı.", ephemeral=True
      )


# --- YENİ EKLENEN FAYDALI YÖNETİM KOMUTLARI ---


@bot.tree.command(
    name="kurallar", description="Sunucunun resmi T.C. Anayasa kurallarını yayınlar."
)
@app_commands.default_permissions(administrator=True)
async def kurallar(interaction: discord.Interaction):
  embed = discord.Embed(
      title="📜 T.C. KAMU ANAYASASI VE KURALLARI",
      description=(
          "1️⃣ **Saygı ve Disiplin:** Her vatandaşa karşı saygılı olmak"
          " zorunludur.\n2️⃣ **Küfür ve Hakaret:** Kesinlikle yasaktır, filtre"
          " otomatik siler.\n3️⃣ **Spam / Reklam:** Her türlü izinsiz reklam"
          " yasaktır.\n4️⃣ **Telsiz Düzeni:** Ses kanallarında gürültü kirliliği"
          " yaratılamaz.\n5️⃣ **Yetkili Kararları:** Yönetimin kararları"
          " esastır."
      ),
      color=discord.Color.dark_red(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.set_footer(text="T.C. İçişleri Bakanlığı Yönetimi")
  await interaction.channel.send(embed=embed)
  await interaction.response.send_message(
      "✅ Resmi kurallar başarıyla yayınlandı.", ephemeral=True
  )


@bot.tree.command(
    name="rapor", description="Yönetime gizli bir şikayet veya ihbar bildirir."
)
@app_commands.describe(sikayet="Şikayetiniz veya ihbarınız nedir?")
async def rapor(interaction: discord.Interaction, sikayet: str):
  embed = discord.Embed(
      title="🚨 YENİ VATANDAŞ İHBARI / BİLDİRİMİ",
      color=discord.Color.orange(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.add_field(name="Bildiren Vatandaş", value=interaction.user.mention)
  embed.add_field(name="İçerik", value=sikayet, inline=False)

  await ozel_kanal_logla(interaction.guild, "siberay_log", embed)
  await interaction.response.send_message(
      "✅ İhbarınız güvenli bir şekilde Siberay Log birimine iletildi.",
      ephemeral=True,
  )


@bot.tree.command(name="rol-ver", description="Bir vatandaşa hızlıca rol atar.")
@app_commands.describe(vatandas="Rol verilecek üye", rol="Verilecek rol")
@app_commands.default_permissions(manage_roles=True)
async def rolver(
    interaction: discord.Interaction, vatandas: discord.Member, rol: discord.Role
):
  try:
    await vatandas.add_roles(rol)
    await interaction.response.send_message(
        f"✅ {vatandas.mention} adlı vatandaşa başarıyla {rol.mention} rolü"
        " verildi.",
        ephemeral=True,
    )
  except Exception as e:
    await interaction.response.send_message(
        f"❌ Rol verme başarısız: {e}", ephemeral=True
    )


@bot.tree.command(name="rol-al", description="Bir vatandaşın rolünü alır.")
@app_commands.describe(vatandas="Rolü alınacak üye", rol="Alınacak rol")
@app_commands.default_permissions(manage_roles=True)
async def rolal(
    interaction: discord.Interaction, vatandas: discord.Member, rol: discord.Role
):
  try:
    await vatandas.remove_roles(rol)
    await interaction.response.send_message(
        f"✅ {vatandas.mention} adlı vatandaştan {rol.mention} rolü"
        " kaldırıldı.",
        ephemeral=True,
    )
  except Excepti
