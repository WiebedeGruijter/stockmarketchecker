import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # no display needed when run headlessly (e.g. in GitHub Actions)
import matplotlib.pyplot as plt


# --- Config ---
SENDER_EMAIL = "wiebedg@gmail.com"           # your Gmail address
RECIPIENT_EMAIL = "wiebedg@gmail.com"        # where to send the report
INCLUDE_DIVIDENDS = True                     # use Adj Close (dividends reinvested) vs raw Close
BUY_SIGNAL_DRAWDOWN_THRESHOLD = -15.0        # trigger "BUY BUY BUY" if current drawdown is worse than this (%)


def download_data():
    """Download the full available history of the S&P 500 index from Yahoo Finance."""
    sp500 = yf.download("^GSPC", start="1900-01-01", auto_adjust=False)

    # yfinance sometimes returns MultiIndex columns (ticker, field) -- flatten if so
    if isinstance(sp500.columns, pd.MultiIndex):
        sp500.columns = sp500.columns.get_level_values(0)

    sp500 = sp500.reset_index().sort_values("Date").reset_index(drop=True)
    sp500["Change %"] = sp500["Close"].pct_change() * 100
    return sp500


def make_plots(combined):
    """Generate the daily % change, rolling volatility, and drawdown/duration plots."""
    plot_paths = []

    # --- Daily % change ---
    plt.figure(figsize=(12, 6))
    plt.plot(combined["Date"], combined["Change %"], linewidth=0.5)
    plt.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    plt.title("S&P 500 Daily Percentage Change")
    plt.xlabel("Date")
    plt.ylabel("Change (%)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    path = "sp500_daily_pct_change.png"
    plt.savefig(path, dpi=150)
    plt.close()
    plot_paths.append(path)

    # --- Rolling 3-month (~63 trading day) volatility ---
    vol = combined.set_index("Date")["Change %"].sort_index()
    window_days = 63
    rolling_vol = vol.rolling(window=window_days).std()

    plt.figure(figsize=(12, 6))
    plt.plot(rolling_vol.index, rolling_vol.values, linewidth=1, color="darkorange")
    plt.title(f"S&P 500 Rolling {window_days}-Day (~3-Month) Volatility")
    plt.xlabel("Date")
    plt.ylabel("Rolling Std Dev (%)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    path = "sp500_rolling_volatility.png"
    plt.savefig(path, dpi=150)
    plt.close()
    plot_paths.append(path)

    # --- Price / drawdown / drawdown duration ---
    price_col = "Adj Close" if INCLUDE_DIVIDENDS else "Close"
    price = combined.set_index("Date")[price_col].sort_index()

    running_max = price.cummax()
    drawdown = (price / running_max - 1) * 100
    at_new_high = (price >= running_max)
    days_since_high = (~at_new_high).astype(int)
    groups = at_new_high.cumsum()
    drawdown_duration = days_since_high.groupby(groups).cumsum()

    label_suffix = " (Total Return, Dividends Reinvested)" if INCLUDE_DIVIDENDS else " (Price Only)"

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    axes[0].plot(price.index, price.values, linewidth=1, color="steelblue")
    axes[0].set_title(f"S&P 500{label_suffix}")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.3)

    axes[1].fill_between(drawdown.index, drawdown.values, 0, color="crimson", alpha=0.5)
    axes[1].set_title(f"Drawdown from Running Peak (%){label_suffix}")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(drawdown_duration.index, drawdown_duration.values, linewidth=1, color="darkorange")
    axes[2].set_title(f"Days Since Last All-Time High{label_suffix}")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    suffix_file = "_div" if INCLUDE_DIVIDENDS else "_nodiv"
    path = f"sp500_drawdown_analysis{suffix_file}.png"
    plt.savefig(path, dpi=150)
    plt.close()
    plot_paths.append(path)

    current_drawdown = drawdown.iloc[-1]  # most recent value, i.e. today's drawdown from peak

    return plot_paths, current_drawdown


def send_email_with_plots(plot_paths, current_drawdown):
    """Send the generated plots as email attachments via Gmail SMTP (app password auth)."""
    if current_drawdown <= BUY_SIGNAL_DRAWDOWN_THRESHOLD:
        signal_line = "BUY BUY BUY"
    else:
        signal_line = "HOLD"

    body_text = (
        f"Current drawdown from all-time high: {current_drawdown:.2f}%\n"
        f"Threshold for a buy signal: {BUY_SIGNAL_DRAWDOWN_THRESHOLD:.2f}%\n\n"
        f"Signal: {signal_line}\n\n"
        "(Novelty indicator based on a single metric -- not financial advice.)\n\n"
        "Attached: this month's S&P 500 plots."
    )

    msg = MIMEMultipart()
    msg["Subject"] = f"Monthly S&P 500 Report -- {signal_line}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(body_text, "plain"))

    for path in plot_paths:
        if os.path.exists(path):
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, os.environ["GOOGLEPASSKEY"])
        server.send_message(msg)

    print("Email sent.")


if __name__ == "__main__":
    combined = download_data()
    print(f"Data range: {combined['Date'].min().date()} to {combined['Date'].max().date()}")
    print(f"Total trading days: {len(combined)}")

    plots, current_drawdown = make_plots(combined)
    send_email_with_plots(plots, current_drawdown)
