import requests
import json
import os
import time
import random
import logging
import re
import hashlib
import fcntl
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from discord_notifier import DiscordNotifier

class RiseAboveMonitor:
    def __init__(self, root_dir, data_file="rise_above_stock.json"):
        print(f"Current file path: {__file__}")

        self.root_dir = root_dir
        self.data_dir = os.path.join(self.root_dir, "data")
        self.html_dir = os.path.join(self.root_dir, "html")                        
        self.data_file = os.path.join(self.data_dir, data_file)
        self.alert_history_file = os.path.join(self.data_dir, "alert_history.json")
        
        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)  # Only show warnings and errors in tests
            formatter = logging.Formatter('%(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.WARNING)
        
        self.discord = DiscordNotifier()
        self.stock_data = self.load_stock_data()
        self.alert_history = self.load_alert_history()
        self.current_products = {}
        # Treat as first run only when there are genuinely no previously saved products.
        # Checking the file path after load_stock_data() is unreliable because that method
        # may rename/backup a corrupted file, and an empty products dict (from a bad file)
        # would otherwise cause every product to fire as a "new variant" alert.
        self.stock_file_exists = bool(self.stock_data.get("products"))
        self.stock_changed = False
        self.fetch_errors = 0  # count of failed page fetches this run
    
    def normalize_text(self, text):
        """Normalize text for consistent product key generation"""
        if not text:
            return ""
        
        # Remove HTML entities and extra whitespace
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Replace problematic characters for file system compatibility
        text = re.sub(r'[<>:"/\\|?*]', '_', text)
        text = re.sub(r'[^\w\s\-_]', '', text)
        
        # Normalize case and spacing - replace spaces with single underscores
        text = re.sub(r'\s+', '_', text.strip())
        # Remove multiple consecutive underscores
        text = re.sub(r'_+', '_', text)
        # Remove leading/trailing underscores
        text = text.strip('_')
        
        return text
    
    def generate_product_key(self, artist_name, album_name, variant_type):
        """Generate a consistent, unique product key"""
        normalized_artist = self.normalize_text(artist_name)
        normalized_album = self.normalize_text(album_name)
        normalized_variant = self.normalize_text(variant_type)
        
        product_key = f"{normalized_artist}_{normalized_album}_{normalized_variant}"
        
        # Validate key uniqueness within current run
        if product_key in self.current_products:
            self.logger.warning(f"Duplicate product key detected: {product_key}")
        
        return product_key
    
    def ensure_boolean(self, value):
        """Ensure stock status is a proper boolean type"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(value, (int, float)):
            return bool(value)
        else:
            self.logger.warning(f"Invalid stock status type: {type(value)}, value: {value}")
            return False
    
    def load_alert_history(self):
        """Load recent alert history for duplicate prevention"""
        if os.path.exists(self.alert_history_file):
            try:
                with open(self.alert_history_file, "r") as f:
                    history = json.load(f)
                    # Clean up old alerts (older than 24 hours)
                    cutoff = datetime.now() - timedelta(hours=24)
                    cleaned_history = {}
                    for alert_key, timestamp_str in history.items():
                        try:
                            alert_time = datetime.fromisoformat(timestamp_str)
                            if alert_time > cutoff:
                                cleaned_history[alert_key] = timestamp_str
                        except ValueError:
                            continue
                    return cleaned_history
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Error loading alert history: {e}")
        return {}
    
    def save_alert_history(self):
        """Save alert history for duplicate prevention"""
        try:
            os.makedirs(os.path.dirname(self.alert_history_file), exist_ok=True)
            with open(self.alert_history_file, "w") as f:
                json.dump(self.alert_history, f, indent=2)
        except IOError as e:
            self.logger.error(f"Error saving alert history: {e}")
    
    def should_send_alert(self, alert_type, product_key):
        """Check if alert should be sent (duplicate prevention)"""
        alert_key = f"{alert_type}_{product_key}"
        
        if alert_key in self.alert_history:
            last_sent = datetime.fromisoformat(self.alert_history[alert_key])
            # Prevent duplicate alerts within 1 hour
            if datetime.now() - last_sent < timedelta(hours=1):
                self.logger.info(f"Suppressing duplicate alert: {alert_key}")
                return False
        
        # Record this alert
        self.alert_history[alert_key] = datetime.now().isoformat()
        return True
    
    def get_page(self, url):
        time.sleep(random.uniform(2, 5))
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.fetch_errors += 1
            self.logger.error(f"Error fetching {url}: {e}")
            print(f"Error fetching {url}: {e}")
            return None
    
    def save_html(self, content, filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
    
    def load_html(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    
    def load_stock_data(self):
        """Load stock data with validation and error handling"""
        if not os.path.exists(self.data_file):
            return {"last_updated": None, "products": {}}
        
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                
                # Validate structure
                if not isinstance(data, dict) or "products" not in data:
                    self.logger.warning("Invalid stock data structure, initializing clean state")
                    return {"last_updated": None, "products": {}}
                
                # Normalize stock status to boolean
                for product_key, product_data in data["products"].items():
                    if "in_stock" in product_data:
                        product_data["in_stock"] = self.ensure_boolean(product_data["in_stock"])
                
                self.logger.info(f"Loaded stock data for {len(data['products'])} products")
                return data
                
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading stock data: {e}")
            # Create backup of corrupted file
            backup_file = f"{self.data_file}.backup.{int(datetime.now().timestamp())}"
            try:
                os.rename(self.data_file, backup_file)
                self.logger.info(f"Corrupted file backed up to: {backup_file}")
            except OSError:
                pass
            return {"last_updated": None, "products": {}}
    
    def save_stock_data(self):
        """Save stock data with atomic operations and error handling"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        last_updated = datetime.now().isoformat() if self.stock_changed else self.stock_data.get("last_updated")
        data_to_save = {
            "products": self.current_products, 
            "last_updated": last_updated,
            "checksum": self.calculate_data_checksum(self.current_products)
        }
        
        # Atomic save using temporary file
        temp_file = f"{self.data_file}.tmp"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                with open(temp_file, "w") as f:
                    # Use file locking to prevent concurrent access
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(data_to_save, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                
                # Atomic move
                os.rename(temp_file, self.data_file)
                self.logger.info(f"Stock data saved successfully ({len(self.current_products)} products)")
                break
                
            except (IOError, OSError) as e:
                self.logger.error(f"Error saving stock data (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.logger.error("Failed to save stock data after all retries")
        
        # Clean up temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
    
    def calculate_data_checksum(self, data):
        """Calculate checksum for data integrity verification"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def verify_data_integrity(self):
        """Verify the integrity of loaded stock data"""
        if "checksum" not in self.stock_data:
            self.logger.info("No checksum found in stock data (legacy file)")
            return True
        
        expected_checksum = self.stock_data["checksum"]
        actual_checksum = self.calculate_data_checksum(self.stock_data["products"])
        
        if expected_checksum != actual_checksum:
            self.logger.error("Data integrity check failed - checksum mismatch")
            return False
        
        return True
    
    def process_artist(self, url, artist_name, mode='test'):
        artist_key = self.normalize_text(artist_name)
        filename = f"{self.html_dir}/{artist_key}.html"
        
        if mode == 'test' and not os.path.exists(filename):
            html = self.get_page(url)
            if html:
                self.save_html(html, filename)
        
        html = self.load_html(filename) if mode == 'test' else self.get_page(url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        product_links = soup.find_all('a', class_='woocommerce-LoopProduct-link')
        product_titles = soup.find_all('h2', class_='woocommerce-loop-product__title')
        
        self.logger.info(f"Processing artist: {artist_name}")
        print(f"\n=== {artist_name} ===")
        for link, title in zip(product_links, product_titles):
            album_name = self.normalize_text(title.get_text().strip())
            self.process_product(link.get('href'), album_name, artist_name, mode)
    
    def process_product(self, url, album_name, artist_name, mode):
        artist_key = self.normalize_text(artist_name)
        album_key = self.normalize_text(album_name)
        filename = f"{self.html_dir}/{artist_key}/{album_key}.html"
        
        if mode == 'test' and not os.path.exists(filename):
            html = self.get_page(url)
            if html:
                self.save_html(html, filename)
        
        html = self.load_html(filename) if mode == 'test' else self.get_page(url)
        if not html:
            return
        
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form', class_='variations_form')
        if not form or not form.get('data-product_variations'):
            return
        
        try:
            variations = json.loads(form.get('data-product_variations'))
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing product variations for {url}: {e}")
            return
        
        print(f"Album: {album_name.replace('_', ' ')}")
        
        for variation in variations:
            try:
                variant_type = self.get_variant_type(soup, variation)
                if not variant_type or 'CD' in variant_type or 'cd' in variant_type.lower():
                    continue
                
                # Validate required fields
                if not variation.get('display_price') or 'is_in_stock' not in variation:
                    self.logger.warning(f"Missing required fields in variation: {variation}")
                    continue
                
                product_key = self.generate_product_key(artist_name, album_name, variant_type)
                
                product_data = {
                    "artist": artist_name,
                    "album": album_name.replace('_', ' '),
                    "variant": self.normalize_text(variant_type),
                    "price": f"£{variation['display_price']}",
                    "in_stock": self.ensure_boolean(variation['is_in_stock']),
                    "url": url
                }
                
                self.check_changes(product_key, product_data)
                self.current_products[product_key] = product_data
                
                status = "In stock" if product_data["in_stock"] else "Out of stock"
                print(f"  {variant_type}: {product_data['price']} - {status}")
                
            except Exception as e:
                self.logger.error(f"Error processing variation: {e}")
                continue
        
        print("-" * 40)
    
    def get_variant_type(self, soup, variation):
        """Extract and normalize variant type from product variation"""
        try:
            attr_key = list(variation['attributes'].keys())[0]
            variant_value = variation['attributes'][attr_key]
            option = soup.find('option', {'value': variant_value})
            
            if option:
                variant_text = option.get_text().strip()
                # Remove HTML artifacts and normalize
                variant_text = re.sub(r'&[a-zA-Z0-9#]+;', '', variant_text)
                variant_text = re.sub(r'\s+', ' ', variant_text.strip())
                return variant_text
            else:
                return str(variant_value).strip()
                
        except (KeyError, IndexError, AttributeError) as e:
            self.logger.error(f"Error extracting variant type: {e}")
            return None
    
    def check_changes(self, product_key, product_data):
        """Enhanced change detection with type safety and duplicate prevention"""
        if not self.stock_file_exists:
            # First run — send new variant alert for everything to verify Discord is working
            if self.should_send_alert("new_variant", product_key):
                try:
                    self.discord.send_new_variant_alert(
                        artist=product_data['artist'],
                        album=product_data['album'],
                        variant=product_data['variant'],
                        price=product_data['price'],
                        url=product_data['url'],
                        in_stock=product_data['in_stock']
                    )
                except Exception as e:
                    self.logger.error(f"Error sending new variant alert: {e}")
            product_data["last_changed"] = datetime.now().isoformat()
            self.stock_changed = True
            return
            
        if product_key in self.stock_data["products"]:
            old_product = self.stock_data["products"][product_key]
            old_stock = self.ensure_boolean(old_product.get("in_stock", False))
            new_stock = self.ensure_boolean(product_data["in_stock"])
            
            # Log comparison for debugging
            self.logger.debug(f"Stock comparison for {product_key}: {old_stock} -> {new_stock}")
            
            # Only trigger alerts for actual status changes
            if old_stock != new_stock:
                if not old_stock and new_stock:
                    # Restock alert
                    if self.should_send_alert("restock", product_key):
                        self.logger.warning(f"RESTOCK: {product_data['artist']} - {product_data['album']} - {product_data['variant']}")
                        print(f"🔔 RESTOCK: {product_data['album']} - {product_data['variant']}")
                        try:
                            self.discord.send_restock_alert(**{k: product_data[k] for k in ['artist', 'album', 'variant', 'price', 'url']})
                        except Exception as e:
                            self.logger.error(f"Error sending restock alert: {e}")
                        self.stock_changed = True
                        
                elif old_stock and not new_stock:
                    # Out of stock alert
                    if self.should_send_alert("out_of_stock", product_key):
                        self.logger.warning(f"OUT OF STOCK: {product_data['artist']} - {product_data['album']} - {product_data['variant']}")
                        print(f"⚠️ OUT OF STOCK: {product_data['album']} - {product_data['variant']}")
                        try:
                            self.discord.send_out_of_stock_alert(**{k: product_data[k] for k in ['artist', 'album', 'variant', 'price', 'url']})
                        except Exception as e:
                            self.logger.error(f"Error sending out of stock alert: {e}")
                        self.stock_changed = True
                        
                product_data["last_changed"] = datetime.now().isoformat()
            else:
                # No change - preserve last_changed timestamp
                product_data["last_changed"] = old_product.get("last_changed")
                
        else:
            # New variant detected
            if self.should_send_alert("new_variant", product_key):
                self.logger.info(f"NEW VARIANT: {product_data['artist']} - {product_data['album']} - {product_data['variant']} - {'In Stock' if product_data['in_stock'] else 'Out of Stock'}")
                print(f"🆕 NEW VARIANT: {product_data['album']} - {product_data['variant']}")
                try:
                    self.discord.send_new_variant_alert(
                        artist=product_data['artist'],
                        album=product_data['album'], 
                        variant=product_data['variant'],
                        price=product_data['price'],
                        url=product_data['url'],
                        in_stock=product_data['in_stock']
                    )
                except Exception as e:
                    self.logger.error(f"Error sending new variant alert: {e}")
                    
            product_data["last_changed"] = datetime.now().isoformat()
            self.stock_changed = True
    
    def generate_report(self):
        artists = {}
        for product in self.current_products.values():
            artist = product["artist"]
            if artist not in artists:
                artists[artist] = []
            artists[artist].append(product)
        
        last_stock_change = self.stock_data.get("last_updated", "Never")
        
        os.makedirs(self.data_dir,  exist_ok=True)
        report_file = os.path.join(self.data_dir, "rise_above_report.md")
        with open(report_file, "w") as f:
            f.write("# Rise Above Records Stock Report\n\n")
            f.write(f"**Last Check:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Last Stock Change:** {last_stock_change}\n\n")
            
            for artist, items in artists.items():
                f.write(f"## {artist}\n\n")
                f.write("| Album | Variant | Price | Stock Status |\n")
                f.write("|-------|---------|-------|--------------|\n")
                
                for item in sorted(items, key=lambda x: (x["album"], x["variant"])):
                    status = "✅ In Stock" if item["in_stock"] else "❌ Out of Stock"
                    f.write(f"| {item['album']} | {item['variant']} | {item['price']} | {status} |\n")
                f.write("\n")
    
    def run(self, root_dir, artist_urls, mode='test'):
        """Main execution method with enhanced error handling and validation"""
        self.logger.info(f"Starting stock monitoring in {mode} mode")
        
        # Verify data integrity
        if not self.verify_data_integrity():
            self.logger.warning("Data integrity check failed, but continuing with monitoring")
        
        # Validate reasonable product count
        previous_count = len(self.stock_data.get("products", {}))
        
        try:
            for url, artist_name in artist_urls.items():
                self.process_artist(url, artist_name, mode)
            
            current_count = len(self.current_products)
            
            # Guard: if fetch errors caused a near-total wipeout, preserve the
            # existing data file rather than overwriting it with an empty/partial result.
            if previous_count > 0 and current_count < previous_count * 0.5:
                self.logger.error(
                    f"Significant data loss detected: {previous_count} -> {current_count} products "
                    f"({self.fetch_errors} fetch error(s)). Skipping save to protect existing data."
                )
                print(
                    f"\n⚠️  Fetch errors caused data loss ({previous_count} -> {current_count} products). "
                    f"Existing data file preserved."
                )
                return

            self.save_stock_data()
            self.save_alert_history()
            self.generate_report()
            
            self.logger.info(f"Stock monitoring completed: {current_count} products tracked")
            print(f"\nStock data updated: {current_count} products tracked")
            
        except Exception as e:
            self.logger.error(f"Critical error during monitoring: {e}")
            raise

if __name__ == "__main__":
    import sys
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(current_dir, "logs")
    
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'rise_above_monitor.log'), mode='w'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)

    mode = sys.argv[1] if len(sys.argv) > 1 else 'test'

    if '--no-delay' not in sys.argv:
        delay = random.uniform(120, 300)
        start_time = datetime.now().timestamp() + delay
        start_time_str = datetime.fromtimestamp(start_time).strftime('%H:%M:%S')
        logger.info(f"Script will start in {delay/60:.1f} minutes at {start_time_str}")
        print(f"Starting in {delay/60:.1f} minutes at {start_time_str}...")
        time.sleep(delay)

    artist_urls = {
        "https://riseaboverecords.com/product-category/electric-wizard-2/": "Electric Wizard",
        "https://riseaboverecords.com/product-category/uncle-acid-and-the-deadbeats-3/": "Uncle Acid and the Deadbeats"
    }

    monitor = RiseAboveMonitor(current_dir)
    monitor.run(current_dir, artist_urls, mode)