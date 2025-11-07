import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from data_fetch import get_game_json, get_game_id
from human_format import ToHumanFormat


# Load authorized user ID
def load_authorized_id():
    try:
        with open('secrets/my_telegram_id.txt', 'r') as f:
            return int(f.read().strip())
    except Exception as e:
        print(f"ERROR: Failed to load authorized user ID: {e}", file=sys.stderr)
        sys.exit(1)


# Load bot token
def load_bot_token():
    try:
        with open('secrets/bot_token.txt', 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"ERROR: Failed to load bot token: {e}", file=sys.stderr)
        sys.exit(1)


AUTHORIZED_USER_ID = load_authorized_id()
BOT_TOKEN = load_bot_token()


def is_authorized(update: Update) -> bool:
    """Check if the user is authorized to use the bot"""
    return update.effective_user.id == AUTHORIZED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command"""
    if not is_authorized(update):
        return
    
    await update.message.reply_text(
        "Send me a PokerStars hand replay URL and I'll convert it to human-readable format.\n\n"
        "Example: https://www.pokerstarsreplayer.com/hands/<id>/"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages containing URLs"""
    if not is_authorized(update):
        return
    
    url = update.message.text.strip()
    
    # Basic validation
    if not url.startswith("http"):
        await update.message.reply_text("Please send a valid URL starting with http:// or https://")
        return
    
    try:
        # Fetch and parse the game data
        game_data = get_game_json(url)
        
        # Convert to human-readable format
        converter = ToHumanFormat(game_data)
        human_readable = converter.human_readable_lines()
        
        # AI request
        ai_request = "Analyse my play in the following poker hand\n\n"
        human_readable = ai_request + human_readable
        # Send the result
        await update.message.reply_text(f"```\n{human_readable}\n```", parse_mode='Markdown')
    
    except Exception as e:
        print(f"ERROR: Failed to process URL {url}: {e}", file=sys.stderr)
        await update.message.reply_text(
            "Sorry, I couldn't process this URL. Please make sure it's a valid PokerStars hand replay URL."
        )


def main():
    """Start the bot"""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("Bot started successfully")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
