import discord
from discord.ext import commands
import datetime
import os

# Bot Niyetleri (Intents)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Minimum hesap yaşı (Gün olarak)
MIN_ACCOUNT_AGE_DAYS = 15

@bot.event
async def on_ready():
    print(f"🇹🇷 {bot.user.name} EGM Guard Modülleri ve Komutlar Aktif Edildi!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="T.C. Kamu Güvenliği | EGM Guard"))

# 🛡️ EGM GUARD - HESAP YAŞI KONTROLÜ VE OTOMATİK KICK
@bot.event
async def on_member_join(member):
    now = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now - member.created_at).days

    if account_age < MIN_ACCOUNT_AGE_DAYS:
        # DM Mesajı İçeriği
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
            # DM Gönder
            await member.send(egm_dm_message)
        except discord.Forbidden:
            pass
        
        # Sunucudan At
        try:
            await member.kick(reason=f"EGM Guard: Hesap yaşı 15 günden küçük ({account_age} gün).")
        except discord.Forbidden:
            print(f"⚠️ HATA: {member.name} atılamadı. Botun rolünün üstte olduğundan emin olun.")
    else:
        # Hesap yaşı uygunsa Otomatik "Kayıtsız" rolü ver
        kayitsiz_rol = discord.utils.get(member.guild.roles, name="Kayıtsız")
        if kayitsiz_rol:
            await member.add_roles(kayitsiz_rol)

# 🤬 KÜFÜR VE REKLAM ENGELLEME FİLTRESİ
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

# BOTU ÇALIŞTIRMA
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token.strip())
else:
    print("❌ HATA: DISCORD_TOKEN bulunamadı!")
    
