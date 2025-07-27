# Rise Above Records Stock Monitor

A Python tool that monitors vinyl record stock on Rise Above Records and sends Discord alerts for restocks and new variants.

## Features

- **Restock Alerts**: Get notified when out-of-stock vinyl comes back in stock
- **New Variant Detection**: Alerts for newly added vinyl variants (colors, limited editions)
- **Discord Integration**: Rich embedded notifications with product details
- **Markdown Reports**: Generate readable stock status reports
- **Test Mode**: Cache HTML files for faster development/testing
- **Production Mode**: Live monitoring with polite request delays

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Discord webhook**:
   Create `.env` file with your Discord webhook URL:
   ```
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-webhook-url
   ```

3. **Test Discord integration**:
   ```bash
   python app/test_discord.py
   ```

## Usage

### Basic Usage
```bash
# Test mode (uses cached HTML)
python app/rise_above_monitor.py

# Production mode (live monitoring)
python app/rise_above_monitor.py production
```

### Custom Configuration
```python
from rise_above_monitor import RiseAboveMonitor

# Custom data file and HTML directory
monitor = RiseAboveMonitor(data_file="my_data.json", html_dir="cache")

# Add your artist URLs
artist_urls = {
    "https://riseaboverecords.com/product-category/artist-name/": "Artist Name"
}

monitor.run(artist_urls, mode='production')
```

## Files Generated

- `data/rise_above_stock.json` - Persistent stock tracking data
- `data/rise_above_report.md` - Human-readable stock status report
- `html/` - Cached HTML files (test mode only)

## Discord Notifications

- 🔔 **Green alerts**: Vinyl restocks (out-of-stock → in-stock)
- ⚠️ **Orange alerts**: Items going out of stock (in-stock → out-of-stock)
- 🆕 **Blue alerts**: New vinyl variants detected

## Automation

Set up daily monitoring with cron:
```bash
0 9 * * * cd /path/to/project && python app/rise_above_monitor.py production
```

## Configuration

Edit `artist_urls` in `rise_above_monitor.py` to monitor different artists:
```python
artist_urls = {
    "https://riseaboverecords.com/product-category/electric-wizard-2/": "Electric Wizard",
    "https://riseaboverecords.com/product-category/uncle-acid-and-the-deadbeats-3/": "Uncle Acid and the Deadbeats",
}
```

## Notes

- Only monitors vinyl records (CDs are filtered out)
- Includes 2-5 second delays between requests to be respectful
- No alerts sent on first run (prevents spam when setting up)
- Tracks price changes and stock status over time
- Generates unique product keys for variant tracking