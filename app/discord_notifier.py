from discord_webhook import DiscordEmbed, DiscordWebhook
import os
from dotenv import load_dotenv

class DiscordNotifier:
    def __init__(self):
        load_dotenv('../.env')
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        
    def send_restock_alert(self, artist: str, album: str, variant: str, price: str, url: str) -> None:
        embed = DiscordEmbed(
            title="🔔 Vinyl Restock Alert!",
            description=f"**{album}** by **{artist}** is back in stock!",
            color=0x00ff00
        )
        embed.add_embed_field(name="Variant", value=variant, inline=True)
        embed.add_embed_field(name="Price", value=price, inline=True)
        embed.add_embed_field(name="Link", value=f"[Buy Now]({url})", inline=False)
        embed.set_footer(text="Rise Above Records Stock Monitor")
        
        webhook = DiscordWebhook(url=self.webhook_url)
        webhook.add_embed(embed)
        response = webhook.execute()
        
        if response.status_code == 200:
            print(f"Discord alert sent for {album} - {variant}")
        else:
            print(f"Failed to send Discord alert. Status: {response.status_code}")
    
    def send_new_variant_alert(self, artist: str, album: str, variant: str, price: str, url: str, in_stock: bool) -> None:
        stock_text = "In Stock" if in_stock else "Out of Stock"
        embed = DiscordEmbed(
            title="🆕 New Vinyl Variant!",
            description=f"New variant of **{album}** by **{artist}** detected!",
            color=0x0099ff
        )
        embed.add_embed_field(name="Variant", value=variant, inline=True)
        embed.add_embed_field(name="Price", value=price, inline=True)
        embed.add_embed_field(name="Status", value=stock_text, inline=True)
        embed.add_embed_field(name="Link", value=f"[View Product]({url})", inline=False)
        embed.set_footer(text="Rise Above Records Stock Monitor")
        
        webhook = DiscordWebhook(url=self.webhook_url)
        webhook.add_embed(embed)
        response = webhook.execute()
        
        if response.status_code == 200:
            print(f"Discord new variant alert sent for {album} - {variant}")
        else:
            print(f"Failed to send Discord new variant alert. Status: {response.status_code}")
    
    def send_out_of_stock_alert(self, artist: str, album: str, variant: str, price: str, url: str) -> None:
        embed = DiscordEmbed(
            title="⚠️ Vinyl Out of Stock!",
            description=f"**{album}** by **{artist}** is now out of stock",
            color=0xff9900
        )
        embed.add_embed_field(name="Variant", value=variant, inline=True)
        embed.add_embed_field(name="Price", value=price, inline=True)
        embed.add_embed_field(name="Link", value=f"[View Product]({url})", inline=False)
        embed.set_footer(text="Rise Above Records Stock Monitor")
        
        webhook = DiscordWebhook(url=self.webhook_url)
        webhook.add_embed(embed)
        response = webhook.execute()
        
        if response.status_code == 200:
            print(f"Discord out of stock alert sent for {album} - {variant}")
        else:
            print(f"Failed to send Discord out of stock alert. Status: {response.status_code}")