"""
HYDRA Arm 3 — Regulatory Intelligence Service

Provides rule-based regulatory analysis without requiring external AI APIs.

Capabilities:
  1. Risk scoring — matches business description keywords against regulatory triggers
  2. Jurisdiction comparison — structured data for US states + international
  3. Regulatory Q&A — keyword-matched answers from knowledge base
  4. Applicable regulations — maps business activities to specific laws

Knowledge base covers:
  Federal: Securities Act 1933, Exchange Act 1934, Investment Company Act 1940,
           Investment Advisers Act 1940, Commodity Exchange Act, Bank Secrecy Act,
           USA PATRIOT Act, Dodd-Frank, JOBS Act, Regulation D, Regulation A+,
           Regulation CF, FinCEN CDD Rule, AML/KYC requirements
  State:   Wyoming, Delaware, Nevada, Texas, New York (BitLicense),
           California, Florida, Wyoming DAO LLC Act
  Crypto:  MiCA (EU), FCA (UK), MAS (Singapore), FinCEN guidance on VC
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.models.schemas import (
    ApplicableRegulation,
    BusinessType,
    JurisdictionComparisonResponse,
    JurisdictionProfile,
    JurisdictionRequirement,
    RegulatoryQueryResponse,
    RegulatoryScenResponse,
    RiskLevel,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Regulatory Trigger Keywords → Regulations
# ─────────────────────────────────────────────────────────────

REGULATORY_TRIGGERS: list[dict[str, Any]] = [
    # Securities offerings
    {
        "keywords": ["invest", "equity", "securities", "stock", "share", "fund", "capital raise",
                     "token sale", "ico", "sto", "tokenized", "investment", "investor",
                     "accredited", "crowdfund", "reg d", "regulation d", "offering"],
        "regulation": ApplicableRegulation(
            name="Securities Act of 1933",
            citation="15 U.S.C. § 77a et seq.",
            regulator="SEC",
            relevance="Any offer or sale of securities must be registered or qualify for an exemption",
            risk_level=RiskLevel.HIGH,
            description=(
                "The Securities Act of 1933 requires registration of securities offerings with the SEC "
                "unless an exemption applies (Reg D, Reg A+, Reg CF, Reg S, etc.). "
                "Tokens that meet the Howey test are likely securities."
            ),
            recommended_actions=[
                "Conduct Howey test analysis to determine if tokens/instruments qualify as securities",
                "If securities: register offering or qualify for exemption (Reg D 506(b)/506(c), Reg A+, Reg CF)",
                "Engage securities counsel before any public offering",
                "File Form D within 15 days of first sale under Reg D",
                "Implement investor accreditation verification procedures if using Reg D 506(b)",
            ],
        ),
        "risk_weight": 25,
    },
    # Broker-dealer
    {
        "keywords": ["broker", "dealer", "exchange", "trading platform", "buy and sell",
                     "secondary market", "marketplace", "otc", "dark pool", "market maker",
                     "order book", "trade execution"],
        "regulation": ApplicableRegulation(
            name="Securities Exchange Act of 1934 — Broker-Dealer Registration",
            citation="15 U.S.C. § 78o; 17 C.F.R. § 240.15a-1",
            regulator="SEC / FINRA",
            relevance="Entities effecting securities transactions or inducing their purchase/sale must register as broker-dealers",
            risk_level=RiskLevel.CRITICAL,
            description=(
                "Any person engaged in the business of effecting transactions in securities for others must "
                "register as a broker-dealer with the SEC and become a FINRA member. "
                "Operating an unregistered securities exchange is a federal crime."
            ),
            recommended_actions=[
                "Register as broker-dealer via Form BD with the SEC and FINRA",
                "Alternatively, consider operating as an ATS (Alternative Trading System) if volume qualifies",
                "Explore whether a no-action letter or exemption applies (e.g., 15a-6 for foreign broker-dealers)",
                "Implement robust KYC/AML program as required by FINRA Rule 3310",
                "Designate a Chief Compliance Officer (CCO) and establish written supervisory procedures (WSP)",
            ],
        ),
        "risk_weight": 30,
    },
    # Investment adviser
    {
        "keywords": ["investment advice", "financial advice", "portfolio management", "wealth management",
                     "investment advisory", "robo-advisor", "investment manager", "asset management",
                     "advise on investments", "investment recommendations"],
        "regulation": ApplicableRegulation(
            name="Investment Advisers Act of 1940",
            citation="15 U.S.C. § 80b-1 et seq.",
            regulator="SEC / State Securities Regulators",
            relevance="Persons in the business of providing investment advice for compensation must register",
            risk_level=RiskLevel.HIGH,
            description=(
                "Investment advisers managing ≥$100M in assets must register with the SEC. "
                "Those managing $25M–$100M register with state regulators. "
                "Registered advisers owe a fiduciary duty to clients."
            ),
            recommended_actions=[
                "Register with SEC (Form ADV) if AUM ≥$100M, or with state regulators if $25M–$100M",
                "Consider IA exemptions: venture capital fund adviser, private fund adviser (<$150M)",
                "Implement written compliance policies per Advisers Act Rule 206(4)-7",
                "Designate Chief Compliance Officer (CCO) and conduct annual compliance review",
                "Disclose conflicts of interest in Form ADV Part 2A (brochure)",
            ],
        ),
        "risk_weight": 20,
    },
    # Money transmission / payments
    {
        "keywords": ["transfer money", "money transmitter", "payment", "remittance", "wire",
                     "mobile payment", "digital wallet", "stored value", "prepaid", "e-money",
                     "payment processor", "merchant services", "money services business",
                     "msb", "cryptocurrency exchange", "crypto exchange", "virtual currency",
                     "bitcoin", "ethereum", "usdc", "stablecoin", "send funds"],
        "regulation": ApplicableRegulation(
            name="Bank Secrecy Act / FinCEN Money Services Business Registration",
            citation="31 U.S.C. § 5311 et seq.; 31 C.F.R. Part 1010",
            regulator="FinCEN",
            relevance="Money services businesses must register with FinCEN and implement AML programs",
            risk_level=RiskLevel.HIGH,
            description=(
                "Entities operating as money services businesses (MSBs) — including money transmitters, "
                "cryptocurrency exchangers, and administrators of convertible virtual currency — must register "
                "with FinCEN within 180 days of establishing the business. "
                "MSBs must maintain anti-money laundering (AML) programs and file SARs and CTRs."
            ),
            recommended_actions=[
                "Register with FinCEN as an MSB via BSA E-Filing System",
                "Implement written AML program: policies, procedures, internal controls",
                "Designate AML Compliance Officer",
                "Conduct employee AML training annually",
                "File Suspicious Activity Reports (SARs) for transactions ≥$2,000 involving suspected crime",
                "File Currency Transaction Reports (CTRs) for cash transactions >$10,000",
                "Apply Customer Due Diligence (CDD) and Know Your Customer (KYC) procedures",
            ],
        ),
        "risk_weight": 25,
    },
    # State money transmitter licenses
    {
        "keywords": ["transfer money", "money transmitter", "payment", "remittance",
                     "cryptocurrency exchange", "crypto exchange", "virtual currency exchange",
                     "mobile payment", "digital wallet", "stored value"],
        "regulation": ApplicableRegulation(
            name="State Money Transmitter Licenses (MTLs)",
            citation="Various state statutes (e.g., NY Banking Law § 641; CA Fin. Code § 2030)",
            regulator="State Banking Regulators (50 states + DC + territories)",
            relevance="Most states require separate MTLs for money transmission; NY BitLicense for virtual currency",
            risk_level=RiskLevel.HIGH,
            description=(
                "Operating a money transmission business typically requires licenses in each state where you "
                "serve customers. 49 states plus DC require money transmitter licenses. "
                "New York additionally requires a BitLicense for virtual currency businesses. "
                "The NMLS (Nationwide Multistate Licensing System) manages most state MTL applications."
            ),
            recommended_actions=[
                "Map your customer base and obtain MTLs in all applicable states",
                "Apply for NY BitLicense if serving New York customers (cryptocurrency)",
                "Use NMLS for multi-state licensing efficiency",
                "Consider surety bond requirements (typically $25K–$5M per state)",
                "Evaluate Wyoming's Special Purpose Depository Institution (SPDI) charter as alternative",
                "Evaluate the Uniform Money Transmission Modernization Act (UMTMA) states for streamlined licensing",
            ],
        ),
        "risk_weight": 20,
    },
    # Lending
    {
        "keywords": ["loan", "lending", "credit", "borrow", "mortgage", "consumer finance",
                     "installment", "payday", "underwriting", "credit scoring", "BNPL",
                     "buy now pay later", "interest rate", "APR"],
        "regulation": ApplicableRegulation(
            name="Truth in Lending Act (TILA) / Regulation Z",
            citation="15 U.S.C. § 1601 et seq.; 12 C.F.R. Part 1026",
            regulator="CFPB",
            relevance="Consumer credit products must clearly disclose APR, fees, and terms",
            risk_level=RiskLevel.HIGH,
            description=(
                "Regulation Z (implementing TILA) requires creditors to disclose credit terms clearly "
                "and standardize APR disclosures for consumer credit. "
                "Violations can result in actual damages, statutory damages up to $1M in class actions, "
                "and attorney's fees."
            ),
            recommended_actions=[
                "Provide required Regulation Z disclosures before credit is extended",
                "Calculate and disclose APR accurately",
                "Register as non-bank consumer lender in each state of operation",
                "Comply with state usury laws (interest rate caps vary by state)",
                "Implement ECOA / Fair Lending policies to prevent discriminatory lending",
                "For BNPL: monitor CFPB interpretive guidance on TILA applicability",
            ],
        ),
        "risk_weight": 20,
    },
    # Banking / deposits
    {
        "keywords": ["bank", "banking", "deposit", "fdic", "insured", "savings account",
                     "checking account", "debit card", "chartered", "SPDI", "neo-bank",
                     "banking-as-a-service", "BaaS"],
        "regulation": ApplicableRegulation(
            name="National Bank Act / Federal Deposit Insurance Act",
            citation="12 U.S.C. § 1 et seq.; 12 U.S.C. § 1811 et seq.",
            regulator="OCC / FDIC / Federal Reserve",
            relevance="Accepting deposits requires a bank charter and FDIC insurance in the US",
            risk_level=RiskLevel.CRITICAL,
            description=(
                "Taking deposits from the public requires either a federal or state banking charter. "
                "Federal banks are chartered by the OCC; state banks are chartered by state banking authorities "
                "and supervised by the FDIC or Federal Reserve. "
                "Representing deposits as FDIC-insured without proper authorization violates federal law."
            ),
            recommended_actions=[
                "Obtain OCC national bank charter or state banking charter",
                "Alternatively, partner with an FDIC-insured bank sponsor for Banking-as-a-Service",
                "If offering crypto banking: consider Wyoming SPDI charter or OCC FinTech charter",
                "Never use terms 'bank', 'savings', or 'FDIC insured' without proper authorization",
                "Comply with Community Reinvestment Act (CRA) if taking deposits",
            ],
        ),
        "risk_weight": 35,
    },
    # Crypto / DeFi
    {
        "keywords": ["defi", "decentralized finance", "smart contract", "blockchain", "nft",
                     "non-fungible", "dao", "decentralized autonomous", "yield farming",
                     "liquidity pool", "amm", "automated market maker", "staking",
                     "governance token", "web3", "dex", "decentralized exchange"],
        "regulation": ApplicableRegulation(
            name="SEC Digital Asset Framework / CFTC Commodity Classification",
            citation="SEC Framework for Investment Contract Analysis of Digital Assets (Apr. 2019); CFTC Guidance",
            regulator="SEC / CFTC",
            relevance="Digital assets may be securities (SEC) or commodities (CFTC) depending on their characteristics",
            risk_level=RiskLevel.HIGH,
            description=(
                "The SEC uses the Howey test to determine whether digital assets are securities. "
                "The CFTC has asserted jurisdiction over crypto commodities (BTC, ETH) and derivatives. "
                "DeFi protocols may be considered unregistered securities exchanges, broker-dealers, or "
                "investment companies depending on their structure."
            ),
            recommended_actions=[
                "Conduct Howey test analysis for each token/asset",
                "Evaluate whether protocol constitutes an unregistered securities exchange",
                "Consider SEC's DAO Report and subsequent guidance on token classification",
                "Review CFTC enforcement actions against DeFi protocols",
                "Consider legal opinions on commodity vs. security classification for each asset",
                "Implement geofencing to exclude US persons if not registered with SEC/CFTC",
            ],
        ),
        "risk_weight": 20,
    },
    # KYC / AML
    {
        "keywords": ["kyc", "know your customer", "identity verification", "aml", "anti-money laundering",
                     "sanctions", "ofac", "terrorist financing", "cdd", "customer due diligence",
                     "beneficial ownership", "politically exposed", "pep"],
        "regulation": ApplicableRegulation(
            name="FinCEN Customer Due Diligence (CDD) Rule / AML Program Requirements",
            citation="31 C.F.R. § 1010.230; 31 C.F.R. § 1020.210",
            regulator="FinCEN / OFAC",
            relevance="Covered financial institutions must collect beneficial ownership information and maintain AML programs",
            risk_level=RiskLevel.HIGH,
            description=(
                "The FinCEN CDD Rule (effective May 2018) requires covered financial institutions to identify "
                "and verify the identity of the beneficial owners of legal entity customers (>25% ownership "
                "or managerial control). OFAC sanctions compliance requires screening against SDN List."
            ),
            recommended_actions=[
                "Implement KYC procedures: identity verification for all customers",
                "Collect beneficial ownership information for legal entity customers",
                "Screen customers and transactions against OFAC SDN List",
                "Integrate real-time sanctions screening into onboarding and transaction monitoring",
                "File SARs within 30 days of detecting suspicious activity",
                "Retain records for 5 years (BSA requirement)",
            ],
        ),
        "risk_weight": 15,
    },
    # Derivatives / futures
    {
        "keywords": ["derivative", "futures", "options", "swap", "forward", "commodity pool",
                     "commodity trading", "cta", "cpd", "commodity pool operator",
                     "commodity trading advisor", "fx", "forex", "leveraged trading"],
        "regulation": ApplicableRegulation(
            name="Commodity Exchange Act / CFTC Registration",
            citation="7 U.S.C. § 1 et seq.; 17 C.F.R. Parts 1–190",
            regulator="CFTC / NFA",
            relevance="Trading or advising on commodity derivatives requires CFTC registration through NFA",
            risk_level=RiskLevel.HIGH,
            description=(
                "The Commodity Exchange Act regulates futures, swaps, and options on commodities. "
                "Commodity Pool Operators (CPOs) and Commodity Trading Advisors (CTAs) must register with "
                "the CFTC through the NFA. Retail foreign exchange dealers (RFEDs) must also register."
            ),
            recommended_actions=[
                "Register CPO/CTA with CFTC via NFA membership",
                "Comply with CFTC disclosure document requirements",
                "Implement risk management and position limit procedures",
                "For swap dealers: register with CFTC, comply with Title VII Dodd-Frank requirements",
                "Consider NFA self-regulatory requirements",
            ],
        ),
        "risk_weight": 20,
    },
    # Data privacy
    {
        "keywords": ["personal data", "user data", "privacy", "gdpr", "ccpa", "data collection",
                     "data processing", "biometric", "location data", "consumer data",
                     "data broker", "targeted advertising"],
        "regulation": ApplicableRegulation(
            name="CCPA / GDPR — Consumer Data Privacy",
            citation="Cal. Civ. Code § 1798.100 et seq. (CCPA); EU Regulation 2016/679 (GDPR)",
            regulator="California AG / EU Data Protection Authorities",
            relevance="Businesses collecting personal data from California residents or EU persons must comply",
            risk_level=RiskLevel.MEDIUM,
            description=(
                "CCPA grants California consumers rights to know, delete, and opt-out of sale of personal data. "
                "GDPR (applicable to EU persons anywhere) requires lawful basis for processing, data minimization, "
                "and imposes fines up to 4% of global revenue for violations."
            ),
            recommended_actions=[
                "Publish Privacy Policy disclosing data collection, use, and sharing practices",
                "Implement CCPA opt-out mechanism ('Do Not Sell My Personal Information')",
                "For GDPR: identify lawful basis for each processing activity",
                "Appoint Data Protection Officer (DPO) if required by GDPR",
                "Implement data breach notification procedures (72-hour GDPR window)",
                "Conduct Data Protection Impact Assessments (DPIAs) for high-risk processing",
            ],
        ),
        "risk_weight": 10,
    },
]


# ─────────────────────────────────────────────────────────────
# Jurisdiction Data
# ─────────────────────────────────────────────────────────────

JURISDICTION_DATA: dict[str, dict[str, Any]] = {
    "WY": {
        "full_name": "Wyoming, USA",
        "overall_friendliness": "very_friendly",
        "friendliness_score": 95,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="Entity Formation",
                    requirement="Wyoming DAO LLC Act (W.S. § 17-31-101 et seq.) — first US state to legally recognize DAOs",
                    notes="DAOs can organize as limited liability companies with on-chain governance",
                ),
                JurisdictionRequirement(
                    category="Banking",
                    requirement="Wyoming Special Purpose Depository Institution (SPDI) charter available",
                    notes="SPDIs can hold digital assets, issue stablecoins, provide custodial services without FDIC insurance",
                ),
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="No state MTL required for virtual currency-only businesses (W.S. § 40-22-104)",
                    notes="Wyoming exempted virtual currency from money transmission licensing in 2019",
                ),
                JurisdictionRequirement(
                    category="Property Tax",
                    requirement="Virtual currency classified as intangible property — may be exempt from property tax",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Fintech Sandbox",
                    requirement="Wyoming Sandbox (W.S. § 40-29-101) — 2-year regulatory relief for innovative financial products",
                ),
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="Standard MTL required for fiat money transmission",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="Securities Registration",
                    requirement="Wyoming Uniform Securities Act — state securities registration required for intrastate offerings",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="State Charter",
                    requirement="Wyoming Division of Banking issues state bank charters and SPDI charters",
                    notes="SPDI is unique to Wyoming — allows crypto custody without FDIC insurance requirement",
                ),
            ],
        },
        "key_advantages": [
            "First state to legally recognize DAOs as LLCs",
            "No state income tax",
            "No franchise tax",
            "SPDI charter enables crypto banking without FDIC requirement",
            "Virtual currency exempt from money transmission licensing",
            "Strong LLC privacy protections",
            "Fintech regulatory sandbox available",
        ],
        "key_risks": [
            "Small state — limited local legal/compliance talent pool",
            "SPDI charter requires substantial capital (minimum $5M or 5% of assets)",
            "Federal regulation (SEC, CFTC, FinCEN) still applies regardless of state",
        ],
        "notable_regulations": [
            "Wyoming DAO LLC Act (2021) — W.S. § 17-31-101",
            "Wyoming SPDI Act (2020) — W.S. § 13-12-101",
            "Virtual Currency Exemption (2019) — W.S. § 40-22-104",
            "Wyoming Digital Asset Act (2019) — W.S. § 34-29-101",
            "Wyoming Sandbox (2019) — W.S. § 40-29-101",
        ],
        "incorporation_cost_usd": "$100 filing fee",
        "time_to_incorporate_days": "1-3 business days",
    },
    "DE": {
        "full_name": "Delaware, USA",
        "overall_friendliness": "friendly",
        "friendliness_score": 85,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="Entity Formation",
                    requirement="Standard Delaware LLC or Corporation — well-established corporate law",
                    notes="No specific crypto legislation; tokens may be securities under Delaware law if they meet Howey test",
                ),
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="Delaware MTL required for money transmission including virtual currency (5 Del. C. § 2301)",
                    notes="Delaware issued guidance including virtual currency in MTL requirements",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="Delaware MTL required — issued by Delaware Office of the State Bank Commissioner",
                ),
                JurisdictionRequirement(
                    category="Lending",
                    requirement="Consumer lending license may be required under Delaware Licensed Lenders Act",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="Securities",
                    requirement="Delaware Securities Act — intrastate securities registration",
                    notes="Most VC-backed companies incorporate in Delaware for Court of Chancery expertise",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="State Charter",
                    requirement="Delaware State Banking Commissioner issues state bank charters",
                    notes="Delaware is popular for credit card banks (MBNA, Discover historically chartered here)",
                ),
            ],
        },
        "key_advantages": [
            "Most popular US state for incorporation (67% of Fortune 500)",
            "Court of Chancery — specialized business court with sophisticated precedent",
            "Flexible LLC and corporation law",
            "Well-understood by VCs and institutional investors",
            "No sales tax",
            "No income tax on companies not operating in Delaware",
        ],
        "key_risks": [
            "Franchise tax can be significant for large authorized share counts (alternative calculation recommended)",
            "No specific crypto-friendly legislation",
            "MTL required for virtual currency transmission",
            "Must register as foreign entity in state of actual operations",
        ],
        "notable_regulations": [
            "Delaware General Corporation Law (DGCL) — Title 8 Del. C.",
            "Delaware LLC Act — 6 Del. C. § 18-101",
            "Delaware Securities Act — 6 Del. C. § 7301",
            "Licensed Lenders Act — 5 Del. C. § 2201",
            "Money Transmitters Act — 5 Del. C. § 2301",
        ],
        "incorporation_cost_usd": "$90 filing fee (LLC) / $89+ (corporation)",
        "time_to_incorporate_days": "1-2 business days",
    },
    "NV": {
        "full_name": "Nevada, USA",
        "overall_friendliness": "friendly",
        "friendliness_score": 78,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="Virtual Currency",
                    requirement="Nevada Blockchain Act (NRS § 719) — legal recognition of blockchain records and smart contracts",
                    notes="Nevada recognizes blockchain-based records as valid legal records",
                ),
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="Nevada MTL required — issued by Nevada Financial Institutions Division",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Regulatory Sandbox",
                    requirement="Nevada Regulatory Experimentation Program (NRS § 657A) — sandbox for financial services",
                    notes="Up to 2-year sandbox period with waiver of certain licensing requirements",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="Securities",
                    requirement="Nevada Securities Act (NRS § 90) — Blue Sky law",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="State Charter",
                    requirement="Nevada Financial Institutions Division regulates state-chartered banks",
                ),
            ],
        },
        "key_advantages": [
            "No state corporate income tax",
            "No personal income tax",
            "Strong corporate privacy (no public disclosure of beneficial owners)",
            "Blockchain Act legally recognizes smart contracts",
            "FinTech regulatory sandbox",
            "Favorable litigation environment for corporations",
        ],
        "key_risks": [
            "Commerce tax on gross revenues >$4M (0.051%–0.331%)",
            "Less established corporate law precedent than Delaware",
            "MTL required for crypto money transmission",
        ],
        "notable_regulations": [
            "Nevada Blockchain Act (2019) — NRS § 719",
            "Nevada Securities Act — NRS § 90",
            "Nevada Financial Institutions Division regulations — NRS § 671",
            "Regulatory Experimentation Program — NRS § 657A",
        ],
        "incorporation_cost_usd": "$75 filing fee (LLC)",
        "time_to_incorporate_days": "1-5 business days",
    },
    "NY": {
        "full_name": "New York, USA",
        "overall_friendliness": "restrictive",
        "friendliness_score": 30,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="BitLicense",
                    requirement="NY DFS BitLicense required to conduct virtual currency business activity with NY residents",
                    notes="Application fee: $5,000; extensive documentation, AML program, capital requirements; often takes 1-2 years",
                ),
                JurisdictionRequirement(
                    category="Limited Purpose Trust Charter",
                    requirement="Alternative to BitLicense — NY Banking Law Article III limited purpose trust charter",
                    notes="Higher capital requirements but broader banking powers",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="NY MTL required — issued by NY DFS; one of the most onerous in the US",
                ),
                JurisdictionRequirement(
                    category="Lending",
                    requirement="NY Licensed Lender required for consumer lending",
                    notes="NY usury law caps: 16% civil, 25% criminal — some exemptions for licensed banks",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="Martin Act",
                    requirement="New York Martin Act (GBL § 352 et seq.) — broad state securities fraud liability",
                    notes="No scienter requirement for Martin Act fraud — among the most aggressive state securities laws",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="State Charter",
                    requirement="NY DFS charters state banks, limited purpose trust companies, and private bankers",
                ),
            ],
        },
        "key_advantages": [
            "World's leading financial center — access to capital, talent, partners",
            "NY courts widely recognized for sophisticated commercial dispute resolution",
            "Prestigious address for financial services",
        ],
        "key_risks": [
            "BitLicense is notoriously expensive and slow (1-2 years, $5,000+ in fees)",
            "Martin Act creates broad liability for securities fraud without intent requirement",
            "High regulatory compliance costs",
            "NY DFS actively enforces against unlicensed crypto businesses",
            "High cost of operations (rent, salaries)",
        ],
        "notable_regulations": [
            "NY BitLicense — 23 NYCRR § 200",
            "New York Martin Act — GBL § 352 et seq.",
            "NY Banking Law — Article III (Limited Purpose Trust Charters)",
            "NY Licensed Lender Act — Banking Law § 340",
            "NY Uniform Commercial Code",
        ],
        "incorporation_cost_usd": "$200 filing fee (LLC) + biennial fee",
        "time_to_incorporate_days": "7-14 business days",
    },
    "TX": {
        "full_name": "Texas, USA",
        "overall_friendliness": "friendly",
        "friendliness_score": 75,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="Virtual Currency",
                    requirement="Texas Virtual Currency Act (Tex. Fin. Code § 12.001) — virtual currency is legal property; cryptocurrency exchanges may require MTL",
                    notes="Texas DBA issued guidance that most virtual currency transactions require MTL",
                ),
                JurisdictionRequirement(
                    category="Mining",
                    requirement="Texas has attracted Bitcoin mining due to deregulated power market and no state income tax",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Money Transmission",
                    requirement="Texas MTL required — issued by Texas Department of Banking",
                    notes="Texas is a signatory to the CSBS multi-state MSB licensing initiative",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="Texas Securities Act",
                    requirement="Texas Securities Act (Tex. Rev. Civ. Stat. art. 581) — securities registration required unless exempt",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="State Charter",
                    requirement="Texas Department of Banking issues state bank charters",
                ),
            ],
        },
        "key_advantages": [
            "No state income tax",
            "Business-friendly regulatory environment",
            "Large talent pool (tech sector in Austin)",
            "Low cost of operations vs. NY/CA",
            "Strong crypto and mining community",
        ],
        "key_risks": [
            "MTL required for crypto exchanges",
            "Property tax is relatively high",
            "Franchise tax (margin tax) applies to most businesses",
        ],
        "notable_regulations": [
            "Texas Virtual Currency Act — Tex. Fin. Code § 12.001",
            "Texas Money Services Act — Tex. Fin. Code § 151",
            "Texas Securities Act — Tex. Rev. Civ. Stat. art. 581",
        ],
        "incorporation_cost_usd": "$300 filing fee (LLC)",
        "time_to_incorporate_days": "3-5 business days",
    },
    "EU": {
        "full_name": "European Union",
        "overall_friendliness": "neutral",
        "friendliness_score": 55,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="MiCA",
                    requirement="Markets in Crypto-Assets Regulation (MiCA) — EU Regulation 2023/1114, fully applicable from Dec 2024",
                    notes="Crypto-asset service providers (CASPs) must be authorized; stablecoin issuers face enhanced requirements",
                ),
                JurisdictionRequirement(
                    category="AML",
                    requirement="EU AML Directive (AMLD6) — crypto service providers are obliged entities",
                    notes="KYC/AML requirements apply; travel rule (FATF) applies to transfers",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="PSD2",
                    requirement="Payment Services Directive 2 (PSD2) — requires authorization as Payment Institution or E-Money Institution",
                    notes="Passporting allows single authorization to operate across all EU member states",
                ),
                JurisdictionRequirement(
                    category="GDPR",
                    requirement="General Data Protection Regulation — comprehensive data privacy requirements",
                    notes="Fines up to €20M or 4% of global turnover for violations",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="MiFID II",
                    requirement="Markets in Financial Instruments Directive II — authorization required for investment services",
                    notes="Passporting allows single authorization for all EU member states",
                ),
                JurisdictionRequirement(
                    category="Prospectus",
                    requirement="EU Prospectus Regulation — public offerings >€8M require approved prospectus",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="Banking License",
                    requirement="EU Banking Directive (CRD V) — credit institutions require authorization from national competent authority",
                    notes="ECB directly supervises significant institutions",
                ),
            ],
        },
        "key_advantages": [
            "Single market access (27 countries) with one authorization via passporting",
            "MiCA provides legal clarity for crypto businesses",
            "PSD2 enables Open Banking and fintech innovation",
            "Strong investor trust due to regulatory oversight",
        ],
        "key_risks": [
            "High compliance costs — MiCA requires dedicated compliance infrastructure",
            "GDPR penalties are substantial (up to 4% global revenue)",
            "Regulatory heterogeneity — member state implementation varies",
            "MiCA stablecoin rules are strict (asset reserve requirements)",
        ],
        "notable_regulations": [
            "MiCA — EU Regulation 2023/1114",
            "GDPR — EU Regulation 2016/679",
            "PSD2 — EU Directive 2015/2366",
            "MiFID II — EU Directive 2014/65/EU",
            "AMLD6 — EU Directive 2021/1160",
        ],
        "incorporation_cost_usd": "Varies by member state (€100–€2,500+)",
        "time_to_incorporate_days": "Varies (1 day in Estonia to 2+ weeks in Germany)",
    },
    "UK": {
        "full_name": "United Kingdom",
        "overall_friendliness": "neutral",
        "friendliness_score": 65,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="FCA Registration",
                    requirement="FCA cryptoasset business registration required under MLRs 2017 (as amended)",
                    notes="Separate from full FCA authorization — anti-money laundering focused; approval rate has been low (<50%)",
                ),
                JurisdictionRequirement(
                    category="Financial Promotion",
                    requirement="UK financial promotion rules apply to crypto marketing since October 2023",
                    notes="Must be approved by FCA-authorized person; clear risk warnings required",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="FCA Authorization",
                    requirement="FCA authorization required for regulated activities (payment services, investment management, etc.)",
                    notes="FCA sandbox (regulatory sandbox) available for innovative firms",
                ),
                JurisdictionRequirement(
                    category="PSD2 (UK)",
                    requirement="UK Payment Services Regulations 2017 — FCA authorization as PI or EMI required",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="FCA Authorization",
                    requirement="FCA Part 4A permission required for investment activities under FSMA 2000",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="PRA / FCA Authorization",
                    requirement="Dual regulation by PRA (prudential) and FCA (conduct) for banks",
                    notes="New Bank Start-up Unit (NBSU) supports new bank applications",
                ),
            ],
        },
        "key_advantages": [
            "FCA regulatory sandbox — test innovative products with regulatory support",
            "Strong fintech ecosystem (London)",
            "Common law legal system",
            "Post-Brexit ability to diverge from EU regulation (potential future advantage)",
            "Competitive regulatory environment for fintech",
        ],
        "key_risks": [
            "FCA crypto registration approval rate has been low and slow",
            "Post-Brexit loss of EU passporting",
            "Evolving crypto regulation (Digital Securities Sandbox, crypto regime under Financial Services Act 2023)",
            "FCA financial promotion rules create significant marketing restrictions",
        ],
        "notable_regulations": [
            "Financial Services and Markets Act 2000 (FSMA)",
            "Money Laundering Regulations 2017 (MLRs) — as amended for crypto",
            "Financial Promotion Order",
            "UK Payment Services Regulations 2017",
            "Financial Services Act 2023",
        ],
        "incorporation_cost_usd": "£12 Companies House filing fee (~$15)",
        "time_to_incorporate_days": "24-48 hours",
    },
    "SG": {
        "full_name": "Singapore",
        "overall_friendliness": "friendly",
        "friendliness_score": 82,
        "requirements_by_type": {
            "crypto": [
                JurisdictionRequirement(
                    category="MAS License",
                    requirement="Payment Services Act (PSA) license required for Digital Payment Token (DPT) services",
                    notes="MAS licenses: Standard Payment Institution (SPI) or Major Payment Institution (MPI) depending on volume",
                ),
                JurisdictionRequirement(
                    category="AML",
                    requirement="MAS Notice PSN02 — AML/CFT requirements for DPT service providers",
                ),
            ],
            "fintech": [
                JurisdictionRequirement(
                    category="Regulatory Sandbox",
                    requirement="MAS Fintech Regulatory Sandbox — test innovative financial services under relaxed regulations",
                ),
                JurisdictionRequirement(
                    category="PSA License",
                    requirement="Payment Services Act license for payment services",
                ),
            ],
            "securities": [
                JurisdictionRequirement(
                    category="MAS Authorization",
                    requirement="Capital Markets Services (CMS) license required for securities activities",
                ),
            ],
            "banking": [
                JurisdictionRequirement(
                    category="Banking License",
                    requirement="MAS banking license; Digital Full Bank (DFB) licenses available for non-bank digital players",
                    notes="MAS issued 4 digital bank licenses in 2020 (GrabPay, SEA/Shopee, Ant Group, Green Link)",
                ),
            ],
        },
        "key_advantages": [
            "Proactive and technology-forward regulator (MAS)",
            "Fintech and crypto regulatory sandbox",
            "Strategic Asia-Pacific hub",
            "No capital gains tax",
            "Low corporate income tax (17% flat)",
            "Strong rule of law and IP protection",
        ],
        "key_risks": [
            "PSA licensing process is rigorous and can take 12+ months",
            "MAS has been tightening crypto retail access",
            "High operating costs (Singapore is expensive)",
            "Recent retail crypto advertising restrictions",
        ],
        "notable_regulations": [
            "Payment Services Act 2019 (PSA) — Cap. 225",
            "Securities and Futures Act — Cap. 289",
            "Financial Advisers Act — Cap. 110",
            "MAS Notice PSN02 (AML/CFT for DPT)",
        ],
        "incorporation_cost_usd": "$315 SGD filing fee (~$235 USD)",
        "time_to_incorporate_days": "1-3 business days",
    },
}


# ─────────────────────────────────────────────────────────────
# Q&A Knowledge Base
# ─────────────────────────────────────────────────────────────

QA_KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "keywords": ["money transmitter", "MTL", "Wyoming", "crypto exchange", "Wyoming MTL"],
        "question_patterns": ["money transmitter license wyoming", "wyoming crypto exchange license",
                               "mtl wyoming", "wyoming money transmission"],
        "answer": (
            "Wyoming does not require a money transmitter license (MTL) for businesses dealing exclusively "
            "in virtual currency. Wyoming Statute § 40-22-104 exempts virtual currency from the state's "
            "money transmission licensing requirements. This makes Wyoming uniquely attractive for "
            "crypto-native businesses. However, you still must register with FinCEN as a Money Services "
            "Business (MSB) at the federal level, and you must comply with federal AML/KYC requirements "
            "under the Bank Secrecy Act. If you transmit fiat currency (USD), a Wyoming MTL is required. "
            "Note that serving customers in other states triggers MTL requirements in those states."
        ),
        "relevant_regulations": [
            "Wyoming Statute § 40-22-104 (Virtual Currency Exemption)",
            "Bank Secrecy Act — 31 U.S.C. § 5311",
            "FinCEN Guidance FIN-2013-G001 (Virtual Currency)",
        ],
        "relevant_agencies": ["FinCEN", "Wyoming Division of Banking"],
        "confidence": "high",
        "follow_up_questions": [
            "Do I need to register with FinCEN as an MSB even if Wyoming doesn't require an MTL?",
            "What AML program is required for a Wyoming crypto exchange?",
            "Do I need an MTL in other states if I serve customers there?",
        ],
    },
    {
        "keywords": ["ny bitlicense", "new york", "virtual currency license", "bitlicense requirements",
                     "nydfs crypto"],
        "question_patterns": ["bitlicense", "new york crypto license", "ny dfs virtual currency",
                               "nydfs bitlicense"],
        "answer": (
            "The New York BitLicense (23 NYCRR § 200) is required for any person engaged in 'virtual "
            "currency business activity' involving New York residents, including: buying/selling virtual "
            "currency as a customer business, transmitting virtual currency, storing/holding virtual "
            "currency on behalf of others, or controlling, administering, or issuing a virtual currency. "
            "The application requires: $5,000 non-refundable fee, detailed business plan, AML/BSA "
            "compliance program, cybersecurity program, consumer protection policies, financial statements, "
            "and background checks on principals. Review and approval typically takes 12-24 months. "
            "Alternatively, companies may apply for a Limited Purpose Trust Charter under NY Banking Law "
            "Article III, which provides broader banking powers but requires higher capital."
        ),
        "relevant_regulations": [
            "23 NYCRR § 200 (BitLicense)",
            "NY Banking Law Article III",
            "NY DFS Guidance on Virtual Currency",
        ],
        "relevant_agencies": ["NY DFS (Department of Financial Services)"],
        "confidence": "high",
        "follow_up_questions": [
            "Can I operate in New York while my BitLicense application is pending?",
            "What are the capital requirements for the NY BitLicense?",
            "Is there a simpler path to serving New York crypto customers?",
        ],
    },
    {
        "keywords": ["howey test", "security token", "token classification", "is my token a security",
                     "investment contract", "sec token"],
        "question_patterns": ["howey test", "is my token a security", "security token",
                               "token security analysis", "utility token vs security"],
        "answer": (
            "The Howey test (SEC v. W.J. Howey Co., 328 U.S. 293 (1946)) determines whether a digital "
            "asset is a 'security.' A token is likely a security if it involves: (1) an investment of "
            "money, (2) in a common enterprise, (3) with an expectation of profits, (4) primarily from "
            "the efforts of others. The SEC's 2019 DAO Report and subsequent Framework for Investment "
            "Contract Analysis of Digital Assets provide further guidance. Factors suggesting a token IS "
            "a security: investors expect price appreciation, a promoter controls the network, the token "
            "has no current consumptive use, tokens are marketed as investments. Factors suggesting NOT "
            "a security: fully decentralized network, token has immediate consumptive utility, no "
            "reasonable expectation of profits from others' efforts. 'Utility token' is not a legally "
            "recognized category — the SEC has rejected this framing. The CFTC has concurrent jurisdiction "
            "over tokens that are commodities (Bitcoin, Ether per CFTC guidance)."
        ),
        "relevant_regulations": [
            "Securities Act of 1933 — § 2(a)(1) (definition of security)",
            "SEC v. W.J. Howey Co., 328 U.S. 293 (1946)",
            "SEC Framework for Investment Contract Analysis of Digital Assets (Apr. 2019)",
            "SEC DAO Report (2017)",
        ],
        "relevant_agencies": ["SEC", "CFTC"],
        "confidence": "high",
        "follow_up_questions": [
            "What happens if my token is classified as a security?",
            "What exemptions are available for token sales?",
            "How do I structure a token sale under Regulation D?",
        ],
    },
    {
        "keywords": ["reg d", "regulation d", "506b", "506c", "accredited investor", "private placement",
                     "exempt offering"],
        "question_patterns": ["regulation d", "reg d exemption", "506b 506c", "private placement exempt",
                               "accredited investor offering"],
        "answer": (
            "Regulation D under the Securities Act of 1933 provides exemptions from SEC registration for "
            "private securities offerings. Key exemptions:\n\n"
            "Rule 506(b): Raise unlimited capital from up to 35 non-accredited but sophisticated investors "
            "plus unlimited accredited investors. NO general solicitation or advertising permitted. "
            "File Form D with SEC within 15 days of first sale.\n\n"
            "Rule 506(c): Raise unlimited capital from accredited investors only. General solicitation "
            "and advertising PERMITTED. Must take reasonable steps to verify accreditor status "
            "(e.g., review tax returns, bank statements, third-party verification letters). "
            "File Form D with SEC within 15 days of first sale.\n\n"
            "Accredited Investor definition (Rule 501): Individual with net worth >$1M (excluding primary "
            "residence) OR income >$200K ($300K joint) in each of last 2 years. Institutions with "
            ">$5M in assets. Licensed financial professionals with Series 7/65/82.\n\n"
            "State Blue Sky laws: Regulation D provides federal preemption for 'covered securities' "
            "under Rule 506, but states may require filing notices and fees."
        ),
        "relevant_regulations": [
            "Securities Act § 4(a)(2)",
            "17 C.F.R. § 230.506(b)",
            "17 C.F.R. § 230.506(c)",
            "17 C.F.R. § 230.501 (Accredited Investor definition)",
        ],
        "relevant_agencies": ["SEC"],
        "confidence": "high",
        "follow_up_questions": [
            "What are the disclosure requirements under Regulation D?",
            "Can foreign investors participate in a Regulation D offering?",
            "What is Regulation S for offshore offerings?",
        ],
    },
    {
        "keywords": ["dao", "decentralized autonomous organization", "dao llc", "wyoming dao",
                     "dao legal structure", "dao taxation"],
        "question_patterns": ["dao legal", "dao llc", "wyoming dao", "dao structure",
                               "dao liability", "dao taxation"],
        "answer": (
            "Wyoming was the first US state to legally recognize Decentralized Autonomous Organizations "
            "as LLCs under the Wyoming DAO LLC Act (W.S. § 17-31-101, effective 2021). "
            "A Wyoming DAO LLC can be 'member-managed' (by token holders) or 'algorithmically managed' "
            "(governance by smart contract). Key features: DAO members are shielded from personal "
            "liability (like traditional LLC), governance rules can be encoded in smart contracts, "
            "the DAO's articles of organization must identify the smart contract address on-chain, "
            "and the DAO must have a registered agent in Wyoming.\n\n"
            "Tax treatment: The IRS has not issued specific DAO guidance. Most DAOs are treated as "
            "partnerships or corporations depending on structure and activities. DAO token holders "
            "may owe taxes on governance token distributions (potentially ordinary income).\n\n"
            "Securities risk: Governance tokens that provide economic rights or profit expectations "
            "may be securities under the Howey test — regardless of DAO legal wrapper.\n\n"
            "Alternatives: Marshall Islands DAO Act, Vermont Blockchain-Based LLC, Tennessee."
        ),
        "relevant_regulations": [
            "Wyoming DAO LLC Act — W.S. § 17-31-101 et seq.",
            "IRS Notice 2014-21 (Virtual Currency — general principles)",
            "Securities Act of 1933 (Howey test for governance tokens)",
        ],
        "relevant_agencies": ["Wyoming Secretary of State", "IRS", "SEC"],
        "confidence": "high",
        "follow_up_questions": [
            "How are DAO governance token distributions taxed?",
            "What are the liability protections for Wyoming DAO LLC members?",
            "Can a DAO LLC issue tokens in a Regulation D offering?",
        ],
    },
    {
        "keywords": ["mica", "eu crypto regulation", "europe crypto", "eu markets in crypto assets",
                     "casp license eu"],
        "question_patterns": ["mica regulation", "eu crypto license", "casp authorization",
                               "europe crypto framework", "mica requirements"],
        "answer": (
            "MiCA (Markets in Crypto-Assets Regulation, EU 2023/1114) is the EU's comprehensive crypto "
            "framework, fully applicable from December 30, 2024. Key requirements:\n\n"
            "Crypto-Asset Service Providers (CASPs): Must be authorized by an EU member state's national "
            "competent authority. Once authorized, CASPs can passport across all 27 EU member states. "
            "Services covered: custody, trading, exchange, transfer, advice, portfolio management.\n\n"
            "Stablecoin Issuers: Asset-Referenced Tokens (ARTs) and E-Money Tokens (EMTs) face the "
            "strictest requirements — reserve asset requirements, redemption rights, issuer authorization, "
            "and volume caps for large issuers (non-EUR EMTs >€200M/day must be capped or charged a fee).\n\n"
            "NFTs: Generally exempt from MiCA if truly unique and not fungible, but fractional NFTs "
            "or large NFT collections may be caught.\n\n"
            "DeFi: Decentralized protocols are currently exempt if 'fully decentralized' — but the "
            "European Commission will review this by Dec 2025.\n\n"
            "Non-EU firms: Must notify ESMA and be authorized locally or appoint an EU representative "
            "to serve EU customers."
        ),
        "relevant_regulations": [
            "EU Regulation 2023/1114 (MiCA)",
            "MiCA Level 2 Technical Standards (EBA/ESMA RTS/ITS)",
        ],
        "relevant_agencies": ["ESMA", "EBA", "National Competent Authorities (e.g., BaFin, AMF, CBI)"],
        "confidence": "high",
        "follow_up_questions": [
            "Which EU member state is most favorable for CASP authorization?",
            "What are the capital requirements for a MiCA CASP license?",
            "Does MiCA apply to DeFi protocols?",
        ],
    },
    {
        "keywords": ["aml program", "anti-money laundering", "bsa compliance", "fincen registration",
                     "msb registration", "aml policy"],
        "question_patterns": ["aml program requirements", "bsa compliance program", "fincen msb",
                               "money services business registration", "aml policy"],
        "answer": (
            "FinCEN requires Money Services Businesses (MSBs) to register and maintain AML programs. "
            "An MSB is any person doing business in the US in: money transmission, currency exchange, "
            "check cashing, issuing/selling money orders or traveler's checks, or dealing in prepaid "
            "cards. Virtual currency exchangers and administrators are also MSBs.\n\n"
            "Registration: File with FinCEN via BSA E-Filing System within 180 days of establishing "
            "the business. Re-register every 2 years.\n\n"
            "AML Program must include 4 pillars (31 C.F.R. § 1022.210):\n"
            "1. Written internal policies, procedures, and controls\n"
            "2. Designated compliance officer\n"
            "3. Ongoing employee training\n"
            "4. Independent audit/testing\n\n"
            "CTR filing: Report cash transactions >$10,000 within 15 days.\n"
            "SAR filing: Report suspicious transactions ≥$2,000 (for MSBs) within 30 days of detection.\n"
            "Travel Rule: Transmittal orders ≥$3,000 must include originator/beneficiary information "
            "(per FinCEN, also applies to crypto transfers).\n\n"
            "Penalties: Failure to maintain AML program or file SARs — up to $25,000/day; intentional "
            "violations — criminal charges."
        ),
        "relevant_regulations": [
            "31 U.S.C. § 5311 (Bank Secrecy Act)",
            "31 C.F.R. § 1022.380 (MSB Registration)",
            "31 C.F.R. § 1022.210 (AML Program)",
            "FinCEN Guidance FIN-2019-G001 (Cryptocurrency AML)",
        ],
        "relevant_agencies": ["FinCEN", "IRS (BSA exam authority for MSBs)"],
        "confidence": "high",
        "follow_up_questions": [
            "What KYC procedures are required for a crypto MSB?",
            "When must a SAR be filed for suspicious crypto transactions?",
            "Does the Travel Rule apply to DeFi protocol transactions?",
        ],
    },
    {
        "keywords": ["investment company act", "fund structure", "3c1", "3c7", "hedge fund",
                     "venture capital", "private fund", "exempt fund"],
        "question_patterns": ["investment company act", "3c1 exemption", "3c7 exemption",
                               "fund registration", "private fund exemption"],
        "answer": (
            "The Investment Company Act of 1940 requires companies that issue securities and are primarily "
            "engaged in investing securities to register as investment companies with the SEC. "
            "Most private funds avoid registration via two key exemptions:\n\n"
            "Section 3(c)(1): Fund with no more than 100 beneficial owners (or 250 for 'qualifying "
            "venture capital funds') and not making a public offering. No limit on assets.\n\n"
            "Section 3(c)(7): Fund where ALL investors are 'qualified purchasers' — individuals with "
            ">$5M in investments, companies with >$25M in investments. No limit on number of investors.\n\n"
            "Token funds/crypto funds: Must analyze whether tokens held qualify as securities. "
            "If >40% of assets are securities, the fund may be an investment company regardless "
            "of exemptions.\n\n"
            "Venture Capital Exemption: SEC Rule 203(l) exempts VC fund advisers managing <$150M "
            "from investment adviser registration if funds: make only qualifying investments, "
            "don't borrow, and investors are qualified clients.\n\n"
            "Family Office Exclusion: Section 202(a)(11)(G) excludes single family offices."
        ),
        "relevant_regulations": [
            "Investment Company Act of 1940 — 15 U.S.C. § 80a-1 et seq.",
            "15 U.S.C. § 80a-3(c)(1) (100-person exemption)",
            "15 U.S.C. § 80a-3(c)(7) (qualified purchaser exemption)",
            "SEC Rule 203(l) (VC fund adviser exemption)",
        ],
        "relevant_agencies": ["SEC"],
        "confidence": "high",
        "follow_up_questions": [
            "What is a 'qualified purchaser' under the Investment Company Act?",
            "Can a crypto fund use the 3(c)(1) exemption?",
            "What are the reporting requirements for exempt private funds?",
        ],
    },
]


# ─────────────────────────────────────────────────────────────
# Risk Scoring Engine
# ─────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    return text.lower()


def _score_business(description: str) -> tuple[list[ApplicableRegulation], int]:
    """
    Score a business description against regulatory triggers.
    Returns (applicable_regulations, raw_risk_score).
    """
    normalized = _normalize_text(description)
    triggered: list[tuple[int, ApplicableRegulation]] = []
    seen_citations: set[str] = set()

    for trigger in REGULATORY_TRIGGERS:
        match_count = sum(
            1 for kw in trigger["keywords"]
            if kw.lower() in normalized
        )
        if match_count >= 1:
            reg = trigger["regulation"]
            if reg.citation not in seen_citations:
                seen_citations.add(reg.citation)
                triggered.append((trigger["risk_weight"] * min(match_count, 3), reg))

    # Sort by weight descending
    triggered.sort(key=lambda x: x[0], reverse=True)

    # Calculate total risk score (cap at 100)
    raw_score = sum(w for w, _ in triggered)
    risk_score = min(100, raw_score)

    regs = [reg for _, reg in triggered]
    return regs, risk_score


def _risk_level_from_score(score: int) -> RiskLevel:
    if score >= 70:
        return RiskLevel.CRITICAL
    elif score >= 45:
        return RiskLevel.HIGH
    elif score >= 20:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def _derive_compliance_gaps(
    regulations: list[ApplicableRegulation],
    description: str,
) -> list[str]:
    """Infer key compliance gaps from triggered regulations."""
    gaps: list[str] = []
    normalized = _normalize_text(description)

    critical_regs = [r for r in regulations if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)]

    for reg in critical_regs[:5]:
        gaps.append(f"No mention of {reg.name} compliance framework — may require immediate attention")

    if "aml" not in normalized and "kyc" not in normalized and any(
        kw in normalized for kw in ["transfer", "payment", "exchange", "crypto", "token"]
    ):
        gaps.append("AML/KYC program not addressed — required for most financial activities")

    if "license" not in normalized and "licensed" not in normalized and any(
        r.regulator in ("SEC", "CFTC", "FinCEN") for r in regulations
    ):
        gaps.append("Licensing strategy not described — multiple federal and state licenses may be required")

    if "privacy" not in normalized and "gdpr" not in normalized and "ccpa" not in normalized:
        if any(kw in normalized for kw in ["user data", "customer", "account", "profile"]):
            gaps.append("Data privacy compliance (CCPA/GDPR) not addressed")

    return gaps[:8]


def _derive_priority_actions(
    regulations: list[ApplicableRegulation],
    risk_score: int,
) -> list[str]:
    """Derive the top priority actions from triggered regulations."""
    actions: list[str] = []

    if risk_score >= 70:
        actions.append("URGENT: Engage specialized regulatory counsel before conducting any business activities")

    # Collect unique high-priority actions across all regs
    seen: set[str] = set()
    for reg in regulations[:4]:  # Top 4 most relevant
        for action in reg.recommended_actions[:2]:
            if action not in seen:
                seen.add(action)
                actions.append(action)

    if risk_score >= 45:
        actions.append("Conduct a comprehensive regulatory gap analysis with qualified compliance counsel")

    actions.append("Monitor ongoing regulatory developments via SEC, CFTC, and FinCEN official channels")
    return actions[:10]


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def analyze_regulatory_risk(
    business_description: str,
    jurisdiction: str = "US",
) -> RegulatoryScenResponse:
    """
    Analyze regulatory risk for a business description.
    Uses Claude LLM if ANTHROPIC_API_KEY is configured, otherwise falls back
    to rule-based keyword matching.
    """
    # ── Try LLM-powered analysis first ──
    try:
        from src.services.llm import analyze_regulatory_risk_llm, is_llm_available
        if is_llm_available():
            llm_result = analyze_regulatory_risk_llm(business_description, jurisdiction)
            if llm_result is not None:
                logger.info("Using LLM-powered regulatory analysis for: %s...", business_description[:60])
                regs = []
                for r in llm_result.get("applicable_regulations", []):
                    regs.append(ApplicableRegulation(
                        name=r.get("name", "Unknown"),
                        citation=r.get("citation", "N/A"),
                        regulator=r.get("regulator", "N/A"),
                        relevance=r.get("relevance", ""),
                        risk_level=RiskLevel(r.get("risk_level", "MEDIUM").upper()) if r.get("risk_level", "").upper() in [e.value for e in RiskLevel] else RiskLevel.MEDIUM,
                        description=r.get("description", ""),
                        recommended_actions=r.get("recommended_actions", []),
                    ))
                return RegulatoryScenResponse(
                    business_description=business_description,
                    jurisdiction=jurisdiction,
                    overall_risk_score=llm_result.get("overall_risk_score", 50),
                    overall_risk_level=RiskLevel(llm_result.get("overall_risk_level", "MEDIUM").upper()) if llm_result.get("overall_risk_level", "").upper() in [e.value for e in RiskLevel] else RiskLevel.MEDIUM,
                    applicable_regulations=regs or [],
                    key_compliance_gaps=llm_result.get("key_compliance_gaps", []),
                    priority_actions=llm_result.get("priority_actions", []),
                )
    except Exception as exc:
        logger.warning("LLM regulatory analysis failed, falling back to rule-based: %s", exc)

    # ── Fallback: rule-based keyword matching ──
    regulations, raw_score = _score_business(business_description)

    # Jurisdiction-based adjustments
    jur_upper = jurisdiction.upper()
    if "NY" in jur_upper:
        raw_score = min(100, raw_score + 10)  # NY is more restrictive
    elif "WY" in jur_upper:
        raw_score = max(0, raw_score - 5)    # WY is more permissive for crypto

    risk_level = _risk_level_from_score(raw_score)
    gaps = _derive_compliance_gaps(regulations, business_description)
    priority_actions = _derive_priority_actions(regulations, raw_score)

    if not regulations:
        # Default low-risk response for non-financial businesses
        regulations = [
            ApplicableRegulation(
                name="General Business Compliance",
                citation="N/A",
                regulator="Federal / State",
                relevance="Standard business compliance requirements",
                risk_level=RiskLevel.LOW,
                description=(
                    "Based on the business description provided, no specific high-risk financial regulatory "
                    "triggers were identified. Standard business licensing, tax registration, and general "
                    "consumer protection laws apply."
                ),
                recommended_actions=[
                    "Register business entity in state of operation",
                    "Obtain required state and local business licenses",
                    "Register for federal and state tax purposes (EIN)",
                    "Implement basic privacy policy if collecting user data",
                ],
            )
        ]
        priority_actions = [
            "Register business entity and obtain required local licenses",
            "Consult an attorney to confirm no regulatory triggers apply to your specific activities",
        ]

    return RegulatoryScenResponse(
        business_description=business_description,
        jurisdiction=jurisdiction,
        overall_risk_score=raw_score,
        overall_risk_level=risk_level,
        applicable_regulations=regulations,
        key_compliance_gaps=gaps,
        priority_actions=priority_actions,
    )


def compare_jurisdictions(
    jurisdictions: list[str],
    business_type: BusinessType,
) -> JurisdictionComparisonResponse:
    """
    Compare regulatory requirements across jurisdictions for a given business type.
    """
    profiles: list[JurisdictionProfile] = []
    bt = business_type.value

    for jur in jurisdictions:
        data = JURISDICTION_DATA.get(jur.upper())
        if not data:
            # Unknown jurisdiction — provide minimal profile
            profiles.append(
                JurisdictionProfile(
                    jurisdiction=jur,
                    full_name=f"{jur} (data not available)",
                    overall_friendliness="neutral",
                    friendliness_score=50,
                    requirements=[
                        JurisdictionRequirement(
                            category="General",
                            requirement="Detailed regulatory data not available for this jurisdiction",
                            notes="Consult local legal counsel",
                        )
                    ],
                    key_advantages=["Data not available"],
                    key_risks=["Consult local counsel for accurate risk assessment"],
                    notable_regulations=["Consult local counsel"],
                    incorporation_cost_usd="Unknown",
                    time_to_incorporate_days="Unknown",
                )
            )
            continue

        reqs_for_type = data["requirements_by_type"].get(bt, data["requirements_by_type"].get("fintech", []))

        profiles.append(
            JurisdictionProfile(
                jurisdiction=jur.upper(),
                full_name=data["full_name"],
                overall_friendliness=data["overall_friendliness"],
                friendliness_score=data["friendliness_score"],
                requirements=reqs_for_type,
                key_advantages=data["key_advantages"],
                key_risks=data["key_risks"],
                notable_regulations=data["notable_regulations"],
                incorporation_cost_usd=data.get("incorporation_cost_usd"),
                time_to_incorporate_days=data.get("time_to_incorporate_days"),
            )
        )

    # Sort by friendliness score descending
    profiles.sort(key=lambda p: p.friendliness_score, reverse=True)

    # Build comparison matrix
    matrix: dict[str, dict[str, str]] = {}
    dimensions = ["Friendliness Score", "Incorporation Cost", "Time to Incorporate", "Key Challenge"]
    for p in profiles:
        matrix[p.jurisdiction] = {
            "Friendliness Score": f"{p.friendliness_score}/100",
            "Incorporation Cost": p.incorporation_cost_usd or "N/A",
            "Time to Incorporate": p.time_to_incorporate_days or "N/A",
            "Regulatory Approach": p.overall_friendliness.replace("_", " ").title(),
        }

    # Generate recommendation
    if profiles:
        best = profiles[0]
        recommendation = (
            f"For {bt} businesses, {best.full_name} ({best.jurisdiction}) scores highest "
            f"({best.friendliness_score}/100) for regulatory friendliness. "
        )
        if len(profiles) > 1:
            second = profiles[1]
            recommendation += (
                f"{second.jurisdiction} is also favorable ({second.friendliness_score}/100). "
            )
        recommendation += (
            "Note: Federal US regulations (SEC, CFTC, FinCEN) apply regardless of state of incorporation. "
            "Consult legal counsel before making jurisdiction decisions."
        )
    else:
        recommendation = "No valid jurisdictions provided for comparison."

    return JurisdictionComparisonResponse(
        business_type=bt,
        jurisdictions_compared=[p.jurisdiction for p in profiles],
        profiles=profiles,
        recommendation=recommendation,
        comparison_matrix=matrix,
    )


def answer_regulatory_query(question: str) -> RegulatoryQueryResponse:
    """
    Answer a regulatory question.
    Uses Claude LLM if available, otherwise falls back to keyword-matched knowledge base.
    """
    # ── Try LLM-powered Q&A first ──
    try:
        from src.services.llm import answer_regulatory_query_llm, is_llm_available
        if is_llm_available():
            llm_result = answer_regulatory_query_llm(question)
            if llm_result is not None:
                logger.info("Using LLM-powered Q&A for: %s...", question[:60])
                return RegulatoryQueryResponse(
                    question=question,
                    answer=llm_result.get("answer", ""),
                    confidence=llm_result.get("confidence", 0.7),
                    relevant_regulations=llm_result.get("relevant_statutes", []),
                    relevant_agencies=llm_result.get("relevant_agencies", []),
                    follow_up_questions=[],
                )
    except Exception as exc:
        logger.warning("LLM Q&A failed, falling back to rule-based: %s", exc)

    # ── Fallback: keyword-matched knowledge base ──
    normalized_q = _normalize_text(question)

    best_match: dict | None = None
    best_score: int = 0

    for entry in QA_KNOWLEDGE_BASE:
        # Score by keyword matches
        score = sum(
            1 for kw in entry["keywords"]
            if kw.lower() in normalized_q
        )
        # Bonus for pattern matches
        score += sum(
            2 for pattern in entry["question_patterns"]
            if pattern.lower() in normalized_q
        )
        if score > best_score:
            best_score = score
            best_match = entry

    if best_match and best_score >= 1:
        return RegulatoryQueryResponse(
            question=question,
            answer=best_match["answer"],
            confidence=best_match["confidence"],
            relevant_regulations=best_match["relevant_regulations"],
            relevant_agencies=best_match["relevant_agencies"],
            follow_up_questions=best_match["follow_up_questions"],
        )

    # Fallback: attempt partial match on broad keywords
    broad_keywords = {
        "sec": "securities",
        "securities": "securities",
        "cftc": "derivatives",
        "futures": "derivatives",
        "fincen": "aml",
        "aml": "aml",
        "kyc": "aml",
        "bank": "banking",
        "crypto": "crypto",
        "token": "crypto",
        "privacy": "privacy",
        "gdpr": "privacy",
        "ccpa": "privacy",
    }

    detected_topics = set()
    for kw, topic in broad_keywords.items():
        if kw in normalized_q:
            detected_topics.add(topic)

    if detected_topics:
        topics_str = " and ".join(detected_topics)
        answer = (
            f"Your question touches on {topics_str} regulations. "
            f"The HYDRA Arm 3 knowledge base covers: SEC securities law, "
            f"CFTC commodity/derivatives regulations, FinCEN AML/BSA requirements, "
            f"state money transmission licensing, cryptocurrency regulation (Howey test, MiCA), "
            f"banking regulation, and data privacy (CCPA/GDPR).\n\n"
            f"For a more specific answer, try rephrasing your question to include specific regulatory "
            f"terms, agency names, or jurisdiction names. Example: 'Do I need a money transmitter "
            f"license in Wyoming for a crypto exchange?'"
        )
        return RegulatoryQueryResponse(
            question=question,
            answer=answer,
            confidence="low",
            relevant_regulations=[],
            relevant_agencies=list(detected_topics),
            follow_up_questions=[
                "Can you be more specific about which regulation or jurisdiction concerns you?",
                "What specific activity or business model are you asking about?",
                "Which country or US state is most relevant to your question?",
            ],
        )

    # Generic fallback
    return RegulatoryQueryResponse(
        question=question,
        answer=(
            "The HYDRA Arm 3 regulatory knowledge base covers: US federal securities law (SEC), "
            "derivatives regulation (CFTC), anti-money laundering and Bank Secrecy Act (FinCEN), "
            "state money transmission licensing, cryptocurrency regulation (including NY BitLicense, "
            "Wyoming crypto laws, EU MiCA), investment adviser regulation, banking regulation, "
            "and data privacy (CCPA/GDPR). Try asking about a specific regulation, agency, "
            "jurisdiction, or business activity for a targeted answer."
        ),
        confidence="low",
        relevant_regulations=[],
        relevant_agencies=["SEC", "CFTC", "FinCEN", "State Regulators"],
        follow_up_questions=[
            "Do I need a license to operate a cryptocurrency exchange?",
            "What is the Howey test and does it apply to my token?",
            "What AML program is required for a money services business?",
            "How does MiCA affect EU crypto businesses?",
        ],
    )
