#!/usr/bin/env python3
"""
Test script to validate the duplicate stock alert fixes
"""

import os
import sys
import json
import tempfile
from datetime import datetime, timedelta

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rise_above_monitor import RiseAboveMonitor

def test_text_normalization():
    """Test the text normalization function"""
    print("Testing text normalization...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = RiseAboveMonitor(temp_dir)
        
        # Test cases for text normalization
        test_cases = [
            ("Electric Wizard", "Electric_Wizard"),
            ("Uncle Acid & The Deadbeats", "Uncle_Acid_The_Deadbeats"),
            ("Album/Name With Spaces", "Album_Name_With_Spaces"),
            ("  Extra   Spaces  ", "Extra_Spaces"),
            ("Special<>Characters", "Special_Characters"),
        ]
        
        for input_text, expected in test_cases:
            result = monitor.normalize_text(input_text)
            print(f"  '{input_text}' -> '{result}' (expected: '{expected}')")
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    print("✅ Text normalization tests passed")

def test_boolean_conversion():
    """Test the boolean conversion function"""
    print("\nTesting boolean conversion...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = RiseAboveMonitor(temp_dir)
        
        test_cases = [
            (True, True),
            (False, False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
            (1, True),
            (0, False),
            ("invalid", False),
        ]
        
        for input_val, expected in test_cases:
            result = monitor.ensure_boolean(input_val)
            print(f"  {input_val} ({type(input_val).__name__}) -> {result}")
            assert result == expected, f"Expected {expected}, got {result}"
    
    print("✅ Boolean conversion tests passed")

def test_product_key_generation():
    """Test consistent product key generation"""
    print("\nTesting product key generation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = RiseAboveMonitor(temp_dir)
        
        # Test that same inputs produce same keys
        key1 = monitor.generate_product_key("Electric Wizard", "Dopethrone", "Black Vinyl")
        key2 = monitor.generate_product_key("Electric Wizard", "Dopethrone", "Black Vinyl")
        
        print(f"  Key 1: {key1}")
        print(f"  Key 2: {key2}")
        assert key1 == key2, "Same inputs should produce same keys"
        
        # Test that different inputs produce different keys
        key3 = monitor.generate_product_key("Electric Wizard", "Dopethrone", "Red Vinyl")
        print(f"  Key 3: {key3}")
        assert key1 != key3, "Different inputs should produce different keys"
    
    print("✅ Product key generation tests passed")

def test_duplicate_alert_prevention():
    """Test the duplicate alert prevention system"""
    print("\nTesting duplicate alert prevention...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = RiseAboveMonitor(temp_dir)
        
        product_key = "Electric_Wizard_Dopethrone_Black_Vinyl"
        
        # First alert should be allowed
        should_send_1 = monitor.should_send_alert("restock", product_key)
        print(f"  First alert: {should_send_1}")
        assert should_send_1 == True, "First alert should be allowed"
        
        # Immediate duplicate should be blocked
        should_send_2 = monitor.should_send_alert("restock", product_key)
        print(f"  Immediate duplicate: {should_send_2}")
        assert should_send_2 == False, "Immediate duplicate should be blocked"
        
        # Different alert type should be allowed
        should_send_3 = monitor.should_send_alert("out_of_stock", product_key)
        print(f"  Different alert type: {should_send_3}")
        assert should_send_3 == True, "Different alert type should be allowed"
    
    print("✅ Duplicate alert prevention tests passed")

def test_data_persistence():
    """Test robust data persistence"""
    print("\nTesting data persistence...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create monitor and add some data
        monitor1 = RiseAboveMonitor(temp_dir)
        monitor1.current_products = {
            "Electric_Wizard_Dopethrone_Black_Vinyl": {
                "artist": "Electric Wizard",
                "album": "Dopethrone",
                "variant": "Black Vinyl",
                "price": "£25.00",
                "in_stock": True,
                "url": "https://example.com",
                "last_changed": datetime.now().isoformat()
            }
        }
        monitor1.stock_changed = True
        monitor1.save_stock_data()
        
        # Create new monitor and load data
        monitor2 = RiseAboveMonitor(temp_dir)
        
        # Ensure logger is initialized for the second monitor
        if not hasattr(monitor2, 'logger') or monitor2.logger is None:
            monitor2.logger = logging.getLogger(__name__)
        
        loaded_data = monitor2.stock_data
        
        print(f"  Loaded {len(loaded_data['products'])} products")
        assert len(loaded_data['products']) == 1, "Should load 1 product"
        
        # Verify data integrity
        integrity_ok = monitor2.verify_data_integrity()
        print(f"  Data integrity check: {integrity_ok}")
        assert integrity_ok == True, "Data integrity should be valid"
    
    print("✅ Data persistence tests passed")

if __name__ == "__main__":
    print("Running duplicate stock alert fix tests...\n")
    
    try:
        test_text_normalization()
        test_boolean_conversion()
        test_product_key_generation()
        test_duplicate_alert_prevention()
        test_data_persistence()
        
        print("\n🎉 All tests passed! The fixes should resolve the duplicate alert issues.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)