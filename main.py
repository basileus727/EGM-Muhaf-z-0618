import datetime
import json
import os
import random
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

# --- SAHTE VERİTABANI ---
kullanici_bakiyeleri = {}
maas_cooldown = {}
kullanici_xp = {}
kullanici_yatirim = {}
yetkili_puanlari = {}  # {user_id: {"puan": 0, "ceza": 0}}
ses_giris_zamanlari = {}  # {user_id: datetime}

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
  """Belirtilen özel kanala log atar."""
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
  print(f"🇹🇷 {bot.user.name} Tüm T.C. Devlet Modülleri Aktif Edildi!")
  await bot.change_presence(
      activity=discord.Activity(
          type=discord.ActivityType.watching,
          name="T.C. Kamu Güvenliği & Arşivler",
      )
  )
  try:
    synced = await bot.tree.sync()
    print(f"✅ {len(synced)} Slash komutu senkronize edildi.")
  except Exception as e:
    print(f"Komut senkronizasyon hatası: {e}")


# ==========================================
# 🛡️ 1. EGM GUARD & NÜFUS / GİRİŞ-ÇIKIŞ SİSTEMLERİ
# ==========================================


@bot.event
async def on_member_join(member):
  guild = member.guild
  now = datetime.datetime.now(datetime.timezone.utc)
  account_age = (now - member.created_at).days

  # Nüfus Hareketleri (Üye ve Bot Sayacı)
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
    egm_dm_message = (
        "🇹🇷 **T.C. İÇİŞLERİ BAKANLIĞI - EGM GUARD**\n"
        f"Hesap yaşı {MIN_ACCOUNT_AGE_DAYS} günden küçük olduğu için geçici"
        " olarak engellendiniz."
    )
    try:
      await member.send(egm_dm_message)
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
# 📑 2. EVRAK, MESAJ VE YETKİLİ DENETİM SİSTEMİ
# ==========================================

KUFUR_LISTESI = ["amk", "aq", "oç", "piç", "sik", "yarrak", "orospu"]


@bot.event
async def on_message(message):
  if message.author.bot:
    return

  msg_content = message.content.lower()
  if any(kufur in msg_content for kufur in KUFUR_LISTESI):
    await message.delete()
    await message.channel.send(
        f"⚠️ {message.author.mention}, T.C. Kamu Düzeni uyarınca hakaret"
        " yasaktır!",
        delete_after=5,
    )

    embed = discord.Embed(
        title="⚠️ KÜFÜR TESPİTİ",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
    embed.add_field(name="Mesaj", value=message.content, inline=False)
    await ozel_kanal_logla(message.guild, "siberay_log", embed)
    return

  # Yetkili Puanlama (Mesaj başına puan artışı)
  user_id = message.author.id
  if user_id not in yetkili_puanlari:
    yetkili_puanlari[user_id] = {"puan": 0, "ceza": 0}

  # Eğer kullanıcı yetkili rollerindense puan ekle
  yetkili_mi = any(
      "Yetkili" in r.name or "Yönetici" in r.name or "Mod" in r.name
      for r in message.author.roles
  )
  if yetkili_mi:
    yetkili_puanlari[user_id]["puan"] += 1

  # Normal Seviye ve XP
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
  embed.add_field(name="Mesaj Sahib", value=message.author.mention, inline=True)
  embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
  embed.add_field(
      name="İmha Edilen İçerik",
      value=message.content or "İçerik/Medya yok",
      inline=False,
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

  # Ses kanalına giriş
  if before.channel is None and after.channel is not None:
    ses_giris_zamanlari[member.id] = now
    embed = discord.Embed(
        title="📻 TELSİZ BAĞLANTISI - GİRİŞ",
        color=discord.Color.green(),
        timestamp=now,
    )
    embed.add_field(name="Personel / Vatandaş", value=member.mention, inline=True)
    embed.add_field(name="Kanal", value=after.channel.name, inline=True)
    await ozel_kanal_logla(guild, "telsiz_dinleme", embed)

  # Ses kanalından çıkış veya kanal değiştirme
  elif before.channel is not None and after.channel is None:
    giris_zamani = ses_giris_zamanlari.pop(member.id, None)
    kalinan_sure_str = "Bilinmiyor"
    if giris_zamani:
      fark = now - giris_zamani
      dakika = int(fark.total_seconds() // 60)
      kalinan_sure_str = f"{dakika} dakika"

    embed = discord.Embed(
        title="📻 TELSİZ BAĞLANTISI - ÇIKIŞ",
        color=discord.Color.red(),
        timestamp=now,
    )
    embed.add_field(name="Personel / Vatandaş", value=member.mention, inline=True)
    embed.add_field(name="Ayrıldığı Kanal", value=before.channel.name, inline=True)
    embed.add_field(
        name="Telsizde Kalınan Süre", value=kalinan_sure_str, inline=False
    )
    await ozel_kanal_logla(guild, "telsiz_dinleme", embed)


# ==========================================
# ⚖️ 4. MAHKEME & YETKİLİ DENETİM KOMUTLARI
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
    await interaction.response.send_message("🏛️ Dava arşive kaldırılıyor...")
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


@bot.tree.command(
    name="yetkilidenetim",
    description="Yetkililerin aylık puan ve performans durumunu gösterir.",
)
async def yetkilidenetim(interaction: discord.Interaction):
  embed = discord.Embed(
      title="🛡️ YETKİLİ DENETİM VE PERFORMANS RAPORU", color=discord.Color.gold()
  )

  if not yetkili_puanlari:
    embed.description = "Henüz kayıtlı yetkili aktivite puanı bulunmuyor."
  else:
    for uid, veri in yetkili_puanlari.items():
      user = interaction.guild.get_member(uid)
      user_name = user.name if user else f"ID: {uid}"
      embed.add_field(
          name=f"Yetkili: {user_name}",
          value=(
              f"⭐ Puan: **{veri['puan']}** | ⚠️ Ceza: **{veri['ceza']}**"
          ),
          inline=False,
      )

  await interaction.response.send_message(embed=embed)


# ==========================================
# 🧹 5. YENİ EKLENEN ÜST DÜZEY KOMUTLAR (TEMİZLE, EMBED, ÇEKİLİŞ, ROL)
# ==========================================


@bot.tree.command(
    name="temizle", description="Belirtilen miktarda mesajı kanaldan siler."
)
@app_commands.describe(adet="Silinecek mesaj sayısı (Örn: 50, 200)")
@app_commands.default_permissions(
    manage_messages=True
)  # Sadece mesajları yönet yetkisi olanlar kullanabilir
async def temizle(interaction: discord.Interaction, adet: int):
  if adet <= 0:
    await interaction.response.send_message(
        "Lütfen 0'dan büyük bir sayı gir!", ephemeral=True
    )
    return

  await interaction.response.defer(ephemeral=True)

  try:
    silinen = await interaction.channel.purge(limit=adet)
    await interaction.followup.send(
        f"Başarıyla **{len(silinen)}** adet mesaj silindi!", ephemeral=True
    )
  except Exception as e:
    await interaction.followup.send(
        f"Mesajlar silinirken bir hata oluştu: {e}", ephemeral=True
    )


@bot.tree.command(
    name="embed", description="Özel şık bir duyuru kutusu (embed) oluşturur."
)
@app_commands.describe(baslik="Duyuru Başlığı", icerik="Duyuru Metni")
@app_commands.default_permissions(manage_messages=True)
async def embed_olustur(
    interaction: discord.Interaction, baslik: str, icerik: str
):
  embed = discord.Embed(
      title=baslik,
      description=icerik,
      color=discord.Color.blue(),
      timestamp=datetime.datetime.now(datetime.timezone.utc),
  )
  embed.set_footer(text=f"Yetkili: {interaction.user.name}")
  await interaction.channel.send(embed=embed)
  await interaction.response.send_message(
      "✅ Duyuru başarıyla oluşturuldu.", ephemeral=True
  )


class CekilisKatilButon(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)
    self.katilanlar = set()

  @discord.ui.button(
      label="🎉 Çekilişe Katıl",
      style=discord.ButtonStyle.green,
      custom_id="cekilis_katil_btn",
  )
  async def katil(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if interaction.user.id in self.katilanlar:
      self.katilanlar.remove(interaction.user.id)
      await interaction.response.send_message(
          "❌ Çekilişten katılımınız kaldırıldı.", ephemeral=True
      )
    else:
      self.katilanlar.add(interaction.user.id)
      await interaction.response.send_message(
          "✅ Çekilişe başarıyla katıldınız!", ephemeral=True
      )


@bot.tree.command(name="cekilis", description="Sunucuda yeni bir çekiliş başlatır.")
@app_commands.describe(odul="Verilecek ödül nedir?")
@app_commands.default_permissions(administrator=True)
async def cekilis(interaction: discord.Interaction, odul: str):
  embed = discord.Embed(
      title="🎁 YENİ ÇEKİLİŞ BAŞLADI!",
      description=(
          f"Ödül: **{odul}**\n\nKatılmak için aşağıdaki **Çekilişe Katıl**"
          " butonuna basın!"
      ),
      color=discord.Color.gold(),
  )
  view = CekilisKatilButon()
  await interaction.response.send_message(embed=embed, view=view)


# ==========================================
# 💰 6. EKONOMİ VE BORSA SİSTEMİ
# ==========================================


@bot.tree.command(
    name="cuzdan", description="Merkez Bankası hesap bakiyenizi gösterir."
)
async def cuzdan(interaction: discord.Interaction):
  bakiye = kullanici_bakiyeleri.get(interaction.user.id, 0)
  embed = discord.Embed(title="💳 MERKEZ BANKASI HESABI", color=discord.Color.green())
  embed.add_field(name="Bakiye", value=f"**{bakiye:,} ₺**", inline=False)
  await interaction.response.send_message(embed=embed)


@bot.tree.command(name="maas", description="Günlük vatandaşlık maaşınızı alırsınız.")
async def maas(interaction: discord.Interaction):
  user_id = interaction.user.id
  today = datetime.date.today()
  if kullanici_bakiyeleri.get(f"{user_id}_maas") == today:
    await interaction.response.send_message(
        "❌ Bugünlük maaşınızı zaten aldınız!", ephemeral=True
    )
    return
  kullanici_bakiyeleri[user_id] = kullanici_bakiyeleri.get(user_id, 0) + 1500
  kullanici_bakiyeleri[f"{user_id}_maas"] = today
  await interaction.response.send_message(
      f"💵 1,500 ₺ maaş yatırıldı! Güncel bakiye:"
      f" **{kullanici_bakiyeleri[user_id]:,} ₺**"
  )


@bot.tree.command(name="seviye", description="Rütbe ve XP durumunuzu gösterir.")
async def seviye(interaction: discord.Interaction):
  data = kullanici_xp.get(interaction.user.id, {"xp": 0, "level": 1})
  embed = discord.Embed(title="🎖️ KAMU RÜTBE SİSTEMİ", color=discord.Color.gold())
  embed.add_field(name="Seviye", value=str(data["level"]), inline=True)
  embed.add_field(
      name="XP", value=f"{data['xp']} / {data['level'] * 100}", inline=True
  )
  await interaction.response.send_message(embed=embed)


# BOTU ÇALIŞTIRMA
token = os.environ.get("DISCORD_TOKEN")
if token:
  bot.run(token.strip())
else:
  print("❌ HATA: DISCORD_TOKEN bulunamadı!")
