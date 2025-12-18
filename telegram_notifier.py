import os
import requests
from datetime import datetime
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_telegram_message(message: str, parse_mode: str = 'HTML') -> bool:
    """Send a message via Telegram bot"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        return False
    
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        
        if not result.get('ok', False):
            return False
        
        return True
        
    except Exception:
        return False

def format_job_status(results: List[dict], overall_success: bool, duration: float) -> str:
    """Format job execution results for Telegram"""
    emoji = "✅" if overall_success else "❌"
    status = "SUCCESS" if overall_success else "FAILED"
    
    message = f"{emoji} <b>Trading Assistant Daily Job - {status}</b>\n\n"
    
    for result in results:
        script_emoji = "✅" if result['success'] else "❌"
        message += f"{script_emoji} <b>{result['script']}</b>\n"
        message += f"   Duration: {result['duration_seconds']:.1f}s\n"
        
        if not result['success']:
            message += f"   Exit Code: {result['exit_code']}\n"
            if result.get('error'):
                message += f"   Error: {result['error']}\n"
    
    message += f"\n<b>Total Duration:</b> {duration:.1f}s\n"
    message += f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message

if __name__ == "__main__":
    send_telegram_message("Test message from trading assistant")