# Polymarket Quantitative Arbitrage & Mispricing Engine

A high-performance, event-driven arbitrage engine built in Python to detect and exploit structural inefficiencies on Polymarket (a Web3 prediction market). 

Designed with institutional-grade architecture, this engine bypasses Cloudflare anti-bot protections, maintains resilient WebSocket connections to thousands of concurrent markets, and executes sub-millisecond mathematical analysis using fractional Kelly risk management.

## Key Features

*   **Global Market Surveillance:** Dynamically paginates and streams real-time Order Book data from 1,500+ active markets simultaneously via Websockets.
*   **Anti-Bot Resilience:** Utilizes `curl_cffi` for TLS fingerprinting to bypass Cloudflare's strict 403 geo-blocking and rate limits.
*   **True Slippage Calculation:** Implements "Order Book Walking" rather than relying on naive mid-prices, accurately assessing executable size against available liquidity.
*   **Quantitative Risk Management:** Integrates the Fractional Kelly Criterion to size positions dynamically based on real-time spread disparities and portfolio exposure limits.
*   **Sub-Millisecond Processing:** Achieves **~1ms Tick-to-Trade calculation latency** in pure Python through object caching and memory-efficient Pydantic data modeling.
*   **Fault-Tolerant Streaming:** Robust JSON parsing and dynamic WebSocket chunking (100 tokens per frame) to prevent API disconnections under heavy data loads.

## System Architecture

The engine is built on a modular, event-driven architecture:

1.  **Data Ingestion (`src/data`):** 
    *   REST API (`Gamma`): Fetches and filters active markets, bypassing IP blocks via TLS spoofing.
    *   WebSocket API (`CLOB`): Subscribes to thousands of tokens, handling non-JSON payloads and connection drops gracefully.
2.  **Core Logic (`src/live/paper_trader.py`):** An asynchronous orchestrator that receives raw WebSocket frames, parses them, and updates the in-memory order book state (O(1) lookups).
3.  **Alpha Generation (`src/detectors`):** The `IntraMarketArbDetector` constantly evaluates the synthetic cost of opposing sides (e.g., YES + NO). If the combined ask prices drop below a profitable threshold (e.g., $0.99), it flags an opportunity.
4.  **Risk & Execution (`src/risk` & `src/pricing`):** Validates the opportunity against capital limits and calculates the optimal bet size.

## ⏱️ Performance Metrics

*   **Network Latency (Inbound/Outbound):** ~30-60ms (Location dependent)
*   **Data Parsing & Processing:** ~1-3ms 
*   **Total Tick-to-Trade Latency:** ~70ms 
*(While not fast enough for HFT intra-market arbitrage against C++ bots, this infrastructure is perfectly suited for Logical/Cross-Market Arbitrage where inefficiencies persist for seconds).*

## Tech Stack

*   **Python 3.12+**
*   **Asyncio:** Non-blocking I/O for real-time market data streaming.
*   **Websockets:** Persistent connections to the Polymarket CLOB.
*   **Curl_cffi:** Impersonates Chrome to bypass Cloudflare bot detection.
*   **Pydantic:** Strict, memory-efficient data validation for Order Book models.
*   **Docker:** Containerized deployment for clean, OS-agnostic execution.

## Installation & Setup

### 🐳 Run with Docker (Recommended)
The easiest way to run the engine in an isolated, production-ready environment is via Docker. Ensure your host machine is routed through a supported VPN (e.g., Germany, Netherlands, Switzerland) to bypass geographic restrictions.

1. **Build the image:**
   ```bash
   docker build -t polymarket-arb-engine .
