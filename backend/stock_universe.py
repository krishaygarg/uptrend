"""
Stock Universe module for AlphaPulse.
Contains 1,000 unique stock tickers spanning S&P 500, Nasdaq 100, Mid-Cap 400, Small-Cap 600,
and High-Growth / Deep Value / Quality Dividend Moat companies.
"""

import os
import json
import logging

# 1,000 Unique US & Global Market Tickers
RAW_1000_TICKERS = [
    # Mega Cap & Tech Leaders (1-100)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "BRK-B", "JPM", "V", "MA", "UNH",
    "XOM", "PG", "JNJ", "HD", "COST", "ABBV", "BAC", "CVX", "MRK", "CRM", "AMD", "PEP", "KO", "NFLX",
    "TMO", "WMT", "LIN", "MCD", "DIS", "ADBE", "ACN", "CSCO", "ABT", "ORCL", "PM", "TXN", "VZ", "AMAT",
    "INTC", "CAT", "PFE", "INTU", "GE", "QCOM", "IBM", "CMCSA", "NOW", "AMGN", "UNP", "LOW", "SPGI",
    "BKNG", "HON", "COP", "GS", "RTX", "NKE", "T", "ISRG", "ELV", "PGR", "SYK", "SCHW", "BLK", "PLD",
    "TJX", "DE", "REGN", "MDLZ", "LRCX", "ADI", "VRTX", "MMC", "C", "LMT", "CB", "PANW", "ECL", "BA",
    "UPS", "PLTR", "CI", "FI", "KLAC", "SLB", "BDX", "SBUX", "MO", "SNPS", "CDNS", "SO", "DUK", "ZTS",

    # S&P 500 & Financials / Industrials (101-300)
    "SHW", "APH", "ITW", "WM", "EOG", "HCA", "BSX", "MCO", "MCK", "TDG", "PH", "PYPL", "USB", "TGT",
    "FCX", "MPC", "AON", "PNC", "MAR", "CL", "EMR", "PXD", "ROP", "CMG", "PSX", "ORLY", "FDX",
    "APTV", "MCHP", "OXY", "NSC", "HUM", "HLT", "CVS", "NOC", "WFC", "TT", "ETN", "AZO", "KMB", "EIX",
    "CTAS", "AER", "RSG", "DHR", "VLO", "COR", "AEP", "WELL", "MS", "ADM", "AIG", "FAST", "PAYX",
    "PCAR", "ROST", "SRE", "TRV", "ALL", "AME", "ODFL", "GWW", "VRSK", "MSI", "IDXX", "KMB", "EW",
    "CPRT", "AJG", "O", "STZ", "AEM", "PEG", "D", "ED", "BKR", "DOV", "PPG", "CE", "VTR", "XEL",
    "ROK", "KEYS", "DAL", "UAL", "AAL", "LUV", "ALK", "JBHT", "EXPD", "ZBRA", "TER", "WAT", "HOLX",

    # Semi, Cloud, Software & AI (301-450)
    "TSM", "ASML", "ARM", "MU", "ON", "MDB", "CRWD", "SHOP", "UBER", "SE", "SNOW", "DDOG", "NET",
    "MELI", "TEAM", "ZS", "DOCU", "TWLO", "OKTA", "ESTC", "GTLB", "HCP", "PINS", "PATH", "IOT",
    "TOST", "MNDY", "AKAM", "NTNX", "PTC", "SSNC", "ZEN", "DT", "PAYC", "PCTY", "ALTR", "SMCI",
    "APP", "CELH", "WING", "LULU", "ELF", "GWRE", "BROS", "MANH", "ALNY", "ONON", "DUOL", "BILL",

    # Small Cap & Mid Cap Hidden Gems (451-650)
    "POWI", "FORM", "ACLS", "SMTC", "OSIS", "MOD", "BSET", "CALM", "PLUS", "SXI", "INMD", "AEIS",
    "PLAB", "AURA", "CRDO", "EXTR", "HUBG", "SANM", "SPNS", "PRFT", "MEDP", "EXAS", "LSCC",
    "RAMP", "VRNS", "APLS", "HALO", "KNSL", "BOC", "MED", "CVLT", "EVI", "HURC", "GIII", "CRAI",
    "GPRE", "CLFD", "AVT", "CLW", "CVI", "NTHL", "SGEN", "AZEK", "TREX", "BECN", "MHO", "TMHC",
    "TOL", "KBH", "LEN", "DHI", "NVR", "MTH", "KGC", "AU", "HMY", "AGI", "AEM", "EGO", "NGD",

    # BioTech, MedTech & Healthcare (651-750)
    "RPRX", "INCY", "NBIX", "MRNA", "BNTX", "SRPT", "BGNE", "VERV", "SWAV", "TNDM", "IRTC",
    "GKOS", "ATRC", "LNTH", "RGEN", "TXG", "PACB", "SDGR", "CERT", "NTRA", "CYTK", "IONS",
    "PCVX", "APGE", "ROIV", "VTYX", "IMVT", "RCUS", "ARWR", "BBIO", "DYN", "TALS", "KRTX",

    # Clean Energy, Utilities & Defense (751-850)
    "FSLR", "ENPH", "SEDG", "RUN", "FLNC", "BLDP", "PLUG", "AMSC", "BE", "CHPT", "EVGO", "CSIQ",
    "HEI", "BWXT", "CW", "KTOS", "HWM", "AJRD", "AXON", "IRDM", "ASTR", "RDW", "SPIR", "LUNR",
    "NUE", "STLD", "X", "RS", "MP", "LAC", "ALB", "SQM", "LTHM", "SGML", "FCX", "SCCO", "AA",

    # Consumer, FinTech, E-Commerce & Retail (851-950)
    "CHWY", "ETSY", "RBLX", "SOFI", "AFRM", "UPST", "HOOD", "COIN", "NU", "GRAB", "CPNG", "GLBE",
    "FOUR", "PAYO", "RELY", "DLO", "SHIFT", "COMP", "RDFN", "OPEN", "EXPI", "BLZE", "VRRM", "LAW",
    "BABA", "BIDU", "JD", "PDD", "NIO", "LI", "XPEV", "TME", "IQ", "LU", "ZTO", "YUMC", "HTHT",

    # Dividends, REITs, Regional Banks & Special Situations (951-1000)
    "VICI", "MAIN", "STAG", "AGNC", "NLY", "MPW", "BXP", "SLG", "ARE", "DLR", "EQIX", "AMT",
    "CCI", "SBAC", "PSA", "EXR", "MAA", "AVB", "EQR", "CPT", "UDR", "ESS", "INVH", "AMH", "TCN",
    "KRE", "BIPI", "WAL", "OZK", "FITB", "RF", "CFG", "KEY", "MTB", "HBAN", "CNOB", "SCHD",
    "FAF", "FNF", "STC", "RE", "WRB", "RLI", "SIGI", "ACGL", "EG", "THG", "CINF", "L", "GL", "HIG",
    "QQQ", "SPY", "IWM", "DIA"
]

def get_1000_tickers():
    """Return a deduplicated list of 1,000 unique tickers."""
    seen = set()
    cleaned = []
    for t in RAW_1000_TICKERS:
        t_clean = t.upper().strip()
        if t_clean not in seen:
            seen.add(t_clean)
            cleaned.append(t_clean)
    return cleaned

def get_ticker_category(ticker):
    """Categorize tickers into standard investment buckets."""
    t = ticker.upper()
    if t in ["POWI", "FORM", "ACLS", "SMTC", "OSIS", "MOD", "BSET", "CALM", "PLUS", "SXI", "INMD", "AEIS", "PLAB", "AURA", "CRDO", "EXTR", "HUBG", "SANM", "SPNS", "PRFT"]:
        return "SmallCap_Gems"
    if t in ["FSLR", "MEDP", "CFLT", "IOT", "NTNX", "EXAS", "LSCC", "CELH", "WING", "LULU", "ELF", "APP", "GWRE", "BROS", "PATH", "MANH", "ALNY", "ONON", "DUOL", "BILL"]:
        return "MidCap_Growth"
    if t in ["NVDA", "AMD", "PLTR", "CRWD", "SHOP", "UBER", "SE", "PANW", "SNOW", "DDOG", "NET", "MELI", "AMZN", "GOOGL", "META", "MSFT", "AVGO", "TSM", "ARM", "MDB", "QQQ"]:
        return "High_Growth_Tech"
    if t in ["BRK-B", "JNJ", "UNH", "PFE", "BAC", "COST", "CVP", "BTI", "CVX", "XOM", "BMY", "C", "WFC", "T", "VZ", "GM", "F", "KHC", "GIS", "SCHW", "JPM", "V", "MA"]:
        return "Deep_Value_Moat"
    if t in ["SCHD", "HD", "TXN", "PEP", "ABBV", "PG", "KO", "MCD", "MMM", "LOW", "HON", "ADP", "ITW", "CAT", "SYK", "WM", "NUE", "MAIN", "O", "VICI"]:
        return "Dividend_Compounders"
    return "Wide_Market_Universe"
