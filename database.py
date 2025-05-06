import sqlite3
import json
import os
from cryptography.fernet import Fernet, InvalidToken
from gateways.base import GatewayConfig
import logging

logger = logging.getLogger(__name__)

# --- Encryption Setup ---
ENCRYPTION_KEY = os.environ.get('GATEWAYCTRL_ENCRYPTION_KEY')
fernet = None  # Initialize fernet to None

if not ENCRYPTION_KEY:
    logger.warning("GATEWAYCTRL_ENCRYPTION_KEY environment variable not set. Credentials will NOT be encrypted.")
else:
    try:
        fernet = Fernet(ENCRYPTION_KEY.encode())
        logger.info("Encryption key loaded successfully. Fernet object created.")
    except ValueError as ve:  # Catch specific error for invalid key format
        logger.error(f"Failed to load encryption key due to invalid key format (ValueError): {ve}. Credentials will NOT be encrypted.")
    except Exception as e:
        logger.error(f"Failed to load encryption key due to an unexpected error: {e}. Credentials will NOT be encrypted.")
        # fernet remains None

SENSITIVE_KEYS = [
    'password',
    'tyk_auth_secret',
    'aws_secret_access_key',
    'kong_api_key',
    'gravitee_username',
    'gravitee_password'
]

def encrypt_value(value: str) -> str:
    """Encrypts a string value using Fernet."""
    if not fernet:
        logger.debug("Encrypt_value: Fernet not available, returning original value.")
        return value
    if not isinstance(value, str) or not value:
        logger.debug(f"Encrypt_value: Value is not a non-empty string, returning as is: {type(value)}")
        return value
    try:
        encrypted = fernet.encrypt(value.encode()).decode()
        logger.debug(f"Encrypt_value: Successfully encrypted value starting with '{value[:5]}...'.")
        return encrypted
    except Exception as e:
        logger.error(f"Encryption failed for value starting with '{value[:5]}...': {e}", exc_info=True)
        return value

def decrypt_value(encrypted_value: str) -> str:
    """Decrypts a string value using Fernet."""
    if not fernet:
        logger.warning("Decrypt_value: Fernet object not available (encryption key likely not loaded). Returning original value.")
        return encrypted_value

    if not isinstance(encrypted_value, str) or not encrypted_value:
        logger.debug(f"Decrypt_value: Value is not a non-empty string, returning as is: {type(encrypted_value)}")
        return encrypted_value

    # Only attempt decryption if it looks like a Fernet token.
    # Fernet tokens are base64 encoded and typically start with "gAAAAA".
    # This is a heuristic to avoid trying to decrypt plain text that might be stored.
    if not encrypted_value.startswith("gAAAAA"):
        logger.debug(f"Decrypt_value: Value starting with '{encrypted_value[:10]}...' does not look like a Fernet token. Returning as is.")
        return encrypted_value

    logger.debug(f"Decrypt_value: Attempting to decrypt Fernet token starting with '{encrypted_value[:10]}...'. Length: {len(encrypted_value)}")
    try:
        decrypted = fernet.decrypt(encrypted_value.encode()).decode()
        logger.info(f"Decrypt_value: Successfully decrypted value. Original started with '{encrypted_value[:10]}...', result starts with '{decrypted[:5]}...'.")
        return decrypted
    except InvalidToken:
        logger.error(
            f"Decrypt_value: InvalidToken for value starting with '{encrypted_value[:10]}...'. "
            "This means the encryption key is incorrect for this token, or the token is corrupted. "
            "Ensure GATEWAYCTRL_ENCRYPTION_KEY is the correct one used for encryption. Returning the original (encrypted) value."
        )
        return encrypted_value
    except Exception as e:
        logger.error(f"Decrypt_value: An unexpected error occurred during decryption for value starting with '{encrypted_value[:10]}...': {e}", exc_info=True)
        return encrypted_value

def process_config(config_dict: dict, encrypt: bool = True) -> dict:
    """Encrypts or decrypts sensitive fields in the additional_config."""
    if 'additional_config' in config_dict and isinstance(config_dict['additional_config'], dict):
        processed_additional = {}
        for key, value in config_dict['additional_config'].items():
            if key in SENSITIVE_KEYS and isinstance(value, str):  # Ensure value is a string
                if encrypt:
                    logger.debug(f"Process_config: Encrypting field '{key}'.")
                    processed_additional[key] = encrypt_value(value)
                else:
                    logger.debug(f"Process_config: Decrypting field '{key}'.")
                    processed_additional[key] = decrypt_value(value)
            else:
                processed_additional[key] = value
        config_dict['additional_config'] = processed_additional
    return config_dict
# --- End Encryption Setup ---

class Database:
    def __init__(self, db_name='gatewayctrl.db'):
        self.db_name = db_name
        self._create_table()

    def _connect(self):
        return sqlite3.connect(self.db_name)

    def _create_table(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gateways (
                    name TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    config TEXT NOT NULL
                )
            ''')
            conn.commit()

    def add_gateway(self, name: str, gateway_type: str, config: GatewayConfig):
        with self._connect() as conn:
            cursor = conn.cursor()
            # Encrypt sensitive data before saving
            config_dict = config.model_dump()
            encrypted_config_dict = process_config(config_dict, encrypt=True)
            config_json = json.dumps(encrypted_config_dict)
            try:
                cursor.execute("INSERT INTO gateways (name, type, config) VALUES (?, ?, ?)",
                               (name, gateway_type, config_json))
                conn.commit()
                logger.info(f"Gateway '{name}' added to database.")
            except sqlite3.IntegrityError:
                logger.error(f"Gateway with name '{name}' already exists.")
                raise  # Re-raise the exception

    def update_gateway(self, original_name: str, gateway_type: str, config: GatewayConfig):
        with self._connect() as conn:
            cursor = conn.cursor()
            # Encrypt sensitive data before saving
            config_dict = config.model_dump()
            encrypted_config_dict = process_config(config_dict, encrypt=True)
            config_json = json.dumps(encrypted_config_dict)
            cursor.execute("UPDATE gateways SET name = ?, type = ?, config = ? WHERE name = ?",
                           (config.name, gateway_type, config_json, original_name))
            conn.commit()
            logger.info(f"Gateway '{original_name}' updated to '{config.name}' in database.")

    def delete_gateway(self, name: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gateways WHERE name = ?", (name,))
            conn.commit()
            logger.info(f"Gateway '{name}' deleted from database.")

    def get_gateways(self) -> list:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, type, config FROM gateways")
            gateways = []
            for row in cursor.fetchall():
                name, gateway_type, config_json = row
                try:
                    config_dict = json.loads(config_json)
                    # Decrypt sensitive data after loading
                    logger.debug(f"Get_gateways: Processing config for gateway '{name}' for decryption.")
                    decrypted_config_dict = process_config(config_dict, encrypt=False)

                    config_obj = GatewayConfig(**decrypted_config_dict)
                    gateways.append({
                        'name': name,
                        'type': gateway_type,
                        'config': config_obj
                    })
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Error decoding/parsing config for gateway '{name}': {e}")
                except Exception as e:
                    logger.error(f"Error creating GatewayConfig object for gateway '{name}': {e}", exc_info=True)
            return gateways