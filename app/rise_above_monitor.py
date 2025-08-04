import requests
import json
import os
import time
import random
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from discord_notifier import DiscordNotifier

class RiseAboveMonitor:
    def __init__(self, root_dir, data_file="rise_above_stock.json"):
        print(f"Current file path: {__file__}")

        self.root_dir = root_dir
        self.data_dir = os.path.join(self.root_dir, "data")
        self.html_dir = os.path.join(self.root_dir, "html")                        
        self.data_file = os.path.join(self.data_dir, data_file)
        self.discord = DiscordNotifier()
        self.stock_data = self.load_stock_data()
        self.current_products = {}
        self.stock_file_exists = os.path.exists(data_file)
        self.stock_changed = False
        self.logger = logging.getLogger(__name__)
    
    def get_page(self, url):
        # time.sleep(random.uniform(2, 5))
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
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
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                return json.load(f)
        return {"last_updated": None, "products": {}}
    
    def save_stock_data(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        last_updated = datetime.now().isoformat() if self.stock_changed else self.stock_data.get("last_updated")
        with open(self.data_file, "w") as f:
            json.dump({"products": self.current_products, "last_updated": last_updated}, f, indent=2)
    
    def process_artist(self, url, artist_name, mode='test'):
        artist_key = artist_name.replace(' ', '_')
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
            album_name = title.get_text().strip().replace(' ', '_').replace('/', '_')
            self.process_product(link.get('href'), album_name, artist_name, mode)
    
    def process_product(self, url, album_name, artist_name, mode):
        artist_key = artist_name.replace(' ', '_')
        filename = f"{self.html_dir}/{artist_key}/{album_name}.html"
        
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
        
        variations = json.loads(form.get('data-product_variations'))
        print(f"Album: {album_name.replace('_', ' ')}")
        
        for variation in variations:
            variant_type = self.get_variant_type(soup, variation)
            if 'CD' in variant_type or 'cd' in variant_type.lower():
                continue
            
            product_key = f"{artist_name.replace(' ', '_')}_{album_name}_{variant_type}"
            product_data = {
                "artist": artist_name,
                "album": album_name.replace('_', ' '),
                "variant": variant_type,
                "price": f"£{variation['display_price']}",
                "in_stock": variation['is_in_stock'],
                "url": url
            }
            
            self.check_changes(product_key, product_data)
            self.current_products[product_key] = product_data
            
            status = "In stock" if product_data["in_stock"] else "Out of stock"
            print(f"  {variant_type}: {product_data['price']} - {status}")
        
        print("-" * 40)
    
    def get_variant_type(self, soup, variation):
        attr_key = list(variation['attributes'].keys())[0]
        variant_value = variation['attributes'][attr_key]
        option = soup.find('option', {'value': variant_value})
        return option.get_text().strip() if option else variant_value
    
    def check_changes(self, product_key, product_data):
        if not self.stock_file_exists:
            product_data["last_changed"] = datetime.now().isoformat()
            return
            
        if product_key in self.stock_data["products"]:
            old_stock = self.stock_data["products"][product_key]["in_stock"]
            if old_stock == False and product_data["in_stock"] is True:
                self.logger.warning(f"RESTOCK: {product_data['artist']} - {product_data['album']} - {product_data['variant']}")
                print(f"🔔 RESTOCK: {product_data['album']} - {product_data['variant']}")
                self.discord.send_restock_alert(**{k: product_data[k] for k in ['artist', 'album', 'variant', 'price', 'url']})
                self.stock_changed = True
            elif old_stock is True and product_data["in_stock"] == False:
                self.logger.warning(f"OUT OF STOCK: {product_data['artist']} - {product_data['album']} - {product_data['variant']}")
                print(f"⚠️ OUT OF STOCK: {product_data['album']} - {product_data['variant']}")
                self.discord.send_out_of_stock_alert(**{k: product_data[k] for k in ['artist', 'album', 'variant', 'price', 'url']})
                self.stock_changed = True
            product_data["last_changed"] = self.stock_data["products"][product_key].get("last_changed")
        else:
            self.logger.info(f"NEW VARIANT: {product_data['artist']} - {product_data['album']} - {product_data['variant']} - {'In Stock' if product_data['in_stock'] else 'Out of Stock'}")
            print(f"🆕 NEW VARIANT: {product_data['album']} - {product_data['variant']}")
            self.discord.send_new_variant_alert(**{k: product_data[k] for k in ['artist', 'album', 'variant', 'price', 'url']}, in_stock=product_data["in_stock"])
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
        self.logger.info(f"Starting stock monitoring in {mode} mode")
        for url, artist_name in artist_urls.items():
            self.process_artist(url, artist_name, mode)
        
        self.save_stock_data()
        self.generate_report()
        self.logger.info(f"Stock monitoring completed: {len(self.current_products)} products tracked")
        print(f"\nStock data updated: {len(self.current_products)} products tracked")

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
    
    delay = random.uniform(120, 300)
    start_time = datetime.now().timestamp() + delay
    start_time_str = datetime.fromtimestamp(start_time).strftime('%H:%M:%S')
    logger.info(f"Script will start in {delay/60:.1f} minutes at {start_time_str}")
    print(f"Starting in {delay/60:.1f} minutes at {start_time_str}...")
    # time.sleep(delay)
    
    artist_urls = {
        "https://riseaboverecords.com/product-category/electric-wizard-2/": "Electric Wizard",
        "https://riseaboverecords.com/product-category/uncle-acid-and-the-deadbeats-3/": "Uncle Acid and the Deadbeats"
    }
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
    monitor = RiseAboveMonitor(current_dir)
    monitor.run(current_dir, artist_urls, mode)