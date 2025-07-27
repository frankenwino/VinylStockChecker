from discord_notifier import DiscordNotifier

# Test Discord notifications
discord = DiscordNotifier()

# Test restock alert
discord.send_restock_alert(
    artist="Electric Wizard",
    album="Dopethrone",
    variant="LP Black",
    price="£22.00",
    url="https://riseaboverecords.com/product/dopethrone-2/"
)

# Test new variant alert
discord.send_new_variant_alert(
    artist="Electric Wizard",
    album="Dopethrone",
    variant="LP Limited Red",
    price="£25.00",
    url="https://riseaboverecords.com/product/dopethrone-2/",
    in_stock=True
)

print("Test notifications sent!")