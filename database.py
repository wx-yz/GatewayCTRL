import sqlite3
import json
import logging
from typing import List, Dict, Optional
from gateways.base import GatewayConfig

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = 'gatewayctrl.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create gateways table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gateways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    verify_ssl BOOLEAN NOT NULL,
                    cert_path TEXT,
                    additional_config TEXT NOT NULL
                )
            ''')
            
            conn.commit()
    
    def save_gateway(self, gateway_type: str, gateway_name: str, config: GatewayConfig) -> bool:
        """Save or update a gateway configuration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert config to JSON for storage
                additional_config = json.dumps(config.additional_config)
                
                # Check if gateway exists
                cursor.execute(
                    'SELECT id FROM gateways WHERE name = ?',
                    (gateway_name,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing gateway
                    cursor.execute('''
                        UPDATE gateways 
                        SET type = ?, url = ?, verify_ssl = ?, cert_path = ?, additional_config = ?
                        WHERE name = ?
                    ''', (
                        gateway_type,
                        config.url,
                        config.verify_ssl,
                        config.cert_path,
                        additional_config,
                        gateway_name
                    ))
                else:
                    # Insert new gateway
                    cursor.execute('''
                        INSERT INTO gateways (name, type, url, verify_ssl, cert_path, additional_config)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        gateway_name,
                        gateway_type,
                        config.url,
                        config.verify_ssl,
                        config.cert_path,
                        additional_config
                    ))
                
                conn.commit()
                logger.info(f"Gateway {gateway_name} saved successfully")
                return True
        except Exception as e:
            logger.error(f"Error saving gateway: {str(e)}", exc_info=True)
            return False
    
    def get_gateways(self) -> List[Dict]:
        """Get all configured gateways"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM gateways')
                rows = cursor.fetchall()
                
                gateways = []
                for row in rows:
                    gateways.append({
                        'id': row[0],
                        'name': row[1],
                        'type': row[2],
                        'config': GatewayConfig(
                            name=row[1],
                            url=row[3],
                            verify_ssl=bool(row[4]),
                            cert_path=row[5],
                            additional_config=json.loads(row[6])
                        )
                    })
                
                return gateways
        except Exception as e:
            logger.error(f"Error getting gateways: {str(e)}", exc_info=True)
            return []
    
    def delete_gateway(self, gateway_name: str) -> bool:
        """Delete a gateway configuration"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM gateways WHERE name = ?', (gateway_name,))
                conn.commit()
                logger.info(f"Gateway {gateway_name} deleted successfully")
                return True
        except Exception as e:
            logger.error(f"Error deleting gateway: {str(e)}", exc_info=True)
            return False
    
    def clear_database(self) -> bool:
        """Clear all data from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM gateways')
                conn.commit()
                logger.info("Database cleared successfully")
                return True
        except Exception as e:
            logger.error(f"Error clearing database: {str(e)}", exc_info=True)
            return False 