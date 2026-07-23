#%%
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %%
# Download full history of the S&P 500 index
# auto_adjust=False keeps both 'Close' (price only) and 'Adj Close' (dividends reinvested)
sp500 = yf.download("^GSPC", start="1900-01-01", auto_adjust=False)

# yfinance sometimes returns MultiIndex columns (ticker, field) -- flatten if so
if isinstance(sp500.columns, pd.MultiIndex):
    sp500.columns = sp500.columns.get_level_values(0)

sp500 = sp500.reset_index()  # 'Date' becomes a regular column
sp500 = sp500.sort_values("Date").reset_index(drop=True)

# Daily percentage change (price only, matches your original "Change %")
sp500["Change %"] = sp500["Close"].pct_change() * 100

print(f"Data range: {sp500['Date'].min().date()} to {sp500['Date'].max().date()}")
print(f"Total trading days: {len(sp500)}")

combined = sp500  # keep variable name consistent with the rest of the script

#%%
# Plot: daily percentage change
plt.figure(figsize=(12, 6))
plt.plot(combined["Date"], combined["Change %"], linewidth=0.5)
plt.axhline(0, color="gray", linewidth=0.8, linestyle="--")
plt.title("S&P 500 Daily Percentage Change")
plt.xlabel("Date")
plt.ylabel("Change (%)")
plt.grid(True, alpha=0.3)
plt.tight_layout()

output_path = "sp500_daily_pct_change.png"
plt.savefig(output_path, dpi=150)
print(f"Plot saved to {output_path}")
plt.show()

#%%
# Three-month rolling volatility (std of daily % change)
vol = combined.set_index("Date")["Change %"].sort_index()

window_days = 63  # ~3 months of trading days
rolling_vol = vol.rolling(window=window_days).std()

plt.figure(figsize=(12, 6))
plt.plot(rolling_vol.index, rolling_vol.values, linewidth=1, color="darkorange")
plt.title(f"S&P 500 Rolling {window_days}-Day (≈3-Month) Volatility (Std of Daily % Change)")
plt.xlabel("Date")
plt.ylabel("Rolling Std Dev (%)")
plt.grid(True, alpha=0.3)
plt.tight_layout()

output_path_vol = "sp500_rolling_volatility.png"
plt.savefig(output_path_vol, dpi=150)
print(f"Plot saved to {output_path_vol}")
plt.show()

#%%
# Toggle: include reinvested dividends?
# With yfinance, 'Adj Close' already bakes in actual historical dividends day-by-day,
# so no synthetic yield assumption is needed anymore.
INCLUDE_DIVIDENDS = True

if INCLUDE_DIVIDENDS:
    price = combined.set_index("Date")["Adj Close"].sort_index()
else:
    price = combined.set_index("Date")["Close"].sort_index()

running_max = price.cummax()
drawdown = (price / running_max - 1) * 100

at_new_high = (price >= running_max)
days_since_high = (~at_new_high).astype(int)
groups = at_new_high.cumsum()
drawdown_duration = days_since_high.groupby(groups).cumsum()

fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

label_suffix = " (Total Return, Dividends Reinvested)" if INCLUDE_DIVIDENDS else " (Price Only)"

axes[0].plot(price.index, price.values, linewidth=1, color="steelblue")
axes[0].set_title(f"S&P 500{label_suffix}")
axes[0].set_yscale("log")  # log scale makes sense over a century of compounding
axes[0].grid(True, alpha=0.3)

axes[1].fill_between(drawdown.index, drawdown.values, 0, color="crimson", alpha=0.5)
axes[1].set_title(f"Drawdown from Running Peak (%){label_suffix}")
axes[1].grid(True, alpha=0.3)

axes[2].plot(drawdown_duration.index, drawdown_duration.values, linewidth=1, color="darkorange")
axes[2].set_title(f"Days Since Last All-Time High{label_suffix}")
axes[2].grid(True, alpha=0.3)

plt.tight_layout()
suffix_file = "_div" if INCLUDE_DIVIDENDS else "_nodiv"
plt.savefig(f"sp500_drawdown_analysis{suffix_file}.png", dpi=150)
plt.show()

#%%
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import os

def send_email_with_plots(sender_email, sender_password, recipient_email, plot_paths):
    msg = MIMEMultipart()
    msg["Subject"] = "Monthly S&P 500 Report"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.attach(MIMEText("Attached: this month's S&P 500 plots.", "plain"))

    for path in plot_paths:
        if os.path.exists(path):
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
                msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

    print("Email sent.")

# Call after all your plots have been saved
send_email_with_plots(
    sender_email="wiebedg@gmail.com",
    sender_password=os.environ["EMAIL_APP_PASSWORD"],  # never hardcode this
    recipient_email="wiebedg@gmail.com",
    plot_paths=[
        "sp500_daily_pct_change.png",
        "sp500_rolling_volatility.png",
        "sp500_drawdown_analysis_div.png",
    ],
)