import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import threading

MA_WINDOW = 44
CANDLES_BEFORE = 50
CANDLES_START = 2

def fetch_5min_data(symbol, start_date=None, end_date=None):
    try:
        if start_date and end_date:
            data = yf.download(symbol, interval="5m", start=start_date, end=end_date, auto_adjust=False)
        else:
            data = yf.download(symbol, interval="5m", period="7d", auto_adjust=False)
        if data.empty:
            print(f"No data for {symbol}")
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize('UTC').tz_convert('Asia/Kolkata')
        else:
            data.index = data.index.tz_convert('Asia/Kolkata')
        data = data.sort_index()
        data.columns = [str(col).title() for col in data.columns]
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in data.columns:
                if col == 'Close' and 'Adj Close' in data.columns:
                    data['Close'] = data['Adj Close']
                else:
                    print(f"Missing column {col} in data for {symbol}")
                    return None
        return data
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def resample_to_10min(df):
    df_10min = df.resample('10min', offset='15min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return df_10min

def fetch_historical_10min_volume(symbol, start_date, days_back=5):
    """
    Fetches historical 10-min candle data (including volume) for a symbol.
    Returns a DataFrame with 10-min candles for the days before start_date.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    fetch_start = (start_dt - timedelta(days=days_back)).strftime("%Y-%m-%d")
    fetch_end = start_date
    df_5min = fetch_5min_data(symbol, fetch_start, fetch_end)
    if df_5min is None or df_5min.empty:
        print(f"No 5-min data for {symbol} in range {fetch_start} to {fetch_end}")
        return None
    df_10min = resample_to_10min(df_5min)
    df_10min['date'] = df_10min.index.date
    before_10min = df_10min[df_10min['date'] < start_dt].drop(columns='date')
    return before_10min

def get_44ma_on_52candles_from_date(symbol, start_date_str, data_5min=None):
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        prev5_date = start_date - timedelta(days=5)
        fetch_start = prev5_date.strftime("%Y-%m-%d")
        fetch_end = (start_date + timedelta(days=1)).strftime("%Y-%m-%d")
        if data_5min is None:
            data_5min = fetch_5min_data(symbol, fetch_start, fetch_end)
        if data_5min is None or data_5min.empty:
            return None
        data_10min = resample_to_10min(data_5min)
        data_10min['date'] = data_10min.index.date
        before_10min = data_10min[data_10min['date'] < start_date].drop(columns='date')
        start_10min = data_10min[data_10min['date'] == start_date].drop(columns='date')
        last50_before = before_10min.tail(CANDLES_BEFORE)
        first2_start = start_10min.head(CANDLES_START)
        combined_52 = pd.concat([last50_before, first2_start])
        combined_52['MA44'] = combined_52['Close'].rolling(window=MA_WINDOW).mean()
        return combined_52
    except Exception as e:
        print(f"Error in get_44ma_on_52candles_from_date for {symbol}: {e}")
        return None

def check_first2_against_ma44(df_10min, combined_52):
    if df_10min is None or combined_52 is None or len(df_10min) < 2 or len(combined_52) < 2:
        return "Not enough data"
    first2 = df_10min.head(2)
    last2_ma44 = combined_52['MA44'].tail(2)
    if first2.isnull().any().any() or last2_ma44.isnull().any():
        return "Not enough data"
    green = first2['Close'] > first2['Open']
    red = first2['Open'] > first2['Close']
    above_ma = (first2['Low'].values > last2_ma44.values)
    below_ma = (first2['High'].values < last2_ma44.values)

    # --- Confirmation logic ---
    def strong_body(row):
        rng = abs(row['High'] - row['Low'])
        body = abs(row['Close'] - row['Open'])
        return rng > 0 and (body / rng) > 0.4

    strong_bodies = first2.apply(strong_body, axis=1).all()
    ma_slope_up = last2_ma44.iloc[1] > last2_ma44.iloc[0]
    ma_slope_down = last2_ma44.iloc[1] < last2_ma44.iloc[0]
    close_near_high = abs(first2.iloc[1]['Close'] - first2.iloc[1]['High']) < 0.15 * (first2.iloc[1]['High'] - first2.iloc[1]['Low'])
    close_near_low = abs(first2.iloc[1]['Close'] - first2.iloc[1]['Low']) < 0.15 * (first2.iloc[1]['High'] - first2.iloc[1]['Low'])

    if green.all() and above_ma.all():
        if strong_bodies and ma_slope_up and close_near_high:
            return "Confirmed Bullish"
        return "Bullish"
    elif red.all() and below_ma.all():
        if strong_bodies and ma_slope_down and close_near_low:
            return "Confirmed Bearish"
        return "Bearish"
    else:
        return "No Signal"

class NSEStockScreener(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Stock Candle Screener V1")
        self.geometry("1300x600")
        self.stocks = [
            # ...existing stock list...
            "ABB.NS", "ACC.NS", "APLAPOLLO.NS", "AUBANK.NS", "AARTIIND.NS", "ADANIENSOL.NS", "ADANIENT.NS","ADANIGREEN.NS", "ADANIPORTS.NS", "ATGL.NS", "ABCAPITAL.NS", "ABFRL.NS", "ALKEM.NS", "AMBUJACEM.NS",
            "ANGELONE.NS", "APOLLOHOSP.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS","AUROPHARMA.NS", "DMART.NS", "AXISBANK.NS", "BSOFT.NS", "BSE.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS",
            "BAJAJFINSV.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BANKINDIA.NS", "BEL.NS","BHARATFORG.NS", "BHEL.NS", "BPCL.NS", "BHARTIARTL.NS", "BIOCON.NS", "BOSCHLTD.NS", "BRITANNIA.NS","CESC.NS", "CGPOWER.NS", "CANBK.NS", "CDSL.NS", "CHAMBLFERT.NS", "CHOLAFIN.NS", "CIPLA.NS",
            "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS", "CAMS.NS", "CONCOR.NS", "CROMPTON.NS","CYIENT.NS", "DLF.NS", "DABUR.NS", "DALBHARAT.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DIVISLAB.NS",
            "DIXON.NS", "DRREDDY.NS", "ETERNAL.NS", "EICHERMOT.NS", "ESCORTS.NS", "EXIDEIND.NS", "NYKAA.NS","GAIL.NS", "GMRAIRPORT.NS", "GLENMARK.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS",
            "GRASIM.NS", "HCLTECH.NS", "HDFCAMC.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HFCL.NS", "HAVELLS.NS","HEROMOTOCO.NS", "HINDALCO.NS", "HAL.NS", "HINDCOPPER.NS", "HINDPETRO.NS", "HINDUNILVR.NS",
            "HINDZINC.NS", "ICICIBANK.NS", "HUDCO.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDFCFIRSTB.NS","IIFL.NS", "IRB.NS", "ITC.NS", "INDIANB.NS", "IEX.NS", "IOC.NS", "IRCTC.NS", "IRFC.NS", "IREDA.NS",
            "IGL.NS", "INDUSTOWER.NS", "INDUSINDBK.NS", "NAUKRI.NS", "INFY.NS", "INOXWIND.NS", "INDIGO.NS","JSWENERGY.NS", "JSWSTEEL.NS", "JSL.NS", "JINDALSTEL.NS", "JIOFIN.NS", "JUBLFOOD.NS", "KEI.NS",
            "KPITTECH.NS", "KALYANKJIL.NS", "KOTAKBANK.NS", "LTF.NS", "LICHSGFIN.NS", "LTIM.NS", "LT.NS","LAURUSLABS.NS", "LICI.NS", "LUPIN.NS", "MRF.NS", "LODHA.NS", "MGL.NS", "M&MFIN.NS", "M&M.NS",
            "MANAPPURAM.NS", "MARICO.NS", "MARUTI.NS", "MFSL.NS", "MAXHEALTH.NS", "MPHASIS.NS", "MCX.NS","MUTHOOTFIN.NS", "NBCC.NS", "NCC.NS", "NHPC.NS", "NMDC.NS", "NTPC.NS", "NATIONALUM.NS",
            "NESTLEIND.NS", "OBEROIRLTY.NS", "ONGC.NS", "OIL.NS", "PAYTM.NS", "OFSS.NS", "POLICYBZR.NS","PIIND.NS", "PNBHOUSING.NS", "PAGEIND.NS", "PATANJALI.NS", "PERSISTENT.NS", "PETRONET.NS",
            "PIDILITIND.NS", "PEL.NS", "POLYCAB.NS", "POONAWALLA.NS", "PFC.NS", "POWERGRID.NS", "PRESTIGE.NS","PNB.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SBICARD.NS", "SBILIFE.NS", "SHREECEM.NS",
            "SJVN.NS", "SRF.NS", "MOTHERSON.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SOLARINDS.NS", "SONACOMS.NS","SBIN.NS", "SAIL.NS", "SUNPHARMA.NS", "SUPREMEIND.NS", "SYNGENE.NS", "TATACONSUM.NS", "TITAGARH.NS",
            "TVSMOTOR.NS", "TATACHEM.NS", "TATACOMM.NS", "TCS.NS", "TATAELXSI.NS", "TATAMOTORS.NS","TATAPOWER.NS", "TATASTEEL.NS", "TATATECH.NS", "TECHM.NS", "FEDERALBNK.NS", "INDHOTEL.NS",
            "PHOENIXLTD.NS", "RAMCOCEM.NS", "TORNTPHARM.NS", "TORNTPOWER.NS", "TRENT.NS", "TIINDIA.NS","UPL.NS", "ULTRACEMCO.NS", "UNIONBANK.NS", "UNITDSPR.NS", "VBL.NS", "VEDL.NS", "IDEA.NS",
            "VOLTAS.NS", "WIPRO.NS", "YESBANK.NS", "ZYDUSLIFE.NS"
        ]
        self.auto_refresh = False
        self.refresh_interval_ms = 60 * 1000  # 1 minute (in milliseconds)
        self.create_widgets()

    def create_widgets(self):
        frame_left = tk.Frame(self)
        frame_left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        tk.Label(frame_left, text="Stocks List").pack()
        self.listbox = tk.Listbox(frame_left, width=25, height=25)
        self.listbox.pack()
        for s in self.stocks:
            self.listbox.insert(tk.END, s)
        tk.Button(frame_left, text="Add Stock", command=self.add_stock).pack(pady=5)
        tk.Button(frame_left, text="Remove Stock", command=self.remove_stock).pack(pady=5)

        frame_right = tk.Frame(self)
        frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.mode_var = tk.StringVar(value="Live")
        tk.Label(frame_right, text="Mode:").pack(anchor='w')
        mode_frame = tk.Frame(frame_right)
        mode_frame.pack(anchor='w')
        tk.Radiobutton(mode_frame, text="Live", variable=self.mode_var, value="Live").pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Historical", variable=self.mode_var, value="Historical").pack(side=tk.LEFT)
        tk.Label(frame_right, text="Historical Date (YYYY-MM-DD):").pack(anchor='w', pady=(10, 0))
        self.date_entry = tk.Entry(frame_right)
        self.date_entry.pack(anchor='w')
        tk.Button(frame_right, text="Run Screener", command=self.run_screener).pack(pady=10)
        self.auto_btn = tk.Button(frame_right, text="Start Auto-Refresh", command=self.toggle_auto_refresh)
        self.auto_btn.pack(pady=5)
        self.progress = ttk.Progressbar(frame_right, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=(0, 5))
        self.progress_label = tk.Label(frame_right, text="Progress: 0%")
        self.progress_label.pack()
        self.tree = ttk.Treeview(
            frame_right,
            columns=("Symbol", "1st Open", "1st Close", "2nd Open", "2nd Close", "Signal", "Top 10", "Volume Status"),
            show="headings")
        self.tree.heading("Symbol", text="Symbol")
        self.tree.heading("1st Open", text="1st Open")
        self.tree.heading("1st Close", text="1st Close")
        self.tree.heading("2nd Open", text="2nd Open")
        self.tree.heading("2nd Close", text="2nd Close")
        self.tree.heading("Signal", text="Signal")
        self.tree.heading("Top 10", text="Top 10")
        self.tree.heading("Volume Status", text="Volume Status")
        self.tree.column("Symbol", width=50, anchor='center')
        self.tree.column("1st Open", width=15, anchor='center')
        self.tree.column("1st Close", width=15, anchor='center')
        self.tree.column("2nd Open", width=15, anchor='center')
        self.tree.column("2nd Close", width=15, anchor='center')
        self.tree.column("Signal", width=20, anchor='center')
        self.tree.column("Top 10", width=15, anchor='center')
        self.tree.column("Volume Status", width=15, anchor='center')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure('Bullish', background='lightgreen', foreground='black')
        self.tree.tag_configure('Bearish', background='lightcoral', foreground='black')
        self.tree.tag_configure('Confirmed Bullish', background='#00ff99', foreground='black')
        self.tree.tag_configure('Confirmed Bearish', background='#ff6666', foreground='black')

    def add_stock(self):
        symbol = simpledialog.askstring("Add Stock", "Enter NSE Stock Symbol (e.g. RELIANCE.NS):")
        if symbol:
            symbol = symbol.strip().upper()
            if not symbol.endswith(".NS"):
                symbol += ".NS"
            if symbol not in self.stocks:
                self.stocks.append(symbol)
                self.listbox.insert(tk.END, symbol)
            else:
                messagebox.showinfo("Info", "Stock already in list.")

    def remove_stock(self):
        selected = self.listbox.curselection()
        if selected:
            idx = selected[0]
            stock = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.stocks.remove(stock)

    def toggle_auto_refresh(self):
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self.auto_btn.config(text="Stop Auto-Refresh")
            self.run_screener(auto=True)
        else:
            self.auto_btn.config(text="Start Auto-Refresh")

    def run_screener(self, auto=False):
        self.tree.delete(*self.tree.get_children())
        self.progress['value'] = 0
        self.progress_label.config(text="Progress: 0%")
        threading.Thread(target=self._run_screener_thread, args=(auto,), daemon=True).start()

    def _run_screener_thread(self, auto=False):
        mode = self.mode_var.get()
        if mode == "Historical":
            date_str = self.date_entry.get().strip()
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start_date = date_obj.strftime("%Y-%m-%d")
                end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            except:
                self.after(0, lambda: messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD."))
                return
        else:
            today = datetime.now().date()
            start_date = today.strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        results = []
        pct_changes = {}
        total = len(self.stocks)
        for idx, symbol in enumerate(self.stocks):
            print(f"\n----- Processing {symbol} -----")
            df_5min = fetch_5min_data(symbol, start_date, end_date)
            if df_5min is None or df_5min.empty:
                signal = "No Data"
                print(f"No data for {symbol}")
                pct_changes[symbol] = None
                first_open = first_close = second_open = second_close = ""
                volume_status = ""
            else:
                df_10min = resample_to_10min(df_5min)
                data_10min = df_10min.copy()
                data_10min['date'] = data_10min.index.date
                # Use robust historical fetch for before_10min
                before_10min = fetch_historical_10min_volume(symbol, start_date, days_back=5)
                start_10min = data_10min[data_10min['date'] == datetime.strptime(start_date, "%Y-%m-%d").date()].drop(columns='date')
                avg_vol = before_10min['Volume'].mean() if before_10min is not None and not before_10min.empty else None
                first2_start = start_10min.head(2)
                if avg_vol is not None and len(first2_start) == 2:
                    first2_vol_high = (first2_start['Volume'] > avg_vol).all()
                    volume_status = "High Volume" if first2_vol_high else "Low Volume"
                elif len(first2_start) < 2:
                    volume_status = "No 2 Candles"
                elif avg_vol is None:
                    volume_status = "No Avg Vol"
                else:
                    volume_status = "No Data"
                combined_52 = get_44ma_on_52candles_from_date(symbol, start_date)
                print("\n--- First 2 Candles (10-min) ---")
                print(df_10min.head(2)[['Open', 'High', 'Low', 'Close']])
                print("\n--- Last 2 MA44 Values ---")
                if combined_52 is not None:
                    print(combined_52['MA44'].tail(2))
                signal = check_first2_against_ma44(df_10min, combined_52)
                print(f"Signal: {signal}")
                if len(df_10min) >= 2:
                    first_open = df_10min.iloc[0]['Open']
                    first_close = df_10min.iloc[0]['Close']
                    second_open = df_10min.iloc[1]['Open']
                    second_close = df_10min.iloc[1]['Close']
                elif len(df_10min) == 1:
                    first_open = df_10min.iloc[0]['Open']
                    first_close = df_10min.iloc[0]['Close']
                    second_open = second_close = ""
                else:
                    first_open = first_close = second_open = second_close = ""
                try:
                    day_data = df_5min[df_5min.index.date == datetime.strptime(start_date, "%Y-%m-%d").date()]
                    if not day_data.empty:
                        open_price = day_data.iloc[0]['Open']
                        close_price = day_data.iloc[-1]['Close']
                        pct_change = ((close_price - open_price) / open_price) * 100
                        pct_changes[symbol] = pct_change
                    else:
                        pct_changes[symbol] = None
                except Exception as e:
                    print(f"Error calculating pct_change for {symbol}: {e}")
                    pct_changes[symbol] = None
            results.append((symbol, first_open, first_close, second_open, second_close, signal, volume_status))
            percent = int((idx + 1) / total * 100)
            self.after(0, lambda p=percent: self.progress_label.config(text=f"Progress: {p}%"))
            self.after(0, lambda v=idx+1: self.progress.config(value=v, maximum=total))
        sorted_changes = sorted(
            [(s, pct) for s, pct in pct_changes.items() if pct is not None],
            key=lambda x: x[1], reverse=True)
        top_10_gainers = set([s for s, _ in sorted_changes[:10]])
        top_10_losers = set([s for s, _ in sorted_changes[-10:]])
        def custom_order(symbol, first_open, first_close, second_open, second_close, signal, top10, volume_status):
            # High Volume first, then Low Volume, then others
            if signal == "Confirmed Bullish" and top10 == "Gainer" and volume_status == "High Volume":
                return 0
            elif signal == "Confirmed Bearish" and top10 == "Loser" and volume_status == "High Volume":
                return 1
            elif signal == "Confirmed Bullish" and volume_status == "High Volume":
                return 2
            elif signal == "Confirmed Bearish" and volume_status == "High Volume":
                return 3
            elif signal == "Bullish" and top10 == "Gainer" and volume_status == "High Volume":
                return 4
            elif signal == "Bearish" and top10 == "Loser" and volume_status == "High Volume":
                return 5
            elif signal == "Bullish" and volume_status == "High Volume":
                return 6
            elif signal == "Bearish" and volume_status == "High Volume":
                return 7

            elif signal == "Confirmed Bullish" and top10 == "Gainer" and volume_status == "Low Volume":
                 return 8
            elif signal == "Confirmed Bearish" and top10 == "Loser" and volume_status == "Low Volume":
                 return 9
            elif signal == "Confirmed Bullish" and volume_status == "Low Volume":
                 return 10
            elif signal == "Confirmed Bearish" and volume_status == "Low Volume":
                 return 11
            elif signal == "Bullish" and top10 == "Gainer" and volume_status == "Low Volume":
                 return 12
            elif signal == "Bearish" and top10 == "Loser" and volume_status == "Low Volume":
                 return 13
            elif signal == "Bullish" and volume_status == "Low Volume":
                 return 14
            elif signal == "Bearish" and volume_status == "Low Volume":
                 return 15

            elif signal == "No Signal" and volume_status == "High Volume":
                 return 16
            elif signal == "No Signal":
                 return 17
            elif signal == "Not enough data":
                 return 18
            elif signal == "No Data":
                 return 19
            elif signal == "Fetching...":
                 return 20
            else:
                 return 99
        display_results = []
        for symbol, first_open, first_close, second_open, second_close, signal, volume_status in results:
            if symbol in top_10_gainers:
                top10 = "Gainer"
            elif symbol in top_10_losers:
                top10 = "Loser"
            else:
                top10 = ""
            display_results.append((symbol, first_open, first_close, second_open, second_close, signal, top10, volume_status))
        display_results.sort(key=lambda x: custom_order(*x))
        def update_tree():
            self.tree.delete(*self.tree.get_children())
            for symbol, first_open, first_close, second_open, second_close, signal, top10, volume_status in display_results:
                item = self.tree.insert(
                    "", tk.END,
                    values=(
                        symbol,
                        f"{first_open:.2f}" if isinstance(first_open, (float, int)) else first_open,
                        f"{first_close:.2f}" if isinstance(first_close, (float, int)) else first_close,
                        f"{second_open:.2f}" if isinstance(second_open, (float, int)) else second_open,
                        f"{second_close:.2f}" if isinstance(second_close, (float, int)) else second_close,
                        signal,
                        top10,
                        volume_status))
                if signal == "Bullish":
                    self.tree.item(item, tags=("Bullish",))
                elif signal == "Bearish":
                    self.tree.item(item, tags=("Bearish",))
                elif signal == "Confirmed Bullish":
                    self.tree.item(item, tags=("Confirmed Bullish",))
                elif signal == "Confirmed Bearish":
                    self.tree.item(item, tags=("Confirmed Bearish",))
            self.progress_label.config(text="Progress: 100%")
            self.progress.config(value=total, maximum=total)
        self.after(0, update_tree)
        if auto and self.auto_refresh:
            self.after(self.refresh_interval_ms, lambda: self.run_screener(auto=True))

if __name__ == "__main__":
    app = NSEStockScreener()
    app.mainloop()