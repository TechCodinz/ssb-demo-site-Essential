/**
 * Sol Sniper Bot PRO - Client-Side Key Vault
 * 
 * AES-256 encrypted local storage for private keys.
 * Private keys NEVER leave the browser.
 * All signing happens locally.
 * 
 * Architecture:
 * 1. User imports private key
 * 2. Key is encrypted with user's password
 * 3. Encrypted key stored in localStorage
 * 4. When signing, key is decrypted in memory only
 * 5. Key is wiped from memory after use
 * 6. On logout, everything is cleared
 */

class KeyVault {
    constructor() {
        this.STORAGE_KEY = 'ssb_vault';
        this.SALT_KEY = 'ssb_vault_salt';
        this.IV_LENGTH = 12;
        this.SALT_LENGTH = 16;
        this.KEY_LENGTH = 256;
        this.ITERATIONS = 100000;

        // In-memory decrypted key (wiped after use)
        this._decryptedKey = null;
        this._keyTimeout = null;
    }

    // ============================================================
    // CRYPTO UTILITIES
    // ============================================================

    /**
     * Generate random bytes
     */
    _getRandomBytes(length) {
        return crypto.getRandomValues(new Uint8Array(length));
    }

    /**
     * Derive encryption key from password
     */
    async _deriveKey(password, salt) {
        const encoder = new TextEncoder();
        const passwordKey = await crypto.subtle.importKey(
            'raw',
            encoder.encode(password),
            'PBKDF2',
            false,
            ['deriveBits', 'deriveKey']
        );

        return crypto.subtle.deriveKey(
            {
                name: 'PBKDF2',
                salt: salt,
                iterations: this.ITERATIONS,
                hash: 'SHA-256'
            },
            passwordKey,
            { name: 'AES-GCM', length: this.KEY_LENGTH },
            false,
            ['encrypt', 'decrypt']
        );
    }

    /**
     * Encrypt data with AES-256-GCM
     */
    async _encrypt(data, password) {
        const encoder = new TextEncoder();
        const salt = this._getRandomBytes(this.SALT_LENGTH);
        const iv = this._getRandomBytes(this.IV_LENGTH);

        const key = await this._deriveKey(password, salt);

        const encrypted = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: iv },
            key,
            encoder.encode(data)
        );

        // Combine salt + iv + encrypted data
        const combined = new Uint8Array(
            salt.length + iv.length + encrypted.byteLength
        );
        combined.set(salt, 0);
        combined.set(iv, salt.length);
        combined.set(new Uint8Array(encrypted), salt.length + iv.length);

        return this._arrayBufferToBase64(combined.buffer);
    }

    /**
     * Decrypt data with AES-256-GCM
     */
    async _decrypt(encryptedBase64, password) {
        const decoder = new TextDecoder();
        const combined = this._base64ToArrayBuffer(encryptedBase64);
        const combinedArray = new Uint8Array(combined);

        // Extract salt, iv, and encrypted data
        const salt = combinedArray.slice(0, this.SALT_LENGTH);
        const iv = combinedArray.slice(this.SALT_LENGTH, this.SALT_LENGTH + this.IV_LENGTH);
        const encrypted = combinedArray.slice(this.SALT_LENGTH + this.IV_LENGTH);

        const key = await this._deriveKey(password, salt);

        const decrypted = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: iv },
            key,
            encrypted
        );

        return decoder.decode(decrypted);
    }

    /**
     * Convert ArrayBuffer to Base64
     */
    _arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }

    /**
     * Convert Base64 to ArrayBuffer
     */
    _base64ToArrayBuffer(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
    }

    // ============================================================
    // KEY MANAGEMENT
    // ============================================================

    /**
     * Check if vault has a stored key
     */
    hasKey() {
        return localStorage.getItem(this.STORAGE_KEY) !== null;
    }

    /**
     * Store private key in encrypted vault
     * @param {string} privateKey - Base58 encoded private key
     * @param {string} password - User password for encryption
     */
    async storeKey(privateKey, password) {
        if (!privateKey || !password) {
            throw new Error('Private key and password required');
        }

        if (password.length < 8) {
            throw new Error('Password must be at least 8 characters');
        }

        // Validate private key format (basic check)
        if (privateKey.length < 40 || privateKey.length > 100) {
            throw new Error('Invalid private key format');
        }

        // Encrypt and store
        const encrypted = await this._encrypt(privateKey, password);
        localStorage.setItem(this.STORAGE_KEY, encrypted);

        console.log('🔐 Private key stored securely');
        return true;
    }

    /**
     * Unlock vault and get private key
     * @param {string} password - User password
     * @returns {string} Base58 encoded private key
     */
    async unlockKey(password) {
        const encrypted = localStorage.getItem(this.STORAGE_KEY);

        if (!encrypted) {
            throw new Error('No key stored in vault');
        }

        try {
            const privateKey = await this._decrypt(encrypted, password);

            // Store in memory temporarily
            this._decryptedKey = privateKey;

            // Auto-wipe after 5 minutes
            this._scheduleWipe();

            console.log('🔓 Vault unlocked');
            return privateKey;
        } catch (error) {
            throw new Error('Invalid password');
        }
    }

    /**
     * Get the currently unlocked key (if any)
     */
    getUnlockedKey() {
        return this._decryptedKey;
    }

    /**
     * Check if vault is currently unlocked
     */
    isUnlocked() {
        return this._decryptedKey !== null;
    }

    /**
     * Schedule key wipe from memory
     */
    _scheduleWipe() {
        if (this._keyTimeout) {
            clearTimeout(this._keyTimeout);
        }

        // Wipe after 5 minutes of inactivity
        this._keyTimeout = setTimeout(() => {
            this.wipeMemory();
        }, 5 * 60 * 1000);
    }

    /**
     * Wipe decrypted key from memory
     */
    wipeMemory() {
        if (this._decryptedKey) {
            // Overwrite with zeros before clearing
            this._decryptedKey = '0'.repeat(this._decryptedKey.length);
            this._decryptedKey = null;
        }

        if (this._keyTimeout) {
            clearTimeout(this._keyTimeout);
            this._keyTimeout = null;
        }

        console.log('🧹 Key wiped from memory');
    }

    /**
     * Delete key from vault completely
     */
    deleteKey() {
        localStorage.removeItem(this.STORAGE_KEY);
        this.wipeMemory();
        console.log('🗑️ Key deleted from vault');
        return true;
    }

    /**
     * Clear all vault data (logout)
     */
    clearAll() {
        localStorage.removeItem(this.STORAGE_KEY);
        localStorage.removeItem(this.SALT_KEY);
        this.wipeMemory();
        console.log('🔒 Vault cleared');
    }

    /**
     * Change vault password
     * @param {string} oldPassword - Current password
     * @param {string} newPassword - New password
     */
    async changePassword(oldPassword, newPassword) {
        // Decrypt with old password
        const privateKey = await this.unlockKey(oldPassword);

        // Re-encrypt with new password
        await this.storeKey(privateKey, newPassword);

        // Wipe memory
        this.wipeMemory();

        console.log('🔑 Password changed');
        return true;
    }
}

// ============================================================
// GLOBAL INSTANCE
// ============================================================

const keyVault = new KeyVault();

// Auto-clear on page unload
window.addEventListener('beforeunload', () => {
    keyVault.wipeMemory();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { KeyVault, keyVault };
}
