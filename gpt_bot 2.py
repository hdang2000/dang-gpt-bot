import os
import logging
import tempfile
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI
import speech_recognition as sr
from pydub import AudioSegment

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
client = OpenAI(api_key=OPENAI_API_KEY)

# --- ENABLE LOGGING ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONVERSATION MEMORY ---
conversation_history = {}

# --- COMMAND: /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! I'm your GPT-3.5 assistant. Send a message or voice note!")

# --- TEXT HANDLER ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text

    history = conversation_history.get(user_id, [])
    history.append({"role": "user", "content": user_input})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=history
        )
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        conversation_history[user_id] = history

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        await update.message.reply_text("❌ Something went wrong with OpenAI.")

# --- VOICE HANDLER ---
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tf:
        await file.download_to_drive(custom_path=tf.name)
        ogg_path = tf.name

    wav_path = ogg_path.replace(".ogg", ".wav")
    sound = AudioSegment.from_ogg(ogg_path)
    sound.export(wav_path, format="wav")

    r = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio = r.record(source)
        try:
            text = r.recognize_google(audio)
            update.message.text = text  # simulate a text message
            await handle_text(update, context)
        except sr.UnknownValueError:
            await update.message.reply_text("❌ Could not understand the audio.")
        except Exception as e:
            logger.error(f"Voice transcription error: {e}")
            await update.message.reply_text("❌ Error processing voice message.")

# --- MAIN APP ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("🤖 GPT Bot is running...")
    app.run_polling()
