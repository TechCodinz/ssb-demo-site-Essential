
import os

FILE_PATH = r"c:\Users\User\Downloads\LeanTraderBot_Mini_v4_Premium\static_deploy\index.html"

MODAL_CSS = """
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: var(--bg-card);
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            border: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
        }

        .modal-content h2 {
            margin-bottom: 20px;
            color: var(--accent-cyan);
        }

        .wallet-address {
            background: #1e293b;
            padding: 15px;
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
            margin: 20px 0;
            word-break: break-all;
            border: 1px solid rgba(34, 211, 238, 0.2);
            color: var(--accent-cyan);
        }

        .close-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
            float: right;
            margin-top: -20px;
            margin-right: -20px;
        }
"""

PAGE_TAIL_HTML = """
                    <li>✓ 10 open positions</li>
                    <li>✓ Elite risk engine</li>
                    <li>✓ Early entry boost</li>
                </ul>
                <button class="btn btn-secondary" onclick="openModal('ELITE', 899)">Get Elite</button>
            </div>
        </div>
    </section>

    <!-- Payment Modal -->
    <div class="modal" id="payment-modal">
        <div class="modal-content">
            <button class="close-btn" onclick="closeModal()">&times;</button>
            <h2>Complete Payment</h2>
            <p style="color: var(--text-muted); margin-bottom: 20px;">
                Plan: <strong id="modal-plan">-</strong> • Amount: <strong id="modal-amount">$0</strong> USDT
            </p>

            <div id="order-step">
                <p style="margin-bottom: 20px;">1. Send exact amount (TRC20) to:</p>
                <div class="wallet-address" id="modal-wallet">TBxck6t1a3pZE2YLho4Su1PcGKd2yK2zD4</div>
                <p style="margin-bottom: 20px;">2. Send TX Hash & Email to Telegram:</p>
                <a href="https://t.me/SSB_OrderBot" target="_blank" class="btn btn-primary">Open Telegram Support</a>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <p>© 2025 Sol Sniper Bot PRO. Trade responsibly. Not financial advice.</p>
    </footer>

    <script>
        // Simulated live trading demo
        const logs = [
            { text: '⚡ Engine started - ELITE mode', class: 'log-info' },
            { text: '🔌 Connected to Pump.fun stream', class: 'log-success' },
            { text: '🚀 NEW TOKEN: 5xK8...2Fm9', class: 'log-success' },
            { text: '📊 Analyzing risk... Confidence: 82.4%', class: 'log-info' },
            { text: '🟢 BUY EXECUTED: 0.25 SOL → 5xK8...', class: 'log-success' },
            { text: '🚀 NEW TOKEN: 9aB2...7Xm1', class: 'log-success' },
            { text: '📊 Analyzing risk... Confidence: 45.2%', class: 'log-info' },
            { text: '❌ REJECTED: Low confidence', class: 'log-warning' },
            { text: '💰 SELL (TP): 5xK8... +287%', class: 'log-success' },
            { text: '🚀 NEW TOKEN: 3mN7...4Ks8', class: 'log-success' },
        ];

        const terminal = document.getElementById('terminal');
        let i = 0;

        function addLog() {
            if (i >= logs.length) {
                terminal.innerHTML = '';
                i = 0;
            }
            const log = logs[i];
            const line = document.createElement('div');
            line.className = `log-line ${log.class}`;
            line.style.animationDelay = '0s';
            line.textContent = `[${new Date().toLocaleTimeString()}] ${log.text}`;
            terminal.appendChild(line);
            terminal.scrollTop = terminal.scrollHeight;
            i++;
        }

        // Start demo
        setInterval(addLog, 2000);
        addLog();

        // Modal Logic
        function openModal(plan, price) {
            document.getElementById('modal-plan').textContent = plan;
            document.getElementById('modal-amount').textContent = '$' + price;
            document.getElementById('payment-modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('payment-modal').classList.remove('active');
        }

        // Close modal on click outside
        window.onclick = function (event) {
            if (event.target == document.getElementById('payment-modal')) {
                closeModal();
            }
        }
    </script>
</body>
</html>
"""

def fix_file():
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Inject CSS
    # Find </style> and insert MODAL_CSS before it
    if ".modal {" not in content:
        content = content.replace("    </style>", MODAL_CSS + "\n    </style>")
        print("✅ CSS injected.")
    else:
        print("ℹ️ CSS already present (skipping).")

    # 2. Fix Body Garbage
    # Find the last valid line of the Elite plan
    marker = "<li>✓ 18 trades/hour</li>"
    split_index = content.find(marker)
    
    if split_index == -1:
        print("❌ Could not find split marker!")
        return

    # Cut content right after the marker
    head_content = content[:split_index + len(marker)]
    
    # Combine head + tail
    new_content = head_content + "\n" + PAGE_TAIL_HTML

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print("✅ File repaired successfully.")

if __name__ == "__main__":
    fix_file()
