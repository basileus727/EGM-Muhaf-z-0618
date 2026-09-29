import os
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "T.C. Devlet Botu 7/24 Aktif!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ BAŞARILI: {len(synced)} adet komut Discord'a yüklendi!")
        print(f"🤖 {bot.user.name} göreve hazır!")
    except Exception as e:
        print(f"❌ Komutlar yüklenirken hata oluştu: {e}")

@bot.tree.command(name="kayit", description="T.C. Vatandaşlık kaydı oluşturur.")
async def kayit(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send("🇹🇷 T.C. Nüfus kütüğü kaydınız başarıyla tamamlanmıştır!")

@bot.tree.command(name="duyuru", description="Resmî Gazete duyurusu yayınlar.")
async def duyuru(interaction: discord.Interaction, mesaj: str):
    await interaction.response.defer()
    await interaction.followup.send(f"📢 **T.C. RESMÎ GAZETE DUYURUSU:**\n\n{mesaj}")

keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))
