import os
import time
import tempfile
import traceback

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from openai import OpenAI
import speech_recognition as sr
from pydub import AudioSegment

# ================================
# 🔐 CONFIGURATION
# ================================
BOT_TOKEN = os.getenv("BOT_TOKEN")         # Set in your .env file
GROQ_API_KEY = os.getenv("GROQ_API_KEY")   # Set in your .env file

if not BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("BOT_TOKEN and GROQ_API_KEY must be set as environment variables.")

# Primary + fallback models (Groq)
MODEL_PRIMARY = "llama-3.3-70b-versatile"
MODEL_FALLBACK = "llama-3.1-8b-instant"                      # faster, good fallback

# OpenAI-compatible client, pointing to Groq
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ================================
# 🧠 LLM CALL WITH RETRIES/DIAGNOSTICS
# ================================
def _chat_completion(messages, model, timeout=30):
    """
    Single chat completion call with explicit timeout.
    Returns the reply string or raises the original exception.
    """
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=timeout,  # seconds
    )
    return resp.choices[0].message.content

async def generate_gpt_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    print(f"📨 Text received: {user_input}")

    messages = [
        {"role": "system", "content": "You are a concise, helpful assistant."},
        {"role": "user", "content": user_input}
    ]

    # Retry policy
    attempts = [
        (MODEL_PRIMARY, 0),     # try primary immediately
        (MODEL_PRIMARY, 1),     # retry primary after 1s
        (MODEL_FALLBACK, 2),    # fallback after 2s
    ]

    last_err_detail = None

    for model_name, sleep_s in attempts:
        if sleep_s:
            time.sleep(sleep_s)

        try:
            reply = _chat_completion(messages, model=model_name, timeout=30)
            print(f"✅ LLM reply via {model_name}")
            await update.message.reply_text(reply)
            return
        except Exception as e:
            # Gather as much error info as possible
            status = getattr(e, "status_code", None)
            body = None
            try:
                # Some SDK versions expose response.json(); others store on 'response'
                if hasattr(e, "response") and hasattr(e.response, "json"):
                    body = e.response.json()
                elif hasattr(e, "response") and hasattr(e.response, "text"):
                    body = e.response.text
            except Exception:
                pass

            last_err_detail = f"Model={model_name}, status={status}, err={repr(e)}, body={body}"
            print(f"❌ LLM error: {last_err_detail}")
            traceback.print_exc()

    # If all attempts failed
    await update.message.reply_text("❌ Error fetching AI response (after retries). Please try again.")
    # Optional: also send a short diagnostic to you only (e.g., if you add an admin chat_id)

# ================================
# 🗣️ HANDLE TEXT MESSAGES
# ================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if user_input and user_input.strip():
        await generate_gpt_response(update, context, user_input.strip())
    else:
        await update.message.reply_text("⚠️ Please send some text.")

# ================================
# 🔊 HANDLE VOICE MESSAGES
# ================================
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.id
    print(f"🔊 Received voice message from user {user}")

    voice = await update.message.voice.get_file()
    voice_path_ogg = tempfile.mktemp(suffix=".ogg")
    await voice.download_to_drive(voice_path_ogg)
    print(f"📥 Downloaded voice file: {voice_path_ogg}")

    wav_path = None
    try:
        wav_path = voice_path_ogg.replace(".ogg", ".wav")
        # Convert OGG(OPUS) -> WAV
        AudioSegment.from_file(voice_path_ogg, format="ogg").export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)

        print(f"🗣️ Transcribed Text: {text}")
        if text and text.strip():
            await generate_gpt_response(update, context, text.strip())
        else:
            await update.message.reply_text("⚠️ I couldn't understand the voice message.")

    except Exception as e:
        print(f"❌ Transcription error: {e}")
        traceback.print_exc()
        await update.message.reply_text("❌ Error processing voice message.")
    finally:
        for f in (voice_path_ogg, wav_path):
            if f:
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass

# ================================
# ▶️ START COMMAND
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Dang's Voice Chat Bot (Groq)*!\n\n"
        "🗣️ Send me a voice note or a text question, and I'll answer using AI.\n"
        "ℹ️ Tip: If responses fail occasionally, I'm set to retry and use a fallback model.",
        parse_mode="Markdown"
    )

# ================================
# 🚀 MAIN FUNCTION
# ================================
if __name__ == "__main__":
    print("🤖 GPT Bot is running.. (Groq)")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()
