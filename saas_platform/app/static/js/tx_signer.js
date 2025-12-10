/**
 * Sol Sniper Bot PRO - Client-Side Transaction Signer
 * 
 * Signs Solana transactions locally using the key vault.
 * Transactions are signed in the browser, then sent to backend for broadcast.
 * Private key NEVER leaves the browser.
 * 
 * Flow:
 * 1. Get unsigned transaction from server (base64)
 * 2. Decode and sign with local private key
 * 3. Send signed transaction to server
 * 4. Server broadcasts via RPC
 */

class TransactionSigner {
    constructor() {
        this.API_BASE = '/api/v1';
    }

    // ============================================================
    // KEY UTILITIES
    // ============================================================

    /**
     * Convert Base58 private key to Uint8Array
     */
    _base58ToBytes(base58) {
        const ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
        const ALPHABET_MAP = {};
        for (let i = 0; i < ALPHABET.length; i++) {
            ALPHABET_MAP[ALPHABET[i]] = i;
        }

        let bytes = [0];
        for (let i = 0; i < base58.length; i++) {
            const value = ALPHABET_MAP[base58[i]];
            if (value === undefined) {
                throw new Error('Invalid Base58 character');
            }

            for (let j = 0; j < bytes.length; j++) {
                bytes[j] *= 58;
            }
            bytes[0] += value;

            let carry = 0;
            for (let j = 0; j < bytes.length; j++) {
                bytes[j] += carry;
                carry = bytes[j] >> 8;
                bytes[j] &= 0xff;
            }

            while (carry) {
                bytes.push(carry & 0xff);
                carry >>= 8;
            }
        }

        // Handle leading zeros
        for (let i = 0; i < base58.length && base58[i] === '1'; i++) {
            bytes.push(0);
        }

        return new Uint8Array(bytes.reverse());
    }

    /**
     * Convert bytes to Base58
     */
    _bytesToBase58(bytes) {
        const ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';

        let result = [];
        for (let byte of bytes) {
            let carry = byte;
            for (let i = 0; i < result.length; i++) {
                carry += result[i] << 8;
                result[i] = carry % 58;
                carry = Math.floor(carry / 58);
            }
            while (carry) {
                result.push(carry % 58);
                carry = Math.floor(carry / 58);
            }
        }

        // Handle leading zeros
        for (let i = 0; i < bytes.length && bytes[i] === 0; i++) {
            result.push(0);
        }

        return result.reverse().map(i => ALPHABET[i]).join('');
    }

    /**
     * Get public key from private key
     */
    async getPublicKey(privateKeyBase58) {
        // For Solana, the private key is 64 bytes (secret key + public key)
        // or 32 bytes (secret key only)
        const keyBytes = this._base58ToBytes(privateKeyBase58);

        if (keyBytes.length === 64) {
            // Full keypair - public key is last 32 bytes
            const publicKeyBytes = keyBytes.slice(32);
            return this._bytesToBase58(publicKeyBytes);
        } else if (keyBytes.length === 32) {
            // Need to derive public key - requires ed25519
            // For now, we'll require the full keypair format
            throw new Error('Please use the full keypair format (64 bytes)');
        }

        throw new Error('Invalid private key length');
    }

    // ============================================================
    // TRANSACTION SIGNING
    // ============================================================

    /**
     * Sign a transaction with the local private key
     * @param {string} unsignedTxBase64 - Unsigned transaction from server
     * @param {string} privateKeyBase58 - Private key from vault
     * @returns {string} Signed transaction as Base64
     */
    async signTransaction(unsignedTxBase64, privateKeyBase58) {
        // Import nacl-fast for ed25519 signing
        if (typeof nacl === 'undefined') {
            throw new Error('nacl library not loaded. Include nacl-fast.min.js');
        }

        // Decode transaction
        const txBytes = Uint8Array.from(atob(unsignedTxBase64), c => c.charCodeAt(0));

        // Get keypair from private key
        const keyBytes = this._base58ToBytes(privateKeyBase58);

        let secretKey;
        if (keyBytes.length === 64) {
            secretKey = keyBytes;
        } else if (keyBytes.length === 32) {
            // Derive full keypair from seed
            const keypair = nacl.sign.keyPair.fromSeed(keyBytes);
            secretKey = keypair.secretKey;
        } else {
            throw new Error('Invalid private key length');
        }

        // Sign the transaction
        // Solana transaction structure: signatures + message
        // We need to extract the message and sign it

        const numSignatures = txBytes[0];
        const signatureOffsets = [];

        // Find signature placeholders (64 bytes of zeros)
        for (let i = 0; i < numSignatures; i++) {
            const offset = 1 + (i * 64);
            signatureOffsets.push(offset);
        }

        // Message starts after all signatures
        const messageOffset = 1 + (numSignatures * 64);
        const message = txBytes.slice(messageOffset);

        // Sign the message
        const signature = nacl.sign.detached(message, secretKey);

        // Insert signature into transaction
        const signedTx = new Uint8Array(txBytes);
        signedTx.set(signature, signatureOffsets[0]);

        // Convert to Base64
        let binary = '';
        for (let i = 0; i < signedTx.length; i++) {
            binary += String.fromCharCode(signedTx[i]);
        }

        return btoa(binary);
    }

    // ============================================================
    // API INTEGRATION
    // ============================================================

    /**
     * Submit a signed transaction to the server
     * @param {string} signedTxBase64 - Signed transaction
     * @param {object} metadata - Transaction metadata
     */
    async submitTransaction(signedTxBase64, metadata = {}) {
        const response = await fetch(`${this.API_BASE}/tx/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._getAuthToken()}`
            },
            body: JSON.stringify({
                signed_tx: signedTxBase64,
                tx_type: metadata.type || 'SWAP',
                token_mint: metadata.tokenMint || '',
                amount_sol: metadata.amountSol || 0
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Transaction submission failed');
        }

        return response.json();
    }

    /**
     * Get swap transaction from Jupiter
     * @param {string} inputMint - Input token mint
     * @param {string} outputMint - Output token mint
     * @param {number} amount - Amount in lamports
     * @param {string} userPublicKey - User's public key
     */
    async getSwapTransaction(inputMint, outputMint, amount, userPublicKey) {
        const response = await fetch(`${this.API_BASE}/jupiter/swap`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._getAuthToken()}`
            },
            body: JSON.stringify({
                input_mint: inputMint,
                output_mint: outputMint,
                amount: amount,
                user_pubkey: userPublicKey,
                slippage_bps: 100
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get swap transaction');
        }

        return response.json();
    }

    /**
     * Execute a complete swap flow
     * @param {string} inputMint - Input token mint
     * @param {string} outputMint - Output token mint
     * @param {number} amount - Amount in lamports
     */
    async executeSwap(inputMint, outputMint, amount) {
        // Check if vault is unlocked
        if (!keyVault.isUnlocked()) {
            throw new Error('Please unlock your wallet first');
        }

        const privateKey = keyVault.getUnlockedKey();
        const publicKey = await this.getPublicKey(privateKey);

        // Get swap transaction from server
        console.log('🔄 Getting swap transaction...');
        const { swap_transaction, quote } = await this.getSwapTransaction(
            inputMint,
            outputMint,
            amount,
            publicKey
        );

        // Sign transaction locally
        console.log('✍️ Signing transaction...');
        const signedTx = await this.signTransaction(swap_transaction, privateKey);

        // Submit to server for broadcast
        console.log('📡 Submitting transaction...');
        const result = await this.submitTransaction(signedTx, {
            type: 'SWAP',
            tokenMint: outputMint,
            amountSol: amount / 1e9
        });

        console.log('✅ Transaction submitted:', result.signature);
        return result;
    }

    /**
     * Get auth token from storage
     */
    _getAuthToken() {
        return localStorage.getItem('ssb_auth_token') || '';
    }
}

// ============================================================
// GLOBAL INSTANCE
// ============================================================

const txSigner = new TransactionSigner();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TransactionSigner, txSigner };
}
