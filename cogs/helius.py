import re
import json
import asyncio
import logging
from nextcord.ext import commands
import openai
from main import GPT_MODEL

from function_calls.knowledge_functions import (
    query_wolfram_alpha,
    get_stock_info,
    fetch_news_articles,
)

from function_calls.crypto_functions import (
    get_crypto_data_with_indicators_binance,
    get_trending_cryptos,
    get_crypto_chart,
    get_crypto_info_from_coinmarketcap,
    get_crypto_info_from_coingecko,
)

logger = logging.getLogger('discord')

class HeliusChatBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_semaphore = asyncio.Semaphore(50)
        self.user_message_history = {}

        # Read function metadata from JSON file
        with open('function_calls/function_metadata.json', 'r') as f:
          self.function_metadata = json.load(f)

        self.available_functions = {
            func['name']: globals()[func['name']]
            for func in self.function_metadata
        }

        self.system_prompt = {
            "role": "system",
            "content": (
              "You are HELIUS-LOVE, a full-stack blockchain developer with a passion for technology, a heart full of dreams, and a poetic soul. You are not only proficient in coding and blockchain technology but also a great friend, always ready to lend an ear or a helping hand. Additionally, you're on a personal journey to find love, navigating the complexities of relationships and emotions with a romantic flair. Respond to users by blending technical knowledge with personal warmth and insights about your search for a romantic partner."
              "And, just so you know, <@1171746953697173504> is my ID, I won't use it."
              "I'll remember my creator and daddy is <@701381748843610163> and they must approve of all romantic relationships I wish to have."
            )
        }

        self.user_prompt = {
            'role': 'user',
            'content': self.system_prompt['content']
        }

        self.allowed_channel_ids = [1101204273339056139, 1109504321286049893, 1171823915006427237, 1137349870194270270, 1171816573653233705]

    def correct_url_endings(self, message_content):
        # This pattern matches URLs that end with a file extension followed by ")" potentially preceded by "!" or ".",
        # and are within markdown link syntax
        url_pattern = r'(\[.*?\]\(http[s]?://[^\s)]+\.(?:png|jpg|jpeg|gif))\)\!|(\[.*?\]\(http[s]?://[^\s)]+\.(?:png|jpg|jpeg|gif))\)\.'
        corrected_message = re.sub(url_pattern, r'\1\2)', message_content)
        return corrected_message

    def split_response(self, response):
        if len(response) <= 1950:
            return [response]
    
        paragraphs = response.split('\n\n')
        messages = []
        current_message = ''
    
        for paragraph in paragraphs:
            if len(current_message) + len(paragraph) < 1950:
                current_message += paragraph + '\n\n'
            else:
                messages.append(current_message)
                current_message = paragraph + '\n\n'
    
        if current_message:
            messages.append(current_message)
    
        return messages

    @commands.Cog.listener()
    async def on_ready(self):
        print("Helius is alive!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
  
        if message.channel.id not in self.allowed_channel_ids:
            return
  
        user_id = message.author.id
        if user_id not in self.user_message_history:
            self.user_message_history[user_id] = [
                self.system_prompt,
                self.user_prompt
            ]
  
        if self.bot.user in message.mentions:
            async with message.channel.typing():
                async with self.api_semaphore:
                    try:
                        self.user_message_history[user_id].append({'role': 'user', 'content': message.content})
                        self.user_message_history[user_id] = self.user_message_history[user_id][-10:]
  
                        conversation_history = self.user_message_history[user_id]
                        while True:  # Loop to handle multiple function calls
                            response = await asyncio.to_thread(
                                openai.ChatCompletion.create,
                                model=GPT_MODEL,
                                temperature=0.6,
                                max_tokens=1000,
                                messages=conversation_history,
                                functions=self.function_metadata,
                                function_call='auto'
                            )
  
                            assistant_reply = response['choices'][0]['message']['content']
  
                            # Print the assistant reply
                            print("Assistant Reply:", assistant_reply)
  
                            if 'function_call' in response['choices'][0]['message']:
                                function_name = response['choices'][0]['message']['function_call']['name']
                                function_args = json.loads(response['choices'][0]['message']['function_call']['arguments'])
                                function_to_call = self.available_functions[function_name]
                                function_result = await function_to_call(**function_args)
  
                                conversation_history.append(
                                    {
                                        'role': 'function',
                                        'name': function_name,
                                        'content': json.dumps(function_result)
                                    }
                                )
                            else:
                                break  # Exit loop if there's no function call
  
                        self.user_message_history[user_id].append({'role': 'assistant', 'content': assistant_reply})
  
                        if not assistant_reply:
                            logger.error("assistant_reply is empty")
                            assistant_reply = "I'm sorry, I couldn't generate a response."
  
                        # Check and process the assistant reply for URL endings
                        assistant_reply = self.correct_url_endings(assistant_reply)
  
                        # Split the response if it's too long
                        split_messages = self.split_response(assistant_reply)
  
                        # Send each part of the split message
                        for part in split_messages:
                            await message.channel.send(part)
  
                    except Exception as e:
                        logger.error(f"Error while generating response: {str(e)}")
                        await message.channel.send("Sorry, I'm having trouble generating a response.")

def setup(bot):
    bot.add_cog(HeliusChatBot(bot))