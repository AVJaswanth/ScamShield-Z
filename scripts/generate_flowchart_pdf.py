"""
Generate High-Quality Solution Flowchart PDF for ScamShield Z
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
Uses Playwright to render an executive-grade, vector-crisp PDF document.
"""

import os
import sys
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ScamShield Z — Solution Flowchart & Architecture</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 12mm 14mm 12mm 14mm;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #0f172a;
      background: #ffffff;
      line-height: 1.35;
      font-size: 9.5pt;
    }
    .header-bar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #2563eb;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }
    .title-area h1 {
      font-size: 16pt;
      font-weight: 800;
      color: #1e3a8a;
      letter-spacing: -0.5px;
    }
    .title-area .subtitle {
      font-size: 9.5pt;
      color: #475569;
      font-weight: 500;
      margin-top: 2px;
    }
    .badge-pill {
      display: inline-block;
      padding: 3px 8px;
      font-size: 7.5pt;
      font-weight: 700;
      border-radius: 9999px;
      text-transform: uppercase;
      background: #eff6ff;
      color: #1d4ed8;
      border: 1px solid #bfdbfe;
    }
    .meta-box {
      text-align: right;
      font-size: 8pt;
      color: #64748b;
    }
    .meta-box strong {
      color: #0f172a;
    }

    /* Flowchart Container */
    .flowchart-wrapper {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .section-title {
      font-size: 10pt;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .section-title::before {
      content: "";
      display: inline-block;
      width: 4px;
      height: 13px;
      background: #2563eb;
      border-radius: 2px;
    }

    svg {
      width: 100%;
      height: auto;
      display: block;
    }

    /* Grid Specs */
    .specs-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 10px;
    }
    .spec-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 8px 10px;
    }
    .spec-card h3 {
      font-size: 8.5pt;
      font-weight: 700;
      color: #1e3a8a;
      margin-bottom: 4px;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 3px;
    }
    .spec-card ul {
      list-style-type: none;
      font-size: 7.5pt;
      color: #334155;
    }
    .spec-card li {
      margin-bottom: 2px;
      display: flex;
      justify-content: space-between;
    }
    .spec-card li span.val {
      font-weight: 600;
      color: #0f172a;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }

    /* Table styling */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 7.5pt;
      margin-top: 4px;
    }
    th, td {
      border: 1px solid #e2e8f0;
      padding: 4px 6px;
      text-align: left;
    }
    th {
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
    }
    tr:nth-child(even) td {
      background: #f8fafc;
    }

    .footer-bar {
      margin-top: 8px;
      border-top: 1px solid #e2e8f0;
      padding-top: 6px;
      display: flex;
      justify-content: space-between;
      font-size: 7.5pt;
      color: #64748b;
    }
    .footer-bar a {
      color: #2563eb;
      text-decoration: none;
      font-weight: 600;
    }
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header-bar">
    <div class="title-area">
      <h1>ScamShield Z — Solution Flowchart</h1>
      <div class="subtitle">Real-Time AI Scam & Authorized Push Payment Fraud Detection Architecture</div>
    </div>
    <div class="meta-box">
      <div><strong>IBM Z Datathon 2026</strong></div>
      <div>Theme: Real-Time AI for Critical Decisions</div>
      <div style="margin-top:2px;"><span class="badge-pill">Verified p99 = 0.492 ms</span></div>
    </div>
  </div>

  <!-- Flowchart Section -->
  <div class="flowchart-wrapper">
    <div class="section-title">End-to-End Transaction Decisioning Flowchart</div>
    <svg viewBox="0 0 850 560" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="gBlue" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#1e3a8a"/>
          <stop offset="100%" stop-color="#2563eb"/>
        </linearGradient>
        <linearGradient id="gPurple" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#4c1d95"/>
          <stop offset="100%" stop-color="#6d28d9"/>
        </linearGradient>
        <linearGradient id="gGreen" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#065f46"/>
          <stop offset="100%" stop-color="#059669"/>
        </linearGradient>
        <linearGradient id="gAmber" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#92400e"/>
          <stop offset="100%" stop-color="#d97706"/>
        </linearGradient>
        <linearGradient id="gRed" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#991b1b"/>
          <stop offset="100%" stop-color="#dc2626"/>
        </linearGradient>

        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9 z" fill="#475569"/>
        </marker>
        <marker id="arrowBlue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9 z" fill="#2563eb"/>
        </marker>
      </defs>

      <!-- 1. Transaction Ingestion -->
      <g>
        <rect x="25" y="25" width="220" height="65" rx="8" fill="url(#gBlue)" stroke="#1d4ed8" stroke-width="1.5"/>
        <text x="135" y="47" fill="#ffffff" font-size="12" font-weight="bold" text-anchor="middle">Inbound Payment Event</text>
        <text x="135" y="63" fill="#bfdbfe" font-size="9" text-anchor="middle">Sender, Payee, Amount, Device, Channel, ts</text>
        <text x="135" y="77" fill="#93c5fd" font-size="8.5" text-anchor="middle">50ms Payment Authorization Window</text>
      </g>

      <!-- Arrow 1 -> 2 -->
      <line x1="245" y1="57" x2="295" y2="57" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>

      <!-- 2. Privacy Tokenization -->
      <g>
        <rect x="295" y="25" width="240" height="65" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="1.5"/>
        <text x="415" y="47" fill="#0f172a" font-size="11" font-weight="bold" text-anchor="middle">HMAC SHA-256 Tokenization</text>
        <text x="415" y="63" fill="#475569" font-size="9" text-anchor="middle">Salted hashing of sender, payee & device IDs</text>
        <text x="415" y="77" fill="#64748b" font-size="8.5" text-anchor="middle">Zero plaintext PII passed to scoring pipeline</text>
      </g>

      <!-- Arrow 2 -> 3 -->
      <line x1="535" y1="57" x2="585" y2="57" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>

      <!-- 3. Rolling Feature Store -->
      <g>
        <rect x="585" y="15" width="240" height="85" rx="8" fill="#f0fdf4" stroke="#86efac" stroke-width="1.5"/>
        <text x="705" y="37" fill="#166534" font-size="11" font-weight="bold" text-anchor="middle">Rolling Feature Store (t &lt; t_i)</text>
        <text x="705" y="52" fill="#15803d" font-size="8.5" text-anchor="middle">• Zero future leakage: state updated strictly after t_i</text>
        <text x="705" y="66" fill="#15803d" font-size="8.5" text-anchor="middle">• Bounded deques: 10m, 1h, 24h, 30d sliding windows</text>
        <text x="705" y="80" fill="#15803d" font-size="8.5" text-anchor="middle">• 16 signals: mule fan-in, velocity, depletion ratio</text>
      </g>

      <!-- Arrow 3 down to Dual Scoring -->
      <path d="M 705 100 L 705 135 L 425 135 L 425 155" fill="none" stroke="#2563eb" stroke-width="2" marker-end="url(#arrowBlue)"/>

      <!-- 4. Dual AI Scoring Backends -->
      <g>
        <rect x="180" y="155" width="490" height="95" rx="10" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="4,4"/>
        <text x="425" y="174" fill="#334155" font-size="10.5" font-weight="bold" text-anchor="middle">Dual-Target Scoring Backend (Configurable Runtime Switch)</text>

        <!-- LOCAL_ONNX Card -->
        <rect x="195" y="185" width="220" height="55" rx="6" fill="#1e1b4b" stroke="#6366f1" stroke-width="1.5"/>
        <text x="305" y="206" fill="#c7d2fe" font-size="10" font-weight="bold" text-anchor="middle">LOCAL_ONNX (Laptop CPU)</text>
        <text x="305" y="221" fill="#e0e7ff" font-size="8.5" text-anchor="middle">ONNX Runtime Session | 4,890.1 txn/sec</text>
        <text x="305" y="234" fill="#86efac" font-size="9" font-weight="bold" text-anchor="middle">Measured p50: 0.105ms | p99: 0.492ms</text>

        <!-- WMLZ_HTTP Card -->
        <rect x="435" y="185" width="220" height="55" rx="6" fill="#111827" stroke="#4b5563" stroke-width="1"/>
        <text x="545" y="206" fill="#93c5fd" font-size="10" font-weight="bold" text-anchor="middle">WMLZ_HTTP (Production IBM Z)</text>
        <text x="545" y="221" fill="#cbd5e1" font-size="8.5" text-anchor="middle">IBM Watson Machine Learning for z/OS</text>
        <text x="545" y="234" fill="#94a3b8" font-size="8.5" text-anchor="middle">z16 Telum On-Chip NNPA Coprocessor</text>
      </g>

      <!-- Arrow scoring down to policy engine -->
      <line x1="425" y1="250" x2="425" y2="280" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>

      <!-- 5. Risk Policy Engine Decision Diamond / Box -->
      <g>
        <rect x="180" y="280" width="490" height="60" rx="8" fill="url(#gPurple)" stroke="#5b21b6" stroke-width="1.5"/>
        <text x="425" y="303" fill="#ffffff" font-size="11.5" font-weight="bold" text-anchor="middle">4-Tier Risk Policy & Vulnerability Escalation Engine</text>
        <text x="425" y="320" fill="#ddd6fe" font-size="9" text-anchor="middle">Evaluates Fraud Score P(fraud) with Cost-Tuned Thresholds [0.05, 0.35, 0.65]</text>
        <text x="425" y="333" fill="#fef08a" font-size="8.5" font-weight="600" text-anchor="middle">Vulnerable Customers (Opt-in / 60+): Escalated +1 Band & Triggers Trusted Contact Alert</text>
      </g>

      <!-- Branching Arrows from Policy to Decisions -->
      <path d="M 230 340 L 230 380 L 105 380 L 105 405" fill="none" stroke="#059669" stroke-width="2" marker-end="url(#arrow)"/>
      <path d="M 330 340 L 330 380 L 265 380 L 265 405" fill="none" stroke="#2563eb" stroke-width="2" marker-end="url(#arrow)"/>
      <path d="M 520 340 L 520 380 L 445 380 L 445 405" fill="none" stroke="#d97706" stroke-width="2" marker-end="url(#arrow)"/>
      <path d="M 620 340 L 620 380 L 635 380 L 635 405" fill="none" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow)"/>
      <path d="M 620 340 L 620 380 L 765 380 L 765 405" fill="none" stroke="#991b1b" stroke-width="2" marker-end="url(#arrow)"/>

      <!-- 6. Decision Outcomes -->
      <!-- ALLOW -->
      <g>
        <rect x="25" y="405" width="150" height="65" rx="6" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
        <text x="100" y="426" fill="#15803d" font-size="10.5" font-weight="bold" text-anchor="middle">ALLOW</text>
        <text x="100" y="442" fill="#166534" font-size="8.5" text-anchor="middle">Score &lt; 0.05</text>
        <text x="100" y="457" fill="#334155" font-size="8" text-anchor="middle">Frictionless STP Clearing</text>
      </g>

      <!-- ALLOW WITH NOTICE -->
      <g>
        <rect x="185" y="405" width="160" height="65" rx="6" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
        <text x="265" y="426" fill="#1d4ed8" font-size="10" font-weight="bold" text-anchor="middle">ALLOW WITH NOTICE</text>
        <text x="265" y="442" fill="#1e40af" font-size="8.5" text-anchor="middle">0.05 &lt;= Score &lt; 0.35</text>
        <text x="265" y="457" fill="#334155" font-size="8" text-anchor="middle">Educational App Advisory</text>
      </g>

      <!-- CONFIRM (Step-up 2FA) -->
      <g>
        <rect x="355" y="405" width="160" height="65" rx="6" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"/>
        <text x="435" y="426" fill="#b45309" font-size="10.5" font-weight="bold" text-anchor="middle">CONFIRM (Step-Up)</text>
        <text x="435" y="442" fill="#92400e" font-size="8.5" text-anchor="middle">0.35 &lt;= Score &lt; 0.65</text>
        <text x="435" y="457" fill="#334155" font-size="8" text-anchor="middle">Customer Biometric / OTP</text>
      </g>

      <!-- HOLD -->
      <g>
        <rect x="525" y="405" width="150" height="65" rx="6" fill="#fef2f2" stroke="#ef4444" stroke-width="1.5"/>
        <text x="600" y="426" fill="#b91c1c" font-size="10.5" font-weight="bold" text-anchor="middle">HOLD</text>
        <text x="600" y="442" fill="#991b1b" font-size="8.5" text-anchor="middle">Score &gt;= 0.65</text>
        <text x="600" y="457" fill="#334155" font-size="8" text-anchor="middle">Transfer Paused (4h cooling)</text>
      </g>

      <!-- HUMAN REVIEW -->
      <g>
        <rect x="685" y="405" width="150" height="65" rx="6" fill="#450a0a" stroke="#dc2626" stroke-width="1.5"/>
        <text x="760" y="426" fill="#fecaca" font-size="10" font-weight="bold" text-anchor="middle">HUMAN REVIEW</text>
        <text x="760" y="442" fill="#fca5a5" font-size="8.5" text-anchor="middle">Score &gt;= 0.65 &amp; &gt;=$5,000</text>
        <text x="760" y="457" fill="#ffffff" font-size="8" text-anchor="middle">Escalated to Fraud Ops</text>
      </g>

      <!-- Bottom Compliance & Transparency Bar -->
      <g>
        <rect x="25" y="490" width="810" height="55" rx="6" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1"/>
        <text x="425" y="512" fill="#0f172a" font-size="9.5" font-weight="bold" text-anchor="middle">Governance, Explainability &amp; Fairness Rails (Synchronous In-Path Execution)</text>
        <text x="425" y="528" fill="#475569" font-size="8.5" text-anchor="middle">
          Deterministic Tree SHAP Explanations (Fixed regulatory templates)  |  Demographic Fairness Audit (&lt;0.05 gap across age groups)  |  Audit Trail CSV
        </text>
      </g>
    </svg>
  </div>

  <!-- Technical Specs Grid -->
  <div class="specs-grid">
    <div class="spec-card">
      <h3>Engine & Performance Specifications</h3>
      <ul>
        <li><span>Scoring Engine:</span> <span class="val">ONNX Runtime (CPU) &amp; WMLz HTTP</span></li>
        <li><span>Verified p50 Latency:</span> <span class="val">0.105 ms (104.6 µs)</span></li>
        <li><span>Verified p95 Latency:</span> <span class="val">0.320 ms (319.5 µs)</span></li>
        <li><span>Verified p99 Latency:</span> <span class="val">0.492 ms (491.7 µs)</span></li>
        <li><span>Sustained Throughput:</span> <span class="val">4,890.1 transactions / sec</span></li>
        <li><span>ONNX Max Parity Diff:</span> <span class="val">5.93e-08 (&lt; 1e-05 pass)</span></li>
      </ul>
    </div>

    <div class="spec-card">
      <h3>Risk Policy & Cost Matrix Optimization</h3>
      <ul>
        <li><span>Low Risk (STP Allow):</span> <span class="val">P(fraud) &lt; 0.05</span></li>
        <li><span>Medium Risk (Notice / Confirm):</span> <span class="val">0.05 &lt;= P &lt; 0.35</span></li>
        <li><span>High Risk (Confirm / Hold):</span> <span class="val">0.35 &lt;= P &lt; 0.65</span></li>
        <li><span>Very High Risk (Hold / Review):</span> <span class="val">P &gt;= 0.65</span></li>
        <li><span>Human Review Threshold:</span> <span class="val">Amount &gt;= $5,000.00</span></li>
        <li><span>Cost Optimization Matrix:</span> <span class="val">Miss: 50 | Hold: 5 | Prompt: 1</span></li>
      </ul>
    </div>
  </div>

  <!-- Model Evaluation & Transparency Table -->
  <div class="spec-card" style="margin-bottom: 8px;">
    <h3>Model Evaluation & Data Provenance Summary</h3>
    <table>
      <thead>
        <tr>
          <th>Model / Dataset</th>
          <th>Data Type</th>
          <th>PR-AUC</th>
          <th>ROC-AUC</th>
          <th>Recall @ 1% FPR</th>
          <th>Role in Verification</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>LightGBM (ONNX Runtime)</strong></td>
          <td>Synthetic Stream (200k)</td>
          <td>0.9994</td>
          <td>1.0000</td>
          <td>1.0000</td>
          <td>Pipeline integrity &amp; zero future-leakage verification</td>
        </tr>
        <tr>
          <td><strong>Baseline Logistic Regression</strong></td>
          <td>Synthetic Stream (200k)</td>
          <td>0.8636</td>
          <td>0.9992</td>
          <td>0.9833</td>
          <td>Linear classification baseline</td>
        </tr>
        <tr style="background:#eff6ff;">
          <td><strong>ULB Credit Card Fraud (Real Data)</strong></td>
          <td>Authentic European Cards (100k)</td>
          <td><strong>0.2803</strong></td>
          <td><strong>0.8857</strong></td>
          <td><strong>0.7708</strong></td>
          <td><strong>Real-world baseline with authentic noisy fraud</strong></td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Footer -->
  <div class="footer-bar">
    <div><strong>ScamShield Z</strong> — IBM Z Datathon 2026 Submission</div>
    <div>Code Repository: <a href="https://github.com/AVJaswanth/ScamShield-Z">github.com/AVJaswanth/ScamShield-Z</a></div>
    <div>License: Apache 2.0 / MIT</div>
  </div>

</body>
</html>
"""

def generate_pdf():
    html_path = os.path.join(DOCS_DIR, "flowchart_temp.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)

    pdf_output_docs = os.path.join(DOCS_DIR, "ScamShield_Z_Solution_Flowchart.pdf")
    pdf_output_root = os.path.join(BASE_DIR, "ScamShield_Z_Solution_Flowchart.pdf")
    pdf_output_desktop = os.path.abspath(os.path.join(BASE_DIR, "..", "ScamShield_Z_Solution_Flowchart.pdf"))

    print(f"Generating PDF via Playwright Chromium / Edge...")
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    launch_kwargs = {}
    if os.path.exists(edge_path):
        launch_kwargs["executable_path"] = edge_path
    else:
        launch_kwargs["channel"] = "msedge"

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto(f"file:///{html_path.replace(os.sep, '/')}")
        page.pdf(
            path=pdf_output_docs,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "12mm", "right": "12mm"}
        )
        browser.close()

    # Copy to root and parent directory for easy user access
    import shutil
    shutil.copyfile(pdf_output_docs, pdf_output_root)
    shutil.copyfile(pdf_output_docs, pdf_output_desktop)

    if os.path.exists(html_path):
        os.remove(html_path)

    print(f"[SUCCESS] PDF generated at:")
    print(f"  1. {pdf_output_docs}")
    print(f"  2. {pdf_output_root}")
    print(f"  3. {pdf_output_desktop}")
    print(f"File size: {os.path.getsize(pdf_output_docs) / 1024:.1f} KB")

if __name__ == "__main__":
    generate_pdf()
