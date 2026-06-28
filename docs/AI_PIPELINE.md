AI Trading System — AI_PIPELINE.md
1. Purpose

The AI Pipeline is responsible for:

Interpreting unstructured financial information
Extracting catalysts from news/filings/earnings
Enriching quantitative signals
Producing risk-aware reasoning
Supporting a learning loop (not replacing the quant model)

It is NOT responsible for:

Direct trade decisions without scoring engine
Scanning the entire market universe
Acting as a standalone strategy
2. AI Design Philosophy
2.1 AI is a feature generator, not a trader

AI produces:

Structured insights
Sentiment classification
Catalyst detection
Risk flags
Confidence adjustments

The trading engine decides execution.

2.2 Minimize AI calls (cost control)

AI is ONLY triggered when:

Stock passes quant filters
A catalyst event exists
Signal score > threshold (e.g. 70+)

Never run AI on full universe.

2.3 Multi-model hierarchy

We use 3 AI layers:

Layer 1: Cheap classifier model (optional)
Layer 2: GPT-5 reasoning model
Layer 3: Embedding + RAG retrieval system
3. AI Pipeline Flow
Raw News / Earnings / SEC filings
        ↓
Pre-filter (keyword + scoring)
        ↓
Embedding + similarity search
        ↓
RAG context builder
        ↓
GPT-5 reasoning call
        ↓
Structured JSON output
        ↓
Store in Firestore
4. Input Data Sources
4.1 News
Headlines
Full article text
Source credibility score
Timestamp
4.2 SEC Filings
8-K (events)
10-Q (quarterly)
10-K (annual)
4.3 Earnings
EPS surprise
Guidance changes
Transcript text
4.4 Market Context
Price trend snapshot
Volume spike indicator
Sector performance
5. RAG (Retrieval-Augmented Generation)
5.1 Vector Storage

We store embeddings for:

News articles
SEC filings
Earnings transcripts
Past AI reasoning outputs

Stored in:

ai_embeddings/
5.2 Retrieval Logic

For each event:

Identify ticker
Retrieve top 5–10 similar documents:
past news events
similar catalysts
historical reactions
Inject into prompt
6. GPT-5 Prompt Structure
6.1 System Prompt
You are a financial analysis assistant for a quantitative trading system.

Your job:
- Identify catalysts
- Assess sentiment
- Detect risks
- Provide structured reasoning

You must NOT:
- Recommend direct trades without context
- Ignore risk factors
- Provide vague explanations
6.2 User Prompt Template
TICKER: {ticker}

NEWS:
{news_text}

MARKET CONTEXT:
- Price change: {price_change}
- Volume spike: {volume}
- Sector trend: {sector_trend}

RETRIEVED CONTEXT (RAG):
{similar_events}

FEATURE SUMMARY:
{features}

Return JSON only:
7. AI Output Schema

Every AI call MUST return structured JSON:

{
  "ticker": "NVDA",

  "catalystType": "earnings | news | macro | insider | unknown",

  "sentiment": "positive | neutral | negative",

  "summary": "Short explanation of key driver",

  "keyInsights": [
    "AI demand accelerating",
    "Cloud capex increasing"
  ],

  "riskFactors": [
    "valuation stretched",
    "macro sensitivity"
  ],

  "confidence": 0.82,

  "confidenceAdjustment": 0.10,

  "catalyst_direction": "bullish | neutral | bearish",

  "ai_bias": 0.18,

  "unexpectedSignals": [
    "options flow unusually bullish"
  ]
}

AI output is never trade authority. It may describe catalyst direction and bias, but the trading system must not treat those fields as permission to buy, sell, or bypass risk.
8. Embedding Strategy

We use embeddings for:

Semantic news similarity
Event clustering
Catalyst pattern recognition
Model:
OpenAI embeddings (text-embedding-3-large or equivalent)
Storage:
ai_embeddings/
    news/
    filings/
    earnings/
    insights/
9. Catalyst Detection Engine

Before calling GPT:

We detect triggers using rules:

Examples:
IF headline contains:
- "announces"
- "beats expectations"
- "guidance raised"
- "FDA approval"
- "contract awarded"

THEN trigger AI pipeline
10. AI Cost Optimization Strategy

We aggressively reduce API usage:

Step 1: Filter 6000 stocks → 100
Step 2: Quant score → 20
Step 3: Catalyst filter → 5–10
Step 4: AI → only top candidates

Result:

~10–30 AI calls per day max
11. Learning Loop (Very Important)

Each AI decision is stored with outcome:

input_features
AI_output
trade_result
market_conditions

This allows:

Fine-tuning prompts
Feature importance discovery
Strategy evolution
12. AI Failure Handling

If AI fails:

Phase 1 may continue producing quant-only signals without execution authority
Phase 3+ trade execution is blocked until ai_analysis_id exists
Failure is logged
13. Versioning Strategy

We version all AI logic:

reasoningVersion: gpt-5-v1
promptVersion: 1.0
embeddingVersion: v1

This ensures reproducibility.

14. Key Design Insight

The AI is NOT the edge.

The edge is:

AI + structured market data + strict quant filtering + feedback loop

AI alone is noise.