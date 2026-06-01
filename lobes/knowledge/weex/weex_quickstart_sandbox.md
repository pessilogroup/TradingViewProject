# WEEX Quickstart Sandbox Technical Reference

## 1. Sandbox Environment Overview

WEEX provides a Sandbox (Demo Mode) trading environment to allow developers to build, test, and debug API integrations without financial risk.

---

## 2. Sandbox Network Configuration

### 2.1 Base URLs
| Service | Protocol | Host URL |
| :--- | :--- | :--- |
| **Sandbox REST API** | HTTPS | `https://api-demo.weex.com` |
| **Sandbox WebSocket** | WSS | `wss://ws-demo.weex.com/mix/v1/websocket` |

---

## 3. Demo Mode Account and API Key Rules

*   **Activation**: Sandbox accounts must be explicitly activated via the WEEX web interface or user console.
*   **Separation of Credentials**: Demo API Keys, Secret Keys, and Passphrases must be generated within the Demo profile page. These credentials are functionally distinct and isolated from production API credentials. Trying to use production keys on the Demo endpoints (or vice versa) will result in authentication failure codes.
*   **Consistency of API Formats**: Order execution requests, cancel commands, position detail fetches, WebSocket subscription channels, and signature calculations (HMAC-SHA256) follow the exact identical schemas, payloads, headers, and paths as the production Spot and Contract APIs. Only the host domain names are changed.

---

## 4. Mock Paper Asset Allocation Matrix

No real asset settlement occurs in the Sandbox environment. Test accounts are credited with pre-allocated mock paper assets for testing Spot and Contract Margin scenarios:

| Asset Coin Symbol | Asset Full Name | Mock Balance Allocated | Usage Context |
| :--- | :--- | :--- | :--- |
| `SBTC` | Sandbox Bitcoin | `10,000 SBTC` | Spot and Contract position simulation |
| `SUSDT` | Sandbox Tether | `50,000 SUSDT` | Quote margin asset simulation for USDT-M |
| `SETH` | Sandbox Ethereum | `100 SETH` | Multi-asset collateral test scenarios |
