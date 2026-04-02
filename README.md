# Dang GPT Bot

This bot handles incoming text and voice messages on Telegram, transcribes voice using Google Speech Recognition, and replies using the Groq LLM API (`llama-3.3-70b-versatile`).


## Setup Instructions (Local)

1. Clone the repo:
   ```git clone https://github.com/hdang2000/dang-gpt-bot.git```
   ```cd dang-gpt-bot```

2. Create virtual environment:
```python3 -m venv venv```
```source venv/bin/activate```

3. Install required libraries:
```pip install -r requirements.txt```

4. Set your environment variables:
```export BOT_TOKEN=your_telegram_bot_token_here```
```export GROQ_API_KEY=your_groq_api_key_here```

5. Run the bot:
```python gpt_bot.py```
